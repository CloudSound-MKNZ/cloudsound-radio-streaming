"""Radio streaming service main application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from cloudsound_shared.health import router as health_router
from cloudsound_shared.metrics import get_metrics
from cloudsound_shared.middleware.error_handler import register_exception_handlers
from cloudsound_shared.middleware.correlation import CorrelationIDMiddleware
from cloudsound_shared.logging import configure_logging, get_logger
from cloudsound_shared.config.settings import app_settings

from .api.stations import router as stations_router
from .api.streaming import router as streaming_router
from .api.playback import router as playback_router
from .api.search import router as search_router

# Configure logging
configure_logging(log_level=app_settings.log_level, log_format=app_settings.log_format)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown."""
    # Startup
    logger.info("radio_streaming_service_starting", version=app_settings.app_version)
    logger.info("radio_streaming_service_started", version=app_settings.app_version)
    
    yield
    
    # Shutdown
    logger.info("radio_streaming_service_shutting_down")
    from .producers.kafka_producer import close_producer
    close_producer()
    logger.info("radio_streaming_service_shutdown")


# Create FastAPI app
app = FastAPI(
    title="CloudSound Radio Streaming Service",
    version=app_settings.app_version,
    description="Radio station management and audio streaming service",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID middleware
app.add_middleware(CorrelationIDMiddleware)

# Register all exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(health_router)
app.include_router(stations_router, prefix=app_settings.api_prefix)
app.include_router(streaming_router, prefix=app_settings.api_prefix)
app.include_router(playback_router, prefix=app_settings.api_prefix)
app.include_router(search_router, prefix=app_settings.api_prefix)

# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=get_metrics(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

