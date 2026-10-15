# Quad-Qore Agentic Analytics

An early MVP for monthly housing-loan analysis, developed for KKB Hackathon 2026.
Python collects and validates data, computes the analysis, and returns evidence,
a Plotly chart, and an optional guarded narration. A standalone HTML report is available.

The first scenario identifies months when housing-loan interest rates decreased
but the inflation-adjusted housing-loan stock did not increase. The default
analysis window is January 2021 to December 2025: 60 months.

## Current implementation

| Component | Available behavior | Code / guide |
| --- | --- | --- |
| BDDK ingestion and Silver | Raw bulletin acquisition, receipt/integrity validation, monthly housing-loan Parquet | [Ingestion](docs/bddk-ingestion.md), [Silver](docs/bddk-silver.md) |
| TCMB EVDS ingestion and Silver | Three approved series, Bronze receipts, monthly CSV and weekly-rate aggregation | [EVDS guide](docs/evds-ingestion.md) |
| Gold analysis | Period alignment, real loan stock, monthly changes and deterministic matching rule | [gold.py](app/lakehouse/gold.py) |
| Evidence and chart | Typed evidence and a six-trace, three-panel Plotly chart | [Evidence](app/tools/housing_evidence.py), [chart](app/tools/housing_chart.py) |
| FastAPI | Health, normalized-row analysis, and server-side Silver analysis endpoints | [housing.py](app/api/housing.py) |
| Guarded narration | Model JSON checked against the same month/metric; Turkish text rendered from evidence | [Narration contract](docs/housing-narration.md) |
| LLM client | Configured OpenAI-compatible Chat Completions, bounded SDK timeout, one attempt and safe application errors | [LLM guide](docs/llm-client.md) |
| Question analysis | Turkish question + normalized rows, typed decisions, one allowed Housing analysis and shared period validation | [Question API guide](docs/housing-question.md) |
| HTML report | Embedded Plotly.js, matching-month table, sources, methodology and limitations | [Report guide](docs/housing-report.md) |
| CI | Offline pytest suite on pull requests and pushes to main, using Python 3.12 | [Workflow](.github/workflows/tests.yml) |

