-- Migration: 20261002_create_pois_and_access_points.sql
-- Creates pois and poi_access_points tables with spatial columns, constraints, and GiST indexes

CREATE TABLE IF NOT EXISTS pois (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    name_aliases TEXT[] DEFAULT '{}',
    poi_type VARCHAR(50) NOT NULL CHECK (poi_type IN ('photo location', 'site to see', 'experience', 'food/drink', 'lodging', 'transit')),
    personal_rating INT CHECK (personal_rating BETWEEN 1 AND 5),
    description TEXT,
    category_tags TEXT[] DEFAULT '{}',
    visited BOOLEAN DEFAULT FALSE,
    visit_date DATE NULL,
    location GEOGRAPHY(Point, 4326) NOT NULL,
    geofence_radius_ft INT DEFAULT 500,
    parent_poi_id UUID NULL REFERENCES pois(id) ON DELETE SET NULL,
    physical_effort VARCHAR(50),
    booking_lead_time VARCHAR(50),
    indoor_outdoor VARCHAR(20) CHECK (indoor_outdoor IN ('Indoor', 'Outdoor', 'Mixed')),
    estimated_duration VARCHAR(50),
    cost_tier VARCHAR(20),
    hours_seasonality TEXT,
    best_time_to_visit TEXT,
    website_official TEXT,
    phone_number VARCHAR(50),
    google_place_id VARCHAR(255) NULL,
    primary_image_url TEXT,
    alternate_image_urls TEXT[] DEFAULT '{}',
    source_url TEXT NOT NULL,
    source_type VARCHAR(50),
    raw_selected_text TEXT,
    iptc_sublocation VARCHAR(255),
    iptc_city VARCHAR(255),
    iptc_province_state VARCHAR(255),
    iptc_country_code VARCHAR(2),
    iptc_world_region VARCHAR(100),
    iptc_zip_code VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

-- Spatial GiST Index for high-speed spatial proximity queries
CREATE INDEX IF NOT EXISTS idx_pois_location ON pois USING GIST (location);

-- Trigram GIN indexes for fuzzy search on name and aliases
CREATE INDEX IF NOT EXISTS idx_pois_name_trgm ON pois USING GIN (name gin_trgm_ops);

-- Index on parent_poi_id for fast hierarchy queries
CREATE INDEX IF NOT EXISTS idx_pois_parent_id ON pois (parent_poi_id);

-- Access points table
CREATE TABLE IF NOT EXISTS poi_access_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poi_id UUID NOT NULL REFERENCES pois(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    location GEOGRAPHY(Point, 4326) NOT NULL,
    parking_logistics VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_poi_access_points_location ON poi_access_points USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_poi_access_points_poi_id ON poi_access_points (poi_id);
