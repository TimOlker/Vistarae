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

"""Unit tests for Phase 3 domain entities, value objects, and queue adapters (T-009).

Tests IngestJob, DuplicatePayloadItem, IngestRowMessage, IngestJobStatus,
DuplicateTriageStatus, domain exceptions, IngestJobTable ORM, and queue adapters.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from vistarae_core.adapters.db.tables import IngestJobTable
from vistarae_core.adapters.queue.mock import MockQueueAdapter
from vistarae_core.adapters.queue.sqs import SQSQueueAdapter
from vistarae_core.domain.entities import (
    DuplicatePayloadItem,
    IngestJob,
    IngestRowMessage,
)
from vistarae_core.domain.exceptions import (
    FileTooLargeError,
    IngestJobNotFoundError,
    InvalidCSVHeaderError,
    InvalidMimeTypeError,
    RowLimitExceededError,
)
from vistarae_core.domain.value_objects import (
    DuplicateTriageStatus,
    IngestJobStatus,
)


class TestIngestValueObjectsAndExceptions:
    """Verifies domain enums and error types."""

    def test_ingest_job_status_values(self) -> None:
        """Asserts all required job status values exist."""
        assert IngestJobStatus.PENDING == "PENDING"
        assert IngestJobStatus.PROCESSING == "PROCESSING"
        assert IngestJobStatus.COMPLETED == "COMPLETED"
        assert IngestJobStatus.PARTIAL_SUCCESS == "PARTIAL_SUCCESS"
        assert IngestJobStatus.FAILED == "FAILED"

    def test_duplicate_triage_status_values(self) -> None:
        """Asserts all required triage status values exist."""
        assert DuplicateTriageStatus.PENDING_REVIEW == "PENDING_REVIEW"
        assert DuplicateTriageStatus.COMMITTED == "COMMITTED"
        assert DuplicateTriageStatus.REJECTED == "REJECTED"

    def test_domain_exceptions_attributes(self) -> None:
        """Verifies custom attributes and message formatting of ingestion exceptions."""
        job_err = IngestJobNotFoundError("job-123")
        assert job_err.job_id == "job-123"
        assert "job-123" in str(job_err)

        size_err = FileTooLargeError(3_000_000, 2_097_152)
        assert size_err.size == 3_000_000
        assert size_err.max_size == 2_097_152

        row_err = RowLimitExceededError(2500, 2000)
        assert row_err.count == 2500
        assert row_err.max_rows == 2000

        mime_err = InvalidMimeTypeError("image/png")
        assert mime_err.mime_type == "image/png"
        assert "text/csv" in mime_err.allowed

        header_err = InvalidCSVHeaderError(["name", "latitude"])
        assert "name" in header_err.missing_headers


class TestIngestEntities:
    """Verifies domain entities and aggregates."""

    def test_ingest_job_percent_complete(self) -> None:
        """Tests progress percentage computation across boundary cases."""
        user_id = uuid.uuid4()
        job = IngestJob(
            id=uuid.uuid4(),
            user_id=user_id,
            job_status=IngestJobStatus.PENDING,
            total_rows=0,
            processed_rows=0,
        )
        assert job.percent_complete == 0.0

        job.job_status = IngestJobStatus.COMPLETED
        assert job.percent_complete == 100.0

        job.total_rows = 200
        job.processed_rows = 50
        assert job.percent_complete == 25.0

        job.processed_rows = 200
        assert job.percent_complete == 100.0

    def test_duplicate_payload_item_instantiation(self) -> None:
        """Verifies duplicate payload item attributes."""
        poi_id = uuid.uuid4()
        item = DuplicatePayloadItem(
            row_number=1,
            raw_name="Grand Canyon",
            candidate_poi_id=poi_id,
            match_type="POTENTIAL_DUPLICATE",
            similarity_score=0.92,
            distance_meters=150.0,
            triage_status=DuplicateTriageStatus.PENDING_REVIEW,
            staged_poi_data={"name": "Grand Canyon"},
        )
        assert item.row_number == 1
        assert item.triage_status == DuplicateTriageStatus.PENDING_REVIEW
        assert item.similarity_score == 0.92

    def test_ingest_row_message_instantiation(self) -> None:
        """Verifies IngestRowMessage structure."""
        job_id = uuid.uuid4()
        user_id = uuid.uuid4()
        msg = IngestRowMessage(
            job_id=job_id,
            user_id=user_id,
            absolute_row_number=42,
            row_data={"name": "Half Dome", "latitude": "37.7"},
        )
        assert msg.job_id == job_id
        assert msg.absolute_row_number == 42
        assert msg.target_list_id is None


class TestIngestJobTableORM:
    """Verifies SQLAlchemy IngestJobTable columns and table args."""

    def test_table_columns_and_constraints(self) -> None:
        """Asserts all required columns and constraints are present on IngestJobTable."""
        cols = {c.name for c in IngestJobTable.__table__.columns}
        expected = {
            "id",
            "user_id",
            "job_status",
            "total_rows",
            "processed_rows",
            "duplicate_payloads",
            "target_list_id",
            "error_summary",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(cols)
        assert IngestJobTable.__tablename__ == "ingest_jobs"


@pytest.mark.asyncio
class TestQueueAdapters:
    """Verifies MockQueueAdapter and SQSQueueAdapter behaviors."""

    async def test_mock_queue_adapter_lifecycle(self) -> None:
        """Tests sending, receiving, and deleting messages in MockQueueAdapter."""
        adapter = MockQueueAdapter()
        assert adapter.get_queue_depth("test-queue") == 0

        # Send batch
        entries = [
            {"Id": "1", "MessageBody": {"text": "hello"}, "MessageAttributes": {"traceparent": "00-test-01"}},
            {"Id": "2", "MessageBody": {"text": "world"}},
        ]
        res = await adapter.send_message_batch("test-queue", entries)
        assert len(res) == 2
        assert adapter.get_queue_depth("test-queue") == 2

        # Receive messages
        msgs = await adapter.receive_messages("test-queue", max_messages=5)
        assert len(msgs) == 2
        receipt = msgs[0]["ReceiptHandle"]

        # Delete message
        await adapter.delete_message("test-queue", receipt)
        assert adapter.get_queue_depth("test-queue") == 1

        adapter.clear()
        assert adapter.get_queue_depth("test-queue") == 0

    async def test_sqs_queue_adapter_with_mocked_client(self) -> None:
        """Tests SQSQueueAdapter batch dispatch and error boundaries."""
        mock_boto = MagicMock()
        mock_boto.get_queue_url.return_value = {"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/test-q"}
        mock_boto.send_message_batch.return_value = {
            "Successful": [{"Id": "1", "MessageId": "msg-1"}],
            "Failed": [],
        }
        mock_boto.receive_message.return_value = {
            "Messages": [{"MessageId": "msg-1", "ReceiptHandle": "rh-1", "Body": "{}"}]
        }
        mock_boto.send_message.return_value = {"MessageId": "single-msg-1"}

        adapter = SQSQueueAdapter(client=mock_boto)

        # Single send
        msg_id = await adapter.send_message("test-q", {"test": "data"})
        assert msg_id == "single-msg-1"

        # Batch send
        entries = [
            {
                "Id": "1",
                "MessageBody": {"name": "Test POI"},
                "MessageAttributes": {"traceparent": "00-trace-01"},
            }
        ]
        sent = await adapter.send_message_batch("test-q", entries)
        assert len(sent) == 1
        assert sent[0]["MessageId"] == "msg-1"

        # Receive
        received = await adapter.receive_messages("test-q", max_messages=5)
        assert len(received) == 1

        # Delete
        await adapter.delete_message("test-q", "rh-1")
        mock_boto.delete_message.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123/test-q",
            ReceiptHandle="rh-1",
        )

        # Exceed batch limit
        too_many = [{"Id": str(i), "MessageBody": "{}"} for i in range(11)]
        with pytest.raises(ValueError, match="exceeds maximum of 10"):
            await adapter.send_message_batch("test-q", too_many)
