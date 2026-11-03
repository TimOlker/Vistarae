# Quickstart & Verification Guide: Extractor Scripts (016-cli-extractors)

**Feature**: `016-cli-extractors`  
**Date**: 2026-11-03  
**Status**: Ready  

---

## 1. Prerequisites & Environment Setup

Ensure `packages/core` is installed in editable mode and required dependencies are available:

```bash
# From repository root
pip install -e ./packages/core
pip install click beautifulsoup4 httpx pytest pytest-cov
```

---

## 2. Running the Extractor CLIs

All scripts support standardized flags: `--output`, `--limit`, `--delay`, `--deep`, `--split-size`, `--tag`, `--dry-run`.

### 2.1 Hillman Wonders Extractor

Extract the top 20 Hillman Wonders with wonder tier tags (`HillmanWonder:Gold`, `HillmanWonder:Silver`, `HillmanWonder:Bronze`):

```bash
python extractor_scripts/hillman_wonders.py --limit 20 --output hillman_test.csv
```

*Verification Check*: Open `hillman_test.csv`. Confirm:
- `POI Name` contains wonder names (e.g. "Pyramids of Giza").
- `Tags` contains `HillmanWonder:Gold` (no base `Wonder` tag).
- `Websites` contains JSON array with Hillman reference link.

---

### 2.2 US National Park System Sites Extractor

Extract 25 US National Park units with `NPS` baseline tag and official designations:

```bash
python extractor_scripts/nps_sites.py --limit 25 --output nps_test.csv
```

*Verification Check*: Open `nps_test.csv`. Confirm:
- `Country` is "United States" and `Country Code` is "US".
- `Tags` contains `NPS; National Park` (or `NPS; National Historic Site`).
- `Websites` contains JSON array with `.nps.gov` official portal.
- Multi-location parks have primary location in standard columns and secondary sites in `Additional Address`.

---

### 2.3 Museum Ships Extractor

Extract 20 preserved museum ships worldwide:

```bash
python extractor_scripts/museum_ships.py --limit 20 --output ships_test.csv
```

*Verification Check*: Open `ships_test.csv`. Confirm:
- `Tags` contains `Ship` (plus `Military` if warship; no naval vessel classifications like "Battleship").
- `Town/City` contains home port / berthing location.
- `Websites` contains museum and reference URLs in JSON format.

---

### 2.4 Castles of the World Extractor

Extract 25 castles and fortresses:

```bash
python extractor_scripts/castles.py --limit 25 --output castles_test.csv
```

*Verification Check*: Open `castles_test.csv`. Confirm:
- `Tags` contains `Fortification` (no architectural classification tags).
- `Hero Image URL` contains castle exterior photo URL when available.

---

### 2.5 Aircraft Museums Extractor

Extract 25 aviation museums worldwide:

```bash
python extractor_scripts/aircraft_museums.py --limit 25 --output aviation_test.csv
```

*Verification Check*: Open `aviation_test.csv`. Confirm:
- `Tags` contains `Aircraft` (no collection focus tags).
- `Websites` contains official museum and reference URLs in JSON format.

---

## 3. Advanced Features Verification

### 3.1 Verifying 2,000-Row Automatic Partitioning

Test automatic file splitting using a small partition limit:

```bash
python extractor_scripts/nps_sites.py --limit 15 --split-size 5 --output split_demo.csv
```

*Expected Outcome*: Generates `split_demo_part1.csv`, `split_demo_part2.csv`, and `split_demo_part3.csv`, each containing exactly 5 data rows plus the standardized header.

---

### 3.2 Verifying Formula Injection Neutralization

Ensure cell values starting with dangerous spreadsheet prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) are neutralized:

```bash
python -c "
from vistarae_core.schemas.extractor import neutralize_formula_injection
assert neutralize_formula_injection('=SUM(A1:A10)') == \"'=SUM(A1:A10)\"
assert neutralize_formula_injection('+123') == \"'+123\"
assert neutralize_formula_injection('Normal Text') == 'Normal Text'
print('Formula injection neutralization verified!')
"
```

---

### 3.3 Verifying Compatibility with Vistarae Ingestion

Parse the generated CSV using Vistarae's production CSV parser:

```bash
python -c "
from services.ingest.services.csv_parser import parse_and_sanitize_csv
with open('nps_test.csv', 'rb') as f:
    rows = parse_and_sanitize_csv(f.read(), content_type='text/csv')
print(f'Successfully parsed {len(rows)} rows into Vistarae ingestion pipeline!')
"
```

---

## 4. Running Automated Tests

Run the complete test suite against local canned HTML fixtures with coverage enforcement:

```bash
pytest tests/unit/extractor_scripts/ --cov=extractor_scripts --cov=packages/core/vistarae_core/schemas/extractor.py --cov-fail-under=90
```

All tests execute offline and deterministically without issuing live HTTP calls.

