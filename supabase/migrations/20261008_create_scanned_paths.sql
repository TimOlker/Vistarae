-- Migration: 20261008_create_scanned_paths.sql
-- Tracks all ingested photo folder paths, their extraction status, and links to POIs

CREATE TABLE IF NOT EXISTS scanned_paths (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    poi_id UUID REFERENCES pois(id) ON DELETE SET NULL,

    folder_path TEXT NOT NULL,
    folder_name TEXT NOT NULL,
    parent_folder TEXT,

    -- Lifecycle status: 'pending', 'identified', 'location unknown', 'skipped'
    status VARCHAR(30) NOT NULL DEFAULT 'pending',

    -- Extracted location attributes
    site_name TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    country_code VARCHAR(10),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    -- Confidence & Diagnostics
    confidence VARCHAR(20) DEFAULT 'medium',
    reasoning TEXT,
    raw_llm_json JSONB,
    nominatim_raw JSONB,

    -- File metrics
    photo_count INT DEFAULT 0,
    earliest_date DATE,
    latest_date DATE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_folder_path UNIQUE (user_id, folder_path)
);

CREATE INDEX IF NOT EXISTS idx_scanned_paths_user_status ON scanned_paths(user_id, status);
CREATE INDEX IF NOT EXISTS idx_scanned_paths_poi_id ON scanned_paths(poi_id);
CREATE INDEX IF NOT EXISTS idx_scanned_paths_location ON scanned_paths(country, state, city);
