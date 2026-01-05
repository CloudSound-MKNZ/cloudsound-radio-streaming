"""RadioStation model for radio streaming service."""
from sqlalchemy import Column, String, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from cloudsound_shared.models.base import Base, UUIDMixin, TimestampMixin


class StationType(str, enum.Enum):
    """Radio station type enumeration."""
    UPCOMING = "upcoming"  # Music from upcoming performers
    PAST = "past"  # Music from past performers
    GENRE = "genre"  # Music organized by genre


class RadioStation(Base, UUIDMixin, TimestampMixin):
    """RadioStation model representing a radio station."""
    
    __tablename__ = "radio_stations"
    
    name = Column(String(255), nullable=False, unique=True, index=True)
    type = Column(SQLEnum(StationType), nullable=False, index=True)
    genre = Column(String(100), nullable=True, index=True)  # Only used when type is GENRE
    description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    station_tracks = relationship("StationTrack", back_populates="station", cascade="all, delete-orphan", order_by="StationTrack.order")
    # Note: PlaybackEvent is in analytics service, not radio-streaming
    
    def __repr__(self) -> str:
        return f"<RadioStation(id={self.id}, name='{self.name}', type='{self.type}')>"

