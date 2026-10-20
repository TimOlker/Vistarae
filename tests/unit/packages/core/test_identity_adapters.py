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

"""Unit tests for AWS Cognito adapter and local mock provider (T-016).

Tests cover:
- CognitoIdentityProvider initialization and environment overrides
- JWKS retrieval, caching, and key matching
- Valid RS256 token verification
- Malformed header, missing kid, expired token, and invalid token errors
- AdminDeleteUser invocation and failure handling
- MockIdentityProvider UUID verification and no-op deletion
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from vistarae_core.adapters.identity.cognito import _JWKS_CACHE, CognitoIdentityProvider
from vistarae_core.adapters.identity.mock import MockIdentityProvider


@pytest.fixture
def rsa_key_pair() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    """Generates an ephemeral RSA private key and matching JWK representation."""
    import json

    from jwt.algorithms import RSAAlgorithm

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk_raw = RSAAlgorithm.to_jwk(public_key)
    jwk_dict = json.loads(jwk_raw) if isinstance(jwk_raw, str) else dict(jwk_raw)
    jwk_dict["kid"] = "test-kid-123"
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    return private_key, jwk_dict


class TestCognitoIdentityProvider:
    """Unit tests for CognitoIdentityProvider."""

    def test_init_from_params_and_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Asserts parameters override environment variables correctly."""
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-env")
        monkeypatch.setenv("COGNITO_CLIENT_ID", "client-env")
        monkeypatch.setenv("AWS_REGION", "eu-central-1")

        with patch("boto3.client"):
            provider = CognitoIdentityProvider()
            assert provider._user_pool_id == "pool-env"
            assert provider._client_id == "client-env"
            assert provider._region == "eu-central-1"

            explicit = CognitoIdentityProvider(
                user_pool_id="pool-exp", client_id="client-exp", region="us-west-2"
            )
            assert explicit._user_pool_id == "pool-exp"
            assert explicit._client_id == "client-exp"
            assert explicit._region == "us-west-2"

    def test_init_fast_fail_in_production_missing_pool_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asserts initialization raises RuntimeError when COGNITO_USER_POOL_ID is missing in production."""
        monkeypatch.setenv("STAGE", "production")
        monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
        monkeypatch.setenv("COGNITO_CLIENT_ID", "client-123")

        with patch("boto3.client"), pytest.raises(
            RuntimeError, match="Fast-fail startup error: Cognito configuration missing COGNITO_USER_POOL_ID"
        ):
            CognitoIdentityProvider()

    def test_init_fast_fail_in_staging_missing_client_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asserts initialization raises RuntimeError when COGNITO_CLIENT_ID is missing in staging."""
        monkeypatch.setenv("STAGE", "staging")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
        monkeypatch.delenv("COGNITO_CLIENT_ID", raising=False)

        with patch("boto3.client"), pytest.raises(
            RuntimeError, match="Fast-fail startup error: Cognito configuration missing COGNITO_CLIENT_ID"
        ):
            CognitoIdentityProvider()

    def test_init_success_in_production_with_valid_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asserts initialization succeeds in production when both required parameters are provided."""
        monkeypatch.setenv("STAGE", "production")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_abcdef123")
        monkeypatch.setenv("COGNITO_CLIENT_ID", "appclient123456")

        with patch("boto3.client"):
            provider = CognitoIdentityProvider()
            assert provider._user_pool_id == "us-east-1_abcdef123"
            assert provider._client_id == "appclient123456"

    def test_get_jwks_caching(self) -> None:
        """Asserts JWKS is retrieved via requests.get and cached."""
        _JWKS_CACHE.clear()
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [{"kid": "k1"}]}

        with patch("boto3.client"), patch("requests.get", return_value=mock_response) as mock_get:
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            jwks1 = provider._get_jwks()
            jwks2 = provider._get_jwks()

            assert jwks1 == {"keys": [{"kid": "k1"}]}
            assert jwks2 == jwks1
            assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_verify_token_malformed_header(self) -> None:
        """Asserts DecodeError in unverified header raises ValueError."""
        with patch("boto3.client"):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            with pytest.raises(ValueError, match="Malformed JWT header"):
                await provider.verify_token("invalid.token.format")

    @pytest.mark.asyncio
    async def test_verify_token_key_not_in_jwks(self) -> None:
        """Asserts ValueError if token kid doesn't match JWKS."""
        _JWKS_CACHE.clear()
        token = jwt.encode(
            {"sub": "user-1"},
            "this-is-a-very-long-secret-key-32b!",
            algorithm="HS256",
            headers={"kid": "unknown-kid"},
        )

        with (
            patch("boto3.client"),
            patch.object(
                CognitoIdentityProvider,
                "_get_jwks",
                return_value={"keys": [{"kid": "different-kid"}]},
            ),
        ):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            with pytest.raises(ValueError, match="JWT signing key not found"):
                await provider.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_valid(
        self, rsa_key_pair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
    ) -> None:
        """Asserts valid RS256 token is decoded with expected claims."""
        private_key, jwk_dict = rsa_key_pair
        payload = {
            "sub": "user-sub-1234",
            "email": "user@example.com",
            "aud": "client-1",
            "exp": 9999999999,
        }
        token = jwt.encode(
            payload,
            private_key,
            algorithm="RS256",
            headers={"kid": "test-kid-123"},
        )

        with (
            patch("boto3.client"),
            patch.object(CognitoIdentityProvider, "_get_jwks", return_value={"keys": [jwk_dict]}),
        ):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            claims = await provider.verify_token(token)
            assert claims["sub"] == "user-sub-1234"
            assert claims["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_verify_token_expired(
        self, rsa_key_pair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
    ) -> None:
        """Asserts ExpiredSignatureError translates to ValueError."""
        private_key, jwk_dict = rsa_key_pair
        payload = {
            "sub": "user-sub-1234",
            "aud": "client-1",
            "exp": 1000000000,  # expired
        }
        token = jwt.encode(
            payload,
            private_key,
            algorithm="RS256",
            headers={"kid": "test-kid-123"},
        )

        with (
            patch("boto3.client"),
            patch.object(CognitoIdentityProvider, "_get_jwks", return_value={"keys": [jwk_dict]}),
        ):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            with pytest.raises(ValueError, match="JWT has expired"):
                await provider.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_invalid_audience(
        self, rsa_key_pair: tuple[rsa.RSAPrivateKey, dict[str, Any]]
    ) -> None:
        """Asserts InvalidTokenError (wrong audience) translates to ValueError."""
        private_key, jwk_dict = rsa_key_pair
        payload = {
            "sub": "user-sub-1234",
            "aud": "wrong-client",
            "exp": 9999999999,
        }
        token = jwt.encode(
            payload,
            private_key,
            algorithm="RS256",
            headers={"kid": "test-kid-123"},
        )

        with (
            patch("boto3.client"),
            patch.object(CognitoIdentityProvider, "_get_jwks", return_value={"keys": [jwk_dict]}),
        ):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            with pytest.raises(ValueError, match="Invalid JWT"):
                await provider.verify_token(token)

    @pytest.mark.asyncio
    async def test_delete_user_success(self) -> None:
        """Asserts admin_delete_user called on boto3 client."""
        mock_boto = MagicMock()
        with patch("boto3.client", return_value=mock_boto):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            await provider.delete_user("sub-123")
            mock_boto.admin_delete_user.assert_called_once_with(
                UserPoolId="pool-1", Username="sub-123"
            )

    @pytest.mark.asyncio
    async def test_delete_user_failure(self) -> None:
        """Asserts RuntimeError raised when boto3 admin_delete_user fails."""
        mock_boto = MagicMock()
        mock_boto.admin_delete_user.side_effect = Exception("Cognito unavailable")

        with patch("boto3.client", return_value=mock_boto):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")
            with pytest.raises(RuntimeError, match="Failed to delete Cognito user"):
                await provider.delete_user("sub-123")

    @pytest.mark.asyncio
    async def test_cognito_auth_lifecycle(self) -> None:
        """Asserts sign_up, confirm_sign_up, initiate_auth, forgot_password, confirm_forgot_password, global_sign_out."""
        mock_boto = MagicMock()
        mock_boto.sign_up.return_value = {"UserSub": "sub-123", "UserConfirmed": False}
        mock_boto.confirm_sign_up.return_value = {}
        mock_boto.initiate_auth.return_value = {
            "AuthenticationResult": {
                "AccessToken": "acc-token",
                "IdToken": "id-token",
                "RefreshToken": "ref-token",
                "TokenType": "Bearer",
                "ExpiresIn": 3600,
            }
        }
        mock_boto.forgot_password.return_value = {
            "CodeDeliveryDetails": {"DeliveryMedium": "EMAIL"}
        }
        mock_boto.confirm_forgot_password.return_value = {}
        mock_boto.global_sign_out.return_value = {}

        with patch("boto3.client", return_value=mock_boto):
            provider = CognitoIdentityProvider(user_pool_id="pool-1", client_id="client-1")

            # Sign Up
            signup_res = await provider.sign_up("user@example.com", "Password123!", "Full Name")
            assert signup_res["user_sub"] == "sub-123"
            assert signup_res["user_confirmed"] is False

            # Confirm Sign Up
            confirm_res = await provider.confirm_sign_up("user@example.com", "123456")
            assert confirm_res is True

            # Initiate Auth
            auth_res = await provider.initiate_auth("user@example.com", "Password123!")
            assert auth_res["access_token"] == "acc-token"
            assert auth_res["id_token"] == "id-token"

            # Forgot Password
            forgot_res = await provider.forgot_password("user@example.com")
            assert forgot_res["DeliveryMedium"] == "EMAIL"

            # Confirm Forgot Password
            reset_res = await provider.confirm_forgot_password(
                "user@example.com", "123456", "NewPassword123!"
            )
            assert reset_res is True

            # Global Sign Out
            logout_res = await provider.global_sign_out("acc-token")
            assert logout_res is True


