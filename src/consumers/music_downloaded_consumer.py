"""Consumer for music.downloaded events from music-discovery service.

This consumer listens for downloaded music events and creates Track records
in the radio streaming database, making them available for radio stations.
"""
import asyncio
import threading
import os
from typing import Optional, Dict, Any
from uuid import uuid4

from cloudsound_shared.kafka import KafkaConsumerClient
from cloudsound_shared.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from ..models import Track, Artist, StationTrack, RadioStation, StationType

logger = get_logger(__name__)

MUSIC_DOWNLOADED_TOPIC = "music.downloaded"


class MusicDownloadedConsumer:
    """Consumer for music downloaded events.
    
    When a track is downloaded by the music-discovery service, this consumer:
    1. Creates or finds the Artist record
    2. Creates a Track record with file path pointing to MinIO
    3. Links the track to appropriate radio stations based on concert context
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "cloudsound-kafka:9092",
        group_id: str = "radio-streaming",
    ):
        """Initialize consumer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
            group_id: Consumer group ID
        """
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self._consumer: Optional[KafkaConsumerClient] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._session_factory = None
        
        logger.info(
            "music_downloaded_consumer_initialized",
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
        )
    
    def start(self) -> None:
        """Start consuming messages in a background thread."""
        if self._running:
            logger.warning("music_downloaded_consumer_already_running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="music-downloaded-consumer")
        self._thread.start()
        
        logger.info("music_downloaded_consumer_started")
    
    def stop(self) -> None:
        """Stop consuming messages."""
        self._running = False
        if self._consumer:
            self._consumer.close()
        
        logger.info("music_downloaded_consumer_stopped")
    
    def _run(self) -> None:
        """Run the consumer loop."""
        try:
            # Create a dedicated event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create a dedicated database session factory for this thread's event loop
            # Build database URL from individual env vars
            pg_user = os.getenv("POSTGRES_USER", "cloudsound")
            pg_pass = os.getenv("POSTGRES_PASSWORD", "cloudsound")
            pg_host = os.getenv("POSTGRES_HOST", "cloudsound-postgresql")
            pg_port = os.getenv("POSTGRES_PORT", "5432")
            pg_db = os.getenv("POSTGRES_DB", "cloudsound")
            database_url = os.getenv("DATABASE_URL", f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}")
            engine = create_async_engine(database_url, pool_size=5, max_overflow=10)
            self._session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            
            logger.info("music_downloaded_consumer_db_connected")
            
            self._consumer = KafkaConsumerClient(
                topics=[MUSIC_DOWNLOADED_TOPIC],
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
            )
            
            logger.info(
                "music_downloaded_consumer_consuming",
                topic=MUSIC_DOWNLOADED_TOPIC,
            )
            
            for message in self._consumer.consume():
                if not self._running:
                    break
                
                try:
                    # message is a ConsumerRecord, message.value is the deserialized dict
                    loop.run_until_complete(self._process_message(message.value))
                except Exception as e:
                    logger.error(
                        "music_downloaded_message_processing_failed",
                        error=str(e),
                    )
                    
        except Exception as e:
            logger.error(
                "music_downloaded_consumer_error",
                error=str(e),
            )
        finally:
            self._running = False
            if loop:
                loop.close()
    
    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process a music.downloaded message.
        
        Args:
            message: The Kafka message value containing download info
        """
        logger.info(
            "music_downloaded_message_received",
            url=message.get("url"),
            title=message.get("title"),
        )
        
        # Extract data from message
        url = message.get("url", "")
        file_path = message.get("file_path", "")
        title = message.get("title", "Unknown Track")
        artist_name = message.get("artist", "Unknown Artist")
        duration = message.get("duration", 0)
        file_size = message.get("file_size", 0)
        source = message.get("source", "unknown")
        context = message.get("context", {})
        
        if not file_path:
            logger.warning("music_downloaded_no_file_path", url=url)
            return
        
        # Use the thread's own session factory
        if not self._session_factory:
            logger.error("music_downloaded_no_session_factory")
            return
        
        async with self._session_factory() as session:
            try:
                # 1. Get or create artist
                artist = await self._get_or_create_artist(session, artist_name)
                
                # 2. Create track
                track = await self._create_track(
                    session=session,
                    title=title,
                    artist_id=artist.id,
                    file_path=file_path,
                    file_size=file_size,
                    duration=duration,
                    source_url=url,
                )
                
                # 3. Link to stations based on context
                await self._link_to_stations(session, track, context)
                
                await session.commit()
                
                logger.info(
                    "music_downloaded_track_created",
                    track_id=str(track.id),
                    title=title,
                    artist=artist_name,
                    file_path=file_path,
                )
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "music_downloaded_track_creation_failed",
                    error=str(e),
                    url=url,
                )
                raise
    
    async def _get_or_create_artist(
        self,
        session: AsyncSession,
        artist_name: str,
    ) -> Artist:
        """Get existing artist or create new one.
        
        Args:
            session: Database session
            artist_name: Artist name
            
        Returns:
            Artist record
        """
        # Try to find existing artist
        query = select(Artist).where(Artist.name == artist_name)
        result = await session.execute(query)
        artist = result.scalar_one_or_none()
        
        if artist:
            return artist
        
        # Create new artist - use a fixed UUID for default tenant
        DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"
        artist = Artist(
            id=uuid4(),
            name=artist_name,
            tenant_id=DEFAULT_TENANT_ID,
        )
        session.add(artist)
        await session.flush()
        
        logger.info("artist_created", artist_id=str(artist.id), name=artist_name)
        return artist
    
    async def _create_track(
        self,
        session: AsyncSession,
        title: str,
        artist_id,
        file_path: str,
        file_size: int,
        duration: int,
        source_url: str,
    ) -> Track:
        """Create a new track record.
        
        Args:
            session: Database session
            title: Track title
            artist_id: Artist UUID
            file_path: Path in MinIO storage
            file_size: File size in bytes
            duration: Duration in seconds
            source_url: Original source URL
            
        Returns:
            Created Track record
        """
        # Determine file format from path
        file_format = "mp3"
        if file_path.endswith(".m4a"):
            file_format = "m4a"
        elif file_path.endswith(".opus"):
            file_format = "opus"
        elif file_path.endswith(".webm"):
            file_format = "webm"
        
        # Use a fixed UUID for default tenant
        DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"
        track = Track(
            id=uuid4(),
            title=title,
            artist_id=artist_id,
            file_path=file_path,
            file_size=file_size,
            duration_seconds=duration,
            file_format=file_format,
            tenant_id=DEFAULT_TENANT_ID,
        )
        session.add(track)
        await session.flush()
        
        return track
    
    async def _link_to_stations(
        self,
        session: AsyncSession,
        track: Track,
        context: Dict[str, Any],
    ) -> None:
        """Link track to appropriate radio stations.
        
        Args:
            session: Database session
            track: The track to link
            context: Context from download (may include concert_id)
        """
        # Get all active stations
        query = select(RadioStation).where(RadioStation.is_active == True)
        result = await session.execute(query)
        stations = result.scalars().all()
        
        for station in stations:
            should_link = False
            
            # Link to "Upcoming Bands" station for concert-related tracks
            if station.type == StationType.UPCOMING:
                concert_id = context.get("concert_id")
                if concert_id:
                    should_link = True
            
            # Link to "Past Performers" station as well
            elif station.type == StationType.PAST:
                # Also add to past performers for variety
                should_link = True
            
            # For now, also add to the first genre station we find
            elif station.type == StationType.GENRE:
                should_link = True  # Add to all genre stations for now
            
            if should_link:
                # Get max order for this station
                order_query = select(StationTrack.order).where(
                    StationTrack.station_id == station.id
                ).order_by(StationTrack.order.desc()).limit(1)
                order_result = await session.execute(order_query)
                max_order = order_result.scalar_one_or_none() or 0
                
                station_track = StationTrack(
                    id=uuid4(),
                    station_id=station.id,
                    track_id=track.id,
                    order=max_order + 1,
                )
                session.add(station_track)
                
                logger.info(
                    "track_linked_to_station",
                    track_id=str(track.id),
                    station_id=str(station.id),
                    station_name=station.name,
                )

