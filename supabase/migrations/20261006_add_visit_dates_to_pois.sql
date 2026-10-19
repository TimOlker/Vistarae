-- Migration: 20261006_add_visit_dates_to_pois.sql
-- Adds visit_dates array to pois table to track multiple visit dates

ALTER TABLE pois ADD COLUMN IF NOT EXISTS visit_dates DATE[] DEFAULT '{}';
