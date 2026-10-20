
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)


class JobSourceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    base_url: HttpUrl | None = None

    @field_validator("base_url")
    @classmethod
    def reject_base_url_credentials(
        cls,
        value: HttpUrl | None,
    ) -> HttpUrl | None:
        if value is not None and (value.username or value.password):
            raise ValueError(
                "Source URLs must not include embedded credentials"
            )
        return value


class JobSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    base_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobSourceUpdate(BaseModel):
    is_active: bool


class JobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=250)
    company: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    source_id: int

    external_id: str | None = Field(default=None, max_length=250)
    location: str | None = Field(default=None, max_length=250)
    description: str | None = None

    employment_type: str | None = Field(default=None, max_length=100)
    experience_level: str | None = Field(default=None, max_length=100)

    remote_scope: Literal[
        "worldwide",
        "emea",
        "region_restricted",
        "country_restricted",
        "unknown",
        "non_remote",
        "onsite",
    ] = "unknown"
    remote_status: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    region: str | None = Field(default=None, max_length=100)
    posted_at: datetime | None = None
    eligible_countries: list[str] = Field(default_factory=list)
    eligibility_confidence: Literal["verified", "inferred", "unknown"] = (
        "unknown"
    )
    eligibility_source: str | None = Field(default=None, max_length=100)
    eligibility_reason: str | None = None

    @field_validator("url")
    @classmethod
    def reject_url_credentials(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password:
            raise ValueError("Job URLs must not include embedded credentials")
        return value


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
    remote_status: str
    region: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    eligible_countries: list[str]
    eligibility_confidence: str
    eligibility_source: str | None
    eligibility_reason: str | None
    duplicate_of_id: int | None
    created_at: datetime


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None
    source_slug: str
    source_name: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    fetched: int
    saved: int
    skipped: int
    duplicates: int
    stale: int
    failed: int
    error_summary: str | None


class ScoredJobRead(JobRead):
    relevance_score: int = Field(ge=0, le=100)
    eligibility: Literal[
        "worldwide",
        "emea",
        "region_restricted",
        "country_restricted",
        "non_remote",
        "unknown",
    ]
    relevance_reasons: list[str]
    eligibility_reason: str