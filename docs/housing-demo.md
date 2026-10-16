# Housing Loan Demo (Offline)

This document provides instructions for running the deterministic end-to-end offline demo for the housing loan analysis (Issue #40).

## 1. Installation & Environment

Requires Python 3.12. Ensure you have the virtual environment activated and dependencies installed:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Generate BDDK Silver Data

First, run the BDDK transformation script to process Bronze receipts into the strictly validated Silver parquet artifact:

```powershell
python -m scripts.build_bddk_silver
```
This generates `data/silver/bddk/housing_loans.parquet`. (Note: Existing missing parameters files must be cleaned up as per Lesson 3).

## 3. Obtain EVDS CSV & Manifest

The EVDS Silver artifact and its corresponding manifest are coordinated via Issue #39.
Place them in their respective locations, for example:
- `data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv`
- `data/silver/evds/monthly/manifest.json`

Ensure the manifest complies with `schema_version` 1.0.

The #39 weekly-coverage contract is required under the `TP.KTF12` series as
`weekly_coverage`. Monthly series (`TP.TUKFIY2025.GENEL` and `TP.KFE.TR`) must
omit that field or set it to `null`. Unknown fields are rejected at every level.

The embedded coverage object contains exactly `overall_status`,
`calendar_verification`, and `months`. Current policy requires `unverified`,
`not_available`, and monthly `status: "unverified"` / `expected_count: null`.
Each monthly record also includes `period`, `observed_count`, `observed_dates`,
and a nonblank `quality_note`. Dates must be valid, sorted, unique ISO dates
belonging to that month. Counts must match both the dates and the physical
Silver `weekly_observation_count`; coverage months must match the full Silver
period sequence, including months outside a requested demo slice. There is no
assumption of four or five weeks per month, no inferred expected/missing dates,
and no claim of complete weekly coverage without an official calendar.

The standalone `.coverage.json` additionally carries `schema_version` and
`silver_sha256`. That whole report must not be embedded in the manifest; its
CSV-hash check remains the producer's responsibility. The consumer validates
the embedded subobject against the physical Silver CSV and retains the existing
Bronze/raw/receipt integrity checks.

## 4. Running the Demo

Execute the single command CLI:

```powershell
python -m scripts.run_housing_demo --evds-manifest data/silver/evds/monthly/manifest.json --output-dir out/demo
```

**Optional Arguments:**
- `--bddk-silver`: Path to the BDDK Silver parquet file (default: `data/silver/bddk/housing_loans.parquet`).
- `--evds-silver`: Path to the EVDS Silver CSV file (default: `data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv`).
- `--start-period`: Analysis start period (default: `2021-01`).
- `--end-period`: Analysis end period (default: `2025-12`).
- `--html`: Also render the offline HTML presentation (`report.html`) in the output directory using `render_housing_report`.

## 5. Exit Codes

- `0`: Success. The output directory contains `evidence.json`, `chart.json`, `run_summary.json` (and `report.html` when `--html` is enabled).
- `1`: Data or integrity error (e.g., hash mismatch, missing periods, corrupt files, or output/staging/backup path overlapping with source files).
- `2`: CLI usage/argument error.

## 6. Output Files

- `run_summary.json`: A deterministic trace of the run including input SHA-256 hashes, exact periods, matched periods, methodology rules, and output SHA-256 hashes.
- `evidence.json`: The fully verified mathematical evidence containing cross-dataset references (traceability back to Bronze).
- `chart.json`: Plotly JSON specification mapping precisely to the evidence traces.
- `report.html` (optional, with `--html`): Self-contained offline HTML report rendered from the verified analysis run and summary.

The full validated `weekly_coverage` is retained in
`run_summary.json.manifest.weekly_coverage`, and is included in the HTML review
record. Both evidence quality notes and HTML display the weekly-calendar
limitation; complete monthly rows must not be mistaken for verified weekly
publication coverage.

## Shared producer/consumer verification

`tests/fixtures/evds_manifest_v1` contains the exact physical fixture from
PR #58 / `75159498c545fe21cf385b4a826566a87172ea02`: two synthetic months,
three raw files and receipts, CSV, coverage report, and manifest. Git attributes
preserve fixture bytes across Windows and Linux checkouts. Tests copy it to a
temporary project without rewriting the manifest or its hashes, pass it through
the consumer and real CLI with `--html`, and reject the same incorrect period,
count, date, status, placement, and unknown-field cases through both consumers.

```powershell
python -m pytest tests/test_evds_weekly_coverage_integration.py -q
```

This offline fixture proves contract interoperability. The real 60-month run
and a shareable three-month raw/calculated comparison remain open acceptance
work in #40 and must not be closed by these synthetic tests.

## 7. Limitations & Constraints

- **No Causality:** The analysis identifies months where the interest rate decreased and the real housing loan stock did not increase (faiz düşerken reel konut kredisi stokunun artmadığı aylar). It does not establish mathematical causality.
- **Stock vs Flow:** Housing loan data represents total outstanding stock at period end, not monthly origination flow. Therefore, decreases represent net contraction (repayments exceeding new loans).
- **Deterministic:** The demo runs completely offline without LLM network access.
