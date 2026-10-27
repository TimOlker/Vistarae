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

"""Google Gemini vector embedding adapter implementing IEmbeddingPort (T-027).

Uses google-genai SDK to generate 768-dimensional embeddings via gemini-embedding-001.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from vistarae_core.ports.embedding import IEmbeddingPort


class GeminiEmbeddingAdapter(IEmbeddingPort):
    """Generates 768-dimensional text embeddings using Google Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int = 768,
    ) -> None:
        """Initializes the Gemini embedding adapter.

        Args:
            api_key: Google AI Studio API key (defaults to GEMINI_API_KEY env var).
            model: Embedding model identifier (defaults to GEMINI_EMBEDDING_MODEL or gemini-embedding-001).
            dimension: Dimensionality of the resulting vector (defaults to 768).
        """
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model = model or os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
        self._dimension = dimension

    async def generate_embedding(self, text: str) -> list[float]:
        """Generates a 768-dimensional float embedding for the provided text.

        Args:
            text: Sanitized composite text payload.

        Returns:
            768-element list of float values.

        Raises:
            RuntimeError: If embedding generation fails.
        """
        if not text.strip():
            return [0.0] * self._dimension

        def _call_gemini() -> list[float]:
            from google import genai

            client = genai.Client(api_key=self._api_key)
            config: dict[str, Any] = {}
            if self._dimension:
                config["output_dimensionality"] = self._dimension

            response = client.models.embed_content(
                model=self._model,
                contents=text,
                config=config or None,
            )
            values = None
            if getattr(response, "embeddings", None):
                values = response.embeddings[0].values
            elif getattr(response, "embedding", None):
                values = response.embedding.values

            if values:
                result = [float(v) for v in values]
                if result:
                    return result

            raise RuntimeError(f"Unexpected response structure from Gemini: {response}")

        return await asyncio.to_thread(_call_gemini)
