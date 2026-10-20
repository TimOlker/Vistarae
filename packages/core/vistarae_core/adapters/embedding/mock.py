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

"""In-memory mock embedding adapter for unit testing and offline development."""

from __future__ import annotations

import hashlib

from vistarae_core.ports.embedding import IEmbeddingPort


class MockEmbeddingAdapter(IEmbeddingPort):
    """Generates deterministic pseudo-embeddings for tests without external network calls."""

    def __init__(self, dimension: int = 768) -> None:
        """Initializes mock embedding adapter.

        Args:
            dimension: Dimensionality of generated vectors (defaults to 768).
        """
        self._dim = dimension
        self.call_count = 0

    async def generate_embedding(self, text: str) -> list[float]:
        """Generates deterministic unit vector derived from input text hash.

        Args:
            text: Input text payload.

        Returns:
            Normalized list of float values of length self._dim.
        """
        self.call_count += 1
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector: list[float] = []
        for i in range(self._dim):
            byte_val = digest[i % len(digest)]
            val = ((byte_val / 255.0) * 2.0) - 1.0
            vector.append(round(val, 6))

        return vector
