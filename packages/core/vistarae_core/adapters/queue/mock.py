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

"""In-memory queue adapter test double for deterministic testing.

Implements IQueuePort and IMessageQueue contracts without external daemon requirements.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any


class MockQueueAdapter:
    """In-memory queue adapter recording transmissions and enabling retrieval."""

    def __init__(self) -> None:
        """Initializes mock queue storage."""
        self._queues: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.sent_messages: list[dict[str, Any]] = []

    def clear(self) -> None:
        """Resets all queues and sent messages."""
        self._queues.clear()
        self.sent_messages.clear()

    def get_queue_depth(self, queue_name: str) -> int:
        """Returns the current message count for the queue.

        Args:
            queue_name: Queue identifier.

        Returns:
            Integer message count.
        """
        return len(self._queues[queue_name])

    async def send_message(self, queue_name: str, body: dict[str, Any]) -> str:
        """Sends a single message to the in-memory queue.

        Args:
            queue_name: Target queue name.
            body: Message body dict.

        Returns:
            Generated message ID string.
        """
        msg_id = str(uuid.uuid4())
        record = {
            "MessageId": msg_id,
            "ReceiptHandle": f"rh-{msg_id}",
            "Body": json.dumps(body) if not isinstance(body, str) else body,
            "MessageAttributes": {},
        }
        self._queues[queue_name].append(record)
        self.sent_messages.append({"queue": queue_name, "record": record})
        return msg_id

    async def send_message_batch(
        self,
        queue_name: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sends a batch of messages to the in-memory queue.

        Args:
            queue_name: Target queue name.
            messages: List of message entries with 'Id', 'MessageBody', 'MessageAttributes'.

        Returns:
            List of response objects with 'Id' and 'MessageId'.
        """
        successful: list[dict[str, Any]] = []
        for entry in messages:
            msg_id = str(uuid.uuid4())
            body = entry.get("MessageBody", "{}")
            attrs = entry.get("MessageAttributes", {})
            record = {
                "MessageId": msg_id,
                "ReceiptHandle": f"rh-{msg_id}",
                "Body": json.dumps(body) if isinstance(body, dict) else str(body),
                "MessageAttributes": attrs,
            }
            self._queues[queue_name].append(record)
            self.sent_messages.append({"queue": queue_name, "entry": entry, "record": record})
            successful.append({"Id": entry.get("Id", msg_id), "MessageId": msg_id})
        return successful

    async def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 0,
    ) -> list[dict[str, Any]]:
        """Receives messages from the in-memory queue without deleting them.

        Args:
            queue_name: Target queue name.
            max_messages: Maximum messages to retrieve.
            wait_time_seconds: Ignored in mock.

        Returns:
            List of message dicts.
        """
        queue = self._queues[queue_name]
        return list(queue[:max_messages])

    async def delete_message(self, queue_name: str, receipt_handle: str) -> None:
        """Deletes a message matching the receipt handle.

        Args:
            queue_name: Target queue name.
            receipt_handle: Unique receipt handle.
        """
        queue = self._queues[queue_name]
        self._queues[queue_name] = [m for m in queue if m.get("ReceiptHandle") != receipt_handle]
