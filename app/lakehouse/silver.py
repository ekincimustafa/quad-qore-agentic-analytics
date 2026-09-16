from __future__ import annotations

import pandas as pd


EVDS_DATE_COLUMN = "Tarih"
EVDS_HOUSING_RATE_COLUMN = "TP_KTF12"

EVDS_MONTHLY_VALUE_COLUMNS = (
    "housing_loan_interest_rate_pct",
    "cpi_index",
    "housing_price_index",
    "weekly_observation_count",
)


def _parse_monthly_period(
    value: object,
    *,
    field_name: str,
) -> pd.Period:
    """Parse a strict YYYY-MM value as a real monthly period."""

    value_text = str(value).strip()

    if (
        len(value_text) != 7
        or value_text[4] != "-"
        or not value_text[:4].isdigit()
        or not value_text[5:].isdigit()
    ):
        raise ValueError(
            f"Invalid monthly period for {field_name}: {value}"
        )

    try:
        return pd.Period(value_text, freq="M")
    except ValueError as exc:
        raise ValueError(
            f"Invalid monthly period for {field_name}: {value}"
        ) from exc


def _monthly_period_bounds(
    start_period: str,
    end_period: str,
) -> tuple[pd.Period, pd.Period]:
    """Validate an inclusive monthly period range."""

    start = _parse_monthly_period(
        start_period,
        field_name="start_period",
    )
    end = _parse_monthly_period(
        end_period,
        field_name="end_period",
    )

    if start > end:
        raise ValueError(
            "start_period must be less than or equal to end_period."
        )

    return start, end


def monthly_housing_loan_interest_rate(
    weekly_data: pd.DataFrame,
    *,
    start_date: str = "2021-01-01",
    end_date: str = "2026-06-30",
) -> pd.DataFrame:
    """
    Convert weekly EVDS housing loan interest rates to monthly averages.

    The TP.KTF12 series is kept in its original weekly frequency in Bronze.
    This function creates a monthly Silver representation by taking the
    arithmetic mean of weekly observations within each month.
    """

    required_columns = {
        EVDS_DATE_COLUMN,
        EVDS_HOUSING_RATE_COLUMN,
    }

    missing_columns = required_columns.difference(weekly_data.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required EVDS columns: {sorted(missing_columns)}"
        )

    data = weekly_data[
        [EVDS_DATE_COLUMN, EVDS_HOUSING_RATE_COLUMN]
    ].copy()

    # EVDS Excel files may contain metadata rows below the observations.
    raw_dates = data[EVDS_DATE_COLUMN]
    date_text = raw_dates.astype("string").str.strip()

    parsed_dates = pd.to_datetime(
        raw_dates,
        dayfirst=True,
        format="mixed",
        errors="coerce",
    )

    numeric_observation_values = pd.to_numeric(
        data[EVDS_HOUSING_RATE_COLUMN],
        errors="coerce",
    )

    date_like_mask = date_text.str.fullmatch(
        r"\d{1,4}\D+\d{1,2}\D+\d{1,4}",
        na=False,
    )

    invalid_date_mask = (
        parsed_dates.isna()
        & (
            numeric_observation_values.notna()
            | date_like_mask
        )
    )

    if invalid_date_mask.any():
        invalid_dates = date_text.loc[invalid_date_mask].tolist()
        raise ValueError(
            f"Invalid EVDS observation dates detected: {invalid_dates}"
        )

    observation_mask = parsed_dates.notna()

    data = data.loc[observation_mask].copy()
    data["date"] = parsed_dates.loc[observation_mask]

    data["housing_loan_interest_rate_pct"] = pd.to_numeric(
        data[EVDS_HOUSING_RATE_COLUMN],
        errors="coerce",
    )

    if data["housing_loan_interest_rate_pct"].isna().any():
        raise ValueError(
            "EVDS observation rows contain missing or non-numeric interest rates."
        )

    if data["date"].duplicated().any():
        raise ValueError("Duplicate EVDS observation dates detected.")

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    data = data[
        (data["date"] >= start)
        & (data["date"] <= end)
    ].copy()

    if data.empty:
        raise ValueError("No EVDS observations found in the requested date range.")

    data["period"] = data["date"].dt.to_period("M").astype(str)

    monthly = (
        data.groupby("period", as_index=False)
        .agg(
            housing_loan_interest_rate_pct=(
                "housing_loan_interest_rate_pct",
                "mean",
            ),
            weekly_observation_count=(
                "housing_loan_interest_rate_pct",
                "count",
            ),
        )
        .sort_values("period")
        .reset_index(drop=True)
    )

    return monthly


