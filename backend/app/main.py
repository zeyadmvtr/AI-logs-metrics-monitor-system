import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from app.config import get_settings
from app.logger import logger
from app.database import Base, engine
from app.api.health import router as health_router
from app.api.orders import router as orders_router
from app.api.chaos import router as chaos_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager: sets up DB tables on startup."""
    logger.info("Initializing application resources and schema...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.warning(f"Could not connect to database on startup (will retry on requests): {exc}")
    yield
    logger.info("Shutting down application resources.")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AIOps Microservice Platform with Prometheus Telemetry & Chaos Simulation",
    lifespan=lifespan,
)

# Initialize Prometheus Metrics Instrumentator
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
)
instrumentator.add(metrics.default(metric_namespace="aiops", metric_subsystem="backend"))
instrumentator.instrument(app).expose(app, endpoint=settings.PROMETHEUS_METRICS_PATH)


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Logs incoming HTTP requests and latency with structured JSON fields."""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Pass request_id downstream
    request.state.request_id = request_id

    try:
        response = await call_next(request)
        duration = round((time.time() - start_time) * 1000, 2)

        # Do not flood logs with health or metrics probes
        if not (request.url.path.startswith("/api/v1/health") or request.url.path == "/metrics"):
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration}ms)",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration,
                }
            )
        return response
    except Exception as exc:
        duration = round((time.time() - start_time) * 1000, 2)
        logger.error(
            f"Unhandled exception during {request.method} {request.url.path}: {exc}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration,
                "error": str(exc),
            }
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error", "request_id": request_id}
        )


# Register API Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
if settings.ENABLE_CHAOS:
    app.include_router(chaos_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
def root():
    return {
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "1.0.0",
        "docs_url": "/docs",
        "metrics_url": settings.PROMETHEUS_METRICS_PATH,
    }
# CI/CD Auto Trigger Enabled
# CI/CD Auto Trigger Enabled
