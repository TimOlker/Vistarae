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

"""Worker entrypoint providing Lambda event handler and local polling loop (T-027).

Provides:
- lambda_handler(event, context) for AWS SQS Lambda event source mappings (REQ-WORKER-001, REQ-WORKER-010)
- run_local_worker() for continuous asynchronous ElasticMQ development polling
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from vistarae_core.adapters.db.session import get_session_factory
from vistarae_core.adapters.embedding.gemini import GeminiEmbeddingAdapter
from vistarae_core.adapters.embedding.mock import MockEmbeddingAdapter
from vistarae_core.adapters.queue.sqs import SQSQueueAdapter
from vistarae_core.adapters.repositories.geocache_repo import SqlAlchemyGeocodingCacheRepository
from vistarae_core.ports.embedding import IEmbeddingPort

from services.worker.geocoder import NominatimGeocoder
from services.worker.processor import BatchIngestWorker
from services.worker.rate_limiter import InMemoryRateLimiter

logger = logging.getLogger(__name__)

# Process-wide singletons
_rate_limiter = InMemoryRateLimiter(interval_seconds=1.0)
_worker: BatchIngestWorker | None = None


def get_worker(embedding_port: IEmbeddingPort | None = None) -> BatchIngestWorker:
    """Instantiates or returns the process-wide BatchIngestWorker instance."""
    global _worker
    if _worker is not None:
        return _worker

    session_factory = get_session_factory()
    stage = os.getenv("STAGE", os.getenv("APP_ENV", "local")).lower()

    if embedding_port is not None:
        embedder = embedding_port
    elif stage == "testing":
        embedder = MockEmbeddingAdapter()
    else:
        embedder = GeminiEmbeddingAdapter()

    # Create geocoder using session for geocache repo
    # Note: cache_repo will be instantiated with each session in process_record or through factory
    dummy_session = session_factory()
    cache_repo = SqlAlchemyGeocodingCacheRepository(dummy_session)
    geocoder = NominatimGeocoder(cache_repo=cache_repo, rate_limiter=_rate_limiter)

    _worker = BatchIngestWorker(
        session_factory=session_factory,
        geocoder=geocoder,
        embedding_port=embedder,
    )
    return _worker


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint triggered by SQS event source mapping.

    Args:
        event: SQS Lambda event containing 'Records'.
        context: Lambda execution context.

    Returns:
        Dict with 'batchItemFailures' list isolating retryable errors.
    """
    records = event.get("Records", [])
    if not records:
        return {"batchItemFailures": []}

    worker = get_worker()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(worker.process_batch(records))).result()

    return asyncio.run(worker.process_batch(records))


def candidate_enrichment_lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint triggered by Candidate Enrichment SQS event source mapping.

    Processes staged POI enrichment events concurrently across horizontally scalable Lambda instances.
    """
    import json
    from uuid import UUID
    from services.worker.candidate_enricher import CandidateEnricher

    records = event.get("Records", [])
    if not records:
        return {"batchItemFailures": []}

    enricher = CandidateEnricher()
    failures: list[dict[str, str]] = []

    async def _process_all() -> None:
        for record in records:
            msg_id = str(record.get("messageId", record.get("MessageId", "")))
            try:
                body_raw = record.get("body", "{}")
                body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
                user_id = UUID(str(body["user_id"]))
                candidate_id = UUID(str(body["candidate_id"]))
                job_id = UUID(str(body["job_id"]))
                await enricher.enrich_candidate(user_id=user_id, candidate_id=candidate_id, job_id=job_id)
            except Exception as exc:
                logger.exception("Failed enriching candidate record in Lambda: %s", exc)
                failures.append({"itemIdentifier": msg_id})

    asyncio.run(_process_all())
    return {"batchItemFailures": failures}


async def run_local_worker(
    max_iterations: int | None = None,
    poll_wait_seconds: int = 5,
) -> None:
    """Runs continuous asynchronous polling against local ElasticMQ queue.

    Args:
        max_iterations: Optional loop limit for test runs.
        poll_wait_seconds: Long polling wait timeout.
    """
    queue_adapter = SQSQueueAdapter()
    queue_name = os.getenv("INGEST_QUEUE_NAME", "vistarae-ingest-local")
    worker = get_worker()

    logger.info("Starting local ingest worker loop for queue '%s'", queue_name)
    iteration = 0

    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            messages = await queue_adapter.receive_messages(
                queue_name=queue_name,
                max_messages=10,
                wait_time_seconds=poll_wait_seconds,
            )
            if not messages:
                continue

            result = await worker.process_batch(messages)
            failed_ids = {f["itemIdentifier"] for f in result.get("batchItemFailures", [])}

            # Delete acknowledged messages
            for msg in messages:
                msg_id = msg.get("MessageId")
                receipt = msg.get("ReceiptHandle")
                if msg_id not in failed_ids and receipt:
                    await queue_adapter.delete_message(queue_name, receipt)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Error in worker polling loop: %s", exc)
            await asyncio.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_local_worker())
