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

"""W3C Distributed Tracing telemetry middleware.

Implements Constitution Principle 7:
- Extracts W3C traceparent header (00-{trace_id}-{parent_span_id}-01)
- Generates a new server-side span_id for each request
- Attaches X-Transaction-ID, X-Current-Span-ID, X-Parent-Transaction-ID to responses
- When STAGE == 'local', emits directional MSG: -->| / <--| / <~~| log lines
"""

from __future__ import annotations

import logging
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


def _parse_traceparent(header: str | None) -> tuple[str, str]:
    """Extracts trace_id and parent_span_id from a W3C traceparent header.

    Falls back to freshly generated random identifiers when the header is absent
    or structurally invalid.

    Args:
        header: Raw traceparent string or None.

    Returns:
        Tuple of (trace_id, parent_span_id) as hex strings.
    """
    if header:
        parts = header.strip().split("-")
        if (
            len(parts) == 4
            and len(parts[0]) == 2
            and len(parts[1]) == 32
            and len(parts[2]) == 16
            and len(parts[3]) == 2
            and parts[1] != "0" * 32
            and parts[2] != "0" * 16
        ):
            return parts[1], parts[2]

    # Generate synthetic IDs for requests without a propagated trace context.
    return secrets.token_hex(16), secrets.token_hex(8)


def _new_span_id() -> str:
    """Generates a cryptographically random 8-byte hex span identifier.

    Returns:
        16-character lowercase hex string.
    """
    return secrets.token_hex(8)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Starlette ASGI middleware for W3C trace propagation and local MSG logging.

    When STAGE is 'local', logs inbound and outbound requests using the
    directional message tag protocol required by the Vistarae architecture:

    - Inbound:       ``MSG -->| [{source} -> {destination}] …``
    - Success 2XX:   ``MSG <--| [{destination} -> {source}] …``
    - Error 4XX/5XX: ``MSG <~~| [{destination} -> {source}] …``
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initializes the middleware with STAGE awareness.

        Args:
            app: Inner ASGI application to wrap.
        """
        super().__init__(app)
        self._stage = os.getenv("STAGE", "local")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Processes inbound request: extracts/generates trace context and wraps response.

        Args:
            request: Incoming HTTP request from Starlette.
            call_next: Next ASGI handler in the middleware chain.

        Returns:
            Response with injected correlation headers.
        """
        trace_id, parent_span_id = _parse_traceparent(request.headers.get("traceparent"))
        span_id = _new_span_id()

        source = request.headers.get("X-Source", "client")
        destination = request.headers.get("X-Destination", "gateway")

        if self._stage == "local":
            logger.info(
                "MSG -->| [%s -> %s] [trace=%s] %s %s",
                source,
                destination,
                trace_id,
                request.method,
                request.url.path,
            )

        response = await call_next(request)

        # Attach W3C correlation headers to every outgoing response.
        response.headers["X-Transaction-ID"] = trace_id
        response.headers["X-Current-Span-ID"] = span_id
        response.headers["X-Parent-Transaction-ID"] = parent_span_id

        if self._stage == "local":
            if response.status_code < 400:
                logger.info(
                    "MSG <--| [%s -> %s] [trace=%s] [status=%d]",
                    destination,
                    source,
                    trace_id,
                    response.status_code,
                )
            else:
                logger.warning(
                    "MSG <~~| [%s -> %s] [trace=%s] [status=%d]",
                    destination,
                    source,
                    trace_id,
                    response.status_code,
                )

        return response
