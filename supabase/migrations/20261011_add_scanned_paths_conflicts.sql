-- Migration: 20261011_add_scanned_paths_conflicts.sql
-- Adds multi-POI conflict tracking to scanned_paths so folders in use by multiple POIs can be flagged and manually refactored.

ALTER TABLE scanned_paths ADD COLUMN IF NOT EXISTS conflict_poi_ids UUID[] DEFAULT '{}';
ALTER TABLE scanned_paths ADD COLUMN IF NOT EXISTS has_conflict BOOLEAN DEFAULT FALSE;
ALTER TABLE scanned_paths ADD COLUMN IF NOT EXISTS conflict_note TEXT;

CREATE INDEX IF NOT EXISTS idx_scanned_paths_conflict ON scanned_paths(has_conflict) WHERE has_conflict = TRUE;
CREATE INDEX IF NOT EXISTS idx_scanned_paths_conflict_poi_ids ON scanned_paths USING GIN(conflict_poi_ids);
