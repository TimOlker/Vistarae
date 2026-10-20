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

"""Message queue port interface.

Abstracts Amazon SQS / ElasticMQ messaging behind a typing.Protocol contract
per Constitution Principle 2 (no boto3 imports in domain logic).
"""

from __future__ import annotations

from typing import Any, Protocol


class IMessageQueue(Protocol):
    """Asynchronous message dispatch and acknowledgement contract."""

    async def send_message(self, queue_name: str, body: dict[str, Any]) -> str:
        """Dispatches a JSON message to the named queue.

        Args:
            queue_name: Target queue identifier (e.g. 'vistarae-ingest-local').
            body: Serializable message payload.

        Returns:
            Provider-assigned message ID string.

        Raises:
            RuntimeError: If the queue send operation fails.
        """
        ...

    async def delete_message(self, queue_name: str, receipt_handle: str) -> None:
        """Acknowledges and removes a message from the queue.

        Args:
            queue_name: Queue identifier the message was received from.
            receipt_handle: Opaque handle returned when the message was received.

        Raises:
            RuntimeError: If the delete operation fails.
        """
        ...


class IQueuePort(Protocol):
    """Port interface for message queue operations supporting batches and trace attributes."""

    async def send_message_batch(
        self,
        queue_name: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sends up to 10 messages in a single batch to the specified queue.

        Args:
            queue_name: Queue name or URL.
            messages: List of message payloads with attributes. Each item should contain
                'Id', 'MessageBody' (JSON string), and optional 'MessageAttributes'.

        Returns:
            List of successfully sent message response dicts (e.g. [{'Id': ..., 'MessageId': ...}]).

        Raises:
            RuntimeError: If queue transmission fails.
        """
        ...

    async def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> list[dict[str, Any]]:
        """Receives a batch of messages from the specified queue.

        Args:
            queue_name: Queue name or URL.
            max_messages: Maximum messages to retrieve (up to 10).
            wait_time_seconds: Long-polling wait duration in seconds (0-20).

        Returns:
            List of raw message dictionaries including Body, ReceiptHandle, MessageAttributes.
        """
        ...

    async def delete_message(self, queue_name: str, receipt_handle: str) -> None:
        """Deletes a message from the queue by its receipt handle.

        Args:
            queue_name: Queue name or URL.
            receipt_handle: Receipt handle of the message to delete.
        """
        ...
