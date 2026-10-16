"""EVDS manifest producer helpers."""
import json
from pathlib import Path

import re
import pandas as pd

from app.lakehouse.evds_weekly_coverage import (
    assess_monthly_weekly_coverage,
)

from app.connectors.evds import EVDS_SERIES_FREQUENCIES
from app.lakehouse.bronze import calculate_sha256
from app.lakehouse.core_validators import (
    IntegrityError,
    parse_iso8601_timestamp,
)


def repo_relative_data_path(
    path: str | Path,
    *,
    project_root: str | Path,
    data_root: str | Path,
) -> str:
    """Convert a data file path to a safe repository-relative path."""

    root = Path(project_root).resolve(strict=True)

    data = Path(data_root)
    if not data.is_absolute():
        data = root / data
    data = data.resolve(strict=True)

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = root / file_path
    file_path = file_path.resolve(strict=True)

    try:
        data.relative_to(root)
        file_path.relative_to(data)
    except ValueError as exc:
        raise ValueError(
            "EVDS manifest path must stay inside the project data root."
        ) from exc

    if not file_path.is_file():
        raise ValueError("EVDS manifest path must point to a file.")

    return file_path.relative_to(root).as_posix()


def normalize_receipt_raw_path(
    raw_path: str,
    *,
    project_root: str | Path,
    data_root: str | Path,
) -> str:
    """Normalize an EVDS receipt raw path for the manifest."""

    if not isinstance(raw_path, str):
        raise ValueError("Invalid EVDS receipt raw path.")

    parts = raw_path.split("/")

    if (
        not parts
        or parts[0] != "bronze"
        or any(part in ("", ".", "..") for part in parts)
        or "\\" in raw_path
    ):
        raise ValueError("Unsafe EVDS receipt raw path.")

    root = Path(project_root).resolve(strict=True)

    data = Path(data_root)
    if not data.is_absolute():
        data = root / data

    data = data.resolve(strict=True)

    return repo_relative_data_path(
        data.joinpath(*parts),
        project_root=root,
        data_root=data,
    )


def build_bronze_manifest_entry(
    *,
    selected_raw_path: str | Path,
    series_code: str,
    request_start: str,
    request_end: str,
    project_root: str | Path,
    data_root: str | Path,
) -> dict:
    """Build verified Bronze provenance for an EVDS manifest."""

    root = Path(project_root).resolve(strict=True)

    data = Path(data_root)
    if not data.is_absolute():
        data = root / data
    data = data.resolve(strict=True)

    if series_code not in EVDS_SERIES_FREQUENCIES:
        raise ValueError(f"Unsupported EVDS series: {series_code}")

    selected = Path(selected_raw_path)
    if not selected.is_absolute():
        selected = root / selected
    selected = selected.resolve(strict=True)

    selected_relative = repo_relative_data_path(
        selected,
        project_root=root,
        data_root=data,
    )

    dataset = series_code.lower().replace(".", "_")
    expected_directory = (
        data / "bronze" / "evds" / dataset
    ).resolve()

    if selected.parent != expected_directory:
        raise ValueError(
            "Selected Bronze file belongs to an unexpected dataset."
        )

    receipts_dir = expected_directory / "receipts"

    if not receipts_dir.is_dir():
        raise ValueError("EVDS receipts directory not found.")

    matches = []

    for receipt_file in sorted(receipts_dir.glob("*.json")):
        try:
            receipt = json.loads(
                receipt_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Invalid EVDS receipt: {receipt_file.name}"
            ) from exc

        if not isinstance(receipt, dict):
            raise ValueError("Invalid EVDS receipt structure.")

        required = {
            "series_code",
            "frequency",
            "request_start",
            "request_end",
            "downloaded_at",
            "raw_path",
            "sha256",
            "size_bytes",
        }

        if required.difference(receipt):
            raise ValueError(
                f"Missing EVDS receipt fields: {receipt_file.name}"
            )

        if (
            receipt["series_code"] != series_code
            or receipt["frequency"]
            != EVDS_SERIES_FREQUENCIES[series_code]
            or receipt["request_start"] != request_start
            or receipt["request_end"] != request_end
        ):
            continue

        raw_relative = normalize_receipt_raw_path(
            receipt["raw_path"],
            project_root=root,
            data_root=data,
        )

        raw_file = (root / raw_relative).resolve(strict=True)

        if (
            calculate_sha256(raw_file) != receipt["sha256"]
            or raw_file.stat().st_size != receipt["size_bytes"]
        ):
            raise ValueError(
                f"EVDS Bronze integrity mismatch: {receipt_file.name}"
            )

        try:
            timestamp = parse_iso8601_timestamp(
                receipt["downloaded_at"],
                field_name="downloaded_at",
            )
        except IntegrityError as exc:
            raise ValueError(
                f"Invalid receipt timestamp: {receipt_file.name}"
            ) from exc

        matches.append(
            (
                timestamp,
                receipt_file.name,
                raw_file,
                receipt_file,
                receipt,
                raw_relative,
            )
        )

    if not matches:
        raise ValueError("No matching EVDS Bronze receipt found.")

    # Aynı seçim kuralı: son timestamp, eşitlikte dosya adı.
    latest = max(
        matches,
        key=lambda item: (item[0], item[1]),
    )

    _, _, latest_raw, receipt_file, receipt, raw_relative = latest

    if latest_raw != selected:
        raise ValueError(
            "Selected Bronze file does not match the latest "
            "receipt for this request."
        )

    return {
        "receipt_path": repo_relative_data_path(
            receipt_file,
            project_root=root,
            data_root=data,
        ),
        "raw_path": selected_relative,
        "sha256": receipt["sha256"],
        "size_bytes": receipt["size_bytes"],
        "downloaded_at": receipt["downloaded_at"],
        "request_start": receipt["request_start"],
        "request_end": receipt["request_end"],
    }

