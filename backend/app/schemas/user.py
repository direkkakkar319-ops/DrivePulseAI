"""Public profile response shared with the mobile and web TypeScript contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    firebase_uid: str
    email: str
    username: str | None
    created_at: datetime
    updated_at: datetime
