from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.analysis import router as analysis_router
from app.calls import router as calls_router
from app.config import Settings
from app.database import Database
from app.evidence import router as evidence_router
from app.logging import configure_logging, log_event
from app.migrator import migrate
from app.transcripts import router as transcripts_router


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    logger = configure_logging(app_settings.log_level)
    database = Database(app_settings.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        applied_migrations = migrate(database)
        app.state.database = database
        app.state.logger = logger
        app.state.settings = app_settings
        log_event(logger, "api_started", "Call Center Radar API started")
        if applied_migrations:
            log_event(logger, "database_migrated", "SQLite migrations applied at startup")
        yield
        log_event(logger, "api_stopped", "Call Center Radar API stopped")

    app = FastAPI(
        title="Call Center Radar API",
        version="0.1.0",
        description="Evidence-first call intelligence POC API.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["POST"],
        allow_headers=["*"],
    )

    @app.get("/api")
    def api_root() -> dict[str, str]:
        return {"service": "call-center-radar-api", "status": "ready"}

    @app.get("/api/health")
    def health(request: Request) -> dict[str, str]:
        request.app.state.database.check_connection()
        return {"status": "ok", "database": "reachable"}

    app.include_router(calls_router)
    app.include_router(transcripts_router)
    app.include_router(evidence_router)
    app.include_router(analysis_router)

    return app


app = create_app()
