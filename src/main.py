"""Radio streaming service main application."""
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from cloudsound_shared.health import router as health_router
from cloudsound_shared.metrics import get_metrics
from cloudsound_shared.middleware.error_handler import register_exception_handlers
from cloudsound_shared.middleware.correlation import CorrelationIDMiddleware
from cloudsound_shared.logging import configure_logging, get_logger
from cloudsound_shared.config.settings import app_settings
from cloudsound_shared.db.pool import engine
from cloudsound_shared.multitenancy import TenantAwareSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from .api.stations import router as stations_router
from .api.streaming import router as streaming_router
from .api.playback import router as playback_router
from .api.search import router as search_router
from .consumers.music_downloaded_consumer import MusicDownloadedConsumer

# Configure logging
configure_logging(log_level=app_settings.log_level, log_format=app_settings.log_format)
logger = get_logger(__name__)

# Global consumer instance
music_consumer: Optional[MusicDownloadedConsumer] = None

# Session factory for consumers (using tenant-aware session)
_session_factory = None


def get_db_session_factory():
    """Get the database session factory for use in consumers."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            engine,
            class_=TenantAwareSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown."""
    global music_consumer
    
    # Startup
    logger.info("radio_streaming_service_starting", version=app_settings.app_version)
    
    # Start music downloaded consumer
    try:
        music_consumer = MusicDownloadedConsumer(
            bootstrap_servers=app_settings.kafka_bootstrap_servers,
            group_id="radio-streaming",
        )
        music_consumer.start()
        logger.info("music_downloaded_consumer_started")
    except Exception as e:
        logger.warning("music_downloaded_consumer_start_failed", error=str(e))
    
    logger.info("radio_streaming_service_started", version=app_settings.app_version)
    
    yield
    
    # Shutdown
    logger.info("radio_streaming_service_shutting_down")
    
    # Stop consumer
    if music_consumer:
        music_consumer.stop()
    
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

