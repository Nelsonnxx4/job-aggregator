
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class JobSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    base_url: HttpUrl | None = None


class JobSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    base_url: str | None
    is_active: bool
    created_at: datetime


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    company: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    source_id: int

    external_id: str | None = Field(default=None, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    description: str | None = None

    employment_type: str | None = Field(default=None, max_length=50)
    experience_level: str | None = Field(default=None, max_length=50)

    remote_scope: str = Field(default="unknown", max_length=40)
    region: str | None = Field(default=None, max_length=100)
    posted_at: datetime | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    url: str
    source_id: int
    external_id: str | None
    location: str | None
    description: str | None
    employment_type: str | None
    experience_level: str | None
    remote_scope: str
    region: str | None
    posted_at: datetime | None
    created_at: datetime
