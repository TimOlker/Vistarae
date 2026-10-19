-- Migration: 20261001_init_postgis.sql
-- Enables PostGIS spatial extensions, pg_trgm for fuzzy string matching, and uuid generators

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
