# Quickstart & Verification Guide: Full-Fidelity CSV Export & Re-Import (017-export)

**Feature**: `017-export` | **Date**: 2026-11-11

---

## 1. Prerequisites & Environment Setup

Ensure backend and frontend dependencies are verified:
```bash
# Python backend test execution
python -m pytest tests/unit/packages/core/test_export_schema.py tests/unit/services/ingest/test_csv_parser_reimport.py tests/performance/test_export_import_performance.py -o addopts="" -v

# Frontend Vitest test execution
cd frontend && npx vitest run src/tests/ingest/csvExport.test.ts src/tests/ingest/exportSchema.test.ts

# Schema Parity Validation Script
python scripts/validate_export_schema_sync.py
```

---

## 2. Validation Scenario 1: Exporting Full-Fidelity Staged Candidates

Prove that all candidate metadata, multi-tier admin levels, structured websites, and tags are exported without data loss.

1. Launch backend and frontend development servers.
2. In the browser, open an intake staging session containing candidates with:
   - Complete addresses (Street, Locality, Admin Level 2, Admin Level 1, Country, Country Code).
   - Structured website pairs (`[{"name": "Park Portal", "url": "https://example.com"}]`).
   - Semicolon tags (`Scenic; National Park`).
   - A cell starting with `=SUM(1+1)`.
3. In the candidate detail pane, edit the description without clicking "Save Candidate Changes".
4. Click the **"Export"** button in the workbench header.
5. Inspect the downloaded CSV file:
   - Verify all 35+ headers match [csv-schema.json](./contracts/csv-schema.json).
   - Verify uncommitted description edit is present in the CSV row.
   - Verify the cell starting with `=SUM(1+1)` is neutralized as `'=SUM(1+1)`.
   - Verify tags are formatted as `Scenic; National Park`.
   - Verify website lists are formatted as valid JSON strings safely quoted.

---

## 3. Validation Scenario 2: Roundtrip Lossless Re-Import

Prove that an exported CSV can be uploaded to rebuild the staging session with 100% attribute parity.

1. Open the Vistarae Intake Upload modal.
2. Upload the CSV file exported in Scenario 1.
3. Once staging intake completes, open the Import Staging Workbench for the newly created job.
4. Verify:
   - Candidate dispositions, confidence scores, and justifications match 100%.
   - Tags, dates visited, and photo directories deserialize into array items.
   - Structured websites deserialize into structured objects with matching names and URLs.
   - Leading formula neutralization apostrophes (`'`) are stripped, restoring authentic user strings.
   - Intra-batch parent nesting and merge linkages are correctly translated and linked to the new session UUIDs.

---

## 4. Validation Scenario 3: Backend Streaming API Verification

Execute curl or HTTP client against the export route:

```bash
# Export all candidates in a staging job
curl -X GET "http://localhost:8000/api/ingest/jobs/{job_id}/candidates/export" \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -o staging_export.csv

# Verify line count and UTF-8 BOM
head -n 2 staging_export.csv
```

