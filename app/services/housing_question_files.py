"""Housing questions over server-configured, physically verified local files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.lakehouse.bddk_silver import (
    build_bddk_monthly_silver_table,
    validate_bddk_monthly_silver,
)
from app.lakehouse.core_validators import parse_period_to_date, resolve_secure_raw_path
from app.lakehouse.silver import validate_monthly_evds_data
from app.services.evds_manifest import (
    WEEKLY_COVERAGE_NOTE,
    append_evds_source_refs,
    load_and_validate_manifest,
)
from app.services.housing_analysis import HousingAnalysisRun
from app.services.housing_demo import DEFAULT_BDDK_SILVER_PATH, DEFAULT_BDDK_SOURCE_REF
from app.services.housing_question import (
    HousingDataCoverage,
    HousingDecision,
    ModelCall,
    run_housing_question,
)


class VerifiedHousingQuestionDataError(RuntimeError):
    """The configured source package cannot be verified before planning."""


@dataclass(frozen=True)
class VerifiedHousingQuestionPaths:
    """Trusted server configuration; all artifact paths are relative to project_root."""

    project_root: Path
    bddk_silver: Path = DEFAULT_BDDK_SILVER_PATH
    bddk_bronze: Path = Path("data/bronze/bddk")
    evds_manifest: Path = Path("data/silver/evds/monthly/manifest.json")


@dataclass(frozen=True)
class VerifiedHousingQuestionRun:
    available_period: HousingDataCoverage
    decision: HousingDecision
    analysis: HousingAnalysisRun | None


@dataclass(frozen=True)
class VerifiedQuestionInputs:
    """Verified in-memory snapshot shared by both question entry points."""

    bddk_monthly: pd.DataFrame
    evds_monthly: pd.DataFrame
    housing_coverage: HousingDataCoverage
    evds_source_refs: str
    cpi_source_ref: str


def _server_path(root: Path, relative: Path) -> Path:
    return resolve_secure_raw_path(root, str(relative))


def _load_inputs(
    paths: VerifiedHousingQuestionPaths,
) -> VerifiedQuestionInputs:
    root = Path(paths.project_root).resolve(strict=True)
    bddk_path = _server_path(root, paths.bddk_silver)
    manifest_path = _server_path(root, paths.evds_manifest)
    bddk = pd.read_parquet(bddk_path)
    if bddk.empty or not bddk.columns.is_unique or "period" not in bddk:
        raise ValueError("BDDK Silver must contain unique columns and nonempty periods.")
    periods = bddk["period"].tolist()
    for period in periods:
        if parse_period_to_date(period).isoformat()[:7] != period:
            raise ValueError("BDDK periods must use canonical YYYY-MM format.")
    start, end = min(periods), max(periods)
    bddk = validate_bddk_monthly_silver(bddk, start_period=start, end_period=end)
    # Reuse the existing receipt/hash/caption/unit checks; do not trust Silver labels alone.
    receipts_dir = _server_path(root, paths.bddk_bronze / "aylik/receipts")
    for receipt in receipts_dir.glob("*.json"):
        resolve_secure_raw_path(receipts_dir, receipt.name)
    rebuilt = build_bddk_monthly_silver_table(
        receipts_dir, _server_path(root, paths.bddk_bronze / "aylik/raw"),
        start_period=start, end_period=end,
    )
    stored = bddk.loc[:, rebuilt.columns].sort_values("period").reset_index(drop=True)
    if not stored.eq(rebuilt).all().all():
        raise ValueError("BDDK Silver differs from its verified Bronze inputs.")

    manifest = load_and_validate_manifest(manifest_path, root)
    csv_path = _server_path(root, Path(manifest.silver.path))
    csv_bytes = csv_path.read_bytes()
    if (
        len(csv_bytes) != manifest.silver.size_bytes
        or hashlib.sha256(csv_bytes).hexdigest() != manifest.silver.sha256.lower()
    ):
        raise ValueError("EVDS CSV changed after manifest validation.")
    # Parse the exact verified bytes and keep both frames in memory through planning.
    evds = pd.read_csv(BytesIO(csv_bytes))
    validate_monthly_evds_data(
        evds, start_period=manifest.silver.start_period, end_period=manifest.silver.end_period,
    )
    if (evds["housing_loan_interest_rate_pct"] < 0).any():
        raise ValueError("Housing interest rates must be non-negative.")
    refs = append_evds_source_refs(evds, manifest)["evds_source_refs"].iloc[0]
    shared_start = max(start, manifest.silver.start_period)
    shared_end = min(end, manifest.silver.end_period)
    coverage = HousingDataCoverage(start_period=shared_start, end_period=shared_end)
    cpi_refs = tuple(dict.fromkeys(
        bronze.receipt_path.strip()
        for series in manifest.series if series.series_code == "TP.TUKFIY2025.GENEL"
        for bronze in series.bronze
    ))
    return VerifiedQuestionInputs(stored, evds, coverage, refs, "; ".join(cpi_refs))


def load_verified_question_inputs(paths: VerifiedHousingQuestionPaths) -> VerifiedQuestionInputs:
    """Load the complete physical package before any question planner is called."""
    if not isinstance(paths, VerifiedHousingQuestionPaths):
        raise TypeError("paths must be VerifiedHousingQuestionPaths.")
    try:
        return _load_inputs(paths)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        raise VerifiedHousingQuestionDataError("Yerel konut veri paketi doğrulanamadı.") from None


def with_verified_housing_notes(analysis: HousingAnalysisRun) -> HousingAnalysisRun:
    evidence = analysis.evidence.model_copy(update={
        "data_quality_notes": tuple(dict.fromkeys((
            *analysis.evidence.data_quality_notes, WEEKLY_COVERAGE_NOTE,
        )))
    })
    return replace(analysis, evidence=evidence)


def run_verified_housing_question(
    question: str,
    paths: VerifiedHousingQuestionPaths,
    *,
    model_call: ModelCall | None = None,
) -> VerifiedHousingQuestionRun:
    """Verify all supplied files, then plan once and run the existing Housing service."""
    inputs = load_verified_question_inputs(paths)
    result = run_housing_question(
        question, inputs.bddk_monthly, inputs.evds_monthly, coverage=inputs.housing_coverage,
        bddk_source_ref=DEFAULT_BDDK_SOURCE_REF, evds_source_refs=inputs.evds_source_refs,
        model_call=model_call,
    )
    analysis = result.analysis
    if analysis is not None:
        analysis = with_verified_housing_notes(analysis)
    return VerifiedHousingQuestionRun(
        available_period=inputs.housing_coverage, decision=result.decision, analysis=analysis,
    )
