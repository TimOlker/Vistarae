"""Gemini LLM path parser for determining country, state, city, and site from folder paths."""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from photo_scraper.core.cache import PersistentCache
from photo_scraper.core.config import settings

logger = logging.getLogger("vistarae.photo_scraper.llm_parser")


class GeminiPathLocation(BaseModel):
    """Structured location parsed from directory path by Gemini LLM."""

    model_config = ConfigDict(extra="ignore")

    country: str | None = Field(default=None, description="Country name, e.g. 'China', 'USA', 'Scotland', 'Wales', 'England'")
    state: str | None = Field(default=None, description="State, province, or region, e.g. 'IL', 'New York'")
    city: str | None = Field(default=None, description="City, town, or municipality, e.g. 'Beijing', 'Chicago', 'Edinburgh'")
    site: str = Field(default="", description="Specific site, attraction, landmark, or point of interest name")
    is_travel_location: bool = Field(default=True, description="False if this is a personal/family event like 'Christmas 2021', 'Soccer', 'Receipts'")
    confidence: str = Field(default="medium", description="Confidence rating: 'high', 'medium', or 'low'")
    reasoning: str = Field(default="", description="Brief explanation of the location inference")

    def to_dict(self) -> dict[str, str]:
        return {
            "country": self.country or "",
            "state": self.state or "",
            "city": self.city or "",
            "site": self.site or "",
        }

    def summary(self) -> str:
        parts = []
        if self.country:
            parts.append(f"Country={self.country}")
        if self.state:
            parts.append(f"State={self.state}")
        if self.city:
            parts.append(f"City={self.city}")
        if self.site:
            parts.append(f"Site={self.site}")
        return ", ".join(parts)


