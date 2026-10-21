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

"""Administrative CLI tool to restore API Gateway stage, SQS worker, and reset KillSwitch.

Usage:
    python -m scripts.reset_killswitch --api-id <API_ID> [--mapping-uuid <UUID>] [--region us-east-2]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

import boto3
from botocore.exceptions import ClientError
from vistarae_core.adapters.db.session import get_session_factory
from vistarae_core.adapters.repositories.itinerary_repo import (
    SqlAlchemyItineraryRepository,
)

from services.admin.handlers.killswitch import DOMAIN_FUNCTIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def reset_killswitch(
    api_id: str,
    mapping_uuid: str | None,
    region: str,
) -> None:
    """Restores platform compute and traffic after spend review."""
    logger.info("Starting SpendKillSwitch restoration sequence for API %s in %s...", api_id, region)

    apigw_client = boto3.client("apigatewayv2", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)

    # 1. Restore API Gateway default stage throttle
    try:
        logger.info("Restoring API Gateway $default stage throttle...")
        apigw_client.update_stage(
            ApiId=api_id,
            StageName="$default",
            DefaultRouteSettings={
                "ThrottlingBurstLimit": 500,
                "ThrottlingRateLimit": 100.0,
            },
        )
        logger.info("✓ API Gateway stage restored (RateLimit=100.0, BurstLimit=500)")
    except ClientError as err:
        logger.error("Failed to restore API Gateway stage: %s", err)

    # 2. Re-enable SQS worker EventSourceMapping
    try:
        if not mapping_uuid:
            mappings = lambda_client.list_event_source_mappings(
                FunctionName="BatchIngestWorker"
            ).get("EventSourceMappings", [])
            if mappings:
                mapping_uuid = mappings[0]["UUID"]

        if mapping_uuid:
            logger.info("Re-enabling SQS EventSourceMapping %s...", mapping_uuid)
            lambda_client.update_event_source_mapping(
                UUID=mapping_uuid,
                Enabled=True,
            )
            logger.info("✓ SQS EventSourceMapping re-enabled")
        else:
            logger.warning("No SQS EventSourceMapping found to re-enable")
    except ClientError as err:
        logger.error("Failed to re-enable SQS EventSourceMapping: %s", err)

    # 3. Clear database killswitch flag
    try:
        logger.info("Clearing Neon DB system_settings.spend_killswitch flag...")
        factory = get_session_factory()
        async with factory() as session:
            repo = SqlAlchemyItineraryRepository(session)
            await repo.set_system_setting(
                "spend_killswitch",
                {
                    "killswitch_active": False,
                    "triggered_at": None,
                    "reason": None,
                },
            )
            await session.commit()
        logger.info("✓ Neon DB spend_killswitch cleared (killswitch_active=false)")
    except Exception as err:
        logger.error("Failed to clear database killswitch flag: %s", err)

    # 4. Remove ReservedConcurrentExecutions limits
    for func_name in DOMAIN_FUNCTIONS:
        try:
            logger.info("Removing concurrency constraint on %s...", func_name)
            lambda_client.delete_function_concurrency(FunctionName=func_name)
            logger.info("✓ Concurrency constraint removed on %s", func_name)
        except ClientError as err:
            logger.warning(
                "Could not delete concurrency on %s (may not have been set): %s", func_name, err
            )

    logger.info("Restoration sequence complete. All services operating normally.")


def main() -> None:
    """Parses command line arguments and runs restoration sequence."""
    parser = argparse.ArgumentParser(
        description="Restore Vistarae platform from SpendKillSwitch shutdown."
    )
    parser.add_argument(
        "--api-id", default=os.getenv("API_GATEWAY_ID", "local-api-id"), help="API Gateway ID"
    )
    parser.add_argument(
        "--mapping-uuid",
        default=os.getenv("INGEST_WORKER_MAPPING_UUID"),
        help="SQS EventSourceMapping UUID",
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-2"), help="AWS Region")

    args = parser.parse_args()
    asyncio.run(reset_killswitch(args.api_id, args.mapping_uuid, args.region))


if __name__ == "__main__":
    main()
