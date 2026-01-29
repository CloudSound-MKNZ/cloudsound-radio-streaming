"""Track model for radio streaming service."""
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from cloudsound_shared.models.base import Base, UUIDMixin, TimestampMixin


class Track(Base, UUIDMixin, TimestampMixin):
    """Track model representing a music track."""
    
    __tablename__ = "tracks"
    
    title = Column(String(255), nullable=False, index=True)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False)
    file_path = Column(String(512), nullable=False)  # Path in MinIO/S3
    file_size = Column(Integer, nullable=False)  # Size in bytes
    file_format = Column(String(10), nullable=False, default="mp3")  # mp3, ogg, etc.
    
    # Relationships
    artist = relationship("Artist", back_populates="tracks")
    station_tracks = relationship("StationTrack", back_populates="track", cascade="all, delete-orphan")
    # Note: PlaybackEvent is in analytics service, not radio-streaming
    
    def __repr__(self) -> str:
        return f"<Track(id={self.id}, title='{self.title}', artist_id={self.artist_id})>"

