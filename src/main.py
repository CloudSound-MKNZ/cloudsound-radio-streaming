"""Radio streaming service main application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.stations import router as stations_router
from .api.streaming import router as streaming_router
from .api.playback import router as playback_router
from .api.search import router as search_router
from cloudsound_shared.health import router as health_router
from cloudsound_shared.metrics import get_metrics
from fastapi.responses import Response
from cloudsound_shared.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from cloudsound_shared.middleware.correlation import CorrelationIDMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from cloudsound_shared.logging import configure_logging, get_logger
from cloudsound_shared.config.settings import app_settings
import sys

# Configure logging
configure_logging(log_level=app_settings.log_level, log_format=app_settings.log_format)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="CloudSound Radio Streaming Service",
    version=app_settings.app_version,
    description="Radio station management and audio streaming service",
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

# Exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

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


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("radio_streaming_service_started", version=app_settings.app_version)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    from .producers.kafka_producer import close_producer
    close_producer()
    logger.info("radio_streaming_service_shutdown")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

