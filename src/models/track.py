"""Track model for radio streaming service."""
from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from cloudsound_shared.models.base import Base, UUIDMixin, TimestampMixin
from cloudsound_shared.multitenancy import TenantMixin


class Track(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Track model representing a music track with tenant isolation."""
    
    __tablename__ = "tracks"
    
    title = Column(String(255), nullable=False, index=True)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False)
    file_path = Column(String(512), nullable=False)  # Path in MinIO/S3
    file_size = Column(Integer, nullable=False)  # Size in bytes
    file_format = Column(String(10), nullable=False, default="mp3")  # mp3, ogg, etc.
    
    # Unique file path within tenant (prevents duplicate uploads)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'file_path', name='uq_tracks_tenant_file_path'),
    )
    
    # Relationships
    artist = relationship("Artist", back_populates="tracks")
    station_tracks = relationship("StationTrack", back_populates="track", cascade="all, delete-orphan")
    # Note: PlaybackEvent is in analytics service, not radio-streaming
    
    def __repr__(self) -> str:
        return f"<Track(id={self.id}, title='{self.title}', artist_id={self.artist_id}, tenant_id={self.tenant_id})>"

