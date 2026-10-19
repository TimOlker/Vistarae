# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Admin platform control route handlers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from vistarae_core.domain.entities import User
from vistarae_core.schemas.admin import (
    AdminMessageRequest,
    QuotaDefaultsRequest,
    QuotaDefaultsResponse,
)

from services.admin.dependencies import require_admin

router = APIRouter()

# Module-level mutable state for runtime toggles (not persisted across restarts).
_quota_defaults: dict[str, object] = {
    "default_token_quota": 50000,
    "default_tier": "low",
}
_trace_injection_enabled: bool = False


@router.put("/quotas/defaults", response_model=QuotaDefaultsResponse)
async def update_quota_defaults(
    body: QuotaDefaultsRequest,
    _admin: User = Depends(require_admin),
) -> QuotaDefaultsResponse:
    """Updates the system-wide default token quota and tier for new tenants.

    Args:
        body: QuotaDefaultsRequest with new default values.
        _admin: Admin caller (RBAC enforced).

    Returns:
        QuotaDefaultsResponse confirming the applied defaults.
    """
    global _quota_defaults  # noqa: PLW0603
    _quota_defaults = {
        "default_token_quota": body.default_token_quota,
        "default_tier": str(body.default_tier),
    }
    return QuotaDefaultsResponse(
        default_token_quota=body.default_token_quota,
        default_tier=str(body.default_tier),
    )


@router.post("/trace-injection/toggle", status_code=status.HTTP_200_OK)
async def toggle_trace_injection(
    _admin: User = Depends(require_admin),
) -> dict[str, bool]:
    """Toggles the global admin trace injection override.

    Args:
        _admin: Admin caller (RBAC enforced).

    Returns:
        Dict with 'trace_injection_enabled' boolean reflecting the new state.
    """
    global _trace_injection_enabled  # noqa: PLW0603
    _trace_injection_enabled = not _trace_injection_enabled
    return {"trace_injection_enabled": _trace_injection_enabled}


@router.post("/users/{user_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def send_admin_message(
    user_id: str,
    body: AdminMessageRequest,
    _admin: User = Depends(require_admin),
) -> dict[str, str]:
    """Dispatches an administrative notification message to a specific tenant.

    Args:
        user_id: UUID string of the target tenant.
        body: AdminMessageRequest with title and message.
        _admin: Admin caller (RBAC enforced).

    Returns:
        Acknowledgement dict with status and user_id.
    """
    # In production this would enqueue via IMessageQueue to SQS.
    # For the current phase, returns a 202 Accepted stub.
    return {
        "status": "accepted",
        "user_id": user_id,
        "message": f"Administrative message '{body.title}' queued for delivery.",
    }
