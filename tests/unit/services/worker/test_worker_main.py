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

"""Unit tests for worker entrypoint and local consumer loop (T-027).

Verifies:
- lambda_handler dispatch for AWS SQS trigger events
- run_local_worker loop polling, message processing, and deletion
- Exception recovery in local polling loop
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.worker.main import get_worker, lambda_handler, run_local_worker


@pytest.mark.asyncio
class TestWorkerMain:
    """Test suite for worker entrypoints."""

    async def test_get_worker_returns_instance(self) -> None:
        """Asserts get_worker provides a BatchIngestWorker instance."""
        worker = get_worker()
        assert worker is not None

    async def test_lambda_handler_processes_records(self) -> None:
        """Asserts lambda_handler forwards SQS Records to BatchIngestWorker."""
        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "rh-123",
                    "body": json.dumps({"raw_name": "Test POI", "csv_job_id": "00000000-0000-0000-0000-000000000001", "user_id": "00000000-0000-0000-0000-000000000002", "absolute_row_number": 1}),
                    "messageAttributes": {},
                }
            ]
        }

        mock_worker = AsyncMock()
        mock_worker.process_batch.return_value = {"batchItemFailures": []}

        with patch("services.worker.main.get_worker", return_value=mock_worker):
            res = lambda_handler(event, None)
            assert res == {"batchItemFailures": []}
            mock_worker.process_batch.assert_called_once()

    async def test_run_local_worker_processes_and_deletes(self) -> None:
        """Asserts run_local_worker receives messages, processes batch, and deletes acknowledged."""
        mock_queue = AsyncMock()
        sample_msg = {
            "MessageId": "msg-local-1",
            "ReceiptHandle": "rh-local-1",
            "Body": json.dumps({"raw_name": "Local POI", "csv_job_id": "00000000-0000-0000-0000-000000000001", "user_id": "00000000-0000-0000-0000-000000000002", "absolute_row_number": 1}),
        }
        mock_queue.receive_messages.return_value = [sample_msg]
        mock_queue.delete_message.return_value = None

        mock_worker = AsyncMock()
        mock_worker.process_batch.return_value = {"batchItemFailures": []}

        with (
            patch("services.worker.main.SQSQueueAdapter", return_value=mock_queue),
            patch("services.worker.main.get_worker", return_value=mock_worker),
        ):
            await run_local_worker(max_iterations=1, poll_wait_seconds=0)

            mock_queue.receive_messages.assert_called_once()
            mock_worker.process_batch.assert_called_once()
            mock_queue.delete_message.assert_called_once_with(
                "vistarae-ingest-local", "rh-local-1"
            )

    async def test_run_local_worker_recovers_from_exception(self) -> None:
        """Asserts exception in polling loop is caught and logged without aborting prematurely."""
        mock_queue = AsyncMock()
        mock_queue.receive_messages.side_effect = [RuntimeError("Queue unavailable"), []]

        with (
            patch("services.worker.main.SQSQueueAdapter", return_value=mock_queue),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            await run_local_worker(max_iterations=2, poll_wait_seconds=0)
            mock_sleep.assert_called_with(2)
