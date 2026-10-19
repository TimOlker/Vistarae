# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TelemetryMiddleware (T-014).

Tests cover:
- W3C traceparent extraction from valid and missing headers
- Fresh span_id generation for every request
- Synthetic trace/parent IDs when traceparent is absent
- Correct directional MSG: -->|, <--|, <~~| log output when STAGE=local
- Correlation headers (X-Transaction-ID, X-Current-Span-ID, X-Parent-Transaction-ID) on responses
- No MSG logs emitted when STAGE != 'local'
"""

from __future__ import annotations

import logging

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient
from vistarae_core.middleware.telemetry import TelemetryMiddleware, _parse_traceparent


class TestTraceParentParsing:
    """Unit tests for the _parse_traceparent helper function."""

    def test_valid_traceparent_extracted(self) -> None:
        """Well-formed traceparent header should yield its trace_id and parent_id."""
        header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        trace_id, parent_id = _parse_traceparent(header)
        assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert parent_id == "00f067aa0ba902b7"

    def test_none_header_generates_synthetic_ids(self) -> None:
        """Missing traceparent should produce valid-length synthetic hex strings."""
        trace_id, parent_id = _parse_traceparent(None)
        assert len(trace_id) == 32  # 16 bytes as hex
        assert len(parent_id) == 16  # 8 bytes as hex

    def test_malformed_header_generates_synthetic_ids(self) -> None:
        """Malformed traceparent (wrong segment count) should generate synthetic IDs."""
        trace_id, parent_id = _parse_traceparent("not-a-valid-traceparent")
        assert len(trace_id) == 32
        assert len(parent_id) == 16

    def test_synthetic_ids_are_different_per_call(self) -> None:
        """Each call without a traceparent should produce unique IDs."""
        trace_id_1, _ = _parse_traceparent(None)
        trace_id_2, _ = _parse_traceparent(None)
        assert trace_id_1 != trace_id_2


class TestTelemetryMiddlewareHeaders:
    """Integration tests for correlation header injection via ASGI test client."""

    def _make_app(self, status_code: int = 200) -> Starlette:
        async def handler(request: Request) -> Response:
            return JSONResponse({"ok": True}, status_code=status_code)

        app = Starlette(routes=[Route("/test", handler)])
        app.add_middleware(TelemetryMiddleware)
        return app

    def test_correlation_headers_injected_on_success(self) -> None:
        """2XX response should contain all three W3C correlation headers."""
        app = self._make_app(200)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/test",
            headers={"traceparent": "00-aabbccddeeff00112233445566778899-1122334455667788-01"},
        )
        assert "X-Transaction-ID" in resp.headers
        assert "X-Current-Span-ID" in resp.headers
        assert "X-Parent-Transaction-ID" in resp.headers
        assert resp.headers["X-Transaction-ID"] == "aabbccddeeff00112233445566778899"
        assert resp.headers["X-Parent-Transaction-ID"] == "1122334455667788"

    def test_fresh_span_id_generated_per_request(self) -> None:
        """Each request should get a unique X-Current-Span-ID."""
        app = self._make_app(200)
        client = TestClient(app, raise_server_exceptions=False)
        r1 = client.get("/test")
        r2 = client.get("/test")
        assert r1.headers["X-Current-Span-ID"] != r2.headers["X-Current-Span-ID"]

    def test_synthetic_trace_id_when_no_traceparent(self) -> None:
        """Absent traceparent header should still yield a valid X-Transaction-ID."""
        app = self._make_app(200)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        trace_id = resp.headers.get("X-Transaction-ID", "")
        assert len(trace_id) == 32


class TestTelemetryMiddlewareLogging:
    """Verifies MSG directional log output for local and cloud stages."""

    def _make_app(self, status_code: int = 200) -> Starlette:
        async def handler(request: Request) -> Response:
            return JSONResponse({"ok": True}, status_code=status_code)

        app = Starlette(routes=[Route("/ping", handler)])
        app.add_middleware(TelemetryMiddleware)
        return app

    def test_inbound_msg_logged_in_local_stage(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """STAGE=local must emit a MSG -->| line for inbound requests."""
        monkeypatch.setenv("STAGE", "local")
        app = self._make_app(200)
        client = TestClient(app, raise_server_exceptions=False)
        with caplog.at_level(logging.INFO, logger="vistarae_core.middleware.telemetry"):
            client.get("/ping", headers={"X-Source": "extension", "X-Destination": "gateway"})
        assert any("MSG -->|" in record.message for record in caplog.records)

    def test_success_outbound_msg_logged(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Successful 2XX response should emit MSG <--| log line."""
        monkeypatch.setenv("STAGE", "local")
        app = self._make_app(200)
        client = TestClient(app, raise_server_exceptions=False)
        with caplog.at_level(logging.INFO, logger="vistarae_core.middleware.telemetry"):
            client.get("/ping")
        assert any("MSG <--|" in record.message for record in caplog.records)

    def test_error_outbound_msg_logged(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """4XX/5XX response should emit MSG <~~| log line."""
        monkeypatch.setenv("STAGE", "local")
        app = self._make_app(404)
        client = TestClient(app, raise_server_exceptions=False)
        with caplog.at_level(logging.WARNING, logger="vistarae_core.middleware.telemetry"):
            client.get("/ping")
        assert any("MSG <~~|" in record.message for record in caplog.records)

    def test_no_msg_logs_in_cloud_stage(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """STAGE=cloud must not emit any MSG directional log lines."""
        monkeypatch.setenv("STAGE", "cloud")
        app = self._make_app(200)
        client = TestClient(app, raise_server_exceptions=False)
        with caplog.at_level(logging.DEBUG, logger="vistarae_core.middleware.telemetry"):
            client.get("/ping")
        assert not any("MSG" in record.message for record in caplog.records)
