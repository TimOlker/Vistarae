"""OpenTelemetry W3C Distributed Tracing Middleware & Logging."""

import logging
import os
import re
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("vistarae.telemetry")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Setup Tracer Provider
if not isinstance(trace.get_tracer_provider(), TracerProvider):
    provider = TracerProvider()
    if os.getenv("APP_ENV") == "testing":
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        provider.add_span_processor(BatchSpanProcessor(InMemorySpanExporter()))
    else:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
            )
        except Exception:
            # Fallback to console span processor
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer("vistarae-backend")
propagator = TraceContextTextMapPropagator()

# Messaging Tags
TAG_INBOUND_MSG = "->|  "
TAG_RESPONSE_MSG = "<-|  "
TAG_INBOUND_RESPONSE_ERR_MSG = "<X|  "
TAG_OUTBOUND_MSG = "  |->"
TAG_OUTBOUND_RESP = "  |<-"


def log_msg(tag: str, detail: str) -> None:
    """Logs message with standardized MSG {TAG} prefix."""
    logger.info(f"MSG {tag}{detail}")


def generate_trace_id() -> str:
    """Generates a standard 32-hex-character W3C trace ID."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generates a standard 16-hex-character W3C span ID."""
    return secrets.token_hex(8)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware to extract W3C Traceparent, create server span, and inject response headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        traceparent = request.headers.get("traceparent")
        raw_source = request.headers.get("x-source", "unknown-source")
        raw_destination = request.headers.get("x-destination", str(request.url))
        source = raw_source.split(",")[0].strip() if raw_source else "unknown-source"
        destination = raw_destination.split(",")[0].strip() if raw_destination else str(request.url)

        trace_id = None
        parent_span_id = None
        current_span_id = generate_span_id()

        # Parse W3C traceparent: 00-{trace_id}-{parent_span_id}-{flags}
        if traceparent:
            match = re.match(r"^00-([a-f0-9]{32})-([a-f0-9]{16})-[a-f0-9]{2}$", traceparent.strip())
            if match:
                trace_id = match.group(1)
                parent_span_id = match.group(2)

        parent_id_tag = ""
        if not trace_id:
            trace_id = generate_trace_id()
            parent_span_id = "0000000000000000"
        else:
            parent_id_tag = f"ParentID={parent_span_id} | "

        # Log incoming request using required format
        log_detail = (
            f"TraceID={trace_id} | {parent_id_tag}"
            f"SpanID={current_span_id} | Src={source} -> Dst={destination} | "
            f"Method={request.method} Path={request.url.path}"
        )
        log_msg(TAG_INBOUND_MSG, log_detail)

        # Store IDs in request state
        request.state.trace_id = trace_id
        request.state.span_id = current_span_id
        request.state.parent_span_id = parent_span_id

        # Extract OTel context if available
        carrier = {"traceparent": traceparent} if traceparent else {}
        extracted_context = propagator.extract(carrier=carrier)

        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            context=extracted_context,
            kind=SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.source": source,
                "http.destination": destination,
                "vistarae.trace_id": trace_id,
                "vistarae.span_id": current_span_id,
                "vistarae.parent_span_id": parent_span_id,
            },
        ) as span:
            try:
                response = await call_next(request)

                # Attach correlation and cache-control headers to response
                response.headers["X-Transaction-ID"] = trace_id
                response.headers["X-Current-Span-ID"] = current_span_id
                response.headers["X-Parent-Transaction-ID"] = parent_span_id
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

                rsp_log_detail = (
                    f"TraceID={trace_id} | {parent_id_tag}"
                    f"SpanID={current_span_id} | Src={destination} -> Dst={source} | "
                    f"Method={request.method} Path={request.url.path}"
                    f"Status={response.status_code}"
                )
                log_msg(TAG_RESPONSE_MSG, rsp_log_detail)
                return response
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                rsp_log_detail = (
                    f"TraceID={trace_id} | {parent_id_tag}"
                    f"SpanID={current_span_id} | Src={destination} -> Dst={source} | "
                    f"Method={request.method} Path={request.url.path}"
                    f"Error={exc!s}"
                )
                log_msg(TAG_INBOUND_RESPONSE_ERR_MSG, rsp_log_detail)
                raise


@asynccontextmanager
async def egress_span(destination_name: str, url: str, action: str = "request"):
    """Context manager for tracing and logging outbound external requests (Gemini, Nominatim)."""
    child_span_id = generate_span_id()
    log_msg(
        TAG_OUTBOUND_MSG,
        f"EGRESS | Target={destination_name} | Action={action} | Destination={url} | SpanID={child_span_id}",
    )

    with tracer.start_as_current_span(
        f"Egress {destination_name}",
        kind=SpanKind.CLIENT,
        attributes={
            "http.destination": url,
            "peer.service": destination_name,
            "egress.action": action,
        },
    ) as span:
        try:
            yield span
            log_msg(
                TAG_OUTBOUND_RESP,
                f"EGRESS COMPLETE | Target={destination_name} | Destination={url} | SpanID={child_span_id}",
            )
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            log_msg(
                TAG_OUTBOUND_RESP,
                f"EGRESS ERROR | Target={destination_name} | Destination={url} | Error={exc!s}",
            )
            raise
