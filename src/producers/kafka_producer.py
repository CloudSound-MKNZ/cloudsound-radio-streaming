"""Kafka producer for radio streaming service."""
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from cloudsound_shared.kafka import KafkaProducerClient
from cloudsound_shared.logging import get_logger
from cloudsound_shared.metrics import kafka_messages_produced

logger = get_logger(__name__)

# Global producer instance (singleton pattern)
_producer: Optional[KafkaProducerClient] = None


def get_producer() -> KafkaProducerClient:
    """Get or create Kafka producer instance."""
    global _producer
    if _producer is None:
        _producer = KafkaProducerClient()
        _producer.connect()
    return _producer


def publish_playback_event(
    station_id: UUID,
    track_id: UUID,
    duration_seconds: Optional[int] = None,
    user_id: Optional[str] = None
) -> None:
    """
    Publish a playback event to Kafka.
    
    Args:
        station_id: ID of the radio station
        track_id: ID of the track being played
        duration_seconds: Duration the track was played (None if still playing)
        user_id: Optional user ID (for future use)
    """
    try:
        producer = get_producer()
        
        event = {
            "station_id": str(station_id),
            "track_id": str(track_id),
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": duration_seconds,
            "user_id": user_id,
        }
        
        # Use track_id as key for partitioning (ensures events for same track are ordered)
        key = str(track_id)
        
        producer.send(
            topic="radio.playback.events",
            value=event,
            key=key
        )
        
        # Update metrics
        kafka_messages_produced.labels(topic="radio.playback.events").inc()
        
        logger.info(
            "playback_event_published",
            station_id=str(station_id),
            track_id=str(track_id),
            duration_seconds=duration_seconds
        )
    
    except Exception as e:
        logger.error(
            "playback_event_publish_failed",
            station_id=str(station_id),
            track_id=str(track_id),
            error=str(e),
            exc_info=True
        )
        # Don't raise - we don't want playback failures to break the streaming


def close_producer() -> None:
    """Close the Kafka producer connection."""
    global _producer
    if _producer:
        _producer.close()
        _producer = None
        logger.info("kafka_producer_closed")

