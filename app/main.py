
from fastapi import FastAPI

app = FastAPI(
    title="Remote Job Aggregator API",
    description="An API for collecting and filtering remote job listings.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "message": "Remote Job Aggregator API is running"
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy"
    }
