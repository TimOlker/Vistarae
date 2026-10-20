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

"""Operational DLQ redrive CLI script (T-036).

Re-enqueues failed dead-letter queue messages back into the primary ingestion queue.
Enforces Constitution Principle 6:
- Mandatory --env flag
- Interactive confirmation for all non-local environments
- --non-interactive requires explicit --yes flag
- Uses batch operations on local ElasticMQ and AWS native start_message_move_task in cloud
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import boto3


def redrive_dlq(
    env: str,
    max_messages: int = 100,
    dry_run: bool = False,
    non_interactive: bool = False,
    yes: bool = False,
    endpoint_url: str | None = None,
) -> int:
    """Moves messages from DLQ back to primary queue.

    Args:
        env: Target environment ('local', 'staging', 'prod', 'production').
        max_messages: Maximum count of messages to redrive.
        dry_run: If True, inspects DLQ without moving messages.
        non_interactive: If True, disables interactive confirmation prompts.
        yes: Explicit confirmation flag for non-interactive cloud execution.
        endpoint_url: Optional override endpoint URL (e.g. ElasticMQ locally).

    Returns:
        Number of messages redriven or inspected.

    Raises:
        RuntimeError: If confirmation is rejected or required flags are missing.
    """
    normalized_env = "prod" if env == "production" else env

    # 1. Confirmation handling for cloud environments
    if normalized_env != "local" and not dry_run:
        if non_interactive:
            if not yes:
                raise RuntimeError(
                    f"Non-interactive redrive in '{env}' requires explicit --yes flag."
                )
        elif not yes:
            prompt = input(
                f"WARNING: You are about to redrive DLQ messages in '{env}'.\nType 'yes' to confirm: "
            )
            if prompt.strip().lower() != "yes":
                raise RuntimeError("Operation aborted by user.")

    # 2. SQS client configuration
    sqs_kwargs: dict[str, Any] = {"region_name": os.getenv("AWS_REGION", "us-east-1")}
    if endpoint_url:
        sqs_kwargs["endpoint_url"] = endpoint_url
    elif normalized_env == "local":
        sqs_kwargs["endpoint_url"] = os.getenv("SQS_ENDPOINT_URL", "http://localhost:9324")

    client = boto3.client("sqs", **sqs_kwargs)

    dlq_name = f"vistarae-ingest-dlq-{normalized_env}"
    main_queue_name = f"vistarae-ingest-{normalized_env}"

    try:
        dlq_url = client.get_queue_url(QueueName=dlq_name)["QueueUrl"]
        main_queue_url = client.get_queue_url(QueueName=main_queue_name)["QueueUrl"]
    except Exception as exc:
        print(f"Failed to resolve queue URLs: {exc}", file=sys.stderr)
        return 0

    # 3. Dry run inspection
    if dry_run:
        try:
            attrs = client.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            count = int(attrs.get("Attributes", {}).get("ApproximateNumberOfMessages", 0))
        except Exception:
            # Fallback for mock environments without get_queue_attributes attributes
            resp = client.receive_message(
                QueueUrl=dlq_url,
                MaxNumberOfMessages=min(10, max_messages),
                WaitTimeSeconds=1,
            )
            count = len(resp.get("Messages", []))

        print(f"[DRY RUN] Found ~{count} messages in DLQ {dlq_name}.")
        return count

    # 4. Cloud execution via AWS Native Message Move Task
    if normalized_env != "local":
        try:
            dlq_arn = client.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])[
                "Attributes"
            ]["QueueArn"]
            main_arn = client.get_queue_attributes(
                QueueUrl=main_queue_url, AttributeNames=["QueueArn"]
            )["Attributes"]["QueueArn"]
            response = client.start_message_move_task(
                SourceArn=dlq_arn,
                DestinationArn=main_arn,
                MaxNumberOfMessagesPerSecond=50,
            )
            task_handle = response.get("TaskHandle", "unknown")
            print(f"Started native AWS SQS message move task: {task_handle}")
            return 1
        except Exception as exc:
            print(f"Failed to start message move task: {exc}", file=sys.stderr)
            raise RuntimeError(f"Cloud redrive task failed: {exc}") from exc

    # 5. Local execution via batch receive, send, and delete
    redriven_count = 0
    while redriven_count < max_messages:
        batch_size = min(10, max_messages - redriven_count)
        response = client.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=batch_size,
            WaitTimeSeconds=1,
            MessageAttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if not messages:
            break

        send_entries = [
            {
                "Id": f"msg_{i}",
                "MessageBody": msg["Body"],
                "MessageAttributes": msg.get("MessageAttributes", {}),
            }
            for i, msg in enumerate(messages)
        ]
        client.send_message_batch(
            QueueUrl=main_queue_url,
            Entries=send_entries,
        )

        delete_entries = [
            {
                "Id": f"del_{i}",
                "ReceiptHandle": msg["ReceiptHandle"],
            }
            for i, msg in enumerate(messages)
        ]
        client.delete_message_batch(
            QueueUrl=dlq_url,
            Entries=delete_entries,
        )
        redriven_count += len(messages)

    print(
        f"Redrive complete: {redriven_count} messages moved from {dlq_name} to {main_queue_name}."
    )
    return redriven_count


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments for redrive_dlq utility."""
    parser = argparse.ArgumentParser(description="Vistarae SQS DLQ Redrive Utility")
    parser.add_argument(
        "--env",
        "-e",
        required=True,
        choices=["local", "staging", "prod", "production"],
        help="Target environment (mandatory): local, staging, prod, production.",
    )
    parser.add_argument(
        "--max-messages",
        "-m",
        type=int,
        default=100,
        help="Maximum messages to redrive (default: 100).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect DLQ message count without re-enqueuing.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable interactive prompts (requires --yes for cloud).",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Explicit confirmation for non-interactive cloud runs.",
    )
    parser.add_argument(
        "--endpoint-url",
        type=str,
        default=None,
        help="Override SQS endpoint URL.",
    )
    return parser.parse_args(args)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for redrive_dlq."""
    args = parse_args(argv)
    try:
        redrive_dlq(
            env=args.env,
            max_messages=args.max_messages,
            dry_run=args.dry_run,
            non_interactive=args.non_interactive,
            yes=args.yes,
            endpoint_url=args.endpoint_url,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
