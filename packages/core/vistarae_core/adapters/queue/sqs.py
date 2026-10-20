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

"""Amazon SQS / ElasticMQ queue adapter implementation.

Implements IQueuePort and IMessageQueue contracts using boto3.
Adheres to Constitution Principle 7 (telemetry & trace attributes) and
Operational Invariant 1 (queue discipline & batch partitioning).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class SQSQueueAdapter:
    """Production SQS and local ElasticMQ queue adapter."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        """Initializes SQS client with endpoint fallback.

        Args:
            endpoint_url: Optional custom SQS endpoint URL (e.g. ElasticMQ).
            region_name: AWS region string.
            client: Pre-configured boto3 SQS client for testing.
        """
        self._endpoint_url = endpoint_url or os.getenv("SQS_ENDPOINT_URL")
        self._region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self._queue_urls: dict[str, str] = {}

        if client is not None:
            self._client = client
        else:
            config = Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=25,
            )
            self._client = boto3.client(
                "sqs",
                endpoint_url=self._endpoint_url,
                region_name=self._region_name,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "mock"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "mock"),
                config=config,
            )

    def _resolve_queue_url(self, queue_name_or_url: str) -> str:
        """Resolves queue name to full SQS Queue URL with internal caching.

        Args:
            queue_name_or_url: Name or URL of the target queue.

        Returns:
            Resolved absolute queue URL string.
        """
        if queue_name_or_url.startswith("http://") or queue_name_or_url.startswith("https://"):
            return queue_name_or_url

        if queue_name_or_url in self._queue_urls:
            return self._queue_urls[queue_name_or_url]

        response = self._client.get_queue_url(QueueName=queue_name_or_url)
        url = response["QueueUrl"]
        self._queue_urls[queue_name_or_url] = url
        return url

    async def send_message(self, queue_name: str, body: dict[str, Any]) -> str:
        """Dispatches a single message to the queue.

        Args:
            queue_name: Queue identifier or URL.
            body: Message body dict.

        Returns:
            Dispatched MessageId string.
        """
        queue_url = self._resolve_queue_url(queue_name)
        payload = json.dumps(body) if not isinstance(body, str) else body
        logger.info("MSG   |-> Target=%s Action=send_message", queue_name)
        response = self._client.send_message(
            QueueUrl=queue_url,
            MessageBody=payload,
        )
        return response["MessageId"]

    async def send_message_batch(
        self,
        queue_name: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sends up to 10 messages in a single batch with trace attributes.

        Args:
            queue_name: Target queue name or URL.
            messages: List of message payloads with 'Id', 'MessageBody', 'MessageAttributes'.

        Returns:
            List of successful response entries.

        Raises:
            ValueError: If batch size exceeds 10 items.
            RuntimeError: If all messages in batch fail.
        """
        if not messages:
            return []

        if len(messages) > 10:
            raise ValueError(f"Batch size {len(messages)} exceeds maximum of 10 items.")

        queue_url = self._resolve_queue_url(queue_name)
        entries: list[dict[str, Any]] = []

        for item in messages:
            body = item.get("MessageBody", "{}")
            body_str = json.dumps(body) if isinstance(body, dict) else str(body)
            attrs = item.get("MessageAttributes", {})
            entry: dict[str, Any] = {
                "Id": str(item["Id"]),
                "MessageBody": body_str,
            }
            if attrs:
                formatted_attrs: dict[str, Any] = {}
                for k, v in attrs.items():
                    if isinstance(v, dict) and "DataType" in v:
                        formatted_attrs[k] = v
                    else:
                        formatted_attrs[k] = {"DataType": "String", "StringValue": str(v)}
                entry["MessageAttributes"] = formatted_attrs
            entries.append(entry)

        logger.info(
            "MSG   |-> Target=%s Action=send_message_batch BatchSize=%d",
            queue_name,
            len(entries),
        )
        response = self._client.send_message_batch(
            QueueUrl=queue_url,
            Entries=entries,
        )

        successful = response.get("Successful", [])
        failed = response.get("Failed", [])
        if failed and not successful:
            raise RuntimeError(f"SQS batch send failed for all {len(failed)} items: {failed}")

        return successful

    async def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> list[dict[str, Any]]:
        """Receives a batch of messages from SQS.

        Args:
            queue_name: Target queue name or URL.
            max_messages: Maximum messages to retrieve (clamped to 10).
            wait_time_seconds: Long polling wait time (0 to 20 seconds).

        Returns:
            List of message dictionaries.
        """
        queue_url = self._resolve_queue_url(queue_name)
        response = self._client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=min(max_messages, 10),
            WaitTimeSeconds=max(0, min(wait_time_seconds, 20)),
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if messages:
            logger.info("MSG <-|   Source=%s Count=%d", queue_name, len(messages))
        return messages

    async def delete_message(self, queue_name: str, receipt_handle: str) -> None:
        """Acknowledges and deletes a message from the queue.

        Args:
            queue_name: Target queue name or URL.
            receipt_handle: Receipt handle returned during receive_messages.
        """
        queue_url = self._resolve_queue_url(queue_name)
        self._client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )
