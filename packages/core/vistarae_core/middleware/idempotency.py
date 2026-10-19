# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Database-backed idempotency protection middleware.

Implements Constitution Principle 6 (User Story 4 — REQ-QUOTA-007 through 011):
- Intercepts POST, PUT, PATCH, DELETE requests carrying an Idempotency-Key header
- PENDING  → Returns RFC 7807 409 Conflict (concurrent mutation in progress)
- COMPLETED → Short-circuits and replays cached response with X-Cache-Lookup: HIT
- Newly created → Passes through; caches COMPLETED or marks FAILED on completion

Execution order under Starlette LIFO:
  IdempotencyMiddleware registered first → executes INNERMOST
  Outer: Telemetry → RateLimit → Idempotency : Inner
"""

from __future__ import annotations

import json
import logging
import os
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from vistarae_core.domain.value_objects import IdempotencyStatus

logger = logging.getLogger(__name__)

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_MEDIA_TYPE = "application/problem+json"


def _problem_409(key: str) -> JSONResponse:
    """Constructs an RFC 7807 409 Conflict response for concurrent mutations.

    Args:
        key: The Idempotency-Key that is currently marked PENDING.

    Returns:
        JSONResponse with application/problem+json content type.
    """
    body = {
        "type": "https://errors.vistarae.com/idempotency-conflict",
        "title": "Idempotency Conflict",
        "status": 409,
        "detail": (
            f"A mutation with Idempotency-Key '{key}' is already in progress. "
            "Please wait for the in-flight request to complete before retrying."
        ),
    }
    return JSONResponse(status_code=409, content=body, media_type=_MEDIA_TYPE)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Prevents duplicate mutations across POST/PUT/PATCH/DELETE via DB key locking.

    Requires that ``request.app.state.idempotency_repo`` and
    ``request.state.user_id`` are populated by the auth dependency layer before
    this middleware performs key lookups.  If either is absent, the request
    passes through without idempotency enforcement.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initializes the middleware.

        Args:
            app: Inner ASGI application.
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Inspects mutating requests for Idempotency-Key and enforces uniqueness.

        Args:
            request: Incoming HTTP request.
            call_next: Next ASGI handler in the middleware stack.

        Returns:
            Cached replay, conflict response, or the live downstream response.
        """
        # Only mutating methods are subject to idempotency enforcement.
        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        user_id: UUID | None = getattr(request.state, "user_id", None)
        if user_id is None:
            stage = os.getenv("STAGE", os.getenv("APP_ENV", "local"))
            if stage == "local":
                mock_id = request.headers.get("X-Mock-User-Id")
                if mock_id:
                    try:
                        user_id = UUID(mock_id)
                        request.state.user_id = user_id
                    except (ValueError, AttributeError):
                        pass

        if user_id is None:
            return await call_next(request)

        repo = getattr(request.app.state, "idempotency_repo", None)
        if repo is None:
            try:
                from vistarae_core.adapters.db.session import get_db_session
                from vistarae_core.adapters.repositories.idempotency_repo import (
                    SqlAlchemyIdempotencyRepository,
                )

                override = request.app.dependency_overrides.get(get_db_session)
                session = override() if override else None
                repo = SqlAlchemyIdempotencyRepository(session)
            except Exception:
                repo = None

        if repo is None:
            return await call_next(request)

        # ── Atomic get-or-create the idempotency record ───────────────────
        status, cached_code, cached_payload = await repo.get_or_create(user_id, idempotency_key)

        if status == IdempotencyStatus.PENDING and cached_code is None:
            # Newly inserted PENDING record — proceed with the actual request.
            return await self._execute_and_cache(request, call_next, repo, user_id, idempotency_key)

        if status == IdempotencyStatus.PENDING:
            # Existing PENDING record means a concurrent request is in flight.
            return _problem_409(idempotency_key)

        if status == IdempotencyStatus.COMPLETED and cached_payload is not None:
            # Replay the cached response with the HIT marker.
            return JSONResponse(
                status_code=cached_code or 200,
                content=cached_payload,
                headers={"X-Cache-Lookup": "HIT"},
            )

        # FAILED status — allow retry by re-running (get_or_create transitions to PENDING).
        return await self._execute_and_cache(request, call_next, repo, user_id, idempotency_key)

    @staticmethod
    async def _execute_and_cache(
        request: Request,
        call_next: RequestResponseEndpoint,
        repo: object,
        user_id: UUID,
        key: str,
    ) -> Response:
        """Executes the downstream handler and persists the result.

        On 2XX/3XX success: reads the response body and persists status=COMPLETED.
        On any other status or exception: marks status=FAILED so retries can proceed.

        Args:
            request: Original incoming request.
            call_next: Next ASGI handler.
            repo: IIdempotencyRepository implementation.
            user_id: Authenticated tenant UUID.
            key: Client-provided idempotency key.

        Returns:
            Downstream response, unmodified.
        """
        try:
            response = await call_next(request)
        except Exception:
            await repo.fail(user_id, key)
            raise

        if response.status_code < 300:
            # Buffer the streaming body so we can cache it.
            body_chunks: list[bytes] = []
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body_chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
            body_bytes = b"".join(body_chunks)

            try:
                payload = json.loads(body_bytes)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"raw": body_bytes.decode(errors="replace")}

            await repo.complete(user_id, key, response.status_code, payload)

            # Return a new response with the buffered body so the client still receives it.
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Non-success responses — mark FAILED so subsequent retries are allowed.
        await repo.fail(user_id, key)
        return response
