"""Radio station API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from cloudsound_shared.db.pool import get_db
from cloudsound_shared.logging import get_logger
from cloudsound_shared.exceptions import NotFoundError

from ..services.station_service import RadioStationService
from ..services.track_service import TrackService
from ..models import RadioStation, StationType

logger = get_logger(__name__)

router = APIRouter(prefix="/radio/stations", tags=["radio"])


class StationResponse(BaseModel):
    """Radio station response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str = Field(..., description="Station name")
    type: str = Field(..., description="Station type (upcoming, past, genre)")
    genre: Optional[str] = Field(None, description="Genre for genre-based stations")
    description: Optional[str] = Field(None, description="Station description")
    is_active: bool = Field(..., description="Whether the station is active")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Override to convert datetime to string."""
        if hasattr(obj, '__dict__'):
            data = {}
            for key, value in obj.__dict__.items():
                if hasattr(value, 'isoformat'):  # datetime objects
                    data[key] = value.isoformat()
                else:
                    data[key] = value
            # Handle enum types
            if hasattr(obj, 'type'):
                data['type'] = obj.type.value if hasattr(obj.type, 'value') else str(obj.type)
            return cls(**data)
        return super().model_validate(obj, **kwargs)


class TrackResponse(BaseModel):
    """Track response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: str = Field(..., description="Track title")
    artist_id: UUID = Field(..., description="Artist ID")
    artist_name: Optional[str] = Field(None, description="Artist name")
    duration_seconds: int = Field(..., ge=0, description="Track duration in seconds")
    file_path: str = Field(..., description="Storage path to audio file")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    file_format: str = Field(..., description="Audio format (mp3, flac, etc.)")


@router.get("", response_model=List[StationResponse])
async def list_stations(
    active_only: bool = Query(True, description="Filter by active status"),
    station_type: Optional[StationType] = Query(None, description="Filter by station type"),
    genre: Optional[str] = Query(None, description="Filter by genre (for genre stations)"),
    db: AsyncSession = Depends(get_db)
) -> List[StationResponse]:
    """List all radio stations."""
    logger.info(
        "listing_stations",
        active_only=active_only,
        station_type=station_type.value if station_type else None,
        genre=genre
    )
    
    service = RadioStationService(db)
    
    if station_type:
        stations = await service.get_stations_by_type(station_type, active_only)
    elif genre:
        stations = await service.get_stations_by_genre(genre, active_only)
    else:
        stations = await service.get_all_stations(active_only)
    
    logger.info("stations_listed", count=len(stations))
    return [StationResponse.model_validate(station) for station in stations]


@router.get("/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> StationResponse:
    """Get a radio station by ID."""
    logger.info("getting_station", station_id=str(station_id))
    
    service = RadioStationService(db)
    station = await service.get_station_by_id(station_id)
    
    if not station:
        logger.warning("station_not_found", station_id=str(station_id))
        raise NotFoundError(
            message=f"Station {station_id} not found",
            details={"station_id": str(station_id)},
        )
    
    logger.info("station_retrieved", station_id=str(station_id), station_name=station.name)
    return StationResponse.model_validate(station)


@router.get("/{station_id}/tracks", response_model=List[TrackResponse])
async def get_station_tracks(
    station_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> List[TrackResponse]:
    """Get all tracks for a radio station."""
    logger.info("getting_station_tracks", station_id=str(station_id))
    
    station_service = RadioStationService(db)
    track_service = TrackService(db)
    
    # Verify station exists
    station = await station_service.get_station_by_id(station_id)
    if not station:
        logger.warning("station_not_found_for_tracks", station_id=str(station_id))
        raise NotFoundError(
            message=f"Station {station_id} not found",
            details={"station_id": str(station_id)},
        )
    
    # Get tracks for station
    tracks = await track_service.get_tracks_for_station(station_id)
    
    # Build response with artist names
    track_responses = []
    for track in tracks:
        track_dict = {
            "id": track.id,
            "title": track.title,
            "artist_id": track.artist_id,
            "artist_name": track.artist.name if track.artist else None,
            "duration_seconds": track.duration_seconds,
            "file_path": track.file_path,
            "file_size": track.file_size,
            "file_format": track.file_format
        }
        track_responses.append(TrackResponse(**track_dict))
    
    logger.info("station_tracks_retrieved", station_id=str(station_id), track_count=len(track_responses))
    return track_responses

