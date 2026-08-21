from fastapi import FastAPI

app = FastAPI(
    title="Call Center Radar API",
    version="0.1.0",
    description="Evidence-first call intelligence POC API.",
)


@app.get("/api")
def api_root() -> dict[str, str]:
    """Expose the bootstrap state until Story 0.2 adds operational endpoints."""
    return {"service": "call-center-radar-api", "status": "bootstrap-ready"}
