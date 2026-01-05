"""Playback event tracking API endpoints."""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from cloudsound_shared.logging import get_logger
from cloudsound_shared.metrics import playback_events_total
from ..producers.kafka_producer import publish_playback_event
import time
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter(prefix="/radio/playback", tags=["radio"])


class PlaybackEventRequest(BaseModel):
    """Playback event request model."""
    station_id: UUID
    track_id: UUID
    duration_seconds: Optional[int] = None


class PlaybackEventResponse(BaseModel):
    """Playback event response model."""
    id: UUID
    station_id: UUID
    track_id: UUID
    timestamp: str
    duration_seconds: Optional[int] = None


@router.post("/events", response_model=PlaybackEventResponse, status_code=status.HTTP_201_CREATED)
async def create_playback_event(
    event: PlaybackEventRequest
) -> PlaybackEventResponse:
    """Create a playback event for tracking statistics.
    
    Publishes the event to Kafka for async processing by the analytics service.
    """
    start_time = time.time()
    
    try:
        from uuid import uuid4
        event_id = uuid4()
        timestamp = datetime.utcnow()
        
        # Update metrics
        playback_events_total.labels(
            station_id=str(event.station_id),
            track_id=str(event.track_id)
        ).inc()
        
        # Publish to Kafka for async processing by analytics service
        publish_playback_event(
            station_id=event.station_id,
            track_id=event.track_id,
            duration_seconds=event.duration_seconds
        )
        
        logger.info(
            "playback_event_published",
            event_id=str(event_id),
            station_id=str(event.station_id),
            track_id=str(event.track_id),
            duration_seconds=event.duration_seconds
        )
        
        return PlaybackEventResponse(
            id=event_id,
            station_id=event.station_id,
            track_id=event.track_id,
            timestamp=timestamp.isoformat(),
            duration_seconds=event.duration_seconds
        )
    
    except Exception as e:
        logger.error(
            "playback_event_creation_failed",
            station_id=str(event.station_id),
            track_id=str(event.track_id),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create playback event"
        )

