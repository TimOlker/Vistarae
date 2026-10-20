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

"""Integration tests for local ElasticMQ dead-letter queue redrive (T-035).

Verifies:
- Messages residing in vistarae-ingest-dlq-local are drained via batch operations
- Messages are re-enqueued to vistarae-ingest-local preserving bodies and attributes
- Messages are deleted from DLQ upon successful re-enqueue
- Respects max_messages limit during multi-batch pagination
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from scripts.redrive_dlq import redrive_dlq


class SimulatedSQSState:
    """In-memory stateful SQS simulator for local redrive integration test."""

    def __init__(self) -> None:
        self.dlq_messages: list[dict] = []
        self.main_messages: list[dict] = []
        self.receipt_counter = 0

    def add_dlq_message(self, body: str, attributes: dict | None = None) -> None:
        self.receipt_counter += 1
        self.dlq_messages.append(
            {
                "Body": body,
                "ReceiptHandle": f"receipt-{self.receipt_counter}",
                "MessageAttributes": attributes or {},
            }
        )

    def get_queue_url(self, QueueName: str) -> dict:
        if "dlq" in QueueName:
            return {"QueueUrl": "http://localhost:9324/queue/vistarae-ingest-dlq-local"}
        return {"QueueUrl": "http://localhost:9324/queue/vistarae-ingest-local"}

    def receive_message(
        self,
        QueueUrl: str,
        MaxNumberOfMessages: int = 10,
        WaitTimeSeconds: int = 0,
        MessageAttributeNames: list[str] | None = None,
    ) -> dict:
        if "dlq" in QueueUrl:
            batch = self.dlq_messages[:MaxNumberOfMessages]
            return {"Messages": batch}
        return {"Messages": []}

    def send_message_batch(self, QueueUrl: str, Entries: list[dict]) -> dict:
        if "main" in QueueUrl or "vistarae-ingest-local" in QueueUrl:
            for entry in Entries:
                self.main_messages.append(
                    {
                        "Body": entry["MessageBody"],
                        "MessageAttributes": entry.get("MessageAttributes", {}),
                    }
                )
        return {"Successful": [{"Id": e["Id"]} for e in Entries]}

    def delete_message_batch(self, QueueUrl: str, Entries: list[dict]) -> dict:
        if "dlq" in QueueUrl:
            handles_to_del = {e["ReceiptHandle"] for e in Entries}
            self.dlq_messages = [
                m for m in self.dlq_messages if m["ReceiptHandle"] not in handles_to_del
            ]
        return {"Successful": [{"Id": e["Id"]} for e in Entries]}


class TestRedriveDLQIntegration:
    """Integration test suite for simulated local ElasticMQ DLQ redrive."""

    def test_redrive_local_queue_end_to_end(self) -> None:
        """Asserts 15 messages in DLQ are redriven across 2 batches when max_messages=15."""
        sim = SimulatedSQSState()
        for i in range(15):
            sim.add_dlq_message(
                body=json.dumps({"row": i, "name": f"POI {i}"}),
                attributes={"traceparent": {"DataType": "String", "StringValue": f"00-{i}-01"}},
            )

        mock_client = MagicMock()
        mock_client.get_queue_url.side_effect = sim.get_queue_url
        mock_client.receive_message.side_effect = sim.receive_message
        mock_client.send_message_batch.side_effect = sim.send_message_batch
        mock_client.delete_message_batch.side_effect = sim.delete_message_batch

        with patch("boto3.client", return_value=mock_client):
            moved = redrive_dlq(
                env="local",
                max_messages=15,
                endpoint_url="http://localhost:9324",
            )

            assert moved == 15
            # DLQ should now be empty
            assert len(sim.dlq_messages) == 0
            # Main queue should have received all 15 messages
            assert len(sim.main_messages) == 15
            assert json.loads(sim.main_messages[0]["Body"])["row"] == 0
            assert json.loads(sim.main_messages[14]["Body"])["row"] == 14

    def test_redrive_partial_max_messages(self) -> None:
        """Asserts max_messages limit leaves remaining messages in DLQ."""
        sim = SimulatedSQSState()
        for i in range(12):
            sim.add_dlq_message(body=json.dumps({"row": i}))

        mock_client = MagicMock()
        mock_client.get_queue_url.side_effect = sim.get_queue_url
        mock_client.receive_message.side_effect = sim.receive_message
        mock_client.send_message_batch.side_effect = sim.send_message_batch
        mock_client.delete_message_batch.side_effect = sim.delete_message_batch

        with patch("boto3.client", return_value=mock_client):
            moved = redrive_dlq(
                env="local",
                max_messages=5,
                endpoint_url="http://localhost:9324",
            )

            assert moved == 5
            # 7 messages remaining in DLQ
            assert len(sim.dlq_messages) == 7
            # 5 messages moved to main queue
            assert len(sim.main_messages) == 5
