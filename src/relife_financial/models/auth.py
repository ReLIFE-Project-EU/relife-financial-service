from enum import Enum
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from gotrue.types import UserResponse
from pydantic import BaseModel

from relife_financial.config.settings import get_settings


class AuthenticationMethod(str, Enum):
    """Authentication method used to authenticate the user."""

    SUPABASE = "supabase"
    KEYCLOAK = "keycloak"


class KeycloakRole(BaseModel):
    """Representation of a Keycloak role with its attributes.

    This model represents role information retrieved from Keycloak's identity provider.
    """

    id: str
    name: str
    description: str | None = None
    composite: bool | None = None
    clientRole: bool | None = None
    containerId: str | None = None


class UserIdentity(BaseModel):
    """Represents a user identity from an authentication provider."""

    provider: str
    id: str


class UniversalUser(BaseModel):
    """Provider-agnostic user model that works with any authentication provider.

    This model abstracts away the differences between Supabase GoTrue User objects
    and Keycloak JWT payloads, providing a consistent interface for user data
    regardless of the authentication provider.
    """

    id: str
    email: Optional[str] = None
    user_metadata: Dict[str, str] = {}
    identities: List[UserIdentity] = []

    @classmethod
    def from_supabase_user(cls, user_response: UserResponse) -> "UniversalUser":
        """Create UniversalUser from Supabase UserResponse."""

        user = user_response.user

        identities = []

        if user.identities:
            identities = [
                UserIdentity(provider=identity.provider, id=identity.id)
                for identity in user.identities
            ]

        return cls(
            id=user.id,
            email=user.email,
            user_metadata=user.user_metadata or {},
            identities=identities,
        )

    @classmethod
    def from_keycloak_jwt(
        cls, user_id: str, email: Optional[str], keycloak_url: str
    ) -> "UniversalUser":
        """Create UniversalUser from Keycloak JWT payload."""

        return cls(
            id=user_id,
            email=email,
            user_metadata={"provider_id": user_id, "iss": keycloak_url},
            identities=[UserIdentity(provider="keycloak", id=user_id)],
        )

    @property
    def is_keycloak_provider(self) -> bool:
        """Check if user authenticated via Keycloak."""

        return any(identity.provider == "keycloak" for identity in self.identities)


class AuthenticatedUser(BaseModel):
    """Authenticated user model supporting multiple authentication providers.

    This model abstracts authentication information from various sources (Supabase, Keycloak)
    and provides a consistent interface for user data and permissions.
    """

    token: str
    user: UniversalUser
    authentication_method: AuthenticationMethod
    keycloak_roles: Optional[List[KeycloakRole]] = None

    @property
    def has_admin_role(self) -> bool:
        """Check if the user has the admin role defined in settings."""

        if not self.keycloak_roles:
            return False

        settings = get_settings()

        return any(
            role.name == settings.admin_role_name for role in self.keycloak_roles
        )

    @property
    def user_id(self) -> str:
        """Get the unique identifier for the user."""

        return self.user.id

    @property
    def email(self) -> Optional[str]:
        """Get the user's email address."""

        return self.user.email

    @property
    def is_keycloak_provider(self) -> bool:
        """Check whether the user has logged in via the Keycloak provider."""

        return self.user.is_keycloak_provider

    @property
    def has_supabase_compatible_token(self) -> bool:
        """Check if the user's token is compatible with Supabase RLS.

        Returns True if the user was authenticated via Supabase (including
        Keycloak users who authenticated through Supabase's OIDC integration).
        """

        return self.authentication_method == AuthenticationMethod.SUPABASE

    def raise_if_not_admin(self):
        """Verify the user has admin privileges or raise an exception."""

        if not self.has_admin_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have admin role",
            )
