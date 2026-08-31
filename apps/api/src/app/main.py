from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.analysis import router as analysis_router
from app.analysis_provider import OllamaAnalysisProvider
from app.calls import router as calls_router
from app.config import Settings
from app.customer_history import router as customer_history_router
from app.dashboard import router as dashboard_router
from app.database import Database
from app.evidence import router as evidence_router
from app.logging import bind_request_id, configure_logging, log_event, reset_request_id
from app.migrator import migrate
from app.pipeline import ProcessingPipeline
from app.priority import router as priority_router
from app.service_health import build_service_health
from app.traceability import router as traceability_router
from app.transcripts import router as transcripts_router
from app.worker import DurableProcessingWorker


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
        if not hasattr(app.state, "analysis_provider"):
            app.state.analysis_provider = OllamaAnalysisProvider(app_settings)
        app.state.processing_worker = DurableProcessingWorker(
            database,
            logger,
            lambda: ProcessingPipeline(
                database,
                logger,
                app_settings,
                transcriber=getattr(app.state, "transcriber", None),
            ),
        )
        log_event(logger, "api_started", "Call Center Radar API started")
        if applied_migrations:
            log_event(logger, "database_migrated", "SQLite migrations applied at startup")
        if app_settings.processing_worker_enabled:
            app.state.processing_worker.start()
        yield
        if app_settings.processing_worker_enabled:
            app.state.processing_worker.stop()
        log_event(logger, "api_stopped", "Call Center Radar API stopped")

    app = FastAPI(
        title="Call Center Radar API",
        version="0.1.0",
        description="Evidence-first call intelligence POC API.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
        ],
        allow_credentials=False,
        allow_methods=["DELETE", "GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlate_request(request: Request, call_next):
        request_id = f"req_{uuid4().hex}"
        request.state.request_id = request_id
        token = bind_request_id(request_id)
        try:
            try:
                response = await call_next(request)
            except Exception:
                log_event(
                    logger,
                    "request_failed",
                    "API request failed before a response was created",
                    context={
                        "method": request.method,
                        "path": request.url.path,
                        "failure_reason": "unhandled_server_error",
                    },
                )
                raise
            response.headers["X-Request-ID"] = request_id
            log_event(
                logger,
                "request_completed",
                "API request completed",
                context={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )
            return response
        finally:
            reset_request_id(token)

    @app.get("/api")
    def api_root() -> dict[str, str]:
        return {"service": "call-center-radar-api", "status": "ready"}

    @app.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        return build_service_health(request.app)

    app.include_router(calls_router)
    app.include_router(customer_history_router)
    app.include_router(transcripts_router)
    app.include_router(evidence_router)
    app.include_router(analysis_router)
    app.include_router(dashboard_router)
    app.include_router(priority_router)
    app.include_router(traceability_router)

    if app_settings.static_dir is not None and app_settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=app_settings.static_dir, html=True), name="web")

    return app


app = create_app()
