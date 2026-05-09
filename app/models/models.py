from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    industry = Column(String(100), nullable=False)
    location = Column(String(255), default="")
    phone = Column(String(50), default="")
    website_url = Column(String(500), default="")
    logo_url = Column(String(500), default="")
    brand_color_primary = Column(String(7), default="#1a73e8")
    brand_color_secondary = Column(String(7), default="#ffffff")
    tone = Column(String(50), default="professional")
    target_audience = Column(Text, default="")
    services = Column(Text, default="")
    posting_days = Column(String(100), default="tuesday,friday")
    posting_time = Column(String(10), default="10:00")
    timezone = Column(String(50), default="America/Chicago")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    platforms = relationship("PlatformCredential", back_populates="business", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="business", cascade="all, delete-orphan")


class PlatformCredential(Base):
    __tablename__ = "platform_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    platform = Column(String(50), nullable=False)
    credentials = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="platforms")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    content_text = Column(Text, nullable=False)
    image_path = Column(String(500), default="")
    post_type = Column(String(50), default="promotional")
    scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="posts")
    deliveries = relationship("PostDelivery", back_populates="post", cascade="all, delete-orphan")


class PostDelivery(Base):
    __tablename__ = "post_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    platform = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")
    platform_post_id = Column(String(255), default="")
    error_message = Column(Text, default="")
    delivered_at = Column(DateTime, nullable=True)

    post = relationship("Post", back_populates="deliveries")
