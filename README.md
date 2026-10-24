# Quad-Qore Agentic Analytics

A small, runnable analytics demo built for KKB Hackathon 2026 and CV/portfolio use.
You ask an economic question in natural language; a bounded LLM plan selects one of
the allowed analyses, and Python performs every calculation. A FastAPI web screen
serves the result: housing-loan analysis, a parameterized housing condition filter,
a CPI summary, or a comparison of two full calendar years. Results include evidence,
a Plotly chart where available, and optional guarded narration.

The housing scenario identifies months when housing-loan interest rates decreased
but the inflation-adjusted housing-loan stock did not increase. The default analysis
window is January 2021 to December 2025: 60 months. A key-free synthetic HTML example
can be generated from the included sample script; the real BDDK/EVDS data package is
delivered separately and is not stored in Git.

## Normal model mode vs offline preview

The same local screen has two modes:

- **Normal mode** (`uvicorn app.api.main:app`) plans free-form Turkish questions with
  the configured model, then Python runs at most one allowed analysis.
- **Offline preview** (`scripts.preview_question_ui`) needs no model key and only runs
  fixed plans for the three example questions; other questions ask for clarification.

See [Local question screen — offline preview](#local-question-screen--offline-preview).

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
| Economic question | Bounded question plan and shared HTTP dispatch to existing Housing/CPI services, including the parameterized housing condition filter, the three-panel CPI chart and two full-year CPI comparison | [Economic question guide](docs/economic-question.md) |
| Question evaluation | Nine Housing cases; 45 Economic cases with offline HTTP checks and explicitly selected, budgeted live planning | [Housing evaluation](docs/housing-question-evals.md), [Economic evaluation](docs/economic-question.md#offline-değerlendirme) |
| HTML report | Embedded Plotly.js, matching-month table, sources, methodology and limitations | [Report guide](docs/housing-report.md) |
| File demo CLI | Physical EVDS manifest checks, source/output protection, evidence/chart/summary and optional offline HTML | [Demo guide](docs/housing-demo.md) |
| Verified question files | Server-controlled local BDDK/EVDS files verified before question planning; Python wrapper only | [File question guide](docs/housing-question-files.md) |
| Local setup diagnosis CLI | Offline Python 3.12, runtime package, verified BDDK/EVDS data-package and local LLM-config check | [scripts/check_local_setup.py](scripts/check_local_setup.py) |
| Local app launcher CLI | Pre-checked single-command launcher for `preview` or `model` mode on `127.0.0.1` | [scripts/run_local_app.py](scripts/run_local_app.py) |
| CI | Offline pytest suite on pull requests and pushes to main, using Python 3.12 | [Workflow](.github/workflows/tests.yml) |

The key-free sample below uses **synthetic data**. Manifest production,
physical consumer checks and the file-to-report CLI are implemented and tested
with shared synthetic fixtures. Real-data delivery and acceptance of the complete
Bronze-to-report source chain were independently checked on the delivered real
data (60 months, 22 matching months). EVDS delivery [#39](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39)
and the real-data demo [#40](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40)
are complete, including Mustafa's browser acceptance on 18 October 2026.
The [v0.1.0-rc.1 prerelease](https://github.com/ekincimustafa/quad-qore-agentic-analytics/releases/tag/v0.1.0-rc.1)
is published from `abea431`. The optional portfolio screen recording remains open in
[#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46).
The local question product (#69 backend, #70 screen, #71 end-to-end acceptance)
is complete; the offline and bounded live acceptance recorded four calls for that
run only and is not a general model-accuracy metric.
Weekly publication coverage is explicitly unverified without an official calendar;
the timestamp and coverage policy is documented in the [EVDS guide](docs/evds-ingestion.md).
See the [acceptance record](docs/release-acceptance.md) for verified checks and the
remaining optional portfolio item.
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

### Single offline verification

Run the complete offline check with the same Python 3.12 interpreter from the
repository root. It runs the test suite, both stub evaluations and
`git diff --check` in order, stops at the first failure, and writes per-run logs
and evaluation reports under `out/verification/`.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_project
```

Linux:

```bash
.venv/bin/python -m scripts.verify_project
```

Focused tests remain available with `python -m pytest -q tests/test_<name>.py`.
These checks are offline; they do not call a live model or EVDS.

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
| `POST /analysis/economic/question` | Turkish question + optional Housing/CPI row groups; typed plan, one analysis (including two full-year CPI comparison), clarification/unsupported or data unavailable |
| `POST /analysis/economic/question/files` | Only `question`; verifies server-configured BDDK/EVDS files before planning, then runs at most one existing analysis or two-year CPI comparison |

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
The shared [question endpoint](docs/economic-question.md) routes CPI and
Housing questions through the bounded service core. A third bounded path compares
two explicitly requested full calendar years of CPI changes with the existing
`compare_inflation_years` core; average/partial-period comparison remains out of
scope. Its 45-case evaluator runs offline with stub plans. The Housing question
endpoint still allows only its existing Housing analysis.

The file-backed endpoint expects these paths relative to the repository root:

- `data/silver/bddk/housing_loans.parquet`
- `data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv`

These data files are not shipped in Git. Missing/unreadable files produce
HTTP 503 (`demo_data_unavailable`); invalid analytical input produces HTTP 422.
The older `/housing/demo` service uses generic source references. The new
`/economic/question/files` endpoint uses the existing physical raw/receipt/hash,
BDDK Bronze-to-Silver and EVDS manifest verifier; its provenance is preserved.

### Offline local setup and data-package diagnosis

Before starting the local server or offline preview, run the setup diagnosis CLI to
check Python 3.12, required runtime packages, the verified BDDK/EVDS data package, and
local LLM configuration in a single offline command. This is a setup/health check and
does **not** replace `python -m scripts.verify_project`.

The real BDDK/EVDS data package is delivered separately and is not included in a Git
clone. Data root selection follows `--data-root > process ANALYTICS_DATA_ROOT > local .env > repository root`
without overwriting the process environment with `.env`.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_local_setup --data-root ".\out\question data\inputs"
.\.venv\Scripts\python.exe -m scripts.check_local_setup --data-root ".\out\question data\inputs" --json
```

Linux:

```bash
.venv/bin/python -m scripts.check_local_setup --data-root "./out/question data/inputs"
.venv/bin/python -m scripts.check_local_setup --data-root "./out/question data/inputs" --json
```

If `--data-root` is omitted, `ANALYTICS_DATA_ROOT` (from the process environment or
local `.env`) or the repository root is checked. The command makes zero network, EVDS
or LLM calls, never prints secret values or raw `.env` lines, and never modifies or
repairs files.

- **Exit code `0` (`preview_ready: true`):** Python 3.12, runtime dependencies, and the
  complete Bronze/receipt/hash/Silver data chain passed verification. Offline preview
  (`python -m scripts.preview_question_ui`) is ready even when no LLM key is configured.
- **Exit code `1` (`preview_ready: false`):** Python version, runtime dependencies, or
  the data package is missing or corrupt.
- **Model configuration vs live access:** `normal_mode_configured: true` only means
  `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_CHAT_MODEL` and `LLM_TIMEOUT_SECONDS` passed local
  syntax validation (`Ayar mevcut; sağlayıcı erişimi denenmedi`). Live provider access is
  never tested (`live_model_access_verified: false`).

| Diagnostic code | Category | Meaning and action |
| --- | --- | --- |
| `ok` | All | Check passed |
| `python_version_mismatch` | `python` | Active interpreter is not Python 3.12 (`exit 1`); recreate `.venv` with Python 3.12 |
| `missing_dependencies` | `dependencies` | One or more runtime packages from `requirements.txt` are missing (`exit 1`); run `pip install -r requirements.txt` |
| `incompatible_dependencies` | `dependencies` | Installed package version conflicts with `requirements.txt` pin or major version (`exit 1`); run `pip install -r requirements.txt` |
| `not_run` | `data_root`, `data_package`, `llm_config` | Check skipped (`status: skipped`) because Python or runtime package checks failed (`exit 1`) |
| `data_root_missing` | `data_package` | Selected data root does not exist or is not a directory (`exit 1`); point `--data-root` or `ANALYTICS_DATA_ROOT` to the directory containing `data/` |
| `data_files_missing` | `data_package` | Required Silver, EVDS manifest, or Bronze/receipt files are missing under the selected root (`exit 1`); extract the verified delivery package and select its `inputs` folder |
| `data_integrity_failed` | `data_package` | Hash, provenance, schema, or Bronze-to-Silver verification failed (`exit 1`); re-extract from the unmodified verified archive |
| `llm_configured_untested` | `llm_config` | Local LLM settings are present; live provider access was not tested (`exit 0` if data and runtime are ready) |
| `llm_not_configured` | `llm_config` | Warning: `LLM_API_KEY`, `LLM_BASE_URL` or `LLM_CHAT_MODEL` is not set (`exit 0` for offline preview; configure `.env` for normal mode) |
| `llm_config_invalid` | `llm_config` | Warning: local LLM setting syntax (such as URL or timeout) is invalid (`exit 0` for offline preview; fix `.env` before normal mode) |

### Single-command local app launcher

Use `scripts.run_local_app` to run the offline setup/data-package pre-checks and start
either the key-free offline preview (`--mode preview`, default) or normal model mode
(`--mode model`) on `127.0.0.1` in a single command. The real BDDK/EVDS data package is
delivered separately and is not included in Git; point `--data-root` (or
`ANALYTICS_DATA_ROOT` in the process environment / local `.env`) to the directory
containing `data/` (for example `out/question data/inputs`). This launcher is a local
startup convenience and does **not** replace `python -m scripts.verify_project`.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_local_app --mode preview --data-root "out/question data/inputs"
.\.venv\Scripts\python.exe -m scripts.run_local_app --mode model --data-root "out/question data/inputs" --port 8001
.\.venv\Scripts\python.exe -m scripts.run_local_app --mode preview --data-root "out/question data/inputs" --check-only
```

Linux:

```bash
.venv/bin/python -m scripts.run_local_app --mode preview --data-root "out/question data/inputs"
.venv/bin/python -m scripts.run_local_app --mode model --data-root "out/question data/inputs" --port 8001
.venv/bin/python -m scripts.run_local_app --mode preview --data-root "out/question data/inputs" --check-only
```

- **`--mode preview` (default):** Starts `scripts.preview_question_ui.create_preview_app`
  when Python 3.12, runtime dependencies, and the physical data package pass verification,
  even if no LLM key is configured. Runs fixed plans for only the three example questions.
- **`--mode model`:** Starts `app.api.main.create_app` only when the runtime, physical
  data package, and local LLM settings (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_CHAT_MODEL`,
  `LLM_TIMEOUT_SECONDS`) are valid. Does not make automatic provider calls on startup;
  live model calls occur only when a question is submitted in the UI.
- **`--check-only`:** Runs the pre-checks and reports readiness for the selected mode
  without starting the server, binding a port, opening a browser, or calling a provider.
- **Error and exit behavior:** Invalid CLI flags (`--mode` outside `preview`/`model` or
  `--port` outside `1..65535`) exit with code `2`. Failed environment/data pre-checks,
  missing/invalid LLM settings in `--mode model`, or an already occupied `127.0.0.1:<port>`
  exit with code `1` without starting the server, killing other processes, or switching
  ports. `ANALYTICS_DATA_ROOT` is applied in-process for the server's lifetime and
  restored on exit or Ctrl+C without modifying `.env`.

### Question-only API with verified server files

The server's `ANALYTICS_DATA_ROOT` selects the package root **containing `data/`**.
It can be set in the process environment or local `.env`; the process value wins.
If empty, the repository root is used. The fixed relative paths are documented in
[the existing question guide](docs/economic-question.md#yalnızca-soru-alan-doğrulanmış-dosya-apisi).
Paths, data rows, model names and keys are not request fields.

Use the Python 3.12 `.venv` from the quick start above, or an existing working
Python 3.12 environment. Run from the repository root. The real data is delivered
separately; it is not included in a clone. Reuse the verified
`Housing_tam_teslim_20261018.zip` delivery; no new data download is needed.

If the package is not already extracted, replace the ZIP path below with its
local location and extract once into a new directory. Do not overwrite an
existing data directory. The example deliberately uses a path containing spaces:

```powershell
$packagePath = 'C:\path\to\Housing_tam_teslim_20261018.zip'
$deliveryPath = Join-Path $PWD 'out\question data'
Expand-Archive -LiteralPath $packagePath -DestinationPath $deliveryPath
```

In each server terminal, point to the extracted **`inputs` directory containing
`data/`**, not the ZIP's outer directory. If already extracted elsewhere, replace
the quoted path with that existing `inputs` path. Keep paths quoted when they
contain spaces. This changes only the current terminal's environment; no `.env`
edit is needed:

```powershell
$env:ANALYTICS_DATA_ROOT = (Resolve-Path -LiteralPath '.\out\question data\inputs').Path
```

For the normal API server (question submission uses the configured live model):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

The API is at <http://127.0.0.1:8000/docs>. The new endpoint takes only:

```json
{"question":"2021-2025 faiz düşerken reel konut kredisi stokunun artmadığı aylar hangileri?"}
```

Another supported question is `2023 Ocak-Aralık TÜFE aylık ve yıllık değişimlerini özetle.`
In normal model mode, a parameterized housing question such as
`2021 Ocak-Mart faiz artarken reel konut kredisi stoku artan aylar hangileri?`
can select the condition filter (1–3 AND conditions over the four allowed metrics).
Question planning uses the configured model. The approved four-call live run
in #71 is complete; additional automated live requests need separate approval.
Offline tests use stub plans.
The API was merged in PR #72; the #70 screen was merged in PR #73 (`5bc12a7`).
The screen at <http://127.0.0.1:8000/> calls this API; summaries only format
evidence, with no extra model call. The normal screen supports the fixed Housing
analysis, the parameterized Housing condition filter, the CPI summary and the
two-year CPI comparison. The CPI summary
reuses the existing three-panel index/monthly/annual chart before its table; the
two-year comparison remains table-based. The offline preview below fixes plans
for only the three example questions. No live-model success is claimed for the
condition filter or the two-year comparison.

### Local question screen — offline preview

Set `ANALYTICS_DATA_ROOT` in this terminal as described above, then run from
the repository root with the same Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m scripts.preview_question_ui
```

Open <http://127.0.0.1:8000/>. This explicit **offline preview** runs fixed plans for
the three example questions; click an example, then **Analiz et**. The Housing example
uses 2021–2025 (60 months / 22 matches in the verified delivery); CPI uses 2023
(12 monthly rows); the comparison uses the two full years 2023 and 2024 in that
order (12+12 rows). Other preview questions ask for clarification. The visible
offline label states that only these three fixed examples are supported and that
free-form questions need normal structured model mode; it does not claim
natural-language understanding. Once the environment and data package are ready,
preview needs no model key, additional installation, data download or live model
call. A missing or invalid data root produces a safe data-package error after
**Analiz et**; it does not create or download replacement data.

The normal `uvicorn app.api.main:app` command serves the same screen with configured
model planning. **The four-call acceptance budget in #71 has been consumed; do not
resubmit to reproduce its screenshots.** Opening the page or filling an example
never sends a question automatically. Both launchers use port 8000. Stop your own
server with Ctrl+C before switching between them; do not stop another application's
process to free the port.

Mustafa confirmed both offline examples, the Housing chart/table and interactions,
the CPI table, and sources/limitations on 19 October 2026. This offline user review
is complete. (The preview had two examples then; the 2023/2024 comparison example
was added later in #91.) The four live cases ran on 19 October. On 20 October, Mustafa confirmed
the four saved static screenshots: Housing period/count/chart/table, CPI period
and monthly/annual distinction, clarification/unsupported messages with no stale
result, and no obvious overflow/overlap. This was a static review with no new
interaction test or model call. Acceptance is recorded as complete in
[#71](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/71).
That issue preserves the expectations written before execution and per-case results.
The normal screen used `gemini-3.5-flash-lite`: **four calls, zero retries**,
one submission per case, no extra narration or paid-plan/provider switch.
Housing evidence/chart matched the prior CLI (60 months/22 matches); CPI matched
the direct Python service (12 months). Missing period requested clarification;
the forecast was unsupported, both without analysis. The same responses rendered
the screen. Local `out/live-acceptance-20261019/case-1.png` through `case-4.png`
can be reviewed without making another model call. Real data/audits remain outside
Git; 145 input hashes were unchanged. These four cases are not an accuracy metric.

## Real-data preparation

This is separate from the synthetic quick start and regenerates data from external
services. The delivered package was verified separately on 18 October 2026; these
commands are for reproduction, not a remaining acceptance gate. Set `EVDS_API_KEY`
in the process environment before EVDS acquisition; the EVDS CLI does not load .env
itself.

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
Source hashes, the three sample-month comparisons and complete source binding were
verified on the delivered package on 18 October 2026. See the
[acceptance record](docs/release-acceptance.md) and the BDDK/EVDS guides above.

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

## Team contributions

This was a three-person student team effort. The Git history and the contribution
table in the [acceptance record](docs/release-acceptance.md) hold the dated evidence.

- **Mustafa Ekinci:** housing analysis, evidence/chart, guarded narration, question
  harness and evaluation, FastAPI endpoints, local question screen, and the later CPI
  summary/chart/report and two-year comparison integrations; release and acceptance
  records.
- **Afra Topcu:** secure EVDS ingestion and Silver validation, receipt/coverage checks,
  EVDS manifest producer and demo fixtures, and the initial tool-contract contribution.
- **Osman Erdem Dutar:** BDDK ingestion and Bronze provenance, BDDK Silver pipeline,
  offline housing demo CLI, and the real-data delivery/acceptance work.

## Project guides and security

- [Architecture](docs/architecture.md) and [scenario/design contract](docs/first-demo-scenario.md): design documents; some agent workflow is planned.
- [HTML report](docs/housing-report.md), [narration](docs/housing-narration.md), [acceptance record](docs/release-acceptance.md).
- Runtime calculations use pandas; Parquet I/O uses pyarrow; presentation uses Plotly. Full dependencies are in [requirements.txt](requirements.txt).
- Keep credentials in local configuration. Never commit keys, raw data, generated reports or secret-bearing logs.
- Tests cover deterministic calculations, integrity/error boundaries, API, narration and report behavior. CI is test automation; deployment is future work.
