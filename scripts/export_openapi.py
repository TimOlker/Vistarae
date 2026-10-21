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

"""OpenAPI contract export script (T-051).

Generates ./openapi.json from the unified ASGI gateway for frontend
TypeScript contract generation per Constitution Principle 5.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_CORE_PATH = _REPO_ROOT / "packages" / "core"
if str(_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(_CORE_PATH))

from services.local_gateway import app  # noqa: E402


def export_openapi(output_path: Path | None = None) -> Path:
    """Exports OpenAPI 3.1 specification to JSON.

    Args:
        output_path: Target path for the output file (defaults to ./openapi.json).

    Returns:
        Path to the exported openapi.json file.
    """
    target = output_path or (Path(__file__).resolve().parent.parent / "openapi.json")
    spec = app.openapi()

    with open(target, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    return target


if __name__ == "__main__":
    out = export_openapi()
    print(f"Exported OpenAPI specification to {out}")