class GeminiPathParser:
    """Uses Google Gemini Flash-Lite to extract country, state, city, and site from folder paths with persistent caching."""

    def __init__(
        self,
        api_key: str | None = None,
        cache_file_path: str | None = None,
        model_name: str | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        cache_path = cache_file_path or settings.GEMINI_PATH_CACHE_PATH
        self.cache = PersistentCache(cache_path)

    def save_cache(self, force: bool = False) -> None:
        """Saves any pending in-memory cache entries to disk."""
        self.cache.save(force=force)

    def update_nominatim_result(
        self,
        folder_path: Path | str,
        geo: Any | None,
        query: str | None = None,
        parsed_path: Any | None = None,
    ) -> None:
        """Adds or updates Nominatim geocoding query results in gemini_path_cache.json."""
        norm_key = self._normalize_key(folder_path)
        existing = self.cache.get(norm_key)

        if not isinstance(existing, dict):
            existing = {}
            if parsed_path is not None:
                existing["country"] = getattr(parsed_path, "country", None)
                existing["state"] = getattr(parsed_path, "state", None)
                existing["city"] = getattr(parsed_path, "city", None)
                existing["site"] = getattr(parsed_path, "site", None) or getattr(parsed_path, "cleaned_name", "")
                existing["is_travel_location"] = not getattr(parsed_path, "is_likely_non_location", False)
                existing["reasoning"] = "Resolved from path hierarchy and Nominatim"

        if geo is not None:
            if hasattr(geo, "to_nominatim_dict"):
                existing["nominatim"] = geo.to_nominatim_dict(query=query)
            else:
                existing["nominatim"] = {
                    "query": query,
                    "found": True,
                    "name": getattr(geo, "name", ""),
                    "display_name": getattr(geo, "display_name", ""),
                    "latitude": getattr(geo, "latitude", 0.0),
                    "longitude": getattr(geo, "longitude", 0.0),
                    "street": getattr(geo, "street", None),
                    "city": getattr(geo, "city", None),
                    "state": getattr(geo, "state", None),
                    "country": getattr(geo, "country", None),
                    "country_code": getattr(geo, "country_code", None),
                    "postal_code": getattr(geo, "postal_code", None),
                }
        else:
            existing["nominatim"] = {
                "query": query,
                "found": False,
            }

        self.cache.set(norm_key, existing)
        logger.debug(f"Added Nominatim query result for '{norm_key}' to gemini_path_cache")

    def get_cached_nominatim_location(self, folder_path: Path | str) -> Any | None:
        """Returns GeocodedLocation if previously resolved and cached in gemini_path_cache.json."""
        norm_key = self._normalize_key(folder_path)
        data = self.cache.get(norm_key)
        if isinstance(data, dict):
            nom = data.get("nominatim")
            if isinstance(nom, dict) and nom.get("found"):
                lat = nom.get("latitude")
                lon = nom.get("longitude")
                if lat is not None and lon is not None:
                    from photo_scraper.core.geocoder import GeocodedLocation

                    return GeocodedLocation(
                        name=nom.get("name") or "",
                        display_name=nom.get("display_name") or "",
                        latitude=float(lat),
                        longitude=float(lon),
                        street=nom.get("street"),
                        city=nom.get("city"),
                        state=nom.get("state"),
                        country=nom.get("country"),
                        country_code=nom.get("country_code"),
                        postal_code=nom.get("postal_code"),
                    )
        return None

    def _normalize_key(self, folder_path: Path | str) -> str:
        """Normalizes path for consistent cache lookup."""
        return str(folder_path).replace("\\", "/").strip().lower()

    def is_configured(self) -> bool:
        """Checks if a valid Gemini API key is configured."""
        return bool(self.api_key and self.api_key != "your_gemini_api_key_here")

    def resolve_path(self, folder_path: Path | str, root_path: Path | None = None) -> GeminiPathLocation | None:
        """Determines country, state, city, and site using disk cache first, then Gemini LLM."""
        norm_key = self._normalize_key(folder_path)

        # 1. Check persistent disk cache
        cached_data = self.cache.get(norm_key)
        if cached_data and isinstance(cached_data, dict):
            try:
                res = GeminiPathLocation.model_validate(cached_data)
                logger.debug(f"[Gemini Cache Hit] Resolved '{norm_key}' -> {res.summary()}")
                return res
            except Exception as e:
                logger.warning(f"Failed to validate cached Gemini location: {e}")

        # 2. Check if API key is configured
        if not self.is_configured():
            logger.debug(f"Gemini API key not configured. Skipping LLM resolution for '{folder_path}'")
            return None

        # 3. Call Google Gemini SDK
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            path_str = str(folder_path)
            prompt = f"""You are an expert geographical location parser for travel and photo collections.
Analyze the following folder path hierarchy from a personal photo collection and extract:
- country (e.g. 'China', 'USA', 'Scotland', 'Wales', 'England', 'France')
- state/province (e.g. 'IL', 'New York', 'California')
- city (e.g. 'Beijing', 'Chicago', 'Suzhou', 'Edinburgh', 'London', 'Caerphilly')
- site (e.g. 'Behai Temple', 'Summer Palace', 'Master of Nets Garden', 'Dean Village', 'Pullman National Monument')
- is_travel_location: set to false if this folder is for personal events or non-places (e.g. 'Choir', 'Kids Soccer', 'Birthday', 'Receipts')
- confidence: 'high' if confident from explicit landmark or unambiguous hierarchy, 'medium' if reasonable context clues exist, or 'low' if vague/ambiguous
- reasoning: concise explanation of your conclusion

Strict Guidelines:
1. Ignore intermediate noise or format folders like '2d', '3d', 'RAW', 'master', 'Edited', 'DCIM'.
2. Ignore pure year folders like '2002', '2025' when extracting country/city.
3. Use parent directory context (ancestor folders) to resolve child folders (e.g., in '2023/Japan/Tokyo/Shibuya', 'Japan' and 'Tokyo' anchor 'Shibuya').
4. Handle travel prefixes like 'Trip to China' -> country is 'China'.
5. For Great Britain / UK locations, identify constituent countries: 'Scotland' (e.g. Edinburgh, Glasgow), 'Wales' (e.g. Cardiff, Caerphilly), 'England' (e.g. London, Bath), 'Northern Ireland'.
6. If a landmark name has a minor spelling typo (e.g. 'Behai Temple' in Beijing), recognize the location context and extract country='China', city='Beijing', site='Behai Temple'.
7. If a landmark is a famous US site with no city/state in the path (e.g. '2025/Pullman National Monument'), resolve to country='USA', state='IL', city='Chicago'.
8. ZERO-HALLUCINATION GUARD (CRITICAL): If the folder name or path contains vague, generic, or ambiguous terms (e.g. 'Day 1', 'Day 2', 'Walk', 'Morning Walk', 'Park', 'Beach', 'Vacation', 'Downtown', 'Photos', 'Camera', 'iPhone', 'Trip') WITHOUT explicit geographic context (such as an identifiable city, state, country, or specific landmark), you MUST:
   - Set confidence='low'
   - Set is_travel_location=false
   - Leave country, state, city, and site as null/empty
   - Set reasoning explaining that the path is ambiguous and lacks geographic anchors
   DO NOT guess, assume, or invent locations under any circumstances.

Folder path: {path_str}
"""

            # Prepare configuration with structured JSON output
            # Note: For flash-lite models, thinking_config is not supported by Google's API and causes 400 INVALID_ARGUMENT.
            # Disable automatic function calling (AFC) since this is a direct single-turn structured call without tools.
            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": GeminiPathLocation,
                "temperature": 0.0,
                "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
            }
            if "thinking" in self.model_name.lower():
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

            config = types.GenerateContentConfig(**config_kwargs)

            logger.info(f"MSG   |-> [Gemini LLM] Path='{path_str}'")
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
            except Exception as call_err:
                if "thinking_config" in config_kwargs and "INVALID_ARGUMENT" in str(call_err):
                    config_kwargs.pop("thinking_config", None)
                    config = types.GenerateContentConfig(**config_kwargs)
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=config,
                    )
                else:
                    raise call_err

            logger.info("MSG   |<- [Gemini LLM] Status=200")

            if response and response.text:
                result = GeminiPathLocation.model_validate_json(response.text)
                # Update cache in memory as processing continues
                self.cache.set(norm_key, result.model_dump())
                logger.info(f"Gemini resolved '{folder_path}' -> {result.summary()} (Updated in-memory cache)")
                return result
            else:
                logger.warning(f"Empty response from Gemini for path: '{folder_path}'")

        except Exception as exc:
             logger.error(f"Gemini LLM path parsing exception for '{folder_path}': {exc}")

        return None
