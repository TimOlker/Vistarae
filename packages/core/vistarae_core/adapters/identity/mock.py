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

"""Local mock identity provider for stage-aware bypass.

When STAGE == 'local', the X-Mock-User-Id header substitutes for JWT
authentication, enabling rapid development without a live Cognito pool.

Constitution Principle 2: Zero boto3/Cognito imports here.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class MockIdentityProvider:
    """Stage-aware local authentication bypass.

    Accepts X-Mock-User-Id and X-Mock-User-Tier headers in place of a real JWT
    so developers can exercise all API paths without AWS credentials.
    """

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Parses the mock token as a UUID and returns synthetic claims.

        The mock 'token' can be a raw UUID string or prefixed with
        'mock-access-token-', 'mock-id-token-', or 'mock-'.

        Args:
            token: UUID or mock bearer token string.

        Returns:
            Synthetic claims dict with 'sub' and 'email' populated from the UUID.

        Raises:
            ValueError: If the token is not a valid UUID format.
        """
        raw = token.strip()
        if raw.startswith("Bearer "):
            raw = raw.removeprefix("Bearer ").strip()
        if raw.startswith("mock-access-token-"):
            raw = raw.removeprefix("mock-access-token-")
        elif raw.startswith("mock-id-token-"):
            raw = raw.removeprefix("mock-id-token-")
        elif raw.startswith("mock-token-"):
            raw = raw.removeprefix("mock-token-")
        elif raw.startswith("mock-"):
            raw = raw.removeprefix("mock-")

        try:
            user_uuid = UUID(raw)
        except ValueError:
            import uuid

            user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, raw)

        logger.debug("MSG -->| [mock.py -> local] Mock auth bypass for user_id=%s", user_uuid)

        return {
            "sub": str(user_uuid),
            "email": f"mock-{user_uuid}@local.vistarae.dev",
            "cognito:groups": [],
        }

    async def delete_user(self, cognito_sub: str) -> None:
        """No-op deletion for the local mock provider.

        Args:
            cognito_sub: Ignored — local mock accounts have no external representation.
        """
        logger.info(
            "MSG -->| [mock.py -> local] Mock delete_user called for sub=%s (no-op)",
            cognito_sub,
        )

    async def sign_up(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        """Mock user registration returning deterministic UUID subject.

        Args:
            email: User email.
            password: User password.
            full_name: Optional full name.

        Returns:
            Dict containing user_sub and user_confirmed=False.
        """
        import uuid

        user_sub = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
        logger.info(
            "MSG -->| [mock.py -> local] Mock sign_up for email=%s, sub=%s", email, user_sub
        )
        return {
            "user_sub": user_sub,
            "user_confirmed": False,
        }

    async def confirm_sign_up(self, email: str, confirmation_code: str) -> bool:
        """Mock account confirmation.

        Args:
            email: User email.
            confirmation_code: Verification code (any code accepted in mock mode).

        Returns:
            True always in mock mode.
        """
        logger.info("MSG -->| [mock.py -> local] Mock confirm_sign_up for email=%s", email)
        return True

    async def initiate_auth(self, email: str, password: str) -> dict[str, Any]:
        """Mock authentication returning synthetic JWT bearer tokens.

        Args:
            email: User email.
            password: User password.

        Returns:
            Dict containing mock access_token, id_token, and refresh_token.
        """
        import uuid

        user_sub = str(uuid.uuid5(uuid.NAMESPACE_DNS, email))
        logger.info("MSG -->| [mock.py -> local] Mock initiate_auth for email=%s", email)
        return {
            "access_token": f"mock-access-token-{user_sub}",
            "id_token": f"mock-id-token-{user_sub}",
            "refresh_token": f"mock-refresh-token-{user_sub}",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    async def forgot_password(self, email: str) -> dict[str, Any]:
        """Mock forgot password request.

        Args:
            email: Registered email.

        Returns:
            Dict with delivery medium details.
        """
        logger.info("MSG -->| [mock.py -> local] Mock forgot_password for email=%s", email)
        return {"DeliveryMedium": "EMAIL", "Destination": email}

    async def confirm_forgot_password(
        self,
        email: str,
        confirmation_code: str,
        new_password: str,
    ) -> bool:
        """Mock password reset confirmation.

        Args:
            email: Registered email.
            confirmation_code: Verification code.
            new_password: New password.

        Returns:
            True always in mock mode.
        """
        logger.info("MSG -->| [mock.py -> local] Mock confirm_forgot_password for email=%s", email)
        return True

    async def global_sign_out(self, access_token: str) -> bool:
        """Mock session revocation.

        Args:
            access_token: Access token to revoke.

        Returns:
            True always in mock mode.
        """
        logger.info("MSG -->| [mock.py -> local] Mock global_sign_out")
        return True
