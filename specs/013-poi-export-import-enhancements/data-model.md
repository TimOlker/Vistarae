<!--
Copyright (c) 2026 Tim Olker

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Phase 13 — Multi-Stage POI Export, Flexible Multi-Fidelity Import & Ingestion Enhancements

**Feature Identifier**: `013-poi-export-import-enhancements`  
**Date**: 2026-10-31  
**Spec Reference**: [spec.md](./spec.md)

---

## 1. Domain Entities & Schemas

### 1.1 `POIExchangeRecord` (Core Schema Contract)
Located in `packages/core/vistarae_core/schemas/poi_exchange.py`.  
This schema defines the authoritative data contract for exporting, importing, and serializing POI datasets across all application phases.

```python
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import Field
from vistarae_core.domain.base import StrictBaseModel
from vistarae_core.domain.enums import IngestDisposition

class POIExchangeRecord(StrictBaseModel):
    """Authoritative data exchange schema for POI export, import, and backup."""
    
    poi_id: Optional[UUID] = Field(
        default=None,
        description="Internal POI UUID; populated for committed POIs, empty for raw candidates."
    )
    poi_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Primary display name of the Point of Interest."
    )
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="WGS-84 decimal latitude coordinate."
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="WGS-84 decimal longitude coordinate."
    )
    street_address: Optional[str] = Field(
        default="",
        description="Semicolon-delimited street address line(s)."
    )
    city: Optional[str] = Field(
        default="",
        description="Town, municipality, or city name."
    )
    state_province: Optional[str] = Field(
        default="",
        description="State, province, or primary administrative region."
    )
    postal_code: Optional[str] = Field(
        default="",
        description="ZIP or postal code."
    )
    country: Optional[str] = Field(
        default="",
        description="Country name or ISO code."
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Approved taxonomy tags associated with the POI."
    )
    dates_visited: List[str] = Field(
        default_factory=list,
        description="Chronological dates when the POI was visited."
    )
    photo_directory: Optional[str] = Field(
        default="",
        description="Originating filesystem folder path."
    )
    location_confidence_percent: Optional[int] = Field(
        default=100,
        ge=0,
        le=100,
        description="Confidence score of location resolution (0-100)."
    )
    user_disposition: Optional[IngestDisposition] = Field(
        default=IngestDisposition.ACCEPT,
        description="Triage disposition: accept, ignore, update_existing, sublocation."
    )
    rejection_reason: Optional[str] = Field(
        default="",
        description="Diagnostic explanation when geocoding or triage fails/ignores a record."
    )
    ai_description: Optional[str] = Field(
        default="",
        description="Synthesized descriptive overview of the POI."
    )
    reason_to_visit: Optional[str] = Field(
        default="",
        description="Personalized rationale aligned with traveler profile."
    )
    recommended_duration_hours: Optional[float] = Field(
        default=2.0,
        ge=0.0,
        description="Recommended dwell time in hours."
    )
    itinerary_days: Optional[int] = Field(
        default=1,
        ge=0,
        description="Allocated itinerary visit days."
    )
    hero_image_url: Optional[str] = Field(
        default="",
        description="Public image URL representing the POI."
    )
    official_website: Optional[str] = Field(
        default="",
        description="Official website or booking URL."
    )
    wikipedia_url: Optional[str] = Field(
        default="",
        description="Authoritative Wikipedia article URL."
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the POI was added to Vistarae."
    )
```

---

### 1.2 Ingest Pre-Validation & Resolution Models

```python
class ColumnMappingRequest(StrictBaseModel):
    """User-confirmed alignment of raw uploaded headers to canonical fields."""
    job_id: UUID
    column_mappings: dict[str, str]  # { "raw_header": "target_field_name" }

class PreValidationIssue(StrictBaseModel):
    """Specific format or type error on an uploaded row."""
    row_number: int
    column: str
    raw_value: str
    expected: str

class PreValidationReport(StrictBaseModel):
    """Diagnostic report returned when pre-import checks discover format issues."""
    total_rows: int
    invalid_row_count: int
    issues: List[PreValidationIssue]
    can_skip_invalid: bool = True

class TagValidationSummary(StrictBaseModel):
    """Summary of unvetted tags requiring user action."""
    unapproved_tags: dict[str, int]  # { "tag_name": occurrence_count }
    total_unapproved_tags: int

class TagResolutionAction(StrEnum):
    APPROVE_AND_ADD = "APPROVE_AND_ADD"
    STRIP_UNAPPROVED = "STRIP_UNAPPROVED"
    ABORT = "ABORT"

class TagResolutionRequest(StrictBaseModel):
    job_id: UUID
    action: TagResolutionAction

class SelectiveEnrichmentOverrides(StrictBaseModel):
    """Granular toggles to force re-calculation of specific fields."""
    recalculate_description: bool = False
    recalculate_reason_to_visit: bool = False
    recalculate_tags: bool = False
    recalculate_duration: bool = False
    recalculate_links: bool = False
```

---

## 2. Database Schema Changes (PostgreSQL / Alembic)

### 2.1 Table: `pois` Migration
Add `created_at` column and user-scoped timestamp index.

```sql
-- Migration revision: 20261031_add_poi_created_at.py

ALTER TABLE pois 
ADD COLUMN created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();

CREATE INDEX idx_pois_user_created_at 
ON pois (user_id, created_at DESC);
```

**Reversible Downgrade**:
```sql
DROP INDEX IF EXISTS idx_pois_user_created_at;
ALTER TABLE pois DROP COLUMN IF EXISTS created_at;
```

---

## 3. Entity Relationships & Lifecycle Transitions

```
Uploaded File (CSV / JSON / YAML)
   │
   ▼
[Format Sniffer & Alias Dictionary]
   │
   ├─► Unmapped Headers? ──► [Interactive Column Mapping Modal] ──► User confirms mappings
   │
   ▼
[Type & Range Sanity Validator]
   │
   ├─► Format Errors? ────► [Import Validation Error Modal] ─────► "Skip Invalid Rows" OR "Abort"
   │
   ▼
[Tag Library Validator]
   │
   ├─► Unapproved Tags? ──► [Early Tag Validation Dialog] ──────► "Approve & Add" OR "Strip" OR "Abort"
   │
   ▼
[Ingest Candidate Staging (ingest_candidates table)]
   │
   ▼
[Decoupled Async Worker Pool (Token Bucket Throttled)]
   │
   ├─► Dynamic Field Evaluation (Missing coords? Forward geocode; Missing address? Reverse geocode)
   ├─► Tenant-Scoped ID Check (poi_id matches user_id? -> update_existing; else new UUID)
   │
   ▼
[Phase 1 Triage Modal] ──(Optional: Export Selected Records)──► Streamed CSV/JSON/YAML
   │
   ▼
[Phase 2 AI Enrichment] ──(Optional: Export Selected Records)──► Streamed CSV/JSON/YAML
   │
   ▼
[Commit to pois table] ──(created_at = NOW())
   │
   ▼
[Vistarae Explorer View] ──(Filter by Date Added / Export Selected Records)
```