class TestMockIdentityProvider:
    """Unit tests for MockIdentityProvider."""

    @pytest.mark.asyncio
    async def test_verify_token_valid_uuid(self) -> None:
        """Asserts valid UUID returns synthetic claims."""
        test_uuid = str(uuid.uuid4())
        provider = MockIdentityProvider()
        claims = await provider.verify_token(test_uuid)

        assert claims["sub"] == test_uuid
        assert claims["email"] == f"mock-{test_uuid}@local.vistarae.dev"
        assert claims["cognito:groups"] == []

    @pytest.mark.asyncio
    async def test_verify_token_invalid_uuid(self) -> None:
        """Asserts non-UUID string raises ValueError."""
        provider = MockIdentityProvider()
        with pytest.raises(ValueError, match="X-Mock-User-Id must be a valid UUID"):
            await provider.verify_token("not-a-valid-uuid")

    @pytest.mark.asyncio
    async def test_delete_user_noop(self) -> None:
        """Asserts delete_user completes cleanly without error."""
        provider = MockIdentityProvider()
        await provider.delete_user("any-sub")

    @pytest.mark.asyncio
    async def test_mock_auth_lifecycle(self) -> None:
        """Asserts mock provider auth methods return expected synthetic responses."""
        provider = MockIdentityProvider()

        signup_res = await provider.sign_up("mock@example.com", "Password123!")
        assert "user_sub" in signup_res
        assert signup_res["user_confirmed"] is False

        assert await provider.confirm_sign_up("mock@example.com", "123456") is True

        tokens = await provider.initiate_auth("mock@example.com", "Password123!")
        assert "access_token" in tokens
        assert "id_token" in tokens

        forgot_res = await provider.forgot_password("mock@example.com")
        assert forgot_res["Destination"] == "mock@example.com"

        assert (
            await provider.confirm_forgot_password("mock@example.com", "123456", "New123!") is True
        )
        assert await provider.global_sign_out("any-token") is True