def monthly_cpi_index(
    raw_data: pd.DataFrame,
    *,
    start_period: str = "2021-01",
    end_period: str = "2026-06",
) -> pd.DataFrame:
    """
    Standardize the monthly EVDS CPI export.

    TP.TUKFIY2025.GENEL is exported in wide format:
    months are columns and 'Genel Endeks' is the observation row.
    """

    label_column = "Unnamed: 0"

    if label_column not in raw_data.columns:
        raise ValueError("CPI export does not contain the expected label column.")

    cpi_rows = raw_data[
        raw_data[label_column].astype(str).str.strip() == "Genel Endeks"
    ]

    if len(cpi_rows) != 1:
        raise ValueError("Expected exactly one 'Genel Endeks' row in CPI data.")

    month_columns = [
        column
        for column in raw_data.columns
        if isinstance(column, str)
        and len(column) == 7
        and column[4] == "-"
        and column[:4].isdigit()
        and column[5:].isdigit()
    ]

    if not month_columns:
        raise ValueError("No monthly CPI columns were found.")

    for column in month_columns:
        _parse_monthly_period(
            column,
            field_name="CPI period",
        )

    cpi_row = cpi_rows.iloc[0]

    monthly = pd.DataFrame(
        {
            "period": month_columns,
            "cpi_index": [
                pd.to_numeric(cpi_row[column], errors="coerce")
                for column in month_columns
            ],
        }
    )

    if monthly["cpi_index"].isna().any():
        raise ValueError("CPI observations contain missing or non-numeric values.")

    start, end = _monthly_period_bounds(
        start_period,
        end_period,
    )

    period_values = monthly["period"].map(
        lambda value: _parse_monthly_period(
            value,
            field_name="CPI period",
        )
    )

    monthly = monthly[
        (period_values >= start)
        & (period_values <= end)
    ].copy()

    if monthly.empty:
        raise ValueError("No CPI observations found in the requested period.")

    if monthly["period"].duplicated().any():
        raise ValueError("Duplicate CPI periods detected.")

    return (monthly.sort_values("period").reset_index(drop=True))


def monthly_housing_price_index(
    raw_data: pd.DataFrame,
    *,
    start_period: str = "2021-01",
    end_period: str = "2026-06",
) -> pd.DataFrame:
    """
    Standardize the monthly EVDS Housing Price Index export.

    TP.KFE.TR is already monthly and does not require aggregation.
    """

    required_columns = {"Tarih", "TP_KFE_TR"}

    missing_columns = required_columns.difference(raw_data.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required KFE columns: {sorted(missing_columns)}"
        )

    data = raw_data[["Tarih", "TP_KFE_TR"]].copy()

    periods = data["Tarih"].astype(str).str.strip()

    valid_period_mask = periods.str.fullmatch(r"\d{4}-\d{2}")

    period_values = periods.loc[valid_period_mask]

    for value in period_values:
        _parse_monthly_period(
            value,
            field_name="KFE period",
        )

    data = data.loc[valid_period_mask].copy()
    data["period"] = period_values

    data["housing_price_index"] = pd.to_numeric(
        data["TP_KFE_TR"],
        errors="coerce",
    )

    if data["housing_price_index"].isna().any():
        raise ValueError(
            "KFE observations contain missing or non-numeric values."
        )

    start, end = _monthly_period_bounds(
        start_period,
        end_period,
    )

    parsed_periods = data["period"].map(
        lambda value: _parse_monthly_period(
            value,
            field_name="KFE period",
        )
    )

    data = data[
        (parsed_periods >= start)
        & (parsed_periods <= end)
    ].copy()

    if data.empty:
        raise ValueError("No KFE observations found in the requested period.")

    if data["period"].duplicated().any():
        raise ValueError("Duplicate KFE periods detected.")

    return (
        data[["period", "housing_price_index"]]
        .sort_values("period")
        .reset_index(drop=True)
    )


