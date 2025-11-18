from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from relife_financial.auth.dependencies import (
    _get_authenticated_user,
    get_user_client,
)
from relife_financial.models.auth import (
    AuthenticatedUser,
    AuthenticationMethod,
    UniversalUser,
    UserIdentity,
)


@pytest.mark.asyncio
@patch("relife_financial.auth.dependencies._authenticate_with_supabase")
async def test_valid_supabase_token_authentication(mock_supabase_auth, mock_settings):
    """Test successful authentication using valid Supabase token."""

    universal_user = UniversalUser(
        id="supabase_user_123",
        email="user@example.com",
        identities=[UserIdentity(provider="supabase", id="supabase_user_123")],
    )

    expected_user = AuthenticatedUser(
        token="valid_supabase_token",
        user=universal_user,
        authentication_method=AuthenticationMethod.SUPABASE,
    )

    mock_supabase_auth.return_value = expected_user

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="valid_supabase_token"
    )

    result = await _get_authenticated_user(
        mock_settings, credentials, fetch_roles=False
    )

    assert result.user_id == "supabase_user_123"
    assert result.email == "user@example.com"
    assert not result.is_keycloak_provider
    mock_supabase_auth.assert_called_once()


@pytest.mark.asyncio
@patch("relife_financial.auth.dependencies._authenticate_with_keycloak")
@patch("relife_financial.auth.dependencies._authenticate_with_supabase")
async def test_valid_keycloak_token_authentication(
    mock_supabase_auth, mock_keycloak_auth, mock_settings
):
    """Test successful authentication using valid Keycloak token when Supabase fails."""

    mock_supabase_auth.side_effect = Exception("Supabase auth failed")

    universal_user = UniversalUser(
        id="keycloak_user_456",
        email="keycloak@example.com",
        user_metadata={
            "provider_id": "keycloak_user_456",
            "iss": "https://keycloak.test",
        },
        identities=[UserIdentity(provider="keycloak", id="keycloak_user_456")],
    )

    expected_user = AuthenticatedUser(
        token="valid_keycloak_token",
        user=universal_user,
        authentication_method=AuthenticationMethod.KEYCLOAK,
    )
    mock_keycloak_auth.return_value = expected_user

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="valid_keycloak_token"
    )

    result = await _get_authenticated_user(
        mock_settings, credentials, fetch_roles=False
    )

    assert result.user_id == "keycloak_user_456"
    assert result.email == "keycloak@example.com"
    assert result.is_keycloak_provider
    mock_supabase_auth.assert_called_once()
    mock_keycloak_auth.assert_called_once()


@pytest.mark.asyncio
@patch("relife_financial.auth.dependencies._authenticate_with_keycloak")
@patch("relife_financial.auth.dependencies._authenticate_with_supabase")
async def test_invalid_token_handling(
    mock_supabase_auth, mock_keycloak_auth, mock_settings
):
    """Test authentication failure when both Supabase and Keycloak tokens are invalid."""

    mock_supabase_auth.side_effect = Exception("Invalid Supabase token")
    mock_keycloak_auth.side_effect = Exception("Invalid Keycloak token")

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="invalid_token"
    )

    with pytest.raises(HTTPException) as exc_info:
        await _get_authenticated_user(mock_settings, credentials, fetch_roles=False)

    assert exc_info.value.status_code == 401

    mock_supabase_auth.assert_called_once()
    mock_keycloak_auth.assert_called_once()


@pytest.mark.asyncio
@patch("relife_financial.auth.dependencies._fetch_keycloak_roles")
@patch("relife_financial.auth.dependencies._authenticate_with_supabase")
async def test_fallback_authentication_flow_with_roles(
    mock_supabase_auth, mock_fetch_roles, mock_settings
):
    """Test fallback flow works correctly with role fetching enabled."""

    universal_user = UniversalUser(
        id="user_789",
        email="test@example.com",
        identities=[UserIdentity(provider="supabase", id="user_789")],
    )

    authenticated_user = AuthenticatedUser(
        token="test_token",
        user=universal_user,
        authentication_method=AuthenticationMethod.SUPABASE,
    )

    mock_supabase_auth.return_value = authenticated_user
    mock_fetch_roles.return_value = None  # Modifies user in-place

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="test_token"
    )

    result = await _get_authenticated_user(mock_settings, credentials, fetch_roles=True)

    assert result.user_id == "user_789"
    mock_supabase_auth.assert_called_once()
    mock_fetch_roles.assert_called_once_with(authenticated_user, mock_settings)


@pytest.mark.asyncio
async def test_user_client_rejects_keycloak_only_tokens(mock_settings):
    """Test that UserClientDep raises exception for Keycloak-only tokens."""

    # Create a Keycloak-only user (no Supabase identity)
    universal_user = UniversalUser(
        id="keycloak_only_user",
        email="keycloak@example.com",
        user_metadata={
            "provider_id": "keycloak_only_user",
            "iss": "https://keycloak.test",
        },
        identities=[UserIdentity(provider="keycloak", id="keycloak_only_user")],
    )

    keycloak_only_user = AuthenticatedUser(
        token="keycloak_token",
        user=universal_user,
        authentication_method=AuthenticationMethod.KEYCLOAK,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_user_client(keycloak_only_user, mock_settings)

    assert exc_info.value.status_code == 400

    assert "Direct Keycloak authentication tokens are incompatible" in str(
        exc_info.value.detail
    )


@pytest.mark.asyncio
async def test_user_client_allows_keycloak_via_supabase_users(mock_settings):
    """Test that UserClientDep works for Keycloak users authenticated via Supabase OIDC."""

    # Create a Keycloak user authenticated via Supabase (identity.provider="keycloak" but authentication_method=SUPABASE)
    universal_user = UniversalUser(
        id="keycloak_via_supabase_user",
        email="keycloak@example.com",
        user_metadata={
            "provider_id": "keycloak_via_supabase_user",
            "iss": "https://keycloak.test",
        },
        identities=[
            UserIdentity(provider="keycloak", id="keycloak_via_supabase_user"),
        ],
    )

    # This user was authenticated via Supabase (even though identity provider is "keycloak")
    keycloak_via_supabase_user = AuthenticatedUser(
        token="supabase_token",
        user=universal_user,
        authentication_method=AuthenticationMethod.SUPABASE,
    )

    # Should not raise an exception - authentication method is what matters, not identity provider
    client = await get_user_client(keycloak_via_supabase_user, mock_settings)
    assert client is not None