def build_silver_manifest_entry(
    *,
    silver_path: str | Path,
    project_root: str | Path,
    data_root: str | Path,
) -> dict:
    """Build verified Silver CSV metadata for the EVDS manifest."""

    root = Path(project_root).resolve(strict=True)

    data = Path(data_root)
    if not data.is_absolute():
        data = root / data
    data = data.resolve(strict=True)

    # Dosya yolunu repo köküne göre güvenli biçimde oluştur.
    relative_path = repo_relative_data_path(
        silver_path,
        project_root=root,
        data_root=data,
    )

    csv_path = (root / relative_path).resolve(strict=True)

    expected_directory = (
        data / "silver" / "evds" / "monthly"
    ).resolve()

    if csv_path.parent != expected_directory:
        raise ValueError(
            "EVDS Silver CSV is outside the expected directory."
        )

    if csv_path.suffix.lower() != ".csv":
        raise ValueError("EVDS Silver file must be a CSV.")

    # Gerçek CSV dosyasını oku.
    df = pd.read_csv(csv_path)

    required_columns = [
        "period",
        "housing_loan_interest_rate_pct",
        "weekly_observation_count",
        "cpi_index",
        "housing_price_index",
    ]

    if list(df.columns) != required_columns:
        raise ValueError(
            "EVDS Silver CSV columns do not match the contract."
        )

    if df.empty:
        raise ValueError("EVDS Silver CSV cannot be empty.")

    # Sayısal sütunlarda eksik veya geçersiz değer olmamalı.
    for column in required_columns[1:]:
        values = pd.to_numeric(df[column], errors="coerce")

        if (
            values.isna().any()
            or values.isin([float("inf"), float("-inf")]).any()
        ):
            raise ValueError(
                f"Invalid EVDS Silver values in column: {column}"
            )

    counts = pd.to_numeric(
        df["weekly_observation_count"]
    )

    if ((counts < 1) | (counts % 1 != 0)).any():
        raise ValueError(
            "Invalid weekly observation count in Silver CSV."
        )

    # Aylar YYYY-MM formatında ve kesintisiz olmalı.
    periods = df["period"].astype(str).tolist()

    for period in periods:
        if not re.fullmatch(
            r"\d{4}-(0[1-9]|1[0-2])",
            period,
        ):
            raise ValueError(
                f"Invalid EVDS Silver period: {period}"
            )

    expected_periods = pd.period_range(
        start=periods[0],
        end=periods[-1],
        freq="M",
    ).astype(str).tolist()

    if periods != expected_periods:
        raise ValueError(
            "EVDS Silver periods are not consecutive."
        )

    return {
        "path": relative_path,
        "sha256": calculate_sha256(csv_path),
        "size_bytes": csv_path.stat().st_size,
        "row_count": len(df),
        "start_period": periods[0],
        "end_period": periods[-1],
        "columns": required_columns,
    }

