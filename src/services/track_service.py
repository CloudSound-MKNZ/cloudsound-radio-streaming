"""Track service for managing music tracks."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from ..models import Track, Artist, StationTrack
from cloudsound_shared.logging import get_logger

logger = get_logger(__name__)


class TrackService:
    """Service for managing music tracks."""
    
    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
    
    async def get_track_by_id(self, track_id: UUID) -> Optional[Track]:
        """Get a track by ID."""
        query = select(Track).where(Track.id == track_id)
        query = query.options(selectinload(Track.artist))
        
        result = await self.db.execute(query)
        track = result.scalar_one_or_none()
        
        if track:
            logger.info("retrieved_track", track_id=str(track_id), track_title=track.title)
        else:
            logger.warning("track_not_found", track_id=str(track_id))
        
        return track
    
    async def get_tracks_by_artist(self, artist_id: UUID) -> List[Track]:
        """Get all tracks by an artist."""
        query = select(Track).where(Track.artist_id == artist_id)
        query = query.options(selectinload(Track.artist))
        
        result = await self.db.execute(query)
        tracks = result.scalars().all()
        
        logger.info("retrieved_tracks_by_artist", artist_id=str(artist_id), count=len(tracks))
        return list(tracks)
    
    async def search_tracks(self, query_text: str, limit: int = 50) -> List[Track]:
        """Search tracks by title."""
        query = select(Track).where(Track.title.ilike(f"%{query_text}%"))
        query = query.limit(limit)
        query = query.options(selectinload(Track.artist))
        
        result = await self.db.execute(query)
        tracks = result.scalars().all()
        
        logger.info("searched_tracks", query=query_text, count=len(tracks))
        return list(tracks)
    
    async def get_tracks_for_station(self, station_id: UUID) -> List[Track]:
        """Get all tracks for a radio station, ordered by station_track.order."""
        
        query = select(Track).join(StationTrack).where(StationTrack.station_id == station_id)
        query = query.order_by(StationTrack.order)
        query = query.options(selectinload(Track.artist))
        
        result = await self.db.execute(query)
        tracks = result.scalars().all()
        
        logger.info("retrieved_tracks_for_station", station_id=str(station_id), count=len(tracks))
        return list(tracks)

