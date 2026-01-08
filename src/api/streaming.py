"""Audio streaming API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from cloudsound_shared.multitenancy import get_tenant_db
from ..services.station_service import RadioStationService
from ..services.track_service import TrackService
from cloudsound_shared.storage import StorageClient
from cloudsound_shared.logging import get_logger
from cloudsound_shared.metrics import http_requests_total, http_request_duration_seconds
from ..metrics import (
    streaming_connections_active,
    streaming_bytes_sent_total,
    playback_started_total
)
from ..producers.kafka_producer import publish_playback_event
import time

logger = get_logger(__name__)

router = APIRouter(prefix="/radio/stream", tags=["radio"])


@router.get("/station/{station_id}")
async def stream_station(
    station_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db)
) -> Response:
    """
    Stream audio from a radio station.
    
    This endpoint streams the current track from the station.
    Supports HTTP range requests for seeking and resuming playback.
    """
    start_time = time.time()
    
    try:
        station_service = RadioStationService(db)
        track_service = TrackService(db)
        
        # Get station
        station = await station_service.get_station_by_id(station_id)
        if not station:
            http_requests_total.labels(method="GET", endpoint="/radio/stream/station", status=404).inc()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station {station_id} not found"
            )
        
        if not station.is_active:
            http_requests_total.labels(method="GET", endpoint="/radio/stream/station", status=403).inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Station {station_id} is not active"
            )
        
        # Get tracks for station
        tracks = await track_service.get_tracks_for_station(station_id)
        if not tracks:
            http_requests_total.labels(method="GET", endpoint="/radio/stream/station", status=404).inc()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station {station_id} has no tracks"
            )
        
        # For now, stream the first track
        # TODO: Implement playlist rotation logic
        track = tracks[0]
        
        # Update metrics
        streaming_connections_active.labels(station_id=str(station_id)).inc()
        playback_started_total.labels(
            station_id=str(station_id),
            track_id=str(track.id)
        ).inc()
        
        # Publish playback start event to Kafka
        publish_playback_event(
            station_id=station_id,
            track_id=track.id,
            duration_seconds=None  # Still playing
        )
        
        # Get file from storage
        storage_client = StorageClient()
        
        # Check if file exists
        if not await storage_client.file_exists(track.file_path):
            http_requests_total.labels(method="GET", endpoint="/radio/stream/station", status=404).inc()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {track.file_path}"
            )
        
        # Handle range requests
        range_header = request.headers.get("range")
        
        if range_header:
            # Parse range header (e.g., "bytes=0-1023")
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else track.file_size - 1
            
            # Get file chunk
            file_data = await storage_client.get_file_range(track.file_path, start, end)
            
            # Return partial content
            content_length = end - start + 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{track.file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": f"audio/{track.file_format}"
            }
            
            # Update metrics
            streaming_bytes_sent_total.labels(
                station_id=str(station_id),
                track_id=str(track.id)
            ).inc(content_length)
            
            http_requests_total.labels(method="GET", endpoint="/radio/stream/station", status=206).inc()
            http_request_duration_seconds.labels(method="GET", endpoint="/radio/stream/station").observe(time.time() - start_time)
            
            return Response(
                content=file_data,
                status_code=206,
                headers=headers,
                media_type=f"audio/{track.file_format}"
            )
        else:
            # Return full file
            file_data = await storage_client.get_file(track.file_path)
            
            headers = {
                "Content-Length": str(track.file_size),
                "Content-Type": f"audio/{track.file_format}",
                "Accept-Ranges": "bytes"
            }
            
            # Update metrics
            streaming_bytes_sent_total.labels(
                station_id=str(station_id),
                track_id=str(track.id)
            ).inc(track.file_size)
            
            http_requests_total.labels(method="GET", endpoint="/radio/stream/station", status=200).inc()
            http_request_duration_seconds.labels(method="GET", endpoint="/radio/stream/station").observe(time.time() - start_time)
            
            return Response(
                content=file_data,
                status_code=200,
                headers=headers,
                media_type=f"audio/{track.file_format}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("streaming_error", station_id=str(station_id), error=str(e), exc_info=True)
        streaming_connections_active.labels(station_id=str(station_id)).dec()
        http_requests_total.labels(method="GET", endpoint="/radio/stream/station", status=500).inc()
        http_request_duration_seconds.labels(method="GET", endpoint="/radio/stream/station").observe(time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error streaming audio"
        )


@router.get("/track/{track_id}")
async def stream_track(
    track_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db)
) -> Response:
    """
    Stream a specific track by ID.
    
    Supports HTTP range requests for seeking and resuming playback.
    """
    start_time = time.time()
    
    try:
        track_service = TrackService(db)
        
        # Get track
        track = await track_service.get_track_by_id(track_id)
        if not track:
            http_requests_total.labels(method="GET", endpoint="/radio/stream/track", status=404).inc()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Track {track_id} not found"
            )
        
        # Get file from storage
        storage_client = StorageClient()
        
        # Check if file exists
        if not await storage_client.file_exists(track.file_path):
            http_requests_total.labels(method="GET", endpoint="/radio/stream/track", status=404).inc()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {track.file_path}"
            )
        
        # Handle range requests
        range_header = request.headers.get("range")
        
        if range_header:
            # Parse range header
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else track.file_size - 1
            
            # Get file chunk
            file_data = await storage_client.get_file_range(track.file_path, start, end)
            
            # Return partial content
            content_length = end - start + 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{track.file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": f"audio/{track.file_format}"
            }
            
            http_requests_total.labels(method="GET", endpoint="/radio/stream/track", status=206).inc()
            http_request_duration_seconds.labels(method="GET", endpoint="/radio/stream/track").observe(time.time() - start_time)
            
            return Response(
                content=file_data,
                status_code=206,
                headers=headers,
                media_type=f"audio/{track.file_format}"
            )
        else:
            # Return full file
            file_data = await storage_client.get_file(track.file_path)
            
            headers = {
                "Content-Length": str(track.file_size),
                "Content-Type": f"audio/{track.file_format}",
                "Accept-Ranges": "bytes"
            }
            
            http_requests_total.labels(method="GET", endpoint="/radio/stream/track", status=200).inc()
            http_request_duration_seconds.labels(method="GET", endpoint="/radio/stream/track").observe(time.time() - start_time)
            
            return Response(
                content=file_data,
                status_code=200,
                headers=headers,
                media_type=f"audio/{track.file_format}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("streaming_error", track_id=str(track_id), error=str(e), exc_info=True)
        http_requests_total.labels(method="GET", endpoint="/radio/stream/track", status=500).inc()
        http_request_duration_seconds.labels(method="GET", endpoint="/radio/stream/track").observe(time.time() - start_time)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error streaming audio"
        )

