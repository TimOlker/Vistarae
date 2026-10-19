"""Gemini Flash-Lite Structured Entity Extraction Service."""

import json
import logging

from app.config import settings
from app.middleware.telemetry import egress_span
from app.schemas.extraction import ExtractAndCheckRequest, POIExtractionCandidate

logger = logging.getLogger("vistarae.extraction")


EXTRACTION_SYSTEM_PROMPT = """You are Vistarae's Travel Entity Extractor.
Extract structured Point of Interest (POI) data from the user-selected text, page title, and URL.
Focus on identifying scenic overlooks, trails, iconic viewpoints, museums, natural landmarks, or notable sites.
Generate a deterministic, high-accuracy `search_address_query` suitable for OpenStreetMap Nominatim geocoding.
Ensure IPTC geographic metadata (city, province/state, 2-letter country code) is accurately populated.
"""


async def extract_candidate_from_text(
    payload: ExtractAndCheckRequest,
) -> POIExtractionCandidate:
    """Extracts a structured POI candidate using Google Gemini Flash-Lite with zero thinking budget."""
    gemini_api_key = settings.GEMINI_API_KEY

    # Check if API key is present
    if not gemini_api_key or gemini_api_key.strip() in ("", "your_gemini_api_key_here"):
        logger.warning("GEMINI_API_KEY not configured. Falling back to heuristic extractor.")
        return _fallback_heuristic_extraction(payload)

    prompt = (
        f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"Web Page Title: {payload.page_title}\n"
        f"Web Page URL: {payload.page_url}\n"
        f"Highlighted Content:\n\"\"\"{payload.selected_text}\"\"\"\n"
    )

    async with egress_span("Google Gemini Flash-Lite", "https://generativelanguage.googleapis.com", "generate_content"):
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_api_key)

            # thinking_budget set to 0 for ultra-low latency & minimal token consumption
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=POIExtractionCandidate,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                temperature=0.1,
            )

            # Synchronous SDK call wrapped in executor if necessary
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=config,
            )

            if response and response.text:
                candidate_data = json.loads(response.text)
                return POIExtractionCandidate.model_validate(candidate_data)
            else:
                raise ValueError("Empty response received from Gemini Flash-Lite.")

        except Exception as exc:
            logger.error(f"Gemini Flash-Lite extraction error: {exc}. Using heuristic fallback.")
            return _fallback_heuristic_extraction(payload)


def _fallback_heuristic_extraction(payload: ExtractAndCheckRequest) -> POIExtractionCandidate:
    """Heuristic fallback parser when Gemini API is unavailable or unconfigured."""
    text_snippet = payload.selected_text.strip()
    first_line = text_snippet.split("\n")[0].strip() if text_snippet else ""

    # Derive name candidate from first line or page title
    name_candidate = first_line[:60] if first_line else payload.page_title.split("|")[0].split("-")[0].strip()
    if not name_candidate:
        name_candidate = "Scenic Point of Interest"

    search_query = f"{name_candidate}, {payload.page_title.split('|')[-1].strip()}"

    return POIExtractionCandidate(
        name=name_candidate,
        name_aliases=[],
        poi_type="site to see",
        personal_rating=4,
        description=text_snippet[:300] if text_snippet else "Captured scenic travel location.",
        category_tags=["travel", "scenic"],
        physical_effort="paved walk",
        booking_lead_time="walk-in ok",
        indoor_outdoor="Outdoor",
        estimated_duration="1-2 hours",
        cost_tier="Free",
        hours_seasonality="Open year-round",
        best_time_to_visit="Golden Hour",
        website_official=payload.page_url,
        search_address_query=search_query,
        iptc_sublocation=name_candidate,
        iptc_city="Unknown City",
        iptc_province_state="Unknown State",
        iptc_country_code="US",
        iptc_world_region="North America",
    )