def merge_monthly_evds_series(
    housing_rate: pd.DataFrame,
    cpi: pd.DataFrame,
    housing_price: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge standardized monthly EVDS series using the period column.

    An outer join is used intentionally so missing periods are not
    silently dropped.
    """

    datasets = {
        "housing_rate": housing_rate,
        "cpi": cpi,
        "housing_price": housing_price,
    }

    for name, data in datasets.items():
        if "period" not in data.columns:
            raise ValueError(f"{name} does not contain a period column.")

        if data["period"].duplicated().any():
            raise ValueError(f"Duplicate periods detected in {name}.")

    merged = (
        housing_rate
        .merge(
            cpi,
            on="period",
            how="outer",
            validate="one_to_one",
        )
        .merge(
            housing_price,
            on="period",
            how="outer",
            validate="one_to_one",
        )
        .sort_values("period")
        .reset_index(drop=True)
    )

    return merged


def validate_monthly_evds_data(
    monthly_data: pd.DataFrame,
    *,
    start_period: str = "2021-01",
    end_period: str = "2026-06",
) -> None:
    """Validate the standardized monthly EVDS Silver contract."""

    required_columns = {
        "period",
        *EVDS_MONTHLY_VALUE_COLUMNS,
    }

    missing_columns = required_columns.difference(
        monthly_data.columns
    )

    if missing_columns:
        raise ValueError(
            "Missing required monthly EVDS columns: "
            f"{sorted(missing_columns)}"
        )

    start, end = _monthly_period_bounds(
        start_period,
        end_period,
    )

    parsed_periods = pd.Series(
        [
            _parse_monthly_period(
                value,
                field_name="period",
            )
            for value in monthly_data["period"]
        ],
        index=monthly_data.index,
    )

    duplicate_periods = (
        parsed_periods[
            parsed_periods.duplicated(keep=False)
        ]
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    if duplicate_periods:
        raise ValueError(
            "Duplicate EVDS periods detected: "
            f"{duplicate_periods}"
        )

    expected_periods = set(
        pd.period_range(
            start=start,
            end=end,
            freq="M",
        )
    )

    actual_periods = set(parsed_periods)

    missing_periods = sorted(
        expected_periods - actual_periods
    )

    if missing_periods:
        raise ValueError(
            "Missing expected EVDS periods: "
            f"{[str(period) for period in missing_periods]}"
        )

    unexpected_periods = sorted(
        actual_periods - expected_periods
    )

    if unexpected_periods:
        raise ValueError(
            "Unexpected EVDS periods detected: "
            f"{[str(period) for period in unexpected_periods]}"
        )

    numeric_values = {}

    for column in EVDS_MONTHLY_VALUE_COLUMNS:
        values = pd.to_numeric(
            monthly_data[column],
            errors="coerce",
        )

        if values.isna().any():
            raise ValueError(
                "Non-numeric or missing EVDS values detected "
                f"in {column}."
            )

        finite_mask = values.map(
            lambda value: (
                float("-inf")
                < float(value)
                < float("inf")
            )
        )

        if not finite_mask.all():
            raise ValueError(
                f"Non-finite EVDS values detected in {column}."
            )

        numeric_values[column] = values

    for column in (
        "cpi_index",
        "housing_price_index",
        "weekly_observation_count",
    ):
        if (numeric_values[column] <= 0).any():
            raise ValueError(
                f"{column} must contain only positive values."
            )

    weekly_counts = numeric_values[
        "weekly_observation_count"
    ]

    if (weekly_counts % 1 != 0).any():
        raise ValueError(
            "weekly_observation_count must contain only integer values."
        )
