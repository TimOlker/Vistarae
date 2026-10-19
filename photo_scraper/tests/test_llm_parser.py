"""Unit tests for Gemini LLM path parser and persistent caching."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from photo_scraper.core.llm_parser import GeminiPathLocation, GeminiPathParser


def test_gemini_path_location_model():
    loc = GeminiPathLocation(
        country="China",
        city="Beijing",
        site="Behai Temple",
        is_travel_location=True,
    )
    assert loc.country == "China"
    assert loc.city == "Beijing"
    assert loc.site == "Behai Temple"
    assert loc.summary() == "Country=China, City=Beijing, Site=Behai Temple"
    assert loc.to_dict() == {
        "country": "China",
        "state": "",
        "city": "Beijing",
        "site": "Behai Temple",
    }


def test_gemini_path_parser_unconfigured():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "gemini_cache.json"
        parser = GeminiPathParser(api_key="", cache_file_path=str(cache_file))
        assert parser.is_configured() is False
        assert parser.resolve_path("M:/Photos/2002/China/1-Beijing/Behai Temple") is None
        assert not cache_file.exists()


def test_gemini_path_parser_cache_and_call():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "gemini_cache.json"
        parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(cache_file))
        assert parser.is_configured() is True

        mock_response_data = {
            "country": "China",
            "state": None,
            "city": "Beijing",
            "site": "Behai Temple",
            "is_travel_location": True,
            "reasoning": "Behai refers to Beihai Park and Temple in Beijing, China.",
        }

        # Mock google.genai Client
        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_response_data)

        mock_models = MagicMock()
        mock_models.generate_content.return_value = mock_response

        mock_client = MagicMock()
        mock_client.models = mock_models

        test_path = "M:/Photos/master/Tim/2002/Trip to China/1-Beijing/Behai Temple"

        with patch("google.genai.Client", return_value=mock_client):
            # 1. First run: cache miss -> calls Gemini API and saves to cache
            result1 = parser.resolve_path(test_path)

            assert result1 is not None
            assert result1.country == "China"
            assert result1.city == "Beijing"
            assert result1.site == "Behai Temple"
            assert mock_models.generate_content.call_count == 1

            # Verify updated in memory
            assert parser.cache.is_dirty
            assert len(parser.cache) == 1

            # 2. Second run: cache hit in memory -> returns without invoking Gemini again
            result2 = parser.resolve_path(test_path)
            assert result2 is not None
            assert result2.country == "China"
            assert result2.city == "Beijing"
            assert mock_models.generate_content.call_count == 1

            # 3. Save cache to disk (as done on signal, crash, or shutdown)
            parser.save_cache()
            assert not parser.cache.is_dirty
            assert cache_file.exists()
            with open(cache_file, encoding="utf-8") as f:
                disk_cache = json.load(f)
            assert len(disk_cache) == 1

            # 4. Verify fresh parser loads from disk on startup
            fresh_parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(cache_file))
            assert len(fresh_parser.cache) == 1
            result3 = fresh_parser.resolve_path(test_path)
            assert result3 is not None
            assert result3.country == "China"
            assert mock_models.generate_content.call_count == 1


def test_gemini_path_parser_preseeded_cache():
    """Verifies that pre-existing entries in gemini_path_cache.json are immediately returned without API calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "gemini_cache.json"
        test_path = "m:/photos/master/tim/2025/pullman national monument"

        # Preseed cache file
        cache_file.write_text(
            json.dumps({
                test_path: {
                    "country": "USA",
                    "state": "IL",
                    "city": "Chicago",
                    "site": "Pullman National Monument",
                    "is_travel_location": True,
                    "reasoning": "Preseeded cache entry",
                }
            }),
            encoding="utf-8",
        )

        parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(cache_file))
        result = parser.resolve_path(test_path)

        assert result is not None
        assert result.country == "USA"
        assert result.state == "IL"
        assert result.site == "Pullman National Monument"


def test_gemini_path_parser_with_nominatim_results():
    """Verifies that Nominatim geocoding results are stored and reloaded from gemini_path_cache.json."""
    from photo_scraper.core.geocoder import GeocodedLocation

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "gemini_cache.json"
        parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(cache_file))

        test_path = "m:/photos/master/tim/2002/trip to china/1-beijing/behai temple"
        geo = GeocodedLocation(
            name="Beihai Park",
            display_name="Beihai Park, Xicheng District, Beijing, China",
            latitude=39.9281,
            longitude=116.3883,
            city="Beijing",
            state="Beijing",
            country="China",
            country_code="cn",
            postal_code="100034",
        )

        # 1. Store Nominatim result in gemini cache
        parser.update_nominatim_result(test_path, geo, query="Behai Temple, Beijing, China")
        assert parser.cache.is_dirty

        # 2. Persist to disk
        parser.save_cache()
        assert not parser.cache.is_dirty
        assert cache_file.exists()

        # 3. Verify disk JSON structure
        with open(cache_file, encoding="utf-8") as f:
            disk_data = json.load(f)

        norm_key = test_path.lower()
        assert norm_key in disk_data
        entry = disk_data[norm_key]
        assert "nominatim" in entry
        assert entry["nominatim"]["found"] is True
        assert entry["nominatim"]["query"] == "Behai Temple, Beijing, China"
        assert entry["nominatim"]["name"] == "Beihai Park"
        assert entry["nominatim"]["latitude"] == 39.9281
        assert entry["nominatim"]["longitude"] == 116.3883

        # 4. Verify reload via get_cached_nominatim_location
        fresh_parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(cache_file))
        cached_geo = fresh_parser.get_cached_nominatim_location(test_path)
        assert cached_geo is not None
        assert cached_geo.name == "Beihai Park"
        assert cached_geo.latitude == 39.9281
        assert cached_geo.longitude == 116.3883
        assert cached_geo.country == "China"

        # 5. Verify failed geocoding records found: False
        fail_path = "m:/photos/master/unknown_folder"
        parser.update_nominatim_result(fail_path, geo=None, query="Unknown query")
        parser.save_cache()

        with open(cache_file, encoding="utf-8") as f:
            disk_data2 = json.load(f)
        assert disk_data2[fail_path]["nominatim"]["found"] is False
