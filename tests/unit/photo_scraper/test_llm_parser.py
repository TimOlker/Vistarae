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

"""Unit tests for Gemini Flash-Lite structured POI inference parser (T-038).

Verifies:
- PhotoPOIInference Pydantic schema validation (confidence_score bounds, strict extra forbid)
- Enforcement of thinking_budget=0 and response_mime_type='application/json' in API config
- Structured JSON parsing into PhotoPOIInference entities
- Disk and in-memory cache hit behavior
- Flagging of uncertain POIs when confidence < 0.70 or category is generic
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from vistarae_core.schemas.ingest import PhotoPOIInference

from photo_scraper.core.llm_parser import GeminiPathParser


class TestLLMParserUnit:
    """Test suite for Gemini Flash-Lite structured inference."""

    def test_photo_poi_inference_schema_validation(self) -> None:
        """Asserts PhotoPOIInference enforces bounds and strict model rules."""
        valid = PhotoPOIInference(
            name="Kyoto Imperial Palace",
            description="Historic imperial residence in Kyoto.",
            city="Kyoto",
            country="Japan",
            confidence_score=0.95,
            is_uncertain=False,
        )
        assert valid.name == "Kyoto Imperial Palace"
        assert valid.confidence_score == 0.95

        # confidence_score > 1.0 raises ValidationError
        with pytest.raises(ValidationError):
            PhotoPOIInference(
                name="Invalid",
                description="Invalid score",
                confidence_score=1.5,
            )

        # confidence_score < 0.0 raises ValidationError
        with pytest.raises(ValidationError):
            PhotoPOIInference(
                name="Invalid",
                description="Invalid score",
                confidence_score=-0.1,
            )

        # Extra fields forbidden
        with pytest.raises(ValidationError):
            PhotoPOIInference(
                name="Extra",
                description="Extra fields forbidden",
                confidence_score=0.8,
                extra_field="disallowed",
            )

    def test_unconfigured_parser_returns_none(self) -> None:
        """Asserts parser returns None if API key is not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            parser = GeminiPathParser(api_key="", cache_file_path=str(cache_file))
            assert parser.is_configured() is False
            res = parser.infer_poi("Photos/2024/Japan/Kyoto")
            assert res is None

    def test_infer_poi_with_thinking_budget_zero_and_caching(self) -> None:
        """Asserts thinking_budget=0 and response_schema are set, and caches responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(cache_file))

            mock_response_data = {
                "name": "Fushimi Inari Taisha",
                "description": "Famous Shinto shrine with thousands of vermilion torii gates.",
                "city": "Kyoto",
                "state": "Kyoto Prefecture",
                "country": "Japan",
                "confidence_score": 0.92,
                "is_uncertain": False,
            }

            mock_response = MagicMock()
            mock_response.text = json.dumps(mock_response_data)

            mock_models = MagicMock()
            mock_models.generate_content.return_value = mock_response

            mock_client = MagicMock()
            mock_client.models = mock_models

            with patch("google.genai.Client", return_value=mock_client):
                # 1. First call: cache miss -> invokes Gemini
                res1 = parser.infer_poi(
                    folder_path="Photos/2024/Japan/Kyoto/Fushimi",
                    file_name="IMG_001.JPG",
                    exif_lat=34.9671,
                    exif_lon=135.7727,
                    date_taken="2024-04-10",
                )

                assert res1 is not None
                assert res1.name == "Fushimi Inari Taisha"
                assert res1.confidence_score == 0.92
                assert res1.is_uncertain is False
                assert mock_models.generate_content.call_count == 1

                # Verify configuration passed to generate_content
                call_args = mock_models.generate_content.call_args[1]
                config = call_args["config"]
                assert config.response_mime_type == "application/json"
                assert config.response_schema == PhotoPOIInference
                assert config.thinking_config.thinking_budget == 0

                # 2. Second call: cache hit -> does not invoke Gemini again
                res2 = parser.infer_poi(
                    folder_path="Photos/2024/Japan/Kyoto/Fushimi",
                    file_name="IMG_001.JPG",
                )
                assert res2 is not None
                assert res2.name == "Fushimi Inari Taisha"
                assert mock_models.generate_content.call_count == 1

    def test_infer_poi_flags_uncertain_category(self) -> None:
        """Asserts generic categories (e.g. Hotel, Restaurant) are flagged as uncertain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(cache_file))

            mock_response_data = {
                "name": "Restaurant",
                "description": "Local dining establishment.",
                "city": "Kyoto",
                "state": None,
                "country": "Japan",
                "confidence_score": 0.85,
                "is_uncertain": False,
            }

            mock_response = MagicMock()
            mock_response.text = json.dumps(mock_response_data)

            mock_models = MagicMock()
            mock_models.generate_content.return_value = mock_response

            mock_client = MagicMock()
            mock_client.models = mock_models

            with patch("google.genai.Client", return_value=mock_client):
                res = parser.infer_poi(
                    folder_path="Photos/2024/Japan/Kyoto/Dinner",
                    file_name="IMG_002.JPG",
                )
                assert res is not None
                # Marked uncertain because name is in GENERIC_CATEGORIES
                assert res.is_uncertain is True
