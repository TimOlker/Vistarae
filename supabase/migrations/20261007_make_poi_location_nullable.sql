-- Migration: 20261007_make_poi_location_nullable.sql
-- Allows POIs to be created without coordinates when location cannot be determined
ALTER TABLE pois ALTER COLUMN location DROP NOT NULL;
