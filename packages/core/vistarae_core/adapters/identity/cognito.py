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

"""AWS Cognito identity provider adapter.

Implements the IIdentityProvider port using Boto3 CognitoIdentityProvider
for production JWT verification via JWKS and AdminDeleteUser for GDPR deletion.

Constitution Principle 2: All boto3 imports are confined to this adapter.
No Cognito imports appear in domain logic or port interfaces.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3
import jwt
import requests

logger = logging.getLogger(__name__)

_JWKS_CACHE: dict[str, Any] = {}


class CognitoIdentityProvider:
    """AWS Cognito adapter for JWKS token validation and account deletion."""

    def __init__(
        self,
        user_pool_id: str | None = None,
        client_id: str | None = None,
        region: str | None = None,
        validate_config: bool = True,
    ) -> None:
        """Initializes the Cognito adapter from environment or explicit parameters.

        Fast-fails early if required Cognito provisioning information is missing
        when STAGE is not 'local'.

        Args:
            user_pool_id: AWS Cognito User Pool ID (defaults to COGNITO_USER_POOL_ID env var).
            client_id: Cognito App Client ID (defaults to COGNITO_CLIENT_ID env var).
            region: AWS region (defaults to AWS_REGION env var or 'us-east-1').
            validate_config: Whether to enforce provisioning checks for non-local stages.

        Raises:
            RuntimeError: If STAGE is not 'local' and user_pool_id or client_id is missing.
        """
        self._user_pool_id = user_pool_id or os.environ.get("COGNITO_USER_POOL_ID", "")
        self._client_id = client_id or os.environ.get("COGNITO_CLIENT_ID", "")
        self._region = region or os.environ.get("AWS_REGION", "us-east-1")

        stage = os.environ.get("STAGE", os.environ.get("APP_ENV", "local")).lower()
        if validate_config and stage in ("staging", "prod", "production"):
            missing: list[str] = []
            if not self._user_pool_id:
                missing.append("COGNITO_USER_POOL_ID")
            if not self._client_id:
                missing.append("COGNITO_CLIENT_ID")
            if missing:
                raise RuntimeError(
                    f"Fast-fail startup error: Cognito configuration missing {', '.join(missing)} "
                    f"for STAGE='{stage}'. Ensure these environment variables are provisioned."
                )

        self._jwks_url = (
            f"https://cognito-idp.{self._region}.amazonaws.com/"
            f"{self._user_pool_id}/.well-known/jwks.json"
        )
        self._client = boto3.client("cognito-idp", region_name=self._region)

    def _get_jwks(self) -> dict[str, Any]:
        """Fetches and caches the JWKS public key set.

        Returns:
            Parsed JWKS JSON dict with 'keys' array.
        """
        if self._jwks_url not in _JWKS_CACHE:
            response = requests.get(self._jwks_url, timeout=5)
            response.raise_for_status()
            _JWKS_CACHE[self._jwks_url] = response.json()
        return _JWKS_CACHE[self._jwks_url]

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Validates a Cognito JWT and returns decoded claims.

        Args:
            token: Raw Bearer JWT string.

        Returns:
            Decoded JWT claims dict containing 'sub', 'email', and group claims.

        Raises:
            ValueError: If the token is invalid, expired, or the key is not found.
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as exc:
            raise ValueError(f"Malformed JWT header: {exc}") from exc

        jwks = self._get_jwks()
        key_data = next(
            (k for k in jwks.get("keys", []) if k.get("kid") == unverified_header.get("kid")),
            None,
        )
        if key_data is None:
            raise ValueError("JWT signing key not found in JWKS endpoint.")

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self._client_id,
                options={"verify_exp": True},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ValueError("JWT has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise ValueError(f"Invalid JWT: {exc}") from exc

        logger.debug(
            "MSG |-> [cognito.py -> Cognito JWKS] Verified token for sub=%s",
            claims.get("sub"),
        )
        return claims

    async def delete_user(self, cognito_sub: str) -> None:
        """Permanently removes a user from the Cognito User Pool.

        Args:
            cognito_sub: Unique Cognito subject identifier.

        Raises:
            RuntimeError: If the AdminDeleteUser API call fails.
        """
        try:
            self._client.admin_delete_user(
                UserPoolId=self._user_pool_id,
                Username=cognito_sub,
            )
            logger.info(
                "MSG |-> [cognito.py -> Cognito API] AdminDeleteUser cognito_sub=%s",
                cognito_sub,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to delete Cognito user {cognito_sub}: {exc}") from exc

    async def sign_up(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        """Registers a new user in the AWS Cognito User Pool.

        Args:
            email: User's email address.
            password: User's password.
            full_name: Optional full name attribute.

        Returns:
            Dict with user_sub and user_confirmed boolean.

        Raises:
            ValueError: If user already exists or inputs fail validation.
            RuntimeError: If Cognito API call fails.
        """
        user_attrs = [{"Name": "email", "Value": email}]
        if full_name:
            user_attrs.append({"Name": "name", "Value": full_name})

        try:
            resp = self._client.sign_up(
                ClientId=self._client_id,
                Username=email,
                Password=password,
                UserAttributes=user_attrs,
            )
            logger.info("MSG |-> [cognito.py -> Cognito API] SignUp email=%s", email)
            return {
                "user_sub": resp["UserSub"],
                "user_confirmed": resp.get("UserConfirmed", False),
            }
        except getattr(self._client.exceptions, "UsernameExistsException", Exception) as exc:
            raise ValueError(f"User with email '{email}' already exists.") from exc
        except getattr(self._client.exceptions, "InvalidPasswordException", Exception) as exc:
            raise ValueError(f"Password does not meet requirements: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Cognito SignUp failed: {exc}") from exc

    async def confirm_sign_up(self, email: str, confirmation_code: str) -> bool:
        """Confirms user signup using the verification code.

        Args:
            email: Registered email address.
            confirmation_code: Verification code.

        Returns:
            True if confirmation was successful.

        Raises:
            ValueError: If code is invalid or expired.
            RuntimeError: If Cognito API call fails.
        """
        try:
            self._client.confirm_sign_up(
                ClientId=self._client_id,
                Username=email,
                ConfirmationCode=confirmation_code,
            )
            logger.info("MSG |-> [cognito.py -> Cognito API] ConfirmSignUp email=%s", email)
            return True
        except (
            getattr(self._client.exceptions, "CodeMismatchException", Exception),
            getattr(self._client.exceptions, "ExpiredCodeException", Exception),
        ) as exc:
            raise ValueError(f"Invalid or expired verification code: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Cognito ConfirmSignUp failed: {exc}") from exc

    async def initiate_auth(self, email: str, password: str) -> dict[str, Any]:
        """Authenticates user with USER_PASSWORD_AUTH and returns JWT tokens.

        Args:
            email: User email.
            password: User password.

        Returns:
            Dict containing access_token, id_token, refresh_token, token_type, expires_in.

        Raises:
            ValueError: If credentials are invalid or user not confirmed.
            RuntimeError: If authentication call fails.
        """
        try:
            resp = self._client.initiate_auth(
                ClientId=self._client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": email, "PASSWORD": password},
            )
            result = resp.get("AuthenticationResult", {})
            logger.info("MSG |-> [cognito.py -> Cognito API] InitiateAuth email=%s", email)
            return {
                "access_token": result.get("AccessToken", ""),
                "id_token": result.get("IdToken", ""),
                "refresh_token": result.get("RefreshToken"),
                "token_type": result.get("TokenType", "Bearer"),
                "expires_in": result.get("ExpiresIn", 3600),
            }
        except (
            getattr(self._client.exceptions, "NotAuthorizedException", Exception),
            getattr(self._client.exceptions, "UserNotFoundException", Exception),
        ) as exc:
            raise ValueError("Invalid email or password.") from exc
        except getattr(self._client.exceptions, "UserNotConfirmedException", Exception) as exc:
            raise ValueError(
                "User account is not yet confirmed. Please verify your email."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Cognito InitiateAuth failed: {exc}") from exc

    async def forgot_password(self, email: str) -> dict[str, Any]:
        """Initiates password reset code dispatch.

        Args:
            email: Account email address.

        Returns:
            Dict with delivery details.

        Raises:
            ValueError: If user not found.
            RuntimeError: If Cognito API call fails.
        """
        try:
            resp = self._client.forgot_password(
                ClientId=self._client_id,
                Username=email,
            )
            logger.info("MSG |-> [cognito.py -> Cognito API] ForgotPassword email=%s", email)
            return resp.get("CodeDeliveryDetails", {})
        except getattr(self._client.exceptions, "UserNotFoundException", Exception) as exc:
            raise ValueError(f"User with email '{email}' not found.") from exc
        except Exception as exc:
            raise RuntimeError(f"Cognito ForgotPassword failed: {exc}") from exc

    async def confirm_forgot_password(
        self,
        email: str,
        confirmation_code: str,
        new_password: str,
    ) -> bool:
        """Confirms password reset with received code and new password.

        Args:
            email: Account email.
            confirmation_code: Verification code.
            new_password: New password.

        Returns:
            True if reset succeeded.

        Raises:
            ValueError: If code is invalid or password doesn't meet requirements.
            RuntimeError: If Cognito API call fails.
        """
        try:
            self._client.confirm_forgot_password(
                ClientId=self._client_id,
                Username=email,
                ConfirmationCode=confirmation_code,
                Password=new_password,
            )
            logger.info("MSG |-> [cognito.py -> Cognito API] ConfirmForgotPassword email=%s", email)
            return True
        except (
            getattr(self._client.exceptions, "CodeMismatchException", Exception),
            getattr(self._client.exceptions, "ExpiredCodeException", Exception),
        ) as exc:
            raise ValueError(f"Invalid or expired reset code: {exc}") from exc
        except getattr(self._client.exceptions, "InvalidPasswordException", Exception) as exc:
            raise ValueError(f"Password does not meet requirements: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Cognito ConfirmForgotPassword failed: {exc}") from exc

    async def global_sign_out(self, access_token: str) -> bool:
        """Invalidates all sessions for the token's user.

        Args:
            access_token: Valid access token.

        Returns:
            True if logout succeeded.

        Raises:
            ValueError: If access token is invalid.
            RuntimeError: If Cognito API call fails.
        """
        try:
            self._client.global_sign_out(AccessToken=access_token)
            logger.info("MSG |-> [cognito.py -> Cognito API] GlobalSignOut")
            return True
        except getattr(self._client.exceptions, "NotAuthorizedException", Exception) as exc:
            raise ValueError(f"Invalid or expired access token: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Cognito GlobalSignOut failed: {exc}") from exc
