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

"""Unit tests for vector embedding adapters, text normalizers, and MD5 hashing (T-025).

Tests:
- normalize_whitespace: collapsing multiple spaces, trimming
- build_composite_text: deterministic concatenation of name, description, address, sorted tags
- compute_embedding_md5: 32-char MD5 checksums for change detection
- GeminiEmbeddingAdapter: 768-dim embedding generation, empty text handling, error handling
- MockEmbeddingAdapter: deterministic vector generation and call tracking
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from vistarae_core.adapters.embedding.gemini import GeminiEmbeddingAdapter
from vistarae_core.adapters.embedding.mock import MockEmbeddingAdapter
from vistarae_core.services.embedding_sanitizer import (
    build_composite_text,
    compute_embedding_md5,
    normalize_whitespace,
)


class TestEmbeddingSanitizer:
    """Tests for text normalization and MD5 calculation."""

    def test_normalize_whitespace(self) -> None:
        """Asserts collapsing of redundant whitespace and linebreaks."""
        raw = "  Yosemite \n\n  National   Park\t "
        assert normalize_whitespace(raw) == "Yosemite National Park"

    def test_build_composite_text(self) -> None:
        """Asserts composite text includes all attributes and sorts tags."""
        text = build_composite_text(
            name="Glacier Point",
            description="Panoramic scenic viewpoint over the valley",
            address="Glacier Point Rd",
            city="Yosemite",
            states=["California"],
            countries=["United States"],
            tags=["viewpoint", "scenic", "sunset"],
        )
        assert "Glacier Point" in text
        assert "Panoramic scenic viewpoint" in text
        assert "scenic, sunset, viewpoint" in text
        assert "California" in text

    def test_compute_embedding_md5_stability(self) -> None:
        """Asserts MD5 checksum is 32 chars and unchanged for identical normalized content."""
        t1 = build_composite_text(name="Zion", tags=["hiking", "canyon"])
        t2 = build_composite_text(name="Zion  ", tags=["canyon", "hiking"])
        md5_1 = compute_embedding_md5(t1)
        md5_2 = compute_embedding_md5(t2)
        assert len(md5_1) == 32
        assert md5_1 == md5_2


class TestGeminiEmbeddingAdapter:
    """Tests for GeminiEmbeddingAdapter."""

    @pytest.mark.asyncio
    async def test_empty_text_returns_zero_vector(self) -> None:
        """Empty text returns 768 zeroes without calling API."""
        adapter = GeminiEmbeddingAdapter(api_key="test-key")
        vector = await adapter.generate_embedding("   ")
        assert len(vector) == 768
        assert all(v == 0.0 for v in vector)

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self) -> None:
        """Asserts successful call to Gemini client returns 768-dim float list."""
        adapter = GeminiEmbeddingAdapter(api_key="test-key")

        mock_embedding = MagicMock()
        mock_embedding.values = [0.01 * i for i in range(768)]
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]

        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.models.embed_content.return_value = mock_response
            mock_client_cls.return_value = mock_client

            vector = await adapter.generate_embedding("Half Dome")
            assert len(vector) == 768
            assert vector[10] == pytest.approx(0.10)

    @pytest.mark.asyncio
    async def test_unexpected_response_raises_error(self) -> None:
        """Asserts error when Gemini returns unrecognized structure."""
        adapter = GeminiEmbeddingAdapter(api_key="test-key")

        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock(spec=["status"])
            mock_client.models.embed_content.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Unexpected response structure"):
                await adapter.generate_embedding("Invalid")


class TestMockEmbeddingAdapter:
    """Tests for MockEmbeddingAdapter."""

    @pytest.mark.asyncio
    async def test_mock_vector_generation(self) -> None:
        """Asserts mock generates 768 values deterministically and tracks calls."""
        mock = MockEmbeddingAdapter(dimension=768)
        v1 = await mock.generate_embedding("Bryce Canyon")
        v2 = await mock.generate_embedding("Bryce Canyon")
        assert len(v1) == 768
        assert v1 == v2
        assert mock.call_count == 2
