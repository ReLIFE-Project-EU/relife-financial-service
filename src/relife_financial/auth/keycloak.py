from typing import List

import httpx
import jwt
from fastapi import HTTPException, status

from relife_financial.config.logging import get_logger
from relife_financial.models.auth import (
    AuthenticatedUser,
    AuthenticationMethod,
    KeycloakRole,
    UniversalUser,
)

logger = get_logger(__name__)


async def get_keycloak_token(
    keycloak_url: str, client_id: str, client_secret: str
) -> str:
    """Obtain an admin access token from Keycloak using client credentials flow.
    Raises HTTPException if token request fails."""

    token_url = f"{keycloak_url}/protocol/openid-connect/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

        return response.json()["access_token"]


async def get_keycloak_user_roles(
    keycloak_url: str, admin_token: str, user_id: str
) -> List[KeycloakRole]:
    """Fetch a user's realm roles from Keycloak's admin API.
    Requires an admin token with appropriate permissions."""

    role_mapper_base_url = keycloak_url.replace("/realms", "/admin/realms").rstrip("/")
    role_mapper_url = f"{role_mapper_base_url}/users/{user_id}/role-mappings/realm"

    async with httpx.AsyncClient() as client:
        logger.debug("Requesting roles for user", 
            user_id=user_id, 
            role_mapper_url=role_mapper_url
        )

        response = await client.get(
            role_mapper_url, headers={"Authorization": f"Bearer {admin_token}"}
        )

        response.raise_for_status()
        return [KeycloakRole(**role) for role in response.json()]


async def validate_keycloak_jwt(
    token: str, client_id: str, keycloak_realm_url: str
) -> AuthenticatedUser:
    """Validate JWT token using manually constructed Keycloak URLs.

    This function validates a Keycloak JWT token by:
    1. Constructing the issuer URL from the realm URL
    2. Validating the issuer against the configured trusted issuer
    3. Constructing the JWKS URL from the realm URL
    4. Fetching the public key from the JWKS endpoint
    5. Verifying the JWT signature and claims
    6. Creating a universal user object for API consumption

    Args:
        token: The JWT token to validate
        client_id: The Keycloak client ID for audience validation
        keycloak_realm_url: Base URL of the Keycloak realm

    Returns:
        AuthenticatedUser object with universal user data

    Raises:
        HTTPException: If token validation fails or issuer is not trusted
    """

    try:
        # Construct URLs from realm URL
        trusted_issuer = keycloak_realm_url.rstrip("/")
        jwks_uri = f"{trusted_issuer}/protocol/openid-connect/certs"

        # Decode JWT without verification to get issuer
        unverified_payload = jwt.decode(token, options={"verify_signature": False})

        token_issuer = unverified_payload.get("iss")

        if not token_issuer:
            raise ValueError("JWT missing issuer claim")

        # Security check: Validate issuer against configured realm URL
        if token_issuer != trusted_issuer:
            logger.warning(
                "Untrusted issuer attempted",
                attempted_issuer=token_issuer,
                expected_issuer=trusted_issuer
            )

            raise ValueError(f"Untrusted issuer: {token_issuer}")

        # Get public key from manually constructed JWKS endpoint
        public_key = jwt.PyJWKClient(jwks_uri).get_signing_key_from_jwt(token).key

        # First decode without audience validation to check the claims
        verified_payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        # Manual validation of client authorization
        # In Keycloak, check both 'aud' (audience) and 'azp' (authorized party) claims
        token_audience = verified_payload.get("aud")
        token_azp = verified_payload.get("azp")

        # Validate that our client is either the audience or the authorized party
        if not (
            token_audience == client_id
            or token_azp == client_id
            or (isinstance(token_audience, list) and client_id in token_audience)
        ):
            raise ValueError(
                f"Token not intended for this client. Expected client_id: {client_id}, "
                f"found audience: {token_audience}, authorized party: {token_azp}"
            )

        # Extract user information
        user_id = verified_payload.get("sub")
        email = verified_payload.get("email")

        if not user_id:
            raise ValueError("JWT missing subject claim")

        # Create universal user for Keycloak-only authentication
        universal_user = UniversalUser.from_keycloak_jwt(user_id, email, token_issuer)

        return AuthenticatedUser(
            token=token,
            user=universal_user,
            authentication_method=AuthenticationMethod.KEYCLOAK,
        )

    except jwt.InvalidTokenError as e:
        logger.debug("Keycloak JWT validation failed", error=str(e))

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Keycloak token: {str(e)}",
        )
    except Exception as e:
        logger.debug("Keycloak authentication error", error=str(e))

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Keycloak authentication failed: {str(e)}",
        )


async def fetch_user_roles(
    keycloak_url: str, client_id: str, client_secret: str, user_id: str
) -> List[KeycloakRole]:
    """Fetch Keycloak roles for a user.

    This is a convenience function that combines token acquisition and role fetching.

    Args:
        keycloak_url: The Keycloak realm URL
        client_id: The Keycloak client ID
        client_secret: The Keycloak client secret
        user_id: The user ID to fetch roles for

    Returns:
        List of KeycloakRole objects

    Raises:
        HTTPException: If role fetching fails
    """

    try:
        admin_token = await get_keycloak_token(keycloak_url, client_id, client_secret)
        return await get_keycloak_user_roles(keycloak_url, admin_token, user_id)
    except Exception as e:
        logger.warning(
            "Failed to fetch Keycloak roles for user",
            user_id=user_id, error=str(e)
        )
        return []
