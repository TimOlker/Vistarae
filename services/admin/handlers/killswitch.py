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

"""SpendKillSwitch AWS Lambda handler with 4-tier cascading fallback.

Triggered by AWS Budgets SNS alert at the $15.00 ceiling.
Executes an infallible 4-tier shutdown:
  Tier 1: Throttle API Gateway HTTP API $default stage to 0 rate/burst (drops 100% of edge traffic).
  Tier 2: Disable SQS EventSourceMapping for BatchIngestWorker (Enabled=False).
  Tier 3: Set killswitch_active=true in Neon database system_settings table.
  Tier 4: Best-effort attempt to set ReservedConcurrentExecutions: 0 across domain Lambdas,
          gracefully catching AWS ValidationException if account unreserved concurrency floor is hit.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError
from vistarae_core.adapters.db.session import get_session_factory
from vistarae_core.adapters.repositories.itinerary_repo import (
    SqlAlchemyItineraryRepository,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DOMAIN_FUNCTIONS: list[str] = [
    "PoiFunction",
    "UserFunction",
    "IngestFunction",
    "AdminFunction",
    "BatchIngestWorker",
]


async def _execute_tier1_edge_throttle(apigw_client: Any, api_id: str) -> bool:
    """Tier 1: Throttles API Gateway $default stage to 0 requests/sec."""
    try:
        logger.info("Executing Tier 1 Edge Shutdown on API %s", api_id)
        apigw_client.update_stage(
            ApiId=api_id,
            StageName="$default",
            DefaultRouteSettings={
                "ThrottlingBurstLimit": 0,
                "ThrottlingRateLimit": 0.0,
            },
        )
        logger.info("Tier 1 SUCCESS: API Gateway stage throttled to 0/0")
        return True
    except ClientError as err:
        logger.error("Tier 1 ERROR throttling API Gateway: %s", err)
        return False


async def _execute_tier2_sqs_disable(lambda_client: Any, mapping_uuid: str | None) -> bool:
    """Tier 2: Disables SQS EventSourceMapping for BatchIngestWorker."""
    try:
        if not mapping_uuid:
            # Discover mapping UUID if not provided via environment variable
            mappings = lambda_client.list_event_source_mappings(
                FunctionName="BatchIngestWorker"
            ).get("EventSourceMappings", [])
            if mappings:
                mapping_uuid = mappings[0]["UUID"]

        if mapping_uuid:
            logger.info("Executing Tier 2 SQS Worker Disable for Mapping %s", mapping_uuid)
            lambda_client.update_event_source_mapping(
                UUID=mapping_uuid,
                Enabled=False,
            )
            logger.info("Tier 2 SUCCESS: SQS EventSourceMapping disabled")
            return True
        logger.warning("Tier 2 SKIPPED: No SQS EventSourceMapping found")
        return False
    except ClientError as err:
        logger.error("Tier 2 ERROR disabling SQS EventSourceMapping: %s", err)
        return False


async def _execute_tier3_database_lock(reason: str) -> bool:
    """Tier 3: Sets killswitch_active=true in Neon database system_settings."""
    try:
        logger.info("Executing Tier 3 Database State Lock")
        factory = get_session_factory()
        async with factory() as session:
            repo = SqlAlchemyItineraryRepository(session)
            await repo.set_system_setting(
                "spend_killswitch",
                {
                    "killswitch_active": True,
                    "triggered_at": datetime.now(UTC).isoformat(),
                    "reason": reason,
                },
            )
            await session.commit()
        logger.info("Tier 3 SUCCESS: system_settings.spend_killswitch locked to active")
        return True
    except Exception as err:
        logger.error("Tier 3 ERROR locking database state: %s", err)
        return False


async def _execute_tier4_concurrency_reserve(lambda_client: Any) -> dict[str, str]:
    """Tier 4: Best-effort attempt to set ReservedConcurrentExecutions: 0 across domain Lambdas."""
    results: dict[str, str] = {}
    for func_name in DOMAIN_FUNCTIONS:
        try:
            logger.info("Attempting Tier 4 Concurrency Cut on %s", func_name)
            lambda_client.put_function_concurrency(
                FunctionName=func_name,
                ReservedConcurrentExecutions=0,
            )
            results[func_name] = "CONCURRENCY_SET_TO_ZERO"
            logger.info("Tier 4: Concurrency set to 0 on %s", func_name)
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code", "Unknown")
            error_msg = err.response.get("Error", {}).get("Message", str(err))
            logger.warning(
                "Tier 4: Caught %s setting concurrency on %s (Unreserved Concurrency Floor reached): %s",
                error_code,
                func_name,
                error_msg,
            )
            results[func_name] = f"FLOOR_LIMIT_CAUGHT:{error_code}"
    return results


async def handle_spend_killswitch_async(
    event: dict[str, Any],
    context: Any = None,
    apigw_client: Any = None,
    lambda_client: Any = None,
) -> dict[str, Any]:
    """Core async orchestration for SpendKillSwitch with 4-tier fallback."""
    logger.warning("SPEND KILL SWITCH TRIGGERED: %s", event)

    reason = "AWS Budget threshold breach"
    if "Records" in event and event["Records"]:
        sns_msg = event["Records"][0].get("Sns", {}).get("Message", "")
        if sns_msg:
            reason = f"AWS Budgets alert: {sns_msg}"

    api_id = os.getenv("API_GATEWAY_ID", "local-api-id")
    mapping_uuid = os.getenv("INGEST_WORKER_MAPPING_UUID")

    if apigw_client is None:
        apigw_client = boto3.client(
            "apigatewayv2", region_name=os.getenv("AWS_REGION", "us-east-2")
        )
    if lambda_client is None:
        lambda_client = boto3.client("lambda", region_name=os.getenv("AWS_REGION", "us-east-2"))

    t1_status = await _execute_tier1_edge_throttle(apigw_client, api_id)
    t2_status = await _execute_tier2_sqs_disable(lambda_client, mapping_uuid)
    t3_status = await _execute_tier3_database_lock(reason)
    t4_status = await _execute_tier4_concurrency_reserve(lambda_client)

    return {
        "status": "KILLSWITCH_EXECUTED",
        "timestamp": datetime.now(UTC).isoformat(),
        "tier1_edge_throttle": t1_status,
        "tier2_sqs_disable": t2_status,
        "tier3_database_lock": t3_status,
        "tier4_concurrency_reserve": t4_status,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Synchronous AWS Lambda entrypoint wrapping async orchestration."""
    import asyncio

    return asyncio.run(handle_spend_killswitch_async(event, context))
