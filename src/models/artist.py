"""Artist model for radio streaming service."""
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from cloudsound_shared.models.base import Base, UUIDMixin, TimestampMixin


class Artist(Base, UUIDMixin, TimestampMixin):
    """Artist model representing a music artist."""
    
    __tablename__ = "artists"
    
    name = Column(String(255), nullable=False, unique=True, index=True)
    genre = Column(String(100), nullable=True, index=True)
    bio = Column(String(2000), nullable=True)
    
    # Relationships
    tracks = relationship("Track", back_populates="artist", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Artist(id={self.id}, name='{self.name}', genre='{self.genre}')>"

