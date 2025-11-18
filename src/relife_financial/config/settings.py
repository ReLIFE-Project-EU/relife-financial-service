from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for the service API loaded from environment variables."""

    # URL of the Supabase instance that this service connects to
    supabase_url: str
    # Service role key - this is a special API key with admin privileges that bypasses
    # Row Level Security (RLS) policies and has full access to the database. It should
    # only be used server-side and never exposed to clients.
    supabase_key: str
    # Client ID in Keycloak that this API uses for authentication
    keycloak_client_id: str
    # Client secret in Keycloak that this API uses for authentication
    keycloak_client_secret: str
    # Name of the admin role in the system used for permission checks
    admin_role_name: str = "relife_admin"
    # Name of the default storage bucket in Supabase
    bucket_name: str = "default_relife_bucket"
    # Base URL of the Keycloak realm for authentication
    # Used to construct token, JWKS, and other authentication endpoints
    keycloak_realm_url: str = "https://relife-identity.test.ctic.es/realms/relife"


@lru_cache
def get_settings():
    """Get cached application settings."""

    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
"""Type annotation for dependency injection of Settings in FastAPI endpoints"""
