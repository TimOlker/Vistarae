# Data Model: Unified CLI Extractors & Scraper Toolkit (016-cli-extractors)

**Feature**: `016-cli-extractors`  
**Date**: 2026-11-03  
**Status**: Completed  

---

## 1. Domain Data Transfer Objects (`packages/core/vistarae_core/schemas/extractor.py`)

All models inherit from `vistarae_core.domain.base.StrictBaseModel` enforcing `extra="forbid"`, `validate_assignment=True`, and `str_strip_whitespace=True` (complying with Constitution Principle 5).

### 1.1 `WebsiteRecord`
Represents an external website reference associated with a POI.

```python
class WebsiteRecord(StrictBaseModel):
    """External website reference for a POI."""
    name: str = Field(..., min_length=1, max_length=255, description="Label for the website, e.g. Official Website, Wikipedia")
    url: str = Field(..., min_length=1, max_length=2000, description="Full HTTP/HTTPS URL")
```

### 1.2 `AdditionalAddressRecord`
Represents secondary, satellite, or alternative physical locations for a multi-facility POI (e.g. additional visitor centers or entrances for a national park).

```python
class AdditionalAddressRecord(StrictBaseModel):
    """Secondary or satellite address for multi-location attractions."""
    street_address: str | None = Field(default=None, max_length=255)
    town_city: str | None = Field(default=None, max_length=150)
    state_province: str | None = Field(default=None, max_length=100)
    zip_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    country_code: str | None = Field(default=None, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    facility_name: str | None = Field(default=None, max_length=255, description="Optional label, e.g. South Visitor Center")
```

### 1.3 `ExtractorRecord`
The authoritative in-memory representation of an extracted point of interest ready for serialization.

```python
class ExtractorRecord(StrictBaseModel):
    """Canonical extracted POI record ready for CSV/JSON export."""
    poi_name: str = Field(..., min_length=1, max_length=255, description="Standardized attraction name")
    
    # Primary Address & Coordinates
    street_address: str | None = Field(default=None, max_length=255)
    town_city: str | None = Field(default=None, max_length=150)
    state_province: str | None = Field(default=None, max_length=100)
    zip_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    country_code: str | None = Field(default=None, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    
    # Multi-Location Secondary Addresses
    additional_addresses: list[AdditionalAddressRecord] = Field(default_factory=list)
    
    # Classification & Tags
    tags: list[str] = Field(default_factory=list)
    
    # Web Presence
    websites: list[WebsiteRecord] = Field(default_factory=list)
    
    # Media & Documentation
    hero_image_url: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=4000)
    reason_to_visit: str | None = Field(default=None, max_length=4000)
    photo_directory: str | None = Field(default=None, max_length=500)
    dates_visited: list[str] = Field(default_factory=list)
    
    # Planning & Duration Estimates
    estimated_visit_hours: Decimal | None = Field(default=None, ge=0, le=24)
    itinerary_days: int | None = Field(default=None, ge=1, le=365)
```

---

## 2. CLI Execution Configuration Models (`extractor_scripts/common/models.py`)

### 2.1 `ExtractorConfig`
Encapsulates runtime parameters passed to the extractor CLI.

```python
class ExtractorConfig(StrictBaseModel):
    """Runtime configuration for CLI extraction execution."""
    output_path: Path = Field(..., description="Target CSV file path")
    limit: int | None = Field(default=None, ge=1, description="Maximum number of records to harvest")
    delay_seconds: float = Field(default=1.0, ge=0.1, description="Delay between HTTP requests in seconds")
    deep_scrape: bool = Field(default=False, description="Whether to harvest detailed subpages")
    cache_enabled: bool = Field(default=True, description="Whether to read/write local disk cache")
    split_size: int = Field(default=2000, ge=1, le=2000, description="Max rows per CSV partition file")
    geocode_missing: bool = Field(default=False, description="Whether to invoke Nominatim for missing coordinates")
    user_tags: list[str] = Field(default_factory=list, description="Operator-supplied custom tags to append")
    dry_run: bool = Field(default=False, description="Preview extraction without writing files to disk")
```

### 2.2 `ExtractionResult`
Encapsulates execution statistics returned by an extractor.

```python
class ExtractionResult(StrictBaseModel):
    """Summary metrics of an extractor execution run."""
    extractor_name: str
    total_harvested: int
    total_valid: int
    total_errors: int
    output_files: list[Path]
    duration_seconds: float
```

---

## 3. CSV Column Header & Serialization Mapping Table

The generated CSV maps `ExtractorRecord` fields to the headers consumed by Vistarae's `csv_parser.py`:

| Output CSV Column Header | `ExtractorRecord` Source Field | Value Format & Neutralization | Ingestion Workbench Target Field |
| :--- | :--- | :--- | :--- |
| `POI Name` | `poi_name` | Raw sanitized text (Required) | `poi_name` / `name` |
| `Street Address` | `street_address` | Text, empty string if None | `street_address` |
| `Town/City` | `town_city` | Text, empty string if None | `locality` / `city` |
| `State/Province` | `state_province` | Text, empty string if None | `admin_level_1` / `state` |
| `Zip Code` | `zip_code` | Text, empty string if None | `postal_code` |
| `Country` | `country` | Standard ISO English name | `country` |
| `Country Code` | `country_code` | 2-letter uppercase ISO-3166-1 | `country_code` |
| `latitude` | `latitude` | Decimal string (6 decimals) | `latitude` |
| `longitude` | `longitude` | Decimal string (6 decimals) | `longitude` |
| `Tags` | `tags` | Semicolon-delimited: `Tag1; Tag2` | `tags` |
| `Hero Image URL` | `hero_image_url` | Full HTTP/HTTPS URL | `hero_image_url` |
| `Websites` | `websites` | JSON string: `[{"name": "...", "url": "..."}]` | `related_websites` |
| `Additional Address` | `additional_addresses` | JSON string: `[{"street_address": "...", ...}]` | `additional_addresses` |
| `Estimated Visit Hours` | `estimated_visit_hours` | Decimal numeric string | `recommended_duration_hours` |
| `Itinerary Days` | `itinerary_days` | Integer string | `recommended_visit_days` |
| `Description` | `description` | Text, truncated $\le 4000$ chars | `description` |
| `Reason to Visit` | `reason_to_visit` | Text, truncated $\le 4000$ chars | `reason_to_visit` |
| `Photo Directory` | `photo_directory` | Filesystem path string | `photo_directory` |
| `Dates Visited` | `dates_visited` | Semicolon-delimited ISO dates | `dates_visited` |

---

## 4. Security & Sanitization Invariants

1. **Formula Injection Neutralization**:
   Any cell value starting with `=`, `+`, `-`, `@`, `\t`, or `\r` MUST have a single quote (`'`) prepended prior to CSV serialization.
2. **File Size & Partition Guardrail**:
   When total rows exceed `split_size` (default 2,000), the output MUST be written to partitioned files: `{basename}_part1.csv`, `{basename}_part2.csv`, etc., ensuring no single file exceeds 2,000 rows or 2MB.

