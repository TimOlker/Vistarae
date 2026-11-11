# CLI Interface Contract: Extractor Scripts (016-cli-extractors)

**Feature**: `016-cli-extractors`  
**Date**: 2026-11-03  
**Status**: Completed  

---

## 1. Overview & Standard Invocation

All extractor scripts are located in `/extractor_scripts` and executed directly via Python CLI. They implement the standardized Click interface provided by `extractor_scripts/common/base.py`.

```bash
python extractor_scripts/<script_name>.py [OPTIONS]
```

### Available Extractor Scripts

1. `python extractor_scripts/hillman_wonders.py`
2. `python extractor_scripts/nps_sites.py`
3. `python extractor_scripts/museum_ships.py`
4. `python extractor_scripts/castles.py`
5. `python extractor_scripts/aircraft_museums.py`

---

## 2. Standard CLI Options & Flags

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `-o`, `--output` | `PATH` | `./<script_basename>.csv` | Output file path (e.g. `nps_sites.csv`). If row count $> 2000$, auto-splits into `nps_sites_part1.csv`, etc. |
| `-l`, `--limit` | `INTEGER` | `None` (all) | Maximum number of POI records to extract. |
| `-d`, `--delay` | `FLOAT` | `1.0` | Politeness delay between HTTP network requests in seconds. |
| `--deep / --shallow` | `BOOLEAN` | `--shallow` | `--deep` traverses individual subpages for full descriptions, hero images, and coordinates; `--shallow` parses catalog index tables only. |
| `--cache / --no-cache` | `BOOLEAN` | `--cache` | Cache raw HTML responses under `.cache/extractors/` for instant replay and offline testing. |
| `--split-size` | `INTEGER` | `2000` | Maximum rows per output CSV partition file ($\le 2000$). |
| `--geocode / --no-geocode` | `BOOLEAN` | `--no-geocode` | Query OSM Nominatim (1 req/sec) to resolve missing coordinates at extraction time. |
| `-t`, `--tag` | `TEXT` | `[]` (multiple) | Append operator-defined custom tags to all extracted records (e.g. `--tag "BucketList2026"`). |
| `--dry-run` | `BOOLEAN` | `False` | Run extraction and display summary table in terminal without writing CSV files. |
| `--help` | `FLAG` | — | Display standard command help, options, and descriptions. |

---

## 3. Exit Codes

- `0`: Extraction completed successfully. Output file(s) generated.
- `1`: Validation or operational error (e.g. invalid arguments, unrecoverable network failure).
- `2`: Click parameter parsing error (e.g. missing required value or bad type).

---

## 4. Output Stream Contract

### Standard Output (stdout)
- Operational progress indicators (e.g. `[1/50] Harvesting: Yellowstone National Park...`).
- Final execution summary table:
  ```text
  ============================================================
  Vistarae Extractor Summary: NPS Sites
  ============================================================
  Total Records Harvested: 429
  Total Valid Records:     429
  Validation Errors:       0
  Output Files Generated:
    - ./nps_sites.csv (429 rows)
  Execution Time:          42.3 seconds
  ============================================================
  ```

### Standard Error (stderr)
- Network retry warnings, rate-limiting notifications, and non-fatal parsing anomalies.

