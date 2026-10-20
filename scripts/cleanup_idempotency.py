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

"""Idempotency key retention cleanup script (T-057).

Purges idempotency records older than the specified age threshold (default: 24 hours)
to ensure database storage footprint remains bounded per REQ-QUOTA-012.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure repository root is on sys.path for direct CLI execution
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_CORE_PATH = _REPO_ROOT / "packages" / "core"
if str(_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(_CORE_PATH))

from vistarae_core.adapters.db.session import _get_session_factory, init_engine  # noqa: E402
from vistarae_core.adapters.repositories.idempotency_repo import (  # noqa: E402
    SqlAlchemyIdempotencyRepository,
)

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Purges expired idempotency keys older than the specified age threshold.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Purge idempotency keys older than this age in hours (default: 24).",
    )
    return parser


async def cleanup_idempotency_keys(hours: int = 24) -> int:
    """Executes the retention cleanup query.

    Args:
        hours: Retention window threshold in hours.

    Returns:
        Count of deleted idempotency key rows.
    """
    await init_engine()
    session_factory = _get_session_factory()
    async with session_factory() as session:
        repo = SqlAlchemyIdempotencyRepository(session)
        deleted_count = await repo.cleanup_older_than(hours=hours)
        await session.commit()

    logger.info(
        "Purged %d idempotency record(s) older than %d hour(s).",
        deleted_count,
        hours,
    )
    return deleted_count


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for idempotency retention cleanup.

    Args:
        argv: Command-line arguments.

    Returns:
        Process exit code (0 for success).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    deleted = asyncio.run(cleanup_idempotency_keys(hours=args.hours))
    print(f"Successfully cleaned up {deleted} idempotency key(s) older than {args.hours} hour(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