The key-free sample below uses **synthetic data**. The real-data delivery,
manifest binding and complete Bronze-to-report source chain remain acceptance
work in [#39](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39),
[#40](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40) and
[#45](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/45).
See the [acceptance record](docs/release-acceptance.md) for verified checks and open gates.

Question routing has a bounded Python service and HTTP endpoint with offline
behavior tests. File-backed integration and live semantic evaluation remain open
in [#42](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/42).
A general agent/tool registry, data catalog, general web/anomaly/causality tools
and deployment are planned work. A live Gemini narration contract check passed;
see the [LLM acceptance record](docs/llm-client.md#canlı-kabul-kaydı--15-ekim-2026).
The draft golden cases currently have schema checks; they are not a measured
end-to-end model-accuracy benchmark.

## Quick start: synthetic offline report

Use **Python 3.12**. Cloning and dependency installation require internet access;
after installation, report generation and opening the HTML require neither
internet access nor a BDDK/EVDS/MIA key. No .env file is required for this path.
Run commands from the repository root. An activated virtual environment is optional
because commands below use its Python executable directly.

### Windows PowerShell

```powershell
git clone https://github.com/ekincimustafa/quad-qore-agentic-analytics.git
cd quad-qore-agentic-analytics
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.render_housing_sample
Start-Process .\out\housing-sample.html
.\.venv\Scripts\python.exe -m pytest -q
```

If the Windows `py` launcher is unavailable, use `python -m venv .venv` after
confirming `python --version` reports Python 3.12.

### Linux

```bash
git clone https://github.com/ekincimustafa/quad-qore-agentic-analytics.git
cd quad-qore-agentic-analytics
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.render_housing_sample
.venv/bin/python -m pytest -q
```

Open `out/housing-sample.html` in a browser. The HTML embeds the chart library,
so no CDN or web server is needed. The file is several MB and generated `out/`
content is ignored by Git. Its 60 observations, including weekly counts, are
artificial and must not be presented as real economic findings.

## Local API

Start the server in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Linux equivalent:

```bash
.venv/bin/python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Interactive API documentation: <http://127.0.0.1:8000/docs>.

| Endpoint | Input and behavior |
| --- | --- |
| `GET /health` | API health; does not verify real-data availability or model access |
| `POST /analysis/housing` | Normalized BDDK/EVDS rows and period; returns evidence, chart and optional narration |
| `POST /analysis/housing/demo` | Period and optional narration; reads server-controlled local Silver files |
| `POST /analysis/housing/question` | Turkish question + normalized rows; validates the model plan before analysis, or returns clarification/unsupported |

`include_narration` defaults to `false`, so normalized-row analysis needs no key.
Try [the three-month synthetic request](docs/housing-api-example.json) in a second terminal.

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
$body = Get-Content .\docs\housing-api-example.json -Raw -Encoding UTF8
$result = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analysis/housing -ContentType "application/json" -Body $body
$result.evidence | Select-Object observed_month_count, matched_month_count, matched_periods
```

Linux:

```bash
curl -f http://127.0.0.1:8000/health
curl -f -H 'Content-Type: application/json' --data-binary @docs/housing-api-example.json http://127.0.0.1:8000/analysis/housing
```

The example has three observations and matches `2021-02`. It is independent of
the 60-month HTML sample and does not create Silver files.

For the question endpoint, use [the separate synthetic question request](docs/housing-question-api-example.json)
and [question API instructions](docs/housing-question.md#soru-apisi). Question planning
requires a configured live model even when `include_narration=false`.

The file-backed endpoint expects these paths relative to the repository root:

- `data/silver/bddk/housing_loans.parquet`
- `data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv`

These data files are not shipped in Git. Missing/unreadable files produce
HTTP 503 (`demo_data_unavailable`); invalid analytical input produces HTTP 422.
The current file-backed service uses generic source references. Full per-file
manifest/source binding is tracked in #40; connecting its verified output to
the HTML report remains part of #46.

## Real-data preparation

This is separate from the synthetic quick start. It uses external services and
has not been rerun as part of this acceptance record. Set `EVDS_API_KEY` in the
process environment before EVDS acquisition; the EVDS CLI does not load .env itself.

Activate the installed virtual environment with `.\.venv\Scripts\Activate.ps1`
on Windows or `source .venv/bin/activate` on Linux. The existing preparation commands are:

```bash
python -m scripts.download_bddk --frequency aylik --monthly-tables 4 --groups 10001 --currencies TL --start 2021-01-01 --end 2026-06-30
python -m scripts.build_bddk_silver --start-period 2021-01 --end-period 2026-06
python -m scripts.download_evds --start-period 2021-01 --end-period 2026-06
python -m scripts.build_evds_silver --start-period 2021-01 --end-period 2026-06
```

The BDDK builder requires existing Bronze files. The EVDS builder can download
missing Bronze responses, so it must not be assumed to run offline in all cases.
The intended Silver scope is 66 months; the first analysis selects 60 months.
Real-data hashes, three sample-month comparisons and complete source binding
remain release acceptance gates. See the BDDK and EVDS guides above.

## Optional LLM narration

Copy `.env.example` to a local `.env` and configure `LLM_API_KEY`, `LLM_BASE_URL`
and `LLM_CHAT_MODEL` for a Chat Completions-compatible endpoint/model you can
access. There is no default provider/model or automatic MIA fallback.
`LLM_TIMEOUT_SECONDS` defaults to 30; retries are disabled. See the
[LLM guide](docs/llm-client.md) for configuration and controlled errors.

With the virtual environment activated:

```bash
python -m scripts.smoke_test_llm
```

This sends a small synthetic Housing evidence package to the selected live model
and validates its JSON using the real narration contract. A single live check
passed with `gemini-3.5-flash-lite` on October 15, 2026; this is not a model
accuracy or availability benchmark. Verify access for your own provider/model.
Invalid narration is rejected with HTTP 502 (`narration_failed`). The HTML sample
and `include_narration=false` path do not read LLM settings or call a model.
The old `MIA_*` helper and `scripts.smoke_test_mia` remain a separate legacy path;
that older smoke command only checks basic connectivity.

## Analysis rule and limitations

```text
real_housing_loan_2025_mn_try = nominal_housing_loan_mn_try * 100 / cpi_index
interest_rate_change_pp = current_interest_rate - previous_interest_rate
match = interest_rate_change_pp < 0 AND real_housing_loan_change_pct <= 0
```

Weekly interest observations are aggregated by monthly arithmetic mean.
The first month's change fields and match flag are null because no preceding
month exists inside the analysis window. The result does not establish causality.
KFE is displayed for context; CPI is used to deflate the loan stock.

## Project guides and security

- [Architecture](docs/architecture.md) and [scenario/design contract](docs/first-demo-scenario.md): design documents; some agent workflow is planned.
- [HTML report](docs/housing-report.md), [narration](docs/housing-narration.md), [acceptance record](docs/release-acceptance.md).
- Runtime calculations use pandas; Parquet I/O uses pyarrow; presentation uses Plotly. Full dependencies are in [requirements.txt](requirements.txt).
- Keep credentials in local configuration. Never commit keys, raw data, generated reports or secret-bearing logs.
- Tests cover deterministic calculations, integrity/error boundaries, API, narration and report behavior. CI is test automation; deployment is future work.
