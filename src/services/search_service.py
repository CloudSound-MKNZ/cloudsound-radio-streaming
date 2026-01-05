"""Search service for artists and tracks."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List, Tuple
from ..models import Artist, Track
from cloudsound_shared.logging import get_logger

logger = get_logger(__name__)


class SearchService:
    """Service for searching artists and tracks."""
    
    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
    
    async def search(self, query_text: str, limit: int = 50) -> Tuple[List[Artist], List[Track]]:
        """
        Search for artists and tracks by name/title.
        
        Args:
            query_text: Search query string
            limit: Maximum number of results per type (artists and tracks)
        
        Returns:
            Tuple of (artists, tracks) matching the search query
        """
        if not query_text or not query_text.strip():
            logger.info("empty_search_query")
            return [], []
        
        # Normalize query text (strip whitespace, prepare for ILIKE)
        query_text = query_text.strip()
        search_pattern = f"%{query_text}%"
        
        # Search artists by name
        artists_query = select(Artist).where(
            Artist.name.ilike(search_pattern)
        ).limit(limit)
        artists_query = artists_query.options(selectinload(Artist.tracks))
        
        # Search tracks by title
        tracks_query = select(Track).where(
            Track.title.ilike(search_pattern)
        ).limit(limit)
        tracks_query = tracks_query.options(selectinload(Track.artist))
        
        # Execute both queries
        artists_result = await self.db.execute(artists_query)
        tracks_result = await self.db.execute(tracks_query)
        
        artists = list(artists_result.scalars().all())
        tracks = list(tracks_result.scalars().all())
        
        logger.info(
            "search_completed",
            query=query_text,
            artists_count=len(artists),
            tracks_count=len(tracks),
            limit=limit
        )
        
        return artists, tracks
    
    async def search_artists(self, query_text: str, limit: int = 50) -> List[Artist]:
        """Search for artists by name."""
        if not query_text or not query_text.strip():
            logger.info("empty_artist_search_query")
            return []
        
        query_text = query_text.strip()
        search_pattern = f"%{query_text}%"
        
        query = select(Artist).where(
            Artist.name.ilike(search_pattern)
        ).limit(limit)
        query = query.options(selectinload(Artist.tracks))
        
        result = await self.db.execute(query)
        artists = list(result.scalars().all())
        
        logger.info("artist_search_completed", query=query_text, count=len(artists))
        return artists
    
    async def search_tracks(self, query_text: str, limit: int = 50) -> List[Track]:
        """Search for tracks by title."""
        if not query_text or not query_text.strip():
            logger.info("empty_track_search_query")
            return []
        
        query_text = query_text.strip()
        search_pattern = f"%{query_text}%"
        
        query = select(Track).where(
            Track.title.ilike(search_pattern)
        ).limit(limit)
        query = query.options(selectinload(Track.artist))
        
        result = await self.db.execute(query)
        tracks = list(result.scalars().all())
        
        logger.info("track_search_completed", query=query_text, count=len(tracks))
        return tracks

