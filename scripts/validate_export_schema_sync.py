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

"""Schema synchronization validator between backend and frontend (017-export T-022).

Validates:
- 100% attribute parity between Python export_schema.py and TypeScript export-schema.ts (FR-009)
- Exact header name and sequence alignment
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
PY_SCHEMA_PATH = REPO_ROOT / "packages" / "core" / "vistarae_core" / "schemas" / "export_schema.py"
TS_SCHEMA_PATH = REPO_ROOT / "frontend" / "src" / "types" / "export-schema.ts"


def extract_python_fields() -> list[tuple[str, str]]:
    """Extracts (attribute_key, header_name) tuples from Python CANONICAL_EXPORT_FIELDS."""
    content = PY_SCHEMA_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r'ExportFieldDefinition\(\s*attribute_key="(?P<attr>[^"]+)",\s*header_name="(?P<header>[^"]+)"',
        re.MULTILINE,
    )
    return pattern.findall(content)


def extract_typescript_fields() -> list[tuple[str, str]]:
    """Extracts (attribute_key, header_name) tuples from TypeScript CANONICAL_EXPORT_FIELDS."""
    content = TS_SCHEMA_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r'attribute_key:\s*"(?P<attr>[^"]+)",\s*header_name:\s*"(?P<header>[^"]+)"',
        re.MULTILINE,
    )
    return pattern.findall(content)


def main() -> int:
    """Compares Python and TypeScript canonical export field definitions."""
    if not PY_SCHEMA_PATH.exists():
        print(f"ERROR: Python schema not found at {PY_SCHEMA_PATH}", file=sys.stderr)
        return 1
    if not TS_SCHEMA_PATH.exists():
        print(f"ERROR: TypeScript schema not found at {TS_SCHEMA_PATH}", file=sys.stderr)
        return 1

    py_fields = extract_python_fields()
    ts_fields = extract_typescript_fields()

    print(
        f"Checking schema parity: Python ({len(py_fields)} fields) vs TypeScript ({len(ts_fields)} fields)..."
    )

    if not py_fields:
        print("ERROR: Failed to extract fields from Python schema.", file=sys.stderr)
        return 1
    if not ts_fields:
        print("ERROR: Failed to extract fields from TypeScript schema.", file=sys.stderr)
        return 1

    has_error = False

    if len(py_fields) != len(ts_fields):
        print(
            f"MISMATCH: Field count differs! Python has {len(py_fields)}, TypeScript has {len(ts_fields)}",
            file=sys.stderr,
        )
        has_error = True

    max_len = max(len(py_fields), len(ts_fields))
    for i in range(max_len):
        py_pair = py_fields[i] if i < len(py_fields) else ("<MISSING>", "<MISSING>")
        ts_pair = ts_fields[i] if i < len(ts_fields) else ("<MISSING>", "<MISSING>")

        if py_pair != ts_pair:
            print(
                f"  Row {i}: Python ({py_pair[0]}: '{py_pair[1]}') != TS ({ts_pair[0]}: '{ts_pair[1]}')",
                file=sys.stderr,
            )
            has_error = True

    if has_error:
        print(
            "\nFAILURE: Backend and frontend candidate export schemas are out of sync!",
            file=sys.stderr,
        )
        return 1

    print(f"SUCCESS: All {len(py_fields)} canonical candidate fields are strictly synchronized!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
