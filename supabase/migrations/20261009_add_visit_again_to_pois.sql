-- Migration: 20261009_add_visit_again_to_pois.sql
-- Adds visit_again boolean to pois table to track places to re-visit

ALTER TABLE pois ADD COLUMN IF NOT EXISTS visit_again BOOLEAN NOT NULL DEFAULT FALSE;