def build_evds_manifest(
    *,
    silver_path: str | Path,
    selected_raw_paths: dict[str, str | Path],
    series_metadata: dict[str, dict],
    request_start: str,
    request_end: str,
    project_root: str | Path,
    data_root: str | Path,
) -> dict:
    """Build an EVDS manifest using the consumer's v1.0 schema."""

    required_series = {
        "TP.KTF12": [
            "housing_loan_interest_rate_pct",
            "weekly_observation_count",
        ],
        "TP.TUKFIY2025.GENEL": [
            "cpi_index",
        ],
        "TP.KFE.TR": [
            "housing_price_index",
        ],
    }

    # Üç serinin tamamı bulunmalı.
    if set(selected_raw_paths) != set(required_series):
        raise ValueError(
            "Selected Bronze inputs must contain exactly "
            "the three required EVDS series."
        )

    if set(series_metadata) != set(required_series):
        raise ValueError(
            "EVDS series metadata must contain exactly "
            "the three required EVDS series."
        )

    # Silver dosyasının gerçek bilgilerini al.
    silver_entry = build_silver_manifest_entry(
        silver_path=silver_path,
        project_root=project_root,
        data_root=data_root,
    )

    #45 tarafından üretilen kapsam raporunu doğrula.
    coverage_path = Path(silver_path).with_suffix(
        ".coverage.json"
    )

    weekly_coverage = build_weekly_coverage_manifest_entry(
        coverage_path=coverage_path,
        silver_path=silver_path,
    )

    required_metadata_fields = {
        "silver_columns",
        "unit",
        "native_frequency",
        "target_frequency",
        "base_year",
        "base_year_source",
        "transformation",
    }

    series_entries = []

    for series_code, expected_columns in required_series.items():
        metadata = series_metadata[series_code]

        if (
            not isinstance(metadata, dict)
            or set(metadata) != required_metadata_fields
        ):
            raise ValueError(
                f"Invalid EVDS metadata fields: {series_code}"
            )

        if metadata["silver_columns"] != expected_columns:
            raise ValueError(
                f"Invalid Silver column mapping: {series_code}"
            )

        if (
            metadata["native_frequency"]
            != EVDS_SERIES_FREQUENCIES[series_code]
        ):
            raise ValueError(
                f"Invalid native frequency: {series_code}"
            )

        if metadata["target_frequency"] != "monthly":
            raise ValueError(
                f"Invalid target frequency: {series_code}"
            )

        for field in (
            "unit",
            "native_frequency",
            "target_frequency",
            "base_year_source",
            "transformation",
        ):
            value = metadata[field]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Invalid {field} for {series_code}"
                )

        base_year = metadata["base_year"]

        if base_year is not None and (
            type(base_year) is not int or base_year <= 0
        ):
            raise ValueError(
                f"Invalid base year: {series_code}"
            )

        # Silver üretiminde kullanılan Bronze kaydını doğrula.
        bronze_entry = build_bronze_manifest_entry(
            selected_raw_path=selected_raw_paths[series_code],
            series_code=series_code,
            request_start=request_start,
            request_end=request_end,
            project_root=project_root,
            data_root=data_root,
        )

        series_entry = {
            "series_code": series_code,
            "silver_columns": metadata["silver_columns"],
            "unit": metadata["unit"],
            "native_frequency": metadata["native_frequency"],
            "target_frequency": metadata["target_frequency"],
            "base_year": base_year,
            "base_year_source": metadata["base_year_source"],
            "transformation": metadata["transformation"],
            "bronze": [bronze_entry],
        }

        if series_code == "TP.KTF12":
            series_entry["weekly_coverage"] = weekly_coverage

        series_entries.append(series_entry)

    return {
        "schema_version": "1.0",
        "dataset": "evds_monthly_silver",
        "silver": silver_entry,
        "series": series_entries,
    }

