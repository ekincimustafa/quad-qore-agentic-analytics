"""Deterministic Plotly chart for the first housing-loan demo."""

from __future__ import annotations

import json
import math
import re
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


REQUIRED_COLUMNS = (
    "period",
    "nominal_housing_loan_mn_try",
    "real_housing_loan_2025_mn_try",
    "housing_loan_interest_rate_pct",
    "cpi_index",
    "housing_price_index",
    "rate_down_real_credit_not_up",
)
NUMERIC_COLUMNS = (
    "nominal_housing_loan_mn_try",
    "real_housing_loan_2025_mn_try",
    "housing_loan_interest_rate_pct",
    "cpi_index",
    "housing_price_index",
)
PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class HousingChartError(ValueError):
    """Raised when a trustworthy chart cannot be built from a Gold table."""


def _validated_chart_frame(gold_table: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(gold_table, pd.DataFrame):
        raise HousingChartError("gold_table must be a pandas DataFrame.")

    missing = sorted(set(REQUIRED_COLUMNS).difference(gold_table.columns))
    if missing:
        raise HousingChartError(
            f"gold_table is missing chart columns: {missing}."
        )

    frame = gold_table.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["period"] = frame["period"].astype("string").str.strip()
    invalid_periods = frame.loc[
        frame["period"].isna()
        | ~frame["period"].str.fullmatch(PERIOD_PATTERN.pattern, na=False),
        "period",
    ].tolist()
    if invalid_periods:
        raise HousingChartError(
            f"gold_table contains invalid chart periods: {invalid_periods[:5]}."
        )

    duplicates = sorted(
        frame.loc[frame["period"].duplicated(keep=False), "period"].unique()
    )
    if duplicates:
        raise HousingChartError(
            f"gold_table contains duplicate chart periods: {duplicates[:5]}."
        )

    for column in NUMERIC_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        invalid = numeric.map(
            lambda value: pd.isna(value) or not math.isfinite(float(value))
        )
        if invalid.any():
            periods = frame.loc[invalid, "period"].tolist()
            raise HousingChartError(
                f"{column} contains invalid chart values for periods: "
                f"{periods[:5]}."
            )
        frame[column] = numeric.astype(float)

    flags: list[bool] = []
    for period, value in zip(
        frame["period"],
        frame["rate_down_real_credit_not_up"],
        
    ):
        if pd.isna(value):
            flags.append(False)
        elif isinstance(value, bool) or (
            type(value).__module__ == "numpy"
            and type(value).__name__ in {"bool", "bool_"}
        ):
            flags.append(bool(value))
        else:
            raise HousingChartError(
                "rate_down_real_credit_not_up must contain booleans; "
                f"invalid period: {period}."
            )
    frame["_matched"] = flags

    return frame.sort_values("period").reset_index(drop=True)


def build_housing_chart(gold_table: pd.DataFrame) -> dict[str, Any]:
    """Return a JSON-safe, three-panel Plotly figure specification."""

    frame = _validated_chart_frame(gold_table)
    x_values = (
        pd.PeriodIndex(frame["period"], freq="M")
        .to_timestamp()
        .strftime("%Y-%m-%d")
        .tolist()
    )

    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Konut kredisi stoku",
            "Konut kredisi faiz oranı",
            "TÜFE ve Konut Fiyat Endeksi",
        ),
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=frame["nominal_housing_loan_mn_try"].tolist(),
            mode="lines+markers",
            name="Nominal konut kredisi",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=frame["real_housing_loan_2025_mn_try"].tolist(),
            mode="lines+markers",
            name="Reel konut kredisi (2025 fiyatları)",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=frame["housing_loan_interest_rate_pct"].tolist(),
            mode="lines+markers",
            name="Konut kredisi faizi",
        ),
        row=2,
        col=1,
    )

    matched = frame[frame["_matched"]]
    matched_x = (
        pd.PeriodIndex(matched["period"], freq="M")
        .to_timestamp()
        .strftime("%Y-%m-%d")
        .tolist()
    )
    figure.add_trace(
        go.Scatter(
            x=matched_x,
            y=matched["housing_loan_interest_rate_pct"].tolist(),
            mode="markers",
            marker={"symbol": "diamond", "size": 10},
            name="Koşula uyan ay",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=frame["cpi_index"].tolist(),
            mode="lines+markers",
            name="TÜFE (2025=100)",
        ),
        row=3,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=frame["housing_price_index"].tolist(),
            mode="lines+markers",
            name="Konut Fiyat Endeksi (2023=100)",
        ),
        row=3,
        col=1,
    )

    figure.update_yaxes(title_text="Milyon TL", row=1, col=1)
    figure.update_yaxes(title_text="Yüzde", row=2, col=1)
    figure.update_yaxes(title_text="Endeks", row=3, col=1)
    figure.update_xaxes(title_text="Dönem", row=3, col=1)
    figure.update_layout(
        title="Konut Kredisi Analizi",
        height=850,
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.08, "x": 0},
        template="plotly_white",
    )

    return json.loads(figure.to_json())
