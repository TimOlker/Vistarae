"""SQLAlchemy ORM models for Vistarae."""

import uuid
from datetime import date, datetime
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, server_default=func.clock_timestamp()
    )

    pois: Mapped[list["POI"]] = relationship(
        "POI", back_populates="user", cascade="all, delete-orphan"
    )
    lists: Mapped[list["ListModel"]] = relationship(
        "ListModel", back_populates="user", cascade="all, delete-orphan"
    )
    tags: Mapped[list["UserTag"]] = relationship(
        "UserTag", back_populates="user", cascade="all, delete-orphan"
    )


class POI(Base):
    __tablename__ = "pois"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
    poi_type: Mapped[str] = mapped_column(String(50), nullable=False)
    personal_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
    visited: Mapped[bool] = mapped_column(Boolean, default=False)
    visit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    visit_dates: Mapped[list[date] | None] = mapped_column(ARRAY(Date), default=list)
    visit_again: Mapped[bool] = mapped_column(Boolean, default=False)

    # PostGIS Geography Point (4326) - nullable when location cannot be determined
    location: Mapped[str | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    geofence_radius_ft: Mapped[int] = mapped_column(Integer, default=500)

    parent_poi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pois.id", ondelete="SET NULL"), nullable=True
    )
    physical_effort: Mapped[str | None] = mapped_column(String(50), nullable=True)
    booking_lead_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    indoor_outdoor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estimated_duration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hours_seasonality: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_time_to_visit: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_official: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    google_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternate_image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # IPTC standard location metadata
    iptc_sublocation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    iptc_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    iptc_province_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    iptc_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    iptc_world_region: Mapped[str | None] = mapped_column(Text, nullable=True)
    iptc_zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )

    # Relationships
    access_points: Mapped[list["POIAccessPoint"]] = relationship(
        "POIAccessPoint", back_populates="poi", cascade="all, delete-orphan", lazy="selectin"
    )
    lists: Mapped[list["ListModel"]] = relationship(
        "ListModel", secondary="poi_list_memberships", back_populates="pois", lazy="selectin"
    )
    parent: Mapped[Optional["POI"]] = relationship(
        "POI", remote_side=[id], backref="children", lazy="selectin"
    )
    user: Mapped["User"] = relationship("User", back_populates="pois")
    scanned_paths: Mapped[list["ScannedPath"]] = relationship(
        "ScannedPath", back_populates="poi", lazy="selectin"
    )


class POIAccessPoint(Base):
    __tablename__ = "poi_access_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pois.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    parking_logistics: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )

    poi: Mapped["POI"] = relationship("POI", back_populates="access_points")


class ListModel(Base):
    __tablename__ = "lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_trip: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )

    user: Mapped["User"] = relationship("User", back_populates="lists")
    pois: Mapped[list["POI"]] = relationship(
        "POI", secondary="poi_list_memberships", back_populates="lists"
    )


class POIListMembership(Base):
    __tablename__ = "poi_list_memberships"

    poi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pois.id", ondelete="CASCADE"), primary_key=True
    )
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lists.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class Geocache(Base):
    __tablename__ = "geocache"

    query_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class UserTag(Base):
    __tablename__ = "user_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )

    user: Mapped["User"] = relationship("User", back_populates="tags")


class ScannedPath(Base):
    __tablename__ = "scanned_paths"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    poi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pois.id", ondelete="SET NULL"), nullable=True, index=True
    )

    folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    folder_name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_folder: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)

    site_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    confidence: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    nominatim_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    photo_count: Mapped[int] = mapped_column(Integer, default=0)
    earliest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    latest_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Multi-POI conflict tracking
    conflict_poi_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list
    )
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    conflict_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )

    poi: Mapped[Optional["POI"]] = relationship("POI", back_populates="scanned_paths")
    user: Mapped["User"] = relationship("User")
