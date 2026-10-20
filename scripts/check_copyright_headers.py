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

"""Verification script for mandatory file copyright header banners.

Enforces Constitution Principle 1: checks that all .py, .ts, .tsx, and .sql files
contain the standardized copyright header banner.
"""

from __future__ import annotations

import sys
from pathlib import Path

PYTHON_HEADER = (
    "# Copyright (c) 2026 Tim Olker\n"
    "#\n"
    '# Licensed under the Apache License, Version 2.0 (the "License");\n'
    "# you may not use this file except in compliance with the License.\n"
    "# You may obtain a copy of the License at\n"
    "#\n"
    "#     http://www.apache.org/licenses/LICENSE-2.0\n"
    "#\n"
    "# Unless required by applicable law or agreed to in writing, software\n"
    '# distributed under the License is distributed on an "AS IS" BASIS,\n'
    "# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
    "# See the License for the specific language governing permissions and\n"
    "# limitations under the License.\n"
    "#\n"
    "# SPDX-License-Identifier: Apache-2.0"
)

TYPESCRIPT_HEADER = (
    "// Copyright (c) 2026 Tim Olker\n"
    "//\n"
    '// Licensed under the Apache License, Version 2.0 (the "License");\n'
    "// you may not use this file except in compliance with the License.\n"
    "// You may obtain a copy of the License at\n"
    "//\n"
    "//     http://www.apache.org/licenses/LICENSE-2.0\n"
    "//\n"
    "// Unless required by applicable law or agreed to in writing, software\n"
    '// distributed under the License is distributed on an "AS IS" BASIS,\n'
    "// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
    "// See the License for the specific language governing permissions and\n"
    "// limitations under the License.\n"
    "//\n"
    "// SPDX-License-Identifier: Apache-2.0"
)

SQL_HEADER = (
    "-- Copyright (c) 2026 Tim Olker\n"
    "--\n"
    '-- Licensed under the Apache License, Version 2.0 (the "License");\n'
    "-- you may not use this file except in compliance with the License.\n"
    "-- You may obtain a copy of the License at\n"
    "--\n"
    "--     http://www.apache.org/licenses/LICENSE-2.0\n"
    "--\n"
    "-- Unless required by applicable law or agreed to in writing, software\n"
    '-- distributed under the License is distributed on an "AS IS" BASIS,\n'
    "-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
    "-- See the License for the specific language governing permissions and\n"
    "-- limitations under the License.\n"
    "--\n"
    "-- SPDX-License-Identifier: Apache-2.0"
)

EXT_HEADER_MAP: dict[str, str] = {
    ".py": PYTHON_HEADER,
    ".ts": TYPESCRIPT_HEADER,
    ".tsx": TYPESCRIPT_HEADER,
    ".sql": SQL_HEADER,
}


def check_file(path: Path) -> bool:
    """Checks if a file contains the required copyright header banner.

    Args:
        path: Path to the source code file.

    Returns:
        True if the header is present and valid, False otherwise.
    """
    expected_header = EXT_HEADER_MAP.get(path.suffix)
    if expected_header is None:
        return True

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: Could not read {path}: {exc}", file=sys.stderr)
        return False

    normalized_content = content.replace("\r\n", "\n")
    if expected_header not in normalized_content[:1500]:
        print(
            f"FAIL: Missing required copyright banner in {path}",
            file=sys.stderr,
        )
        return False

    return True


def main() -> int:
    """Main CLI entrypoint for pre-commit copyright header enforcement.

    Returns:
        0 on success, 1 on any violation.
    """
    files_to_check = [Path(arg) for arg in sys.argv[1:]]
    if not files_to_check:
        return 0

    failed_files: list[Path] = []
    for file_path in files_to_check:
        if not file_path.is_file():
            continue
        if not check_file(file_path):
            failed_files.append(file_path)

    if failed_files:
        print(
            f"\nCopyright header check failed on {len(failed_files)} file(s).",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
