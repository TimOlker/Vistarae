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

"""Unit tests for dead-letter queue redrive CLI (T-034).

Verifies:
- Argument parsing for flags: --env, --max-messages, --dry-run, --non-interactive, --yes
- Missing mandatory --env triggers SystemExit
- Cloud environments enforce interactive confirmation or explicit --yes flag
- Non-interactive cloud runs without --yes raise RuntimeError
- Dry-run mode inspects DLQ message count without sending or deleting messages
- Local environment executes without confirmation using batch SQS operations
- main entrypoint exit code behavior
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts.redrive_dlq import main, parse_args, redrive_dlq


class TestRedriveDLQUnit:
    """Unit test suite for DLQ redrive CLI script."""

    def test_parse_args_all_flags(self) -> None:
        """Asserts all flags are properly parsed."""
        args = parse_args(
            [
                "--env",
                "staging",
                "--max-messages",
                "50",
                "--dry-run",
                "--non-interactive",
                "--yes",
                "--endpoint-url",
                "http://localhost:4566",
            ]
        )
        assert args.env == "staging"
        assert args.max_messages == 50
        assert args.dry_run is True
        assert args.non_interactive is True
        assert args.yes is True
        assert args.endpoint_url == "http://localhost:4566"

    def test_parse_args_short_flags(self) -> None:
        """Asserts short flag aliases work properly."""
        args = parse_args(["-e", "prod", "-m", "25", "-y"])
        assert args.env == "prod"
        assert args.max_messages == 25
        assert args.yes is True

    def test_parse_args_missing_env_raises(self) -> None:
        """Asserts omitting --env results in CLI parse error."""
        with pytest.raises(SystemExit):
            parse_args(["--max-messages", "10"])

    def test_parse_args_invalid_env_raises(self) -> None:
        """Asserts invalid environment name raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(["--env", "invalid_env"])

    def test_cloud_interactive_abort(self) -> None:
        """Asserts typing anything other than 'yes' raises RuntimeError."""
        with (
            patch("builtins.input", return_value="no"),
            pytest.raises(RuntimeError, match="Operation aborted by user"),
        ):
            redrive_dlq(env="staging")

    def test_cloud_non_interactive_without_yes_raises(self) -> None:
        """Asserts non-interactive cloud invocation without --yes raises RuntimeError."""
        with pytest.raises(RuntimeError, match="requires explicit --yes flag"):
            redrive_dlq(env="prod", non_interactive=True, yes=False)

    def test_cloud_non_interactive_with_yes_succeeds(self) -> None:
        """Asserts non-interactive cloud invocation with --yes initiates start_message_move_task."""
        mock_sqs = MagicMock()
        mock_sqs.get_queue_url.side_effect = [
            {"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/dlq"},
            {"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/main"},
        ]
        mock_sqs.get_queue_attributes.side_effect = [
            {"Attributes": {"QueueArn": "arn:aws:sqs:us-east-1:123:dlq"}},
            {"Attributes": {"QueueArn": "arn:aws:sqs:us-east-1:123:main"}},
        ]
        mock_sqs.start_message_move_task.return_value = {"TaskHandle": "task-abc-123"}

        with patch("boto3.client", return_value=mock_sqs):
            count = redrive_dlq(env="staging", non_interactive=True, yes=True)
            assert count == 1
            mock_sqs.start_message_move_task.assert_called_once_with(
                SourceArn="arn:aws:sqs:us-east-1:123:dlq",
                DestinationArn="arn:aws:sqs:us-east-1:123:main",
                MaxNumberOfMessagesPerSecond=50,
            )

    def test_dry_run_cloud_inspects_only(self) -> None:
        """Asserts dry-run checks queue attributes and exits without modifying queue."""
        mock_sqs = MagicMock()
        mock_sqs.get_queue_url.side_effect = [
            {"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/dlq"},
            {"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/main"},
        ]
        mock_sqs.get_queue_attributes.return_value = {
            "Attributes": {"ApproximateNumberOfMessages": "42"}
        }

        with patch("boto3.client", return_value=mock_sqs):
            count = redrive_dlq(env="prod", dry_run=True)
            assert count == 42
            mock_sqs.start_message_move_task.assert_not_called()
            mock_sqs.delete_message_batch.assert_not_called()

    def test_local_redrive_batches(self) -> None:
        """Asserts local redrive consumes and batches messages back to main queue."""
        mock_sqs = MagicMock()
        mock_sqs.get_queue_url.side_effect = [
            {"QueueUrl": "http://localhost:9324/queue/dlq"},
            {"QueueUrl": "http://localhost:9324/queue/main"},
        ]
        mock_sqs.receive_message.side_effect = [
            {
                "Messages": [
                    {
                        "Body": '{"id": 1}',
                        "ReceiptHandle": "rh-1",
                        "MessageAttributes": {},
                    },
                    {
                        "Body": '{"id": 2}',
                        "ReceiptHandle": "rh-2",
                        "MessageAttributes": {},
                    },
                ]
            },
            {"Messages": []},
        ]

        with patch("boto3.client", return_value=mock_sqs):
            count = redrive_dlq(env="local", max_messages=10)
            assert count == 2
            mock_sqs.send_message_batch.assert_called_once()
            mock_sqs.delete_message_batch.assert_called_once()

    def test_main_cli_error_exits_code_1(self) -> None:
        """Asserts main catches unhandled exceptions and exits with code 1."""
        with (
            patch("scripts.redrive_dlq.redrive_dlq", side_effect=RuntimeError("Aborted")),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["--env", "staging"])
        assert exc_info.value.code == 1
