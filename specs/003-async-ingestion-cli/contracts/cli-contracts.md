# CLI Interface Contracts: Operational & AI Ingestion Utilities

**Feature Identifier**: `003-async-ingestion-cli`  
**Date**: 2026-10-19  
**Status**: Completed  
**Spec**: [spec.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/spec.md)

---

## 1. Dead-Letter Queue Redrive CLI (`scripts/redrive_dlq.py`)

### 1.1 Command Syntax & Parameters

```bash
python scripts/redrive_dlq.py --env <local|staging|prod> [OPTIONS]
```

| Flag                   | Type     | Required | Default | Description                                                             |
| :--------------------- | :------- | :------- | :------ | :---------------------------------------------------------------------- |
| `--env`, `-e`          | `str`    | **Yes**  | None    | Target environment: `local`, `staging`, `prod` (or `production`).       |
| `--max-messages`, `-m` | `int`    | No       | `100`   | Maximum number of messages to redrive.                                  |
| `--dry-run`            | `switch` | No       | `False` | Inspect DLQ message count without moving or deleting messages.          |
| `--non-interactive`    | `switch` | No       | `False` | Disable interactive prompts (requires `--yes` for cloud).               |
| `--yes`, `-y`          | `switch` | No       | `False` | Explicit confirmation for non-interactive cloud runs.                   |
| `--endpoint-url`       | `str`    | No       | Auto    | Override SQS endpoint (defaults to `http://localhost:9324` in `local`). |

### 1.2 Execution Semantics & Exit Codes

- **Local Execution (`--env local`)**:
  - Connects to ElasticMQ on `http://localhost:9324` or `$SQS_ENDPOINT_URL`.
  - Loops using `receive_message`, `send_message_batch`, and `delete_message_batch` in batches of 10.
  - Requires no interactive confirmation.
- **Cloud Execution (`--env staging` or `--env prod`)**:
  - If `--dry-run`: queries queue attributes, prints `ApproximateNumberOfMessagesVisible`, and exits 0.
  - If interactive TTY and not `--yes`: prompts `WARNING: You are about to redrive DLQ messages in '{env}'.\nType 'yes' to confirm: `. If input != `"yes"`, aborts with code 1.
  - If `--non-interactive` without `--yes`: prints error to `stderr` and exits code 1.
  - If confirmed: calls AWS native `sqs.start_message_move_task(SourceArn=dlq_arn, DestinationArn=main_arn)` and prints task ID.

| Exit Code | Meaning                                                                     |
| :-------- | :-------------------------------------------------------------------------- |
| `0`       | Success (messages redriven or dry run completed).                           |
| `1`       | Aborted by user, confirmation rejected, or non-interactive missing `--yes`. |
| `2`       | Configuration/CLI argument validation error (e.g. invalid `--env`).         |

---

## 2. AI Photo Scanner CLI (`photo_scraper`)

### 2.1 Command Syntax & Parameters

```bash
python -m photo_scraper.main --dir <path_to_photos> [OPTIONS]
# Or via powershell wrapper:
.\vistarae.ps1 scrape <path_to_photos> [OPTIONS]
```

| Flag                  | Type     | Required | Default             | Description                                                              |
| :-------------------- | :------- | :------- | :------------------ | :----------------------------------------------------------------------- |
| `--dir`, `-d`         | `str`    | **Yes**  | Config              | Path to photo library root directory to scan.                            |
| `--out`, `-o`         | `str`    | No       | `output/ingest.csv` | Output CSV path for formatted ingestion records.                         |
| `--max-folders`, `-m` | `int`    | No       | `0` (unlimited)     | Limit of folders to scan.                                                |
| `--exclude`           | `str`    | No       | `""`                | Comma-separated glob patterns to exclude (e.g. `*Kids*,*Raw*`).          |
| `--non-interactive`   | `switch` | No       | `False`             | Run unattended; mark uncertain POIs as `NEEDS_REVIEW` without prompting. |
| `--verbose`, `-v`     | `switch` | No       | `False`             | Enable DEBUG level logging output.                                       |

### 2.2 Interactive Triage Prompt Schema

When Gemini returns `is_uncertain == True`, confidence $< 0.70$, or a generic category ("Airport", "Hotel", "Restaurant", "Train Station"):

- **Interactive Prompt Format**:

  ```text
  [UNCERTAIN POI DETECTED]
  Folder: 2024/Japan/Kyoto/WalkAround
  File:   IMG_9281.JPG
  EXIF:   Lat: 35.0037, Lon: 135.7772 (Taken: 2024-04-12 14:22:00)
  Inferred: Kyoto Traditional Restaurant (Confidence: 0.55)
  Reason: Generic dining establishment detected near Gion district.

  Options:
    [c] Confirm and keep as inferred
    [e] Edit POI name and details
    [s] Skip this POI
  Enter choice [c/e/s]:
  ```

- **Non-Interactive Mode (`--non-interactive` or non-TTY)**:
  - Bypasses terminal prompt.
  - Retains row in output CSV with `triage_status="NEEDS_REVIEW"` and `confidence_score`.

### 2.3 Output Ingestion CSV Schema

The output CSV conforms exactly to the Vistarae Ingestion format:

```csv
name,description,address,city,state,country,latitude,longitude,visited_date,tags,triage_status
"Fushimi Inari Taisha","Iconic Shinto shrine with thousands of vermilion torii gates.","68 Fukakusa Yabunouchicho, Fushimi Ward","Kyoto","Kyoto Prefecture","Japan",34.9671,135.7727,2024-04-10,"shrine,kyoto,scenic",APPROVED
"Gion Corner Viewpoint","Historic wooden machiya district.","Gionmachi Minamigawa","Kyoto","Kyoto Prefecture","Japan",35.0037,135.7772,2024-04-12,"historic,culture",NEEDS_REVIEW
```

- Formula prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) are automatically neutralized during writing.
