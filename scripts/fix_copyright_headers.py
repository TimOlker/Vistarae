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

"""One-off utility to add missing copyright headers to source files."""

from __future__ import annotations

from pathlib import Path

from scripts.check_copyright_headers import (
    EXT_HEADER_MAP,
    check_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {".git", ".venv", "node_modules", "dist", "build", "__pycache__"}


def fix_file(path: Path) -> bool:
    if not path.is_file():
        return False

    header = EXT_HEADER_MAP.get(path.suffix)
    if not header:
        return False

    if check_file(path):
        return False  # Already valid

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"Skipping {path}: {exc}")
        return False

    # Check for shebang
    lines = content.splitlines(keepends=True)
    if lines and lines[0].startswith("#!"):
        shebang = lines[0]
        rest = "".join(lines[1:]).lstrip("\r\n")
        new_content = f"{shebang}\n{header}\n\n{rest}"
    else:
        new_content = f"{header}\n\n{content.lstrip('\r\n')}"

    path.write_text(new_content, encoding="utf-8")
    print(f"Fixed: {path.relative_to(REPO_ROOT)}")
    return True


def main() -> None:
    fixed_count = 0
    for ext in EXT_HEADER_MAP:
        for p in REPO_ROOT.rglob(f"*{ext}"):
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            if fix_file(p):
                fixed_count += 1
    print(f"Total files fixed: {fixed_count}")


if __name__ == "__main__":
    main()
