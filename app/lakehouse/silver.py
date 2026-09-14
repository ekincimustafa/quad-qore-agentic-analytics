from __future__ import annotations

import pandas as pd


EVDS_DATE_COLUMN = "Tarih"
EVDS_HOUSING_RATE_COLUMN = "TP_KTF12"

EVDS_MONTHLY_VALUE_COLUMNS = (
    "housing_loan_interest_rate_pct",
    "cpi_index",
    "housing_price_index",
)


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

    date_like_mask = date_text.str.fullmatch(
        r"\d{1,2}-\d{1,2}-\d{4}",
        na=False,
    )

    parsed_dates = pd.to_datetime(
        raw_dates,
        dayfirst=True,
        errors="coerce",
    )

    invalid_date_mask = date_like_mask & parsed_dates.isna()

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

    monthly = monthly[
        (monthly["period"] >= start_period)
        & (monthly["period"] <= end_period)
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

    data = data.loc[valid_period_mask].copy()
    data["period"] = periods.loc[valid_period_mask]

    data["housing_price_index"] = pd.to_numeric(
        data["TP_KFE_TR"],
        errors="coerce",
    )

    if data["housing_price_index"].isna().any():
        raise ValueError(
            "KFE observations contain missing or non-numeric values."
        )

    data = data[
        (data["period"] >= start_period)
        & (data["period"] <= end_period)
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
    """Validate completeness of standardized monthly EVDS data."""

    required_columns = {
        "period",
        *EVDS_MONTHLY_VALUE_COLUMNS,
    }

    missing_columns = required_columns.difference(monthly_data.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required monthly EVDS columns: {sorted(missing_columns)}"
        )

    expected_periods = pd.period_range(
        start=start_period,
        end=end_period,
        freq="M",
    ).astype(str)

    target = monthly_data[
        (monthly_data["period"] >= start_period)
        & (monthly_data["period"] <= end_period)
    ].copy()

    duplicate_periods = (
        target.loc[
            target["period"].duplicated(keep=False),
            "period",
        ]
        .drop_duplicates()
        .tolist()
    )

    if duplicate_periods:
        raise ValueError(
            f"Duplicate EVDS periods detected: {duplicate_periods}"
        )

    actual_periods = set(target["period"])

    missing_periods = [
        period
        for period in expected_periods
        if period not in actual_periods
    ]

    if missing_periods:
        raise ValueError(
            f"Missing expected EVDS periods: {missing_periods}"
        )

    missing_value_counts = (
        target[list(EVDS_MONTHLY_VALUE_COLUMNS)]
        .isna()
        .sum()
    )

    columns_with_missing_values = {
        column: int(count)
        for column, count in missing_value_counts.items()
        if count > 0
    }

    if columns_with_missing_values:
        raise ValueError(
            "Missing EVDS values detected: "
            f"{columns_with_missing_values}"
        )
