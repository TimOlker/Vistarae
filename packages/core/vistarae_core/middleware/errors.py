# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RFC 7807 / RFC 9457 FastAPI exception handlers.

Formats all non-2XX responses as application/problem+json per Constitution
Principle 5. Registers handlers for common exception types including
RequestValidationError, HTTPException, and domain-specific errors.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from vistarae_core.domain.exceptions import (
    AccountDisabledError,
    IdempotencyConflictError,
    QuotaExceededError,
    TenantNotFoundError,
)
from vistarae_core.schemas.errors import InvalidParam, ProblemDetails

logger = logging.getLogger(__name__)

_MEDIA_TYPE = "application/problem+json"


def _problem_response(problem: ProblemDetails) -> JSONResponse:
    """Serializes a ProblemDetails model to an application/problem+json response.

    Args:
        problem: Populated ProblemDetails model.

    Returns:
        JSONResponse with correct media type and HTTP status.
    """
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=_MEDIA_TYPE,
    )


def add_problem_details_handlers(app: FastAPI) -> None:
    """Registers all RFC 7807 exception handlers on the given FastAPI app.

    Args:
        app: FastAPI application instance to register handlers on.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Converts Pydantic RequestValidationError → 422 ProblemDetails.

        Args:
            request: Incoming HTTP request context.
            exc: Pydantic validation error with field-level details.

        Returns:
            RFC 7807 application/problem+json response.
        """
        invalid_params = [
            InvalidParam(
                name=".".join(str(loc) for loc in e["loc"]),
                reason=e["msg"],
            )
            for e in exc.errors()
        ]
        return _problem_response(
            ProblemDetails(
                type="https://errors.vistarae.com/validation-error",
                title="Validation Error",
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="One or more request fields failed validation.",
                instance=str(request.url),
                invalid_params=invalid_params,
            )
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Converts HTTPException → ProblemDetails with appropriate status.

        Args:
            request: Incoming HTTP request context.
            exc: Starlette HTTPException with status code and detail.

        Returns:
            RFC 7807 application/problem+json response.
        """
        return _problem_response(
            ProblemDetails(
                type=f"https://errors.vistarae.com/http-{exc.status_code}",
                title=str(exc.detail) if exc.detail else "HTTP Error",
                status=exc.status_code,
                detail=str(exc.detail) if exc.detail else "An HTTP error occurred.",
                instance=str(request.url),
            )
        )

    @app.exception_handler(AccountDisabledError)
    async def account_disabled_handler(
        request: Request, exc: AccountDisabledError
    ) -> JSONResponse:
        """Converts AccountDisabledError → 403 Forbidden ProblemDetails.

        Args:
            request: Incoming HTTP request context.
            exc: Domain error for disabled accounts.

        Returns:
            RFC 7807 application/problem+json 403 response.
        """
        return _problem_response(
            ProblemDetails(
                type="https://errors.vistarae.com/account-disabled",
                title="Account Disabled",
                status=status.HTTP_403_FORBIDDEN,
                detail=exc.message,
                instance=str(request.url),
            )
        )

    @app.exception_handler(TenantNotFoundError)
    async def tenant_not_found_handler(
        request: Request, exc: TenantNotFoundError
    ) -> JSONResponse:
        """Converts TenantNotFoundError → 401 Unauthorized ProblemDetails.

        Args:
            request: Incoming HTTP request context.
            exc: Domain error for missing tenant identity.

        Returns:
            RFC 7807 application/problem+json 401 response.
        """
        return _problem_response(
            ProblemDetails(
                type="https://errors.vistarae.com/user-not-found",
                title="User Not Found",
                status=status.HTTP_401_UNAUTHORIZED,
                detail=exc.message,
                instance=str(request.url),
            )
        )

    @app.exception_handler(QuotaExceededError)
    async def quota_exceeded_handler(
        request: Request, exc: QuotaExceededError
    ) -> JSONResponse:
        """Converts QuotaExceededError → 429 Too Many Requests ProblemDetails.

        Args:
            request: Incoming HTTP request context.
            exc: Domain error carrying optional retry_after hint.

        Returns:
            RFC 7807 application/problem+json 429 response with optional Retry-After.
        """
        problem = ProblemDetails(
            type="https://errors.vistarae.com/quota-exceeded",
            title="Quota Exceeded",
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.message,
            instance=str(request.url),
        )
        response = _problem_response(problem)
        if exc.retry_after is not None:
            response.headers["Retry-After"] = str(exc.retry_after)
        return response

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict_handler(
        request: Request, exc: IdempotencyConflictError
    ) -> JSONResponse:
        """Converts IdempotencyConflictError → 409 Conflict ProblemDetails.

        Args:
            request: Incoming HTTP request context.
            exc: Domain error for concurrent key collision.

        Returns:
            RFC 7807 application/problem+json 409 response.
        """
        return _problem_response(
            ProblemDetails(
                type="https://errors.vistarae.com/idempotency-conflict",
                title="Idempotency Conflict",
                status=status.HTTP_409_CONFLICT,
                detail=exc.message,
                instance=str(request.url),
            )
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catches unhandled exceptions and returns a 500 ProblemDetails response.

        Args:
            request: Incoming HTTP request context.
            exc: Unhandled exception.

        Returns:
            RFC 7807 application/problem+json 500 response.
        """
        logger.exception("Unhandled exception on %s: %s", request.url, exc)
        return _problem_response(
            ProblemDetails(
                type="https://errors.vistarae.com/internal-error",
                title="Internal Server Error",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred. Please try again later.",
                instance=str(request.url),
            )
        )
