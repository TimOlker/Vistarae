# Data Model: Unified POI Import Staging Workbench (015-poi-export-import-enhancements-v3)

**Feature**: `015-poi-export-import-enhancements-v3`  
**Date**: 2026-11-02  
**Status**: Completed  

---

## 1. Database Schema & Tables

### 1.1 `pois` (Points of Interest)

Stores canonical, user-owned travel points of interest with normalized ISO administrative layers.

```sql
CREATE TABLE pois (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    parent_poi_id UUID REFERENCES pois(id) ON DELETE SET NULL,
    description TEXT,
    reason_to_visit TEXT,
    
    -- Micro / Postal Layer
    street_address VARCHAR(255),
    postal_code VARCHAR(20),
    geom GEOGRAPHY(Point, 4326) NOT NULL,
    latitude DOUBLE PRECISION GENERATED ALWAYS AS (ST_Y(geom::geometry)) STORED,
    longitude DOUBLE PRECISION GENERATED ALWAYS AS (ST_X(geom::geometry)) STORED,
    
    -- Macro / Administrative Layer (ISO 3166-1 alpha-2)
    country_code CHAR(2) NOT NULL DEFAULT 'US',
    admin_level_1 VARCHAR(100), -- State, Province, Autonomous Region, Constituent Country
    admin_level_2 VARCHAR(100), -- County, Department, Prefecture, District
    locality VARCHAR(150),      -- City, Town, Municipality, Village
    raw_geocoding JSONB,        -- Full geocoder response payload
    
    -- Rich Metadata & Arrays
    official_url TEXT,
    wiki_url TEXT,
    related_websites JSONB NOT NULL DEFAULT '[]'::jsonb,
    image_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    photo_directories JSONB NOT NULL DEFAULT '[]'::jsonb,
    dates_visited JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Planning & State
    visit_state VARCHAR(32) NOT NULL DEFAULT 'NOT_VISITED',
    recommended_duration_hours NUMERIC(4, 2),
    recommended_visit_days INTEGER NOT NULL DEFAULT 1,
    estimated_visit_time_notes TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_pois_user_id ON pois(user_id);
CREATE INDEX idx_pois_geom ON pois USING GIST(geom);
CREATE INDEX idx_pois_name_trgm ON pois USING GIN(name gin_trgm_ops);
CREATE INDEX idx_pois_iso_location ON pois(country_code, admin_level_1, locality);
```

---

### 1.2 `ingest_candidates` (Staged Import Candidates)

Stores staged records during import triage and enrichment before committing to `pois`.

```sql
CREATE TABLE ingest_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES ingest_jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    poi_name VARCHAR(255) NOT NULL,
    
    -- Triage & Disposition
    recommended_disposition VARCHAR(32) NOT NULL DEFAULT 'accept',
    user_disposition VARCHAR(32),
    confidence_score INTEGER NOT NULL DEFAULT 0 CHECK (confidence_score BETWEEN 0 AND 100),
    disposition_justification TEXT,
    is_user_overridden BOOLEAN NOT NULL DEFAULT FALSE,
    is_duplicate BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Relationships & Hierarchy
    matched_existing_poi_id UUID REFERENCES pois(id) ON DELETE SET NULL,
    parent_poi_id UUID REFERENCES pois(id) ON DELETE SET NULL,
    parent_candidate_id UUID REFERENCES ingest_candidates(id) ON DELETE SET NULL,
    merge_target_id UUID REFERENCES ingest_candidates(id) ON DELETE SET NULL,
    
    -- Micro / Postal Coordinates
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    street_address VARCHAR(255),
    postal_code VARCHAR(20),
    
    -- Macro / Administrative Layer (ISO 3166-1 alpha-2)
    country_code CHAR(2) NOT NULL DEFAULT 'US',
    admin_level_1 VARCHAR(100),
    admin_level_2 VARCHAR(100),
    locality VARCHAR(150),
    raw_geocoding JSONB,
    
    -- Rich Metadata & Arrays
    hero_image_url TEXT,
    official_url TEXT,
    wiki_url TEXT,
    related_websites JSONB NOT NULL DEFAULT '[]'::jsonb,
    photo_directory VARCHAR(500),
    photo_directories JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    dates_visited JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT,
    reason_to_visit TEXT,
    
    -- Duration & State
    recommended_duration_hours NUMERIC(4, 2),
    recommended_visit_days INTEGER,
    estimated_visit_time_notes TEXT,
    no_websites BOOLEAN NOT NULL DEFAULT FALSE,
    phase_state VARCHAR(32) NOT NULL DEFAULT 'phase_1_triage',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_candidates_job_id ON ingest_candidates(job_id);
CREATE INDEX idx_candidates_user_id ON ingest_candidates(user_id);
CREATE INDEX idx_candidates_iso_location ON ingest_candidates(country_code, admin_level_1, locality);
```

---

## 2. Domain Value Objects & Entities

### 2.1 `AddressRecord` Value Object

```python
class AddressRecord(StrictBaseModel):
    """Normalized international address record supporting ISO administrative tiers."""
    street: str | None = None
    city: str | None = None
    state_province: str | None = None
    postal_code: str | None = None
    country: str | None = None
    
    # ISO Administrative Tiers
    country_code: str | None = "US"
    admin_level_1: str | None = None
    admin_level_2: str | None = None
    locality: str | None = None
    raw_geocoding: dict[str, Any] | None = None
```

### 2.2 `IngestCandidate` Domain Entity

```python
@dataclass
class IngestCandidate:
    """Core domain model representing a staged POI record."""
    id: UUID
    job_id: UUID
    user_id: UUID
    row_index: int
    poi_name: str
    recommended_disposition: IngestDisposition
    user_disposition: IngestDisposition | None
    
    # Coordinates & Postal
    latitude: float | None
    longitude: float | None
    street_address: str | None
    postal_code: str | None
    
    # ISO Administrative Layers
    country_code: str
    admin_level_1: str | None
    admin_level_2: str | None
    locality: str | None
    raw_geocoding: dict[str, Any] | None
    
    # Associations & Content
    related_websites: list[dict[str, Any]]
    photo_directories: list[str]
    dates_visited: list[str]
    tags: list[str]
    description: str | None
    reason_to_visit: str | None
    hero_image_url: str | None
    confidence_score: int
    disposition_justification: str | None
    no_websites: bool
    phase_state: IngestCandidatePhaseState
    merge_target_id: UUID | None
```

---

## 3. In-Batch Merge Union Semantics

When candidates $C_1, C_2, \dots, C_k$ are merged into surviving target candidate $C_{\text{target}}$:

$$\text{dates\_visited}_{\text{final}} = \text{sort}\left(\bigcup_{i=1}^k \text{dates\_visited}(C_i)\right)$$

$$\text{tags}_{\text{final}} = \bigcup_{i=1}^k \text{tags}(C_i)$$

$$\text{photo\_directories}_{\text{final}} = \bigcup_{i=1}^k \text{photo\_directories}(C_i)$$

$$\text{related\_websites}_{\text{final}} = \text{dedup\_by\_url}\left(\bigcup_{i=1}^k \text{related\_websites}(C_i)\right)$$

The surviving coordinates and administrative tiers default to $C_{\text{target}}$ unless explicitly modified by the user in the detail editor.
