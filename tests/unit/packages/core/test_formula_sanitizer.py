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

"""Unit tests validating formula injection defense and symmetric desanitization (017-export)."""

from __future__ import annotations

import pytest
from vistarae_core.schemas.export_schema import (
    desanitize_formula_prefix,
    sanitize_formula_prefix,
)


class TestFormulaSanitization:
    """Tests formula prefix neutralization and authentic value recovery."""

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
    def test_sanitize_neutralizes_all_formula_prefixes(self, prefix: str) -> None:
        """Asserts each formula trigger character receives a prepended single quote."""
        malicious = f"{prefix}123456"
        sanitized = sanitize_formula_prefix(malicious)
        assert sanitized == f"'{malicious}"

    def test_sanitize_preserves_normal_text(self) -> None:
        """Asserts non-formula text is left completely unmodified."""
        assert sanitize_formula_prefix("Eiffel Tower") == "Eiffel Tower"
        assert sanitize_formula_prefix("42 Wallaby Way") == "42 Wallaby Way"
        assert sanitize_formula_prefix("") == ""

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
    def test_desanitize_strips_neutralizing_quote(self, prefix: str) -> None:
        """Asserts authentic values are restored by removing leading neutralizing quote."""
        neutralized = f"'{prefix}123456"
        desanitized = desanitize_formula_prefix(neutralized)
        assert desanitized == f"{prefix}123456"

    def test_desanitize_preserves_legitimate_apostrophes(self) -> None:
        """Asserts genuine apostrophes not followed by formula triggers are preserved."""
        assert desanitize_formula_prefix("'O'Reilly Pub") == "'O'Reilly Pub"
        assert desanitize_formula_prefix("L'Arc de Triomphe") == "L'Arc de Triomphe"
        assert desanitize_formula_prefix("") == ""
