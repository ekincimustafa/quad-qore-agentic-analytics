# Quad-Qore Agentic Analytics

An early MVP for monthly economic analysis, developed for KKB Hackathon 2026,
with housing-loan analysis and a deterministic CPI-change endpoint.
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
| EVDS manifest | Verified raw/receipt references, series metadata and weekly-coverage policy; normal CLI checks existing Silver against selected Bronze | [Manifest producer](app/lakehouse/evds_manifest_producer.py), [CLI](scripts/build_evds_manifest.py) |
| Gold analysis | Period alignment, real loan stock, monthly changes and deterministic matching rule | [gold.py](app/lakehouse/gold.py) |
| CPI analysis | Monthly and same-month-last-year CPI changes from normalized rows; missing history stays null, no model call | [Inflation guide](docs/inflation-analysis.md) |
| Evidence and chart | Typed evidence and a six-trace, three-panel Plotly chart | [Evidence](app/tools/housing_evidence.py), [chart](app/tools/housing_chart.py) |
| FastAPI | Health, normalized-row analysis, and server-side Silver analysis endpoints | [housing.py](app/api/housing.py) |
| Guarded narration | Model JSON checked against the same month/metric; Turkish text rendered from evidence | [Narration contract](docs/housing-narration.md) |
| LLM client | Configured OpenAI-compatible Chat Completions, bounded SDK timeout, one attempt and safe application errors | [LLM guide](docs/llm-client.md) |
| Question analysis | Turkish question + normalized rows, typed decisions, one allowed Housing analysis and shared period validation | [Question API guide](docs/housing-question.md) |
| Economic question | Bounded question plan and shared HTTP dispatch to existing Housing/CPI services | [Economic question guide](docs/economic-question.md) |
| Question evaluation | Nine Housing cases with offline/budgeted live mode; twelve Economic cases with offline HTTP checks | [Housing evaluation](docs/housing-question-evals.md), [Economic evaluation](docs/economic-question.md#offline-değerlendirme) |
| HTML report | Embedded Plotly.js, matching-month table, sources, methodology and limitations | [Report guide](docs/housing-report.md) |
| File demo CLI | Physical EVDS manifest checks, source/output protection, evidence/chart/summary and optional offline HTML | [Demo guide](docs/housing-demo.md) |
| Verified question files | Server-controlled local BDDK/EVDS files verified before question planning; Python wrapper only | [File question guide](docs/housing-question-files.md) |
| CI | Offline pytest suite on pull requests and pushes to main, using Python 3.12 | [Workflow](.github/workflows/tests.yml) |

The key-free sample below uses **synthetic data**. Manifest production,
physical consumer checks and the file-to-report CLI are implemented and tested
with shared synthetic fixtures. Real-data delivery and acceptance of the complete
Bronze-to-report source chain were independently checked on the delivered real
data (60 months, 22 matching months). EVDS delivery [#39](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39)
and the real-data demo [#40](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40)
are complete, including Mustafa's browser acceptance on 18 October 2026.
The published [v0.1.0-rc.1](https://github.com/ekincimustafa/quad-qore-agentic-analytics/releases/tag/v0.1.0-rc.1)
still targets `abea431`. The unrecorded video in
[#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46) is optional
portfolio work; it does not block the authorized local question product
(backend #69, screen #70, acceptance #71).
Weekly publication coverage is explicitly unverified without an official calendar;
the timestamp and coverage policy is documented in the [EVDS guide](docs/evds-ingestion.md).
See the [acceptance record](docs/release-acceptance.md) for verified checks and open gates.
The [real-data delivery guide](docs/real-demo-delivery.md) records verified
packages, historical request drafts and offline demo steps.
The [tool contracts](docs/tool-contracts.md) map current code to the planned and
disabled generic tools; those generic adapters are not implemented runtime tools.

Question routing has a bounded Python service and HTTP endpoint with offline
behavior tests. A separate server-side Python wrapper verifies local files before
planning; its fixed-plan evidence/chart result was checked against the same real
CLI inputs in [#42](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/42).
This offline acceptance does not measure live model understanding.
A general agent/tool registry, data catalog, general web/anomaly/causality tools
and deployment are planned work. A live Gemini narration contract check passed;
see the [LLM acceptance record](docs/llm-client.md#canlı-kabul-kaydı--15-ekim-2026).
The draft golden cases currently have schema checks; they are not a measured
end-to-end model-accuracy benchmark.
A separate [Housing question set](evals/housing_question_cases.json) has an
[executable evaluator](docs/housing-question-evals.md). Offline stub results
verify harness behavior; they do not measure model understanding.

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
| `POST /analysis/inflation` | Normalized monthly CPI rows and period; deterministic monthly/annual changes, no model or narration |
| `POST /analysis/economic/question` | Turkish question + optional Housing/CPI row groups; typed plan, one analysis, clarification/unsupported or data unavailable |
| `POST /analysis/economic/question/files` | Only `question`; verifies server-configured BDDK/EVDS files before planning, then runs at most one existing analysis |

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

The separate [CPI example](docs/inflation-api-example.json) and
[inflation guide](docs/inflation-analysis.md) work without an API key.
The two-analysis [question endpoint](docs/economic-question.md) routes CPI and
Housing questions through the bounded service core. Its twelve-case evaluator
runs offline with stub plans. The Housing question endpoint still allows only
its existing Housing analysis.

The file-backed endpoint expects these paths relative to the repository root:

- `data/silver/bddk/housing_loans.parquet`
- `data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv`

These data files are not shipped in Git. Missing/unreadable files produce
HTTP 503 (`demo_data_unavailable`); invalid analytical input produces HTTP 422.
The older `/housing/demo` service uses generic source references. The new
`/economic/question/files` endpoint uses the existing physical raw/receipt/hash,
BDDK Bronze-to-Silver and EVDS manifest verifier; its provenance is preserved.

### Question-only API with verified server files

The server's `ANALYTICS_DATA_ROOT` selects the package root **containing `data/`**.
It can be set in the process environment or local `.env`; the process value wins.
If empty, the repository root is used. The fixed relative paths are documented in
[the existing question guide](docs/economic-question.md#yalnızca-soru-alan-doğrulanmış-dosya-apisi).
Paths, data rows, model names and keys are not request fields.

For Mustafa's already installed Python 3.12.15 environment and verified package,
run from the repository root (no installation or download needed):

```powershell
$env:ANALYTICS_DATA_ROOT = (Resolve-Path .\out\housing-acceptance-20261018\inputs).Path
.\out\clean312\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

The API is at <http://127.0.0.1:8000/docs>. The new endpoint takes only:

```json
{"question":"2021-2025 faiz düşerken reel konut kredisi stokunun artmadığı aylar hangileri?"}
```

Another supported question is `2023 Ocak-Aralık TÜFE aylık ve yıllık değişimlerini özetle.`
Question planning uses the configured model: **do not submit a live request until
the separate case list/call-budget approval in #71**. Offline tests use stub plans.
This PR supplies the API; the question screen is the next separate #70 task after
backend merge. It is not available yet. No extra model call generates narration.

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
