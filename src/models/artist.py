"""Artist model for radio streaming service."""
from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.orm import relationship
from cloudsound_shared.models.base import Base, UUIDMixin, TimestampMixin
from cloudsound_shared.multitenancy import TenantMixin


class Artist(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Artist model representing a music artist with tenant isolation."""
    
    __tablename__ = "artists"
    
    name = Column(String(255), nullable=False, index=True)  # Unique per tenant
    genre = Column(String(100), nullable=True, index=True)
    bio = Column(String(2000), nullable=True)
    
    # Unique artist name within tenant
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_artists_tenant_name'),
    )
    
    # Relationships
    tracks = relationship("Track", back_populates="artist", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Artist(id={self.id}, name='{self.name}', genre='{self.genre}', tenant_id={self.tenant_id})>"

