# Copyright (c) 2026 Vistarae. All rights reserved.
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