def build_weekly_coverage_manifest_entry(
    *,
    coverage_path: str | Path,
    silver_path: str | Path,
) -> dict:
    """Validate weekly coverage and return the manifest subobject."""

    coverage_file = Path(coverage_path)
    silver_file = Path(silver_path)

    # 1. Kalite raporunu oku.
    try:
        report = json.loads(
            coverage_file.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "Cannot read EVDS weekly coverage report."
        ) from exc

    if not isinstance(report, dict):
        raise ValueError("Invalid weekly coverage report.")

    required_fields = {
        "schema_version",
        "silver_sha256",
        "overall_status",
        "calendar_verification",
        "months",
    }

    if set(report) != required_fields:
        raise ValueError(
            "Invalid weekly coverage report fields."
        )

    if report["schema_version"] != "1.0":
        raise ValueError(
            "Unsupported weekly coverage report version."
        )

    # 2. Raporun doğru Silver CSV'ye ait olduğunu doğrula.
    actual_sha256 = calculate_sha256(silver_file)

    if report["silver_sha256"] != actual_sha256:
        raise ValueError(
            "Weekly coverage Silver SHA256 mismatch."
        )

    if (
        report["overall_status"] != "unverified"
        or report["calendar_verification"] != "not_available"
    ):
        raise ValueError(
            "Unsupported weekly coverage verification status."
        )

    # 3. Silver CSV'deki dönem ve gözlem sayılarını oku.
    silver = pd.read_csv(silver_file)

    if not {
        "period",
        "weekly_observation_count",
    }.issubset(silver.columns):
        raise ValueError(
            "Silver CSV is missing weekly coverage columns."
        )

    if silver.empty:
        raise ValueError("Silver CSV cannot be empty.")

    periods = silver["period"].astype(str).tolist()

    if any(
        not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", p)
        for p in periods
    ):
        raise ValueError("Invalid Silver monthly periods.")

    expected_periods = pd.period_range(
        start=periods[0],
        end=periods[-1],
        freq="M",
    ).astype(str).tolist()

    if periods != expected_periods:
        raise ValueError(
            "Silver monthly periods are not consecutive."
        )

    counts = pd.to_numeric(
        silver["weekly_observation_count"],
        errors="coerce",
    )

    if (
        counts.isna().any()
        or (counts < 1).any()
        or (counts % 1 != 0).any()
    ):
        raise ValueError(
            "Invalid Silver weekly observation counts."
        )

    # 4. Her ayın kapsam bilgisini doğrula.
    months = report["months"]

    if not isinstance(months, list):
        raise ValueError(
            "Weekly coverage months must be a list."
        )

    if len(months) != len(periods):
        raise ValueError(
            "Weekly coverage month count mismatch."
        )

    required_month_fields = {
        "period",
        "status",
        "observed_count",
        "expected_count",
        "observed_dates",
        "quality_note",
    }

    for index, month in enumerate(months):
        if (
            not isinstance(month, dict)
            or set(month) != required_month_fields
        ):
            raise ValueError(
                "Invalid weekly coverage month fields."
            )

        period = periods[index]

        if month["period"] != period:
            raise ValueError(
                f"Weekly coverage period mismatch: {period}"
            )

        if (
            month["status"] != "unverified"
            or month["expected_count"] is not None
        ):
            raise ValueError(
                f"Invalid weekly coverage status: {period}"
            )

        if (
            not isinstance(month["quality_note"], str)
            or not month["quality_note"].strip()
        ):
            raise ValueError(
                f"Missing weekly coverage quality note: {period}"
            )

        observed_dates = month["observed_dates"]

        if not isinstance(observed_dates, list):
            raise ValueError(
                f"Invalid observed dates: {period}"
            )

        # Mevcut #45 doğrulama fonksiyonunu yeniden kullan.
        assessment = assess_monthly_weekly_coverage(
            period=period,
            observed_dates=observed_dates,
        )

        if observed_dates != list(assessment.observed_dates):
            raise ValueError(
                f"Weekly observation dates are not sorted: {period}"
            )

        if (
            type(month["observed_count"]) is not int
            or month["observed_count"] != assessment.observed_count
            or month["observed_count"] != int(counts.iloc[index])
        ):
            raise ValueError(
                f"Weekly observation count mismatch: {period}"
            )

    # 5. Yalnızca tüketicinin beklediği alt nesneyi döndür.
    return {
        "overall_status": report["overall_status"],
        "calendar_verification": report["calendar_verification"],
        "months": months,
    }