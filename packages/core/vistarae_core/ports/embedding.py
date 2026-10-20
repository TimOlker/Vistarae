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
