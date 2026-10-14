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

## 5. Exit Codes

- `0`: Success. The output directory contains `evidence.json`, `chart.json`, and `run_summary.json`.
- `1`: Data or integrity error (e.g., hash mismatch, missing periods, corrupt files).
- `2`: CLI usage/argument error.

## 6. Output Files

- `run_summary.json`: A deterministic trace of the run including input SHA-256 hashes, exact periods, matched periods, methodology rules, and output SHA-256 hashes.
- `evidence.json`: The fully verified mathematical evidence containing cross-dataset references (traceability back to Bronze).
- `chart.json`: Plotly JSON specification mapping precisely to the evidence traces.

## 7. Limitations & Constraints

- **No Causality:** The analysis identifies months where the interest rate decreased and the real housing loan stock did not increase (faiz düşerken reel konut kredisi stokunun artmadığı aylar). It does not establish mathematical causality.
- **Stock vs Flow:** Housing loan data represents total outstanding stock at period end, not monthly origination flow. Therefore, decreases represent net contraction (repayments exceeding new loans).
- **Deterministic:** The demo runs completely offline without LLM network access.
