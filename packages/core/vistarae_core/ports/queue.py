# Copyright (c) 2026 Vistarae. All rights reserved.
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
