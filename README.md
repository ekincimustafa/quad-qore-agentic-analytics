# Quad-Qore Agentic Analytics

A modular lakehouse and agentic analytics platform developed for KKB Hackathon 2026.

## Project Goal

The platform collects and organizes financial data from sources such as BDDK and TCMB EVDS, executes analytical tools based on natural-language questions, validates the generated results, and presents findings with traceable data sources.

## Architecture Principle

The project follows a harness-first architecture.

Deterministic operations such as data ingestion, cleaning, frequency alignment, statistical calculations, validation, and source tracking are implemented in Python. The language model is used only for tasks that require flexible reasoning, such as understanding user intent, selecting appropriate tools, and explaining verified analytical results.

This separation is intended to improve reliability, traceability, and model-independent performance.

## Core Components

* BDDK and TCMB EVDS data source connectors
* Bronze, Silver, and Gold lakehouse layers
* Data catalog and metadata management
* Deterministic analytical tools
* Agent orchestration and tool selection
* Structured output validation
* Source tracking and traceability
* FastAPI backend
* User interface

## Initial Demo Scenario

The first end-to-end scenario compares housing loan amounts from BDDK with housing loan interest rates from TCMB EVDS.

The scenario aims to:

1. Build a monthly dataset covering the required date range.
2. Identify periods in which housing loan interest rates decreased but housing loan amounts did not increase.
3. Enrich the analysis with inflation-adjusted loan amounts and the Housing Price Index.
4. Present the findings with their source series, units, date ranges, and analytical limitations.

## Current Status

* Initial repository structure has been created.
* Kloudeks MIA chat model connectivity has been verified.
* Environment-based secret management has been configured.
* A reusable MIA client has been implemented.
* A manual MIA connection smoke test has been added.
* Automated tests for the MIA client are passing.
* BDDK and TCMB EVDS data source investigations are in progress.
* A draft golden evaluation dataset with ten behavioral test cases has been added.

## Kloudeks MIA Connection

The application uses the following chat model provided through Kloudeks MIA:

```text
kkbhackathon2026/Qwen3.8-27B
```

The `openai` Python package is used only as an OpenAI-compatible client library. Runtime requests are sent to the Kloudeks MIA base URL and use the hackathon-provided model.

The API key is loaded from a local `.env` file and must never be included in the source code.

## Local Setup

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Install the dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Create the local environment file

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Add the provided API key to the local `.env` file:

```env
MIA_API_KEY=
```

Do not add the actual API key to `.env.example`.

### 4. Verify the MIA connection

Run the manual connection smoke test:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test_mia
```

A successful request produces a text response from the Kloudeks MIA model. The API key is never printed to the terminal.

### 5. Run the automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The automated tests verify configuration validation, empty prompt handling, model selection, request construction, and response processing without sending a real network request.

## Security

* API keys and credentials must never be committed to the repository.
* Local credentials must be stored only in the ignored `.env` file.
* `.env.example` must contain variable names and safe default values only.
* Secrets must not appear in source code, logs, screenshots, issues, or pull requests.
* Repository changes must be reviewed before merging into the `main` branch.
