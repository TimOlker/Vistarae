# Data Model: Full-Fidelity CSV Export & Roundtrip Re-Import (017-export)

**Feature**: `017-export` | **Date**: 2026-11-11

---

## 1. Domain Entities & Schemas

### 1.1 ExportFieldDefinition

A metadata record governing serialization, deserialization, formatting, and security for a single candidate attribute.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `attribute_key` | `str` | Internal property name on `IngestCandidateTable` / `CandidateItem` (e.g. `poi_name`). |
| `header_name` | `str` | Standardized CSV column header emitted in exports (e.g. `POI Name`). |
| `aliases` | `list[str]` | Alternative header names accepted during CSV import (case-insensitive). |
| `data_type` | `FieldType` | Enum: `STRING`, `NUMBER`, `BOOLEAN`, `STRING_LIST`, `JSON_PAIRS`, `UUID`. |
| `is_formula_sanitized` | `bool` | Whether cell values require leading `'` prepending on export and stripping on import. |
| `default_value` | `Any` | Fallback value when missing or null in candidate records. |

### 1.2 StagingCandidateExportRow (35+ Canonical Attributes)

The complete canonical tabular model serialized to CSV and reconstructed during re-import:

| CSV Column Header | Candidate Attribute | Data Type | Export Format | Re-Import Deserializer |
| :--- | :--- | :--- | :--- | :--- |
| `Candidate ID` | `candidate_id` | `UUID` | UUID string | Used for `uuid_translation_map` |
| `Row Index` | `row_index` | `int` | Integer | Preserved row index |
| `POI Name` | `poi_name` | `str` | Quoted string, formula sanitized | Strips `'`, non-empty required |
| `Street Address` | `street_address` | `str` | Quoted string, formula sanitized | Strips `'` |
| `City / Town` | `city` | `str` | Quoted string, formula sanitized | Strips `'` |
| `Locality` | `locality` | `str` | Quoted string, formula sanitized | Strips `'` |
| `County / District (Admin Level 2)` | `admin_level_2` | `str` | Quoted string, formula sanitized | Strips `'` |
| `State / Province (Admin Level 1)` | `admin_level_1` | `str` | Quoted string, formula sanitized | Strips `'` |
| `State / Province` | `state_province` | `str` | Quoted string, formula sanitized | Strips `'` |
| `Postal Code / Zip` | `postal_code` | `str` | Quoted string, formula sanitized | Strips `'` |
| `Country` | `country` | `str` | Quoted string, formula sanitized | Strips `'` |
| `Country Code` | `country_code` | `str` | ISO 3166-1 alpha-2 uppercase | Normalizes to 2-letter uppercase |
| `Latitude` | `latitude` | `float` | WGS-84 decimal ($\le 6$ dec) | Numeric parse, $-90 \le \text{lat} \le 90$ |
| `Longitude` | `longitude` | `float` | WGS-84 decimal ($\le 6$ dec) | Numeric parse, $-180 \le \text{lon} \le 180$ |
| `Recommended Disposition` | `recommended_disposition` | `str` | String token (`accept`, etc.) | Staging disposition |
| `User Disposition` | `user_disposition` | `str` | String token or empty | User override preserved |
| `Confidence Score` | `confidence_score` | `int` | Integer (0–100) | Integer parse |
| `Disposition Justification` | `disposition_justification` | `str` | Quoted string, formula sanitized | Strips `'` |
| `Description` | `description` | `str` | Multiline quoted, formula sanitized | Strips `'`, truncated at 4,000 char |
| `Reason to Visit` | `reason_to_visit` | `str` | Multiline quoted, formula sanitized | Strips `'`, truncated at 4,000 char |
| `Hero Image URL` | `hero_image_url` | `str` | URL string | Validated URL format |
| `Official URL` | `official_url` | `str` | URL string | Validated URL format |
| `Wikipedia URL` | `wiki_url` | `str` | URL string | Validated URL format |
| `Related Websites` | `related_websites` | `list[dict]` | JSON array string | Dual-mode: JSON or semicolon fallback |
| `No Websites Flag` | `no_websites` | `bool` | `true` / `false` | Boolean parse |
| `Tags` | `tags` | `list[str]` | Semicolon-separated (`Tag1; Tag2`) | Dual-mode: JSON or semicolon split |
| `Photo Directory` | `photo_directory` | `str` | Quoted path string | Strips `'` |
| `Photo Directories` | `photo_directories` | `list[str]` | Semicolon-separated paths | Dual-mode: JSON or semicolon split |
| `Dates Visited` | `dates_visited` | `list[str]` | Semicolon-separated dates | Dual-mode: JSON or semicolon split |
| `Recommended Duration Hours` | `recommended_duration_hours` | `float` | Decimal hours (e.g. `2.5`) | Numeric parse |
| `Recommended Visit Days` | `recommended_visit_days` | `int` | Integer days | Numeric parse |
| `Estimated Visit Time Notes` | `estimated_visit_time_notes` | `str` | Quoted string, formula sanitized | Strips `'` |
| `Parent Candidate ID` | `parent_candidate_id` | `UUID` | UUID string | Resolved via `uuid_translation_map` |
| `Parent POI ID` | `parent_poi_id` | `UUID` | UUID string | Checked against existing POIs |
| `Matched Existing POI ID` | `matched_existing_poi_id` | `UUID` | UUID string | Checked against existing POIs |
| `Merge Target ID` | `merge_target_id` | `UUID` | UUID string | Resolved via `uuid_translation_map` |
| `Is User Overridden` | `is_user_overridden` | `bool` | `true` / `false` | Preserves manual override state |

---

## 2. Ingestion State & Translation Mapping

### 2.1 UUID Translation Map

When re-importing an exported CSV:
```text
uuid_translation_map = {
    exported_candidate_id_1: newly_generated_db_uuid_1,
    exported_candidate_id_2: newly_generated_db_uuid_2,
    ...
}
```

Post-processing resolves:
- `candidate.parent_candidate_id = uuid_translation_map.get(raw_parent_id, None)`
- `candidate.merge_target_id = uuid_translation_map.get(raw_merge_target_id, None)`

### 2.2 Dynamic Metadata Preservation

Any column in an uploaded CSV not matched to a canonical attribute in `ExportFieldDefinition` is stored in the candidate's `raw_geocoding` dictionary under an `_unmapped_columns` key:
```json
{
  "_unmapped_columns": {
    "CustomTourGuideNotes": "Requires special permission for sunrise entry",
    "TicketPriceUSD": "25.00"
  }
}
```
This guarantees zero data loss when importing external files with custom attributes.

