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

"""Unit tests for OpenTelemetry W3C distributed tracing and logging tags."""

import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.telemetry import (
    TAG_INBOUND_MSG,
    TAG_OUTBOUND_MSG,
    TAG_OUTBOUND_RESP,
    TAG_RESPONSE_MSG,
    generate_span_id,
    generate_trace_id,
    log_msg,
)


def test_trace_id_generation():
    trace_id = generate_trace_id()
    assert len(trace_id) == 32
    assert re.match(r"^[0-9a-f]{32}$", trace_id)


def test_span_id_generation():
    span_id = generate_span_id()
    assert len(span_id) == 16
    assert re.match(r"^[0-9a-f]{16}$", span_id)


def test_log_msg_format(caplog):
    with caplog.at_level("INFO"):
        log_msg(TAG_INBOUND_MSG, "Test incoming message")
        log_msg(TAG_RESPONSE_MSG, "Test outgoing response")
        log_msg(TAG_OUTBOUND_MSG, "Test external call")
        log_msg(TAG_OUTBOUND_RESP, "Test external response")

    assert f"MSG {TAG_INBOUND_MSG}Test incoming message" in caplog.text
    assert f"MSG {TAG_RESPONSE_MSG}Test outgoing response" in caplog.text
    assert f"MSG {TAG_OUTBOUND_MSG}Test external call" in caplog.text
    assert f"MSG {TAG_OUTBOUND_RESP}Test external response" in caplog.text


@pytest.mark.asyncio
async def test_w3c_traceparent_propagation_headers():
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    client_span_id = "00f067aa0ba902b7"
    traceparent = f"00-{trace_id}-{client_span_id}-01"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={
                "traceparent": traceparent,
                "X-Source": "extension",
                "X-Destination": "backend",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("X-Transaction-ID") == trace_id
    assert response.headers.get("X-Parent-Transaction-ID") == client_span_id
    server_span_id = response.headers.get("X-Current-Span-ID")
    assert server_span_id is not None
    assert len(server_span_id) == 16
