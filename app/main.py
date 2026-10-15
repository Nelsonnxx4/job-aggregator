
from fastapi import FastAPI

from app.config import settings
from app.routers import jobs, sources

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="An API for collecting and filtering remote job listings.",
)

app.include_router(jobs.router)
app.include_router(sources.router)


@app.get("/", tags=["Health"])
def read_root() -> dict[str, str]:
    return {"message": f"{settings.app_name} is running"}


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
