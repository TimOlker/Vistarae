"""Unit tests for Gemini Flash-Lite structured JSON extraction."""

from unittest.mock import MagicMock, patch

import pytest

from app.schemas.extraction import ExtractAndCheckRequest, POIExtractionCandidate
from app.services.extraction import _fallback_heuristic_extraction, extract_candidate_from_text


def test_poi_extraction_candidate_validation():
    valid_data = {
        "name": "Glacier Point Overlook",
        "name_aliases": ["Glacier Point"],
        "poi_type": "photo location",
        "personal_rating": 5,
        "description": "Panoramic view over Yosemite Valley.",
        "category_tags": ["viewpoint", "yosemite"],
        "physical_effort": "paved walk",
        "booking_lead_time": "walk-in ok",
        "indoor_outdoor": "Outdoor",
        "estimated_duration": "1-2 hours",
        "cost_tier": "Free",
        "search_address_query": "Glacier Point, Yosemite, CA",
        "iptc_city": "Yosemite Village",
        "iptc_province_state": "California",
        "iptc_country_code": "US",
    }
    candidate = POIExtractionCandidate.model_validate(valid_data)
    assert candidate.name == "Glacier Point Overlook"
    assert candidate.poi_type == "photo location"
    assert candidate.personal_rating == 5
    assert candidate.indoor_outdoor == "Outdoor"


def test_fallback_heuristic_extraction():
    request = ExtractAndCheckRequest(
        selected_text="Emerald Bay State Park is a state park of California in the United States, centered on Emerald Bay, a Lake Tahoe inlet.",
        page_title="Emerald Bay State Park | Lake Tahoe Travel Guide",
        page_url="https://example.com/emerald-bay",
        og_image_url="https://example.com/emerald-bay.jpg",
    )
    result = _fallback_heuristic_extraction(request)
    assert result.name is not None
    assert len(result.name) > 0
    assert result.poi_type == "site to see"
    assert "Emerald Bay" in result.search_address_query


@pytest.mark.asyncio
async def test_extract_candidate_with_mocked_gemini():
    request = ExtractAndCheckRequest(
        selected_text="Taft Point is a viewpoint in Yosemite National Park west of Glacier Point.",
        page_title="Taft Point Hike",
        page_url="https://example.com/taft-point",
    )

    fake_candidate_json = """{
        "name": "Taft Point",
        "name_aliases": ["Taft Point View"],
        "poi_type": "photo location",
        "personal_rating": 5,
        "description": "Dramatic fissure cliffs and sweeping valley views.",
        "category_tags": ["hiking", "viewpoint"],
        "physical_effort": "moderate hike",
        "booking_lead_time": "walk-in ok",
        "indoor_outdoor": "Outdoor",
        "estimated_duration": "2 hours",
        "cost_tier": "Free",
        "hours_seasonality": "Accessible summer/fall",
        "best_time_to_visit": "Sunset",
        "website_official": "https://www.nps.gov/yose",
        "search_address_query": "Taft Point, Yosemite National Park, California",
        "iptc_sublocation": "Taft Point",
        "iptc_city": "Yosemite Village",
        "iptc_province_state": "California",
        "iptc_country_code": "US",
        "iptc_world_region": "North America"
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = fake_candidate_json
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.config.settings.GEMINI_API_KEY", "test_gemini_key"), \
         patch("google.genai.Client", return_value=mock_client):
        result = await extract_candidate_from_text(request)

        assert result.name == "Taft Point"
        assert result.poi_type == "photo location"
        assert result.personal_rating == 5
        assert result.physical_effort == "moderate hike"
        assert result.iptc_country_code == "US"
