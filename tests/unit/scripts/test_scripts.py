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

"""Unit tests for operational maintenance scripts (T-051, T-052, T-053).

Tests:
- export_openapi outputs valid JSON OpenAPI spec
- seed_local_db enforces STAGE == 'local'
- redrive_dlq enforces interactive confirmation for non-local and redrives messages
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.export_openapi import export_openapi
from scripts.redrive_dlq import redrive_dlq
from scripts.seed_local_db import seed_local_db


def test_export_openapi(tmp_path: Path) -> None:
    """Asserts export_openapi writes valid JSON file with openapi version."""
    out_file = tmp_path / "test_openapi.json"
    result = export_openapi(out_file)
    assert result.exists()
    data = json.loads(result.read_text(encoding="utf-8"))
    assert "openapi" in data
    assert "paths" in data


@pytest.mark.asyncio
async def test_seed_local_db_rejects_non_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts seed_local_db raises RuntimeError when STAGE != 'local'."""
    monkeypatch.setenv("STAGE", "production")
    with pytest.raises(RuntimeError, match="strictly permitted only when STAGE == 'local'"):
        await seed_local_db()


def test_redrive_dlq_non_local_abort() -> None:
    """Asserts non-local redrive raises RuntimeError if user does not type 'yes'."""
    with (
        patch("builtins.input", return_value="no"),
        pytest.raises(RuntimeError, match="Operation aborted"),
    ):
        redrive_dlq(env="production")


def test_redrive_dlq_local_success() -> None:
    """Asserts local redrive receives and deletes messages."""
    mock_sqs = MagicMock()
    mock_sqs.get_queue_url.side_effect = [
        {"QueueUrl": "http://localhost/dlq"},
        {"QueueUrl": "http://localhost/main"},
    ]
    mock_sqs.receive_message.side_effect = [
        {
            "Messages": [
                {
                    "Body": '{"test": 1}',
                    "ReceiptHandle": "h1",
                    "MessageAttributes": {},
                }
            ]
        },
        {"Messages": []},
    ]

    with patch("boto3.client", return_value=mock_sqs):
        count = redrive_dlq(env="local", max_messages=10)
        assert count == 1
        mock_sqs.send_message_batch.assert_called_once()
        mock_sqs.delete_message_batch.assert_called_once()
