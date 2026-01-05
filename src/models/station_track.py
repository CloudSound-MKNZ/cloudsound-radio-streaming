"""StationTrack junction model for radio streaming service."""
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from cloudsound_shared.models.base import Base, UUIDMixin, TimestampMixin


class StationTrack(Base, UUIDMixin, TimestampMixin):
    """Junction model linking radio stations to tracks with ordering."""
    
    __tablename__ = "station_tracks"
    
    station_id = Column(UUID(as_uuid=True), ForeignKey("radio_stations.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id = Column(UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    order = Column(Integer, nullable=False, default=0)  # Order of track in station playlist
    
    # Unique constraint to prevent duplicate track-station pairs
    __table_args__ = (
        UniqueConstraint('station_id', 'track_id', name='uq_station_track'),
    )
    
    # Relationships
    station = relationship("RadioStation", back_populates="station_tracks")
    track = relationship("Track", back_populates="station_tracks")
    
    def __repr__(self) -> str:
        return f"<StationTrack(id={self.id}, station_id={self.station_id}, track_id={self.track_id}, order={self.order})>"

