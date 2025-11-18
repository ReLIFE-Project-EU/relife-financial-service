from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import AsyncClient, create_async_client
from supabase.client import ClientOptions

from relife_financial.auth.keycloak import (
    fetch_user_roles,
    validate_keycloak_jwt,
)
from relife_financial.config.logging import get_logger
from relife_financial.config.settings import SettingsDep
from relife_financial.models.auth import (
    AuthenticatedUser,
    AuthenticationMethod,
    UniversalUser,
)

security = HTTPBearer()
logger = get_logger(__name__)


async def _authenticate_with_supabase(
    token: str, settings: SettingsDep
) -> AuthenticatedUser:
    """Authenticate user via Supabase."""

    client = await get_service_client(settings)
    user_response = await client.auth.get_user(token)
    universal_user = UniversalUser.from_supabase_user(user_response)

    return AuthenticatedUser(
        token=token,
        user=universal_user,
        authentication_method=AuthenticationMethod.SUPABASE,
    )


async def _authenticate_with_keycloak(
    token: str, settings: SettingsDep
) -> AuthenticatedUser:
    """Authenticate user via Keycloak JWT validation."""

    return await validate_keycloak_jwt(
        token, settings.keycloak_client_id, settings.keycloak_realm_url
    )


async def _fetch_keycloak_roles(user: AuthenticatedUser, settings: SettingsDep) -> None:
    """Fetch and attach Keycloak roles to authenticated user."""

    if not user.is_keycloak_provider:
        user.keycloak_roles = []
        return

    user_metadata = user.user.user_metadata
    provider_id = user_metadata.get("provider_id")
    keycloak_url = user_metadata.get("iss")

    if not provider_id or not keycloak_url:
        logger.warning("Missing Keycloak metadata for user", user_id=user.user_id)
        user.keycloak_roles = []
        return

    user.keycloak_roles = await fetch_user_roles(
        keycloak_url,
        settings.keycloak_client_id,
        settings.keycloak_client_secret,
        provider_id,
    )


async def get_service_client(settings: SettingsDep) -> AsyncClient:
    """Create a Supabase client with service role (admin) privileges.
    This client bypasses Row Level Security and has full database access.
    Should only be used for admin/service operations."""

    client = await create_async_client(
        settings.supabase_url,
        settings.supabase_key,
        options=ClientOptions(),
    )

    return client


async def _get_authenticated_user(
    settings: SettingsDep,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    fetch_roles: bool = False,
) -> AuthenticatedUser:
    """Authenticates user with fallback from Supabase to Keycloak.

    Authentication strategy:
    1. Primary: Attempt authentication via Supabase
    2. Fallback: If Supabase fails, validate JWT directly against Keycloak
    3. Role fetching: Optionally fetch Keycloak roles for authorized users

    This dual approach ensures Keycloak users can access the API even if
    they haven't been synchronized to Supabase.
    """

    token = credentials.credentials
    authenticated_user = None

    try:
        # Primary authentication: Try Supabase first
        authenticated_user = await _authenticate_with_supabase(token, settings)
        logger.debug(
            "User authenticated via Supabase",
            user_id=authenticated_user.user_id,
        )

    except Exception as supabase_error:
        logger.debug("Supabase authentication failed", error=str(supabase_error))

        try:
            # Fallback authentication: Try Keycloak directly
            authenticated_user = await _authenticate_with_keycloak(token, settings)

            logger.debug(
                "User authenticated via Keycloak",
                user_id=authenticated_user.user_id,
            )

        except Exception as keycloak_error:
            logger.debug("Keycloak authentication failed", error=str(keycloak_error))

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Supabase and Keycloak authentication failed: Supabase error: '{}', Keycloak error: '{}'".format(
                    supabase_error, keycloak_error
                ),
            )

    # Fetch Keycloak roles if requested
    if fetch_roles:
        await _fetch_keycloak_roles(authenticated_user, settings)

    return authenticated_user


async def get_authenticated_user_without_roles(
    settings: SettingsDep,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthenticatedUser:
    """Authenticates user without fetching Keycloak roles."""

    return await _get_authenticated_user(
        settings=settings, credentials=credentials, fetch_roles=False
    )


async def get_authenticated_user_with_roles(
    settings: SettingsDep,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthenticatedUser:
    """Authenticates user and fetches their Keycloak roles."""

    return await _get_authenticated_user(
        settings=settings, credentials=credentials, fetch_roles=True
    )


AuthenticatedUserDep = Annotated[
    AuthenticatedUser, Depends(get_authenticated_user_without_roles)
]
"""Dependency that provides an authenticated user without Keycloak roles.
Use this dependency when basic user authentication is needed but role information is not required.
"""

AuthenticatedUserWithRolesDep = Annotated[
    AuthenticatedUser, Depends(get_authenticated_user_with_roles)
]
"""Dependency that provides an authenticated user with their Keycloak roles.
Use this dependency when both user authentication and role-based access control are needed.
"""


async def get_user_client(
    current_user: AuthenticatedUserDep, settings: SettingsDep
) -> AsyncClient:
    """Create a Supabase client with user context.
    This client respects Row Level Security policies based on the user's token.

    **Token Compatibility**:
    - ✅ Supabase-issued tokens (including Keycloak users via Supabase OIDC)
    - ❌ Direct Keycloak JWT tokens (will raise HTTPException)

    This function uses the authentication_method field to determine token
    compatibility, which correctly handles Keycloak users who authenticated
    through Supabase's OIDC integration.

    For direct Keycloak authentication, use ServiceClientDep with explicit
    permission checks instead of relying on RLS.

    Raises:
        HTTPException: If the user token is from direct Keycloak authentication
    """

    if not current_user.has_supabase_compatible_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Direct Keycloak authentication tokens are incompatible with Supabase Row Level Security. "
                "This token was authenticated directly against Keycloak without going through Supabase. "
                "Use ServiceClientDep with explicit permission validation instead."
            ),
        )

    client = await create_async_client(
        settings.supabase_url,
        settings.supabase_key,
        options=ClientOptions(
            headers={"Authorization": f"Bearer {current_user.token}"}
        ),
    )

    return client


ServiceClientDep = Annotated[AsyncClient, Depends(get_service_client)]
"""FastAPI dependency providing unrestricted Supabase database access.

**Security Warning**: This client bypasses all Row Level Security policies
and has full database access. It does NOT authenticate users.

Security best practices:
- Always combine with `AuthenticatedUserWithRolesDep` for user verification
- Validate admin permissions before privileged operations
- Log administrative actions for audit trails
- Never expose this client to untrusted code paths
"""

UserClientDep = Annotated[AsyncClient, Depends(get_user_client)]
"""FastAPI dependency providing user-scoped Supabase database access.

This client includes user authentication context and respects Row Level Security
(RLS) policies. Database operations are automatically filtered based on the
authenticated user's permissions and data ownership.

**Token Compatibility**:
- ✅ Supabase-issued tokens (including Keycloak users via Supabase OIDC)
- ❌ Direct Keycloak JWT tokens (will raise HTTPException)

This dependency uses the authentication_method field to determine token 
compatibility, which correctly handles Keycloak users who authenticated 
through Supabase's OIDC integration.

**For direct Keycloak authentication**: Use `ServiceClientDep` with explicit 
permission validation instead of relying on RLS, as direct Keycloak tokens 
cannot be validated by Supabase's Row Level Security system.
"""
