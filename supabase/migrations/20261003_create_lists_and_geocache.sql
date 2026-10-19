-- Migration: 20261003_create_lists_and_geocache.sql
-- Creates lists, poi_list_memberships, and geocache tables

CREATE TABLE IF NOT EXISTS lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    is_trip BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS poi_list_memberships (
    poi_id UUID NOT NULL REFERENCES pois(id) ON DELETE CASCADE,
    list_id UUID NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp(),
    PRIMARY KEY (poi_id, list_id)
);

CREATE INDEX IF NOT EXISTS idx_poi_list_memberships_poi_id ON poi_list_memberships (poi_id);
CREATE INDEX IF NOT EXISTS idx_poi_list_memberships_list_id ON poi_list_memberships (list_id);

-- Geocache table to prevent duplicate calls to OSM Nominatim API
CREATE TABLE IF NOT EXISTS geocache (
    query_hash VARCHAR(64) PRIMARY KEY,
    latitude NUMERIC(10, 7) NOT NULL,
    longitude NUMERIC(10, 7) NOT NULL,
    display_name TEXT,
    raw_json JSONB,
    cached_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_geocache_cached_at ON geocache (cached_at);
