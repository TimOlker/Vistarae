# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Identity provider port interface.

Abstracts AWS Cognito and local mock authentication providers behind a
typing.Protocol contract per Constitution Principle 2.
"""

from __future__ import annotations

from typing import Any, Protocol


class IIdentityProvider(Protocol):
    """Authentication and identity lifecycle contract."""

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Validates a bearer token and extracts claims.

        Args:
            token: Raw JWT bearer string from Authorization header.

        Returns:
            Decoded claims dict containing at minimum 'sub' (subject) field.

        Raises:
            ValueError: If the token is invalid, expired, or structurally malformed.
        """
        ...

    async def delete_user(self, cognito_sub: str) -> None:
        """Permanently removes a user account from the identity provider.

        Args:
            cognito_sub: Unique Cognito subject identifier of the user to delete.

        Raises:
            RuntimeError: If the deletion call to the identity provider fails.
        """
        ...

    async def sign_up(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        """Registers a new user in the identity provider.

        Args:
            email: User email address.
            password: User password.
            full_name: Optional full name attribute.

        Returns:
            Dict containing 'user_sub' and 'user_confirmed' boolean.

        Raises:
            ValueError: If registration input is invalid or user already exists.
            RuntimeError: If identity provider call fails.
        """
        ...

    async def confirm_sign_up(self, email: str, confirmation_code: str) -> bool:
        """Confirms user signup with a verification code.

        Args:
            email: Registered email address.
            confirmation_code: Verification code received by email.

        Returns:
            True if confirmation succeeded.

        Raises:
            ValueError: If the verification code is invalid or expired.
            RuntimeError: If confirmation call fails.
        """
        ...

    async def initiate_auth(self, email: str, password: str) -> dict[str, Any]:
        """Authenticates user credentials and returns tokens.

        Args:
            email: Account email.
            password: Account password.

        Returns:
            Dict containing access_token, id_token, and optional refresh_token.

        Raises:
            ValueError: If authentication fails due to invalid credentials.
            RuntimeError: If identity provider call fails.
        """
        ...

    async def forgot_password(self, email: str) -> dict[str, Any]:
        """Initiates a password reset code dispatch.

        Args:
            email: Registered account email.

        Returns:
            Dict containing delivery details.

        Raises:
            ValueError: If user is not found.
            RuntimeError: If dispatch fails.
        """
        ...

    async def confirm_forgot_password(
        self,
        email: str,
        confirmation_code: str,
        new_password: str,
    ) -> bool:
        """Confirms password reset with code and new password.

        Args:
            email: Registered account email.
            confirmation_code: Received reset code.
            new_password: New password to set.

        Returns:
            True if reset succeeded.

        Raises:
            ValueError: If code is invalid or password policy fails.
            RuntimeError: If reset call fails.
        """
        ...

    async def global_sign_out(self, access_token: str) -> bool:
        """Revokes all active sessions for the user.

        Args:
            access_token: Valid access token of the session.

        Returns:
            True if revocation succeeded.

        Raises:
            ValueError: If token is invalid.
            RuntimeError: If revocation call fails.
        """
        ...

