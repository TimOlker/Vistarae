# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Gemini LLM path and photo inference parser (T-042).

Invokes Google Gemini Flash-Lite with response_mime_type="application/json"
enforcing PhotoPOIInference with thinking_budget=0 per GEMINI.md and Constitution.
Supports disk caching, uncertainty detection, and fallback handling.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from vistarae_core.schemas.ingest import PhotoPOIInference

from photo_scraper.core.cache import PersistentCache
from photo_scraper.core.config import settings

logger = logging.getLogger("vistarae.photo_scraper.llm_parser")

GENERIC_CATEGORIES = {
    "airport",
    "hotel",
    "restaurant",
    "train station",
    "bus station",
    "shopping mall",
    "parking lot",
    "cafe",
    "coffee shop",
    "gas station",
    "supermarket",
    "subway station",
}


class GeminiPathLocation(BaseModel):
    """Structured location parsed from directory path by Gemini LLM."""

    model_config = ConfigDict(extra="ignore")

    country: str | None = Field(
        default=None,
        description="Country name, e.g. 'China', 'USA', 'Scotland', 'Wales', 'England'",
    )
    state: str | None = Field(
        default=None, description="State, province, or region, e.g. 'IL', 'New York'"
    )
    city: str | None = Field(
        default=None, description="City, town, or municipality, e.g. 'Beijing', 'Chicago'"
    )
    site: str = Field(
        default="", description="Specific site, attraction, landmark, or point of interest name"
    )
    is_travel_location: bool = Field(
        default=True,
        description="False if this is a personal/family event like 'Christmas 2021', 'Soccer'",
    )
    confidence: str = Field(
        default="medium", description="Confidence rating: 'high', 'medium', or 'low'"
    )
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
    """Uses Google Gemini Flash-Lite to extract POI inferences with structured JSON."""

    def __init__(
        self,
        api_key: str | None = None,
        cache_file_path: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        cache_path = cache_file_path or settings.GEMINI_PATH_CACHE_PATH
        self.cache = PersistentCache(cache_path)

    def save_cache(self, force: bool = False) -> None:
        """Saves any pending in-memory cache entries to disk."""
        self.cache.save(force=force)

    def is_configured(self) -> bool:
        """Checks if a valid Gemini API key is configured."""
        return bool(self.api_key and self.api_key != "your_gemini_api_key_here")

    def _normalize_key(self, key: Path | str) -> str:
        """Normalizes path or cache key for consistent lookup."""
        return str(key).replace("\\", "/").strip().lower()

    def infer_poi(
        self,
        folder_path: Path | str,
        file_name: str | None = None,
        exif_lat: float | None = None,
        exif_lon: float | None = None,
        date_taken: str | None = None,
    ) -> PhotoPOIInference | None:
        """Extracts structured PhotoPOIInference using Gemini Flash-Lite with thinking_budget=0.

        Args:
            folder_path: Folder containing the photo(s).
            file_name: Optional image file name.
            exif_lat: Optional EXIF GPS latitude.
            exif_lon: Optional EXIF GPS longitude.
            date_taken: Optional date string.

        Returns:
            Validated PhotoPOIInference or None.
        """
        cache_key = f"poi::{self._normalize_key(folder_path)}::{file_name or ''}"

        # 1. Check persistent cache
        cached = self.cache.get(cache_key)
        if cached and isinstance(cached, dict):
            try:
                return PhotoPOIInference.model_validate(cached)
            except Exception as exc:
                logger.warning(f"Invalid cached PhotoPOIInference for {cache_key}: {exc}")

        # 2. Check if API key is configured
        if not self.is_configured():
            logger.debug(f"Gemini API key not configured. Skipping infer_poi for '{folder_path}'")
            return None

        # 3. Invoke Google Gemini Flash-Lite
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            prompt = f"""You are an expert geographical location parser for travel and photo collections.
Analyze the following photo metadata and folder context to infer the specific Point of Interest (POI):

Folder Path: {folder_path}
File Name: {file_name or 'N/A'}
EXIF Coordinates: Lat={exif_lat}, Lon={exif_lon}
Date Taken: {date_taken or 'N/A'}

Strict Guidelines:
1. Infer the canonical Point of Interest name (e.g. 'Fushimi Inari Taisha', 'Kyoto Traditional Restaurant', 'Yosemite Valley Overlook').
2. Provide a concise, descriptive summary of the location in description.
3. Extract city, state/province, and country if identifiable.
4. Estimate confidence_score between 0.0 and 1.0 based on context specificity and geographic certainty.
5. Set is_uncertain=true if:
   - The location is vague, ambiguous, or lacks specific geographic landmarks
   - The location is a generic category (e.g. Airport, Hotel, Restaurant, Train Station, Shopping Mall)
   - confidence_score is below 0.70
"""

            config_kwargs: dict[str, Any] = {
                "response_mime_type": "application/json",
                "response_schema": PhotoPOIInference,
                "temperature": 0.0,
                "thinking_config": types.ThinkingConfig(thinking_budget=0),
                "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
            }

            config = types.GenerateContentConfig(**config_kwargs)

            logger.info(f"MSG   |-> [Gemini LLM infer_poi] Path='{folder_path}' File='{file_name}'")
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            logger.info("MSG   |<- [Gemini LLM infer_poi] Status=200")

            if response and response.text:
                result = PhotoPOIInference.model_validate_json(response.text)

                # Flag generic names or low confidence as uncertain
                if (
                    result.confidence_score < 0.70
                    or result.name.strip().lower() in GENERIC_CATEGORIES
                ):
                    result = PhotoPOIInference(
                        name=result.name,
                        description=result.description,
                        city=result.city,
                        state=result.state,
                        country=result.country,
                        confidence_score=result.confidence_score,
                        is_uncertain=True,
                    )

                self.cache.set(cache_key, result.model_dump())
                return result

        except Exception as exc:
            logger.error(f"Gemini infer_poi exception for '{folder_path}': {exc}")

        return None

    def resolve_path(
        self, folder_path: Path | str, root_path: Path | None = None
    ) -> GeminiPathLocation | None:
        """Determines country, state, city, and site using disk cache first, then Gemini LLM."""
        norm_key = self._normalize_key(folder_path)

        # 1. Check persistent disk cache
        cached_data = self.cache.get(norm_key)
        if cached_data and isinstance(cached_data, dict):
            try:
                res = GeminiPathLocation.model_validate(cached_data)
                return res
            except Exception as e:
                logger.warning(f"Failed to validate cached Gemini location: {e}")

        # 2. Check if API key is configured
        if not self.is_configured():
            logger.debug(
                f"Gemini API key not configured. Skipping LLM resolution for '{folder_path}'"
            )
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
3. Use parent directory context (ancestor folders) to resolve child folders.
4. Handle travel prefixes like 'Trip to China' -> country is 'China'.
5. For Great Britain / UK locations, identify constituent countries: 'Scotland', 'Wales', 'England', 'Northern Ireland'.
6. ZERO-HALLUCINATION GUARD: If the folder name contains vague or ambiguous terms without geographic anchors, set confidence='low', is_travel_location=false, and leave fields empty.

Folder path: {path_str}
"""

            config_kwargs: dict[str, Any] = {
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
                self.cache.set(norm_key, result.model_dump())
                return result

        except Exception as exc:
            logger.error(f"Gemini LLM path parsing exception for '{folder_path}': {exc}")

        return None
