"""Radio station service for managing radio stations."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from ..models import RadioStation, StationType, StationTrack
from cloudsound_shared.logging import get_logger

logger = get_logger(__name__)


class RadioStationService:
    """Service for managing radio stations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
    
    async def get_all_stations(self, active_only: bool = True) -> List[RadioStation]:
        """Get all radio stations, optionally filtering by active status."""
        query = select(RadioStation)
        
        if active_only:
            query = query.where(RadioStation.is_active == True)
        
        query = query.options(
            selectinload(RadioStation.station_tracks).selectinload(StationTrack.track)
        )
        
        result = await self.db.execute(query)
        stations = result.scalars().all()
        
        logger.info("retrieved_stations", count=len(stations), active_only=active_only)
        return list(stations)
    
    async def get_station_by_id(self, station_id: UUID) -> Optional[RadioStation]:
        """Get a radio station by ID."""
        query = select(RadioStation).where(RadioStation.id == station_id)
        query = query.options(
            selectinload(RadioStation.station_tracks).selectinload(StationTrack.track)
        )
        
        result = await self.db.execute(query)
        station = result.scalar_one_or_none()
        
        if station:
            logger.info("retrieved_station", station_id=str(station_id), station_name=station.name)
        else:
            logger.warning("station_not_found", station_id=str(station_id))
        
        return station
    
    async def get_stations_by_type(self, station_type: StationType, active_only: bool = True) -> List[RadioStation]:
        """Get radio stations by type."""
        query = select(RadioStation).where(RadioStation.type == station_type)
        
        if active_only:
            query = query.where(RadioStation.is_active == True)
        
        query = query.options(
            selectinload(RadioStation.station_tracks).selectinload(StationTrack.track)
        )
        
        result = await self.db.execute(query)
        stations = result.scalars().all()
        
        logger.info("retrieved_stations_by_type", type=station_type.value, count=len(stations))
        return list(stations)
    
    async def get_stations_by_genre(self, genre: str, active_only: bool = True) -> List[RadioStation]:
        """Get radio stations by genre."""
        query = select(RadioStation).where(
            and_(
                RadioStation.type == StationType.GENRE,
                RadioStation.genre == genre
            )
        )
        
        if active_only:
            query = query.where(RadioStation.is_active == True)
        
        query = query.options(
            selectinload(RadioStation.station_tracks).selectinload(StationTrack.track)
        )
        
        result = await self.db.execute(query)
        stations = result.scalars().all()
        
        logger.info("retrieved_stations_by_genre", genre=genre, count=len(stations))
        return list(stations)

