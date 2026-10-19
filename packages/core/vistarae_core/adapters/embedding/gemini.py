# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Google Gemini vector embedding adapter implementing IEmbeddingPort (T-027).

Uses google-genai SDK to generate 768-dimensional embeddings via text-embedding-004.
"""

from __future__ import annotations

import asyncio
import os

from vistarae_core.ports.embedding import IEmbeddingPort


class GeminiEmbeddingAdapter(IEmbeddingPort):
    """Generates 768-dimensional text embeddings using Google Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-004",
    ) -> None:
        """Initializes the Gemini embedding adapter.

        Args:
            api_key: Google AI Studio API key (defaults to GEMINI_API_KEY env var).
            model: Embedding model identifier.
        """
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model = model

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
            return [0.0] * 768

        def _call_gemini() -> list[float]:
            from google import genai

            client = genai.Client(api_key=self._api_key)
            response = client.models.embed_content(
                model=self._model,
                contents=text,
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
