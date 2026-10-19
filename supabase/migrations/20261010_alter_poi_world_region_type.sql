-- Migration: 20261010_alter_poi_world_region_type.sql
-- Allow arbitrary length country/region names (e.g. transnational UNESCO sites)

ALTER TABLE pois ALTER COLUMN iptc_world_region TYPE TEXT;
