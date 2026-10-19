# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Operational DLQ redrive CLI script (T-053).

Re-enqueues failed dead-letter queue messages back into the primary ingestion queue.
Enforces Constitution Principle 6: Mandatory --env flag and interactive confirmation
for all non-local environments.
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3


def redrive_dlq(
    env: str,
    max_messages: int = 100,
    dry_run: bool = False,
    endpoint_url: str | None = None,
) -> int:
    """Moves messages from DLQ back to primary queue.

    Args:
        env: Target environment ('local', 'staging', 'production').
        max_messages: Maximum count of messages to redrive.
        dry_run: If True, inspects DLQ without moving messages.
        endpoint_url: Optional override endpoint URL (e.g. ElasticMQ locally).

    Returns:
        Number of messages redriven.

    Raises:
        RuntimeError: If confirmation is rejected for non-local environments.
    """
    if env != "local" and not dry_run:
        prompt = input(
            f"WARNING: You are about to redrive DLQ messages in '{env}'.\nType 'yes' to confirm: "
        )
        if prompt.strip().lower() != "yes":
            raise RuntimeError("Operation aborted by user.")

    sqs_kwargs = {"region_name": os.getenv("AWS_REGION", "us-east-1")}
    if endpoint_url:
        sqs_kwargs["endpoint_url"] = endpoint_url
    elif env == "local":
        sqs_kwargs["endpoint_url"] = os.getenv("SQS_ENDPOINT_URL", "http://localhost:9324")

    client = boto3.client("sqs", **sqs_kwargs)

    dlq_name = f"vistarae-ingest-dlq-{env}"
    main_queue_name = f"vistarae-ingest-{env}"

    try:
        dlq_url = client.get_queue_url(QueueName=dlq_name)["QueueUrl"]
        main_queue_url = client.get_queue_url(QueueName=main_queue_name)["QueueUrl"]
    except Exception as exc:
        print(f"Failed to resolve queue URLs: {exc}", file=sys.stderr)
        return 0

    redriven_count = 0
    while redriven_count < max_messages:
        batch_size = min(10, max_messages - redriven_count)
        response = client.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=batch_size,
            WaitTimeSeconds=2,
            MessageAttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if not messages:
            break

        if dry_run:
            print(f"[DRY RUN] Found {len(messages)} messages in DLQ.")
            return len(messages)

        for msg in messages:
            # Re-enqueue to main queue
            client.send_message(
                QueueUrl=main_queue_url,
                MessageBody=msg["Body"],
                MessageAttributes=msg.get("MessageAttributes", {}),
            )
            # Delete from DLQ
            client.delete_message(
                QueueUrl=dlq_url,
                ReceiptHandle=msg["ReceiptHandle"],
            )
            redriven_count += 1

    print(
        f"Redrive complete: {redriven_count} messages moved from {dlq_name} to {main_queue_name}."
    )
    return redriven_count


def main() -> None:
    """CLI entrypoint for redrive_dlq."""
    parser = argparse.ArgumentParser(description="Vistarae SQS DLQ Redrive Utility")
    parser.add_argument(
        "--env",
        required=True,
        choices=["local", "staging", "production"],
        help="Target environment (mandatory).",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=100,
        help="Maximum messages to redrive (default: 100).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect DLQ message count without re-enqueuing.",
    )
    args = parser.parse_args()

    try:
        redrive_dlq(env=args.env, max_messages=args.max_messages, dry_run=args.dry_run)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
