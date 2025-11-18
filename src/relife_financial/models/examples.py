from typing import Any, List

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    """Response model for file upload endpoint."""

    message: str
    path: str
    public_url: str


class StorageFileInfo(BaseModel):
    """Model representing information about a stored file."""

    name: str
    size: int
    created_at: str
    public_url: str


class TableDataResponse(BaseModel):
    """Response model for table read endpoint."""

    table_name: str
    data: List[dict[str, Any]]
    count: int
