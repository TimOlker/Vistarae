# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Port protocol for vector embedding generation.

Isolates LLM and embedding SDKs (e.g. Gemini 768-dim) from core business logic.
"""

from __future__ import annotations

from typing import Protocol


class IEmbeddingPort(Protocol):
    """Port interface for text vector embedding providers."""

    async def generate_embedding(self, text: str) -> list[float]:
        """Generates a 768-dimensional float embedding for the provided text.

        Args:
            text: Sanitized composite text payload.

        Returns:
            768-element list of float values representing the embedding.
        """
        ...
