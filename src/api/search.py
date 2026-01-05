"""Search API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID
from cloudsound_shared.db.pool import get_db
from ..services.search_service import SearchService
from ..models import Artist, Track
from cloudsound_shared.logging import get_logger
from cloudsound_shared.metrics import http_requests_total, http_request_duration_seconds
from ..metrics import search_queries_total, search_results_total, search_duration_seconds
import time

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


class ArtistSearchResult(BaseModel):
    """Artist search result model."""
    id: UUID
    name: str
    genre: Optional[str] = None
    bio: Optional[str] = None
    track_count: int = 0
    
    class Config:
        from_attributes = True


class TrackSearchResult(BaseModel):
    """Track search result model."""
    id: UUID
    title: str
    artist_id: UUID
    artist_name: Optional[str] = None
    duration_seconds: int
    file_path: str
    file_size: int
    file_format: str
    
    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Search response model."""
    query: str
    artists: List[ArtistSearchResult]
    tracks: List[TrackSearchResult]
    total_results: int


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query string", min_length=1, max_length=255),
    limit: int = Query(50, description="Maximum results per type (artists and tracks)", ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> SearchResponse:
    """
    Search for artists and tracks by name/title.
    
    Returns matching artists and tracks based on the search query.
    """
    start_time = time.time()
    
    logger.info("search_request", query=q, limit=limit)
    
    # Increment request counter
    http_requests_total.labels(method="GET", endpoint="/search", status="processing").inc()
    
    try:
        service = SearchService(db)
        artists, tracks = await service.search(q, limit=limit)
        
        # Build artist results
        artist_results = []
        for artist in artists:
            artist_dict = {
                "id": artist.id,
                "name": artist.name,
                "genre": artist.genre,
                "bio": artist.bio,
                "track_count": len(artist.tracks) if artist.tracks else 0
            }
            artist_results.append(ArtistSearchResult(**artist_dict))
        
        # Build track results
        track_results = []
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
            track_results.append(TrackSearchResult(**track_dict))
        
        total_results = len(artist_results) + len(track_results)
        
        # Record metrics
        duration = time.time() - start_time
        http_request_duration_seconds.labels(method="GET", endpoint="/search").observe(duration)
        http_requests_total.labels(method="GET", endpoint="/search", status="success").inc()
        search_queries_total.labels(query_type="combined").inc()
        search_results_total.labels(result_type="artists").inc(len(artist_results))
        search_results_total.labels(result_type="tracks").inc(len(track_results))
        search_duration_seconds.observe(duration)
        
        logger.info(
            "search_completed",
            query=q,
            artists_count=len(artist_results),
            tracks_count=len(track_results),
            total_results=total_results,
            duration_seconds=duration
        )
        
        return SearchResponse(
            query=q,
            artists=artist_results,
            tracks=track_results,
            total_results=total_results
        )
    
    except Exception as e:
        # Record error metrics
        duration = time.time() - start_time
        http_request_duration_seconds.labels(method="GET", endpoint="/search").observe(duration)
        http_requests_total.labels(method="GET", endpoint="/search", status="error").inc()
        
        logger.error("search_error", query=q, error=str(e), exc_info=True)
        raise

