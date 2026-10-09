import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class APIResponseMeta(BaseModel):
    snapshot_hash: str | None = None
    config_hash: str | None = None
    run_id: str | None = None
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)


class APIResponse(BaseModel):
    data: Any
    meta: APIResponseMeta = Field(default_factory=APIResponseMeta)


class APIError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class APIErrorResponse(BaseModel):
    error: APIError
