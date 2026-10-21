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

"""Unit tests for SpendKillSwitch Lambda handler with 4-tier cascading fallback (T037)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from services.admin.handlers.killswitch import (
    DOMAIN_FUNCTIONS,
    _execute_tier1_edge_throttle,
    _execute_tier2_sqs_disable,
    _execute_tier3_database_lock,
    _execute_tier4_concurrency_reserve,
    handle_spend_killswitch_async,
    lambda_handler,
)


class TestSpendKillSwitchCascade:
    """Verifies that all 4 shutdown tiers execute reliably with cascading fallbacks."""

    @pytest.mark.asyncio
    async def test_tier1_edge_throttle_success(self) -> None:
        """Tier 1: Verify API Gateway stage throttles to 0 rate/burst."""
        mock_apigw = MagicMock()
        mock_apigw.update_stage.return_value = {}

        result = await _execute_tier1_edge_throttle(mock_apigw, "api-12345")
        assert result is True
        mock_apigw.update_stage.assert_called_once_with(
            ApiId="api-12345",
            StageName="$default",
            DefaultRouteSettings={
                "ThrottlingBurstLimit": 0,
                "ThrottlingRateLimit": 0.0,
            },
        )

    @pytest.mark.asyncio
    async def test_tier1_edge_throttle_failure_graceful(self) -> None:
        """Tier 1: Verify graceful error handling when API Gateway call fails."""
        mock_apigw = MagicMock()
        mock_apigw.update_stage.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}, "update_stage"
        )

        result = await _execute_tier1_edge_throttle(mock_apigw, "api-12345")
        assert result is False

    @pytest.mark.asyncio
    async def test_tier2_sqs_disable_with_uuid(self) -> None:
        """Tier 2: Verify SQS EventSourceMapping is disabled when UUID is provided."""
        mock_lambda = MagicMock()
        mock_lambda.update_event_source_mapping.return_value = {}

        result = await _execute_tier2_sqs_disable(mock_lambda, "uuid-mapping-123")
        assert result is True
        mock_lambda.update_event_source_mapping.assert_called_once_with(
            UUID="uuid-mapping-123",
            Enabled=False,
        )

    @pytest.mark.asyncio
    async def test_tier2_sqs_disable_lookup_fallback(self) -> None:
        """Tier 2: Verify mapping UUID is discovered via list_event_source_mappings if missing."""
        mock_lambda = MagicMock()
        mock_lambda.list_event_source_mappings.return_value = {
            "EventSourceMappings": [{"UUID": "discovered-uuid-456"}]
        }
        mock_lambda.update_event_source_mapping.return_value = {}

        result = await _execute_tier2_sqs_disable(mock_lambda, None)
        assert result is True
        mock_lambda.list_event_source_mappings.assert_called_once_with(
            FunctionName="BatchIngestWorker"
        )
        mock_lambda.update_event_source_mapping.assert_called_once_with(
            UUID="discovered-uuid-456",
            Enabled=False,
        )

    @pytest.mark.asyncio
    async def test_tier2_sqs_disable_not_found(self) -> None:
        """Tier 2: Verify graceful skip when no SQS EventSourceMapping is found."""
        mock_lambda = MagicMock()
        mock_lambda.list_event_source_mappings.return_value = {"EventSourceMappings": []}

        result = await _execute_tier2_sqs_disable(mock_lambda, None)
        assert result is False

    @pytest.mark.asyncio
    async def test_tier3_database_lock_success(self) -> None:
        """Tier 3: Verify database system_settings table updated with killswitch state."""
        mock_repo = AsyncMock()
        mock_repo.set_system_setting.return_value = None

        mock_session = AsyncMock()
        mock_session.commit.return_value = None

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_factory = MagicMock(return_value=mock_session_ctx)

        with (
            patch(
                "services.admin.handlers.killswitch.get_session_factory", return_value=mock_factory
            ),
            patch(
                "services.admin.handlers.killswitch.SqlAlchemyItineraryRepository",
                return_value=mock_repo,
            ),
        ):
            result = await _execute_tier3_database_lock("Budget breach")
            assert result is True
            mock_repo.set_system_setting.assert_called_once()
            call_args = mock_repo.set_system_setting.call_args[0]
            assert call_args[0] == "spend_killswitch"
            assert call_args[1]["killswitch_active"] is True
            assert "Budget breach" in call_args[1]["reason"]

    @pytest.mark.asyncio
    async def test_tier4_concurrency_floor_caught(self) -> None:
        """Tier 4: Catch ValidationException when unreserved concurrency floor is hit."""
        mock_lambda = MagicMock()
        # Simulate ValidationException for account concurrency reserve floor (e.g. 10 reserve floor)
        mock_lambda.put_function_concurrency.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ValidationException",
                    "Message": "Specified ReservedConcurrentExecutions for function would lead to value below unreserved floor 10",
                }
            },
            "put_function_concurrency",
        )

        results = await _execute_tier4_concurrency_reserve(mock_lambda)
        assert len(results) == len(DOMAIN_FUNCTIONS)
        for func_name in DOMAIN_FUNCTIONS:
            assert "FLOOR_LIMIT_CAUGHT:ValidationException" in results[func_name]

    @pytest.mark.asyncio
    async def test_tier4_concurrency_success(self) -> None:
        """Tier 4: Verify concurrency set to zero when reserve permits."""
        mock_lambda = MagicMock()
        mock_lambda.put_function_concurrency.return_value = {}

        results = await _execute_tier4_concurrency_reserve(mock_lambda)
        assert len(results) == len(DOMAIN_FUNCTIONS)
        for func_name in DOMAIN_FUNCTIONS:
            assert results[func_name] == "CONCURRENCY_SET_TO_ZERO"

    @pytest.mark.asyncio
    async def test_tier2_sqs_disable_client_error(self) -> None:
        """Tier 2: Verify graceful error handling when AWS Lambda call throws ClientError."""
        mock_lambda = MagicMock()
        mock_lambda.update_event_source_mapping.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Mapping not found"}},
            "update_event_source_mapping",
        )

        result = await _execute_tier2_sqs_disable(mock_lambda, "uuid-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_tier3_database_lock_failure(self) -> None:
        """Tier 3: Verify graceful error handling when database fails."""
        mock_factory = MagicMock(side_effect=RuntimeError("Database connection lost"))

        with patch(
            "services.admin.handlers.killswitch.get_session_factory", return_value=mock_factory
        ):
            result = await _execute_tier3_database_lock("Budget breach")
            assert result is False

    @pytest.mark.asyncio
    async def test_full_killswitch_orchestration(self) -> None:
        """Verifies end-to-end async orchestration across all 4 tiers from SNS event."""
        mock_apigw = MagicMock()
        mock_apigw.update_stage.return_value = {}

        mock_lambda = MagicMock()
        mock_lambda.update_event_source_mapping.return_value = {}
        mock_lambda.put_function_concurrency.return_value = {}

        event = {
            "Records": [
                {
                    "Sns": {
                        "Message": "Budget alert: $15.00 limit reached on account",
                    }
                }
            ]
        }

        with patch(
            "services.admin.handlers.killswitch._execute_tier3_database_lock",
            new_callable=AsyncMock,
        ) as mock_t3:
            mock_t3.return_value = True
            result = await handle_spend_killswitch_async(
                event=event,
                apigw_client=mock_apigw,
                lambda_client=mock_lambda,
            )

            assert result["status"] == "KILLSWITCH_EXECUTED"
            assert result["tier1_edge_throttle"] is True
            assert result["tier3_database_lock"] is True
            assert "tier4_concurrency_reserve" in result

    @pytest.mark.asyncio
    async def test_killswitch_orchestration_defaults_and_boto_init(self) -> None:
        """Verifies handling of event without Records and initialization of default boto clients."""
        mock_boto_client = MagicMock()
        mock_boto_client.update_stage.return_value = {}
        mock_boto_client.list_event_source_mappings.return_value = {"EventSourceMappings": []}
        mock_boto_client.put_function_concurrency.return_value = {}

        with (
            patch("services.admin.handlers.killswitch.boto3.client", return_value=mock_boto_client),
            patch(
                "services.admin.handlers.killswitch._execute_tier3_database_lock",
                new_callable=AsyncMock,
            ) as mock_t3,
        ):
            mock_t3.return_value = True
            result = await handle_spend_killswitch_async(event={})
            assert result["status"] == "KILLSWITCH_EXECUTED"
            assert result["tier1_edge_throttle"] is True

    def test_sync_lambda_handler_entrypoint(self) -> None:
        """Verifies synchronous AWS Lambda entrypoint execution."""
        mock_result = {"status": "KILLSWITCH_EXECUTED"}
        with patch(
            "services.admin.handlers.killswitch.handle_spend_killswitch_async",
            new_callable=AsyncMock,
        ) as mock_async:
            mock_async.return_value = mock_result
            res = lambda_handler({}, None)
            assert res["status"] == "KILLSWITCH_EXECUTED"
            mock_async.assert_called_once()
