from fastapi import APIRouter, File, HTTPException, UploadFile, status

from relife_financial.auth.dependencies import (
    AuthenticatedUserDep,
    AuthenticatedUserWithRolesDep,
    UserClientDep,
)
from relife_financial.config.logging import get_logger
from relife_financial.config.settings import SettingsDep
from relife_financial.models.examples import (
    FileUploadResponse,
    StorageFileInfo,
    TableDataResponse,
)

router = APIRouter(tags=["examples"])

logger = get_logger(__name__)


@router.post("/storage", response_model=FileUploadResponse)
async def upload_file(
    supabase: UserClientDep,
    current_user: AuthenticatedUserDep,
    settings: SettingsDep,
    file: UploadFile = File(...),
):
    """Upload a file to Supabase Storage with user-specific organization.

    This endpoint uploads files to a user-specific folder within the configured storage bucket.
    Each user's files are isolated in their own directory to prevent unauthorized access.
    """

    file_path = f"{current_user.user_id}/{file.filename}"
    file_content = await file.read()

    try:
        response = await supabase.storage.from_(settings.bucket_name).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": file.content_type},
        )

        logger.info(
            "File uploaded successfully",
            file_path=response.full_path,
            user_id=current_user.user_id,
            filename=file.filename,
            content_type=file.content_type,
        )

        public_url = await supabase.storage.from_(settings.bucket_name).get_public_url(
            file_path
        )

        return FileUploadResponse(
            message="File uploaded successfully",
            path=file_path,
            public_url=public_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )


@router.get("/storage", response_model=list[StorageFileInfo])
async def list_files(
    supabase: UserClientDep,
    current_user: AuthenticatedUserDep,
    settings: SettingsDep,
):
    """List all files uploaded by the authenticated user to the default Supabase Storage bucket.

    This endpoint retrieves a comprehensive list of all files that the current user
    has uploaded to their personal storage folder. Each file entry includes metadata
    such as size, creation date, and public access URL.
    """

    try:
        response = await supabase.storage.from_(settings.bucket_name).list(
            current_user.user_id
        )

        files = []

        for file in response:
            public_url = await supabase.storage.from_(
                settings.bucket_name
            ).get_public_url(f"{current_user.user_id}/{file['name']}")

            files.append(
                StorageFileInfo(
                    name=file["name"],
                    size=file["metadata"]["size"],
                    created_at=file["created_at"],
                    public_url=public_url,
                )
            )

        return files
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}",
        )


@router.get("/table/{table_name}", response_model=TableDataResponse)
async def read_table(table_name: str, supabase: UserClientDep):
    """Read data from a Supabase table. The table name is passed as a path parameter.

    This endpoint respects Row Level Security (RLS) policies configured on the table.
    Users will only see data they are authorized to access based on their permissions.
    """

    # Query the table using Supabase client
    response = await supabase.table(table_name).select("*").execute()
    data = response.data if response.data else []

    return TableDataResponse(table_name=table_name, data=data, count=len(data))


@router.get("/user-profile", response_model=dict)
async def get_user_profile(
    current_user: AuthenticatedUserWithRolesDep,
):
    """Get comprehensive user profile information including Keycloak roles.

    This endpoint demonstrates how to work with users authenticated via Keycloak
    without requiring them to be present in Supabase. It shows how to access
    user information and roles from the Keycloak authentication context.

    This works with both Supabase-synchronized and direct Keycloak users.
    """

    # Extract user information from the authenticated user
    user_profile = {
        "user_id": current_user.user_id,
        "email": current_user.user.email,
        "authentication_method": current_user.authentication_method.value,
        "keycloak_roles": current_user.keycloak_roles,
        "user_metadata": current_user.user.user_metadata,
        "has_supabase_compatible_token": current_user.has_supabase_compatible_token,
    }

    has_email = bool(current_user.user.email)
    has_roles = len(current_user.keycloak_roles) > 0

    premium_roles = {"premium", "admin"}

    # Add some example business logic that doesn't depend on Supabase
    # This could be checking against an external service, local cache, etc.
    user_profile["profile_complete"] = has_email and has_roles

    user_profile["premium_features_enabled"] = bool(
        set(current_user.keycloak_roles).intersection(premium_roles)
    )

    return user_profile
