"""Generate a deterministic synthetic EVDS manifest fixture."""

import json
from pathlib import Path

from app.connectors.evds import (
    EvdsRawResponse,
    store_raw_response_in_bronze,
)
from app.lakehouse.bronze import BronzeStore
from app.lakehouse.evds_manifest_producer import build_evds_manifest
from app.lakehouse.evds_pipeline import build_evds_silver_from_bronze
from app.lakehouse.layout import LakehouseLayout


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FIXTURE_ROOT = (
    PROJECT_ROOT / "tests" / "fixtures" / "evds_manifest_v1"
)

DATA_ROOT = FIXTURE_ROOT / "data"

REQUEST_START = "2021-01-01"
REQUEST_END = "2021-02-28"


def make_body(items):
    return json.dumps(
        {
            "totalCount": len(items),
            "items": items,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def main():
    store = BronzeStore(LakehouseLayout(DATA_ROOT))

    fixtures = {
        "TP.KTF12": {
            "frequency": "weekly",
            "items": [
                {"Tarih": "01-01-2021", "TP_KTF12": "10"},
                {"Tarih": "15-01-2021", "TP_KTF12": "20"},
                {"Tarih": "05-02-2021", "TP_KTF12": "30"},
                {"Tarih": "19-02-2021", "TP_KTF12": "40"},
            ],
        },
        "TP.TUKFIY2025.GENEL": {
            "frequency": "monthly",
            "items": [
                {"Tarih": "2021-1", "TP_TUKFIY2025_GENEL": "100"},
                {"Tarih": "2021-2", "TP_TUKFIY2025_GENEL": "101"},
            ],
        },
        "TP.KFE.TR": {
            "frequency": "monthly",
            "items": [
                {"Tarih": "2021-1", "TP_KFE_TR": "200"},
                {"Tarih": "2021-2", "TP_KFE_TR": "201"},
            ],
        },
    }

    selected_raw_paths = {}

    # 1. Gerçek Bronze dosyaları ve makbuzları oluştur.
    for series_code, config in fixtures.items():
        raw = EvdsRawResponse(
            series_code=series_code,
            frequency=config["frequency"],
            request_start=REQUEST_START,
            request_end=REQUEST_END,
            source_url="https://example.invalid/evds/fixture",
            downloaded_at="2026-09-19T10:00:00+00:00",
            content_type="application/json",
            body=make_body(config["items"]),
        )

        stored = store_raw_response_in_bronze(raw, store)

        selected_raw_paths[series_code] = stored.asset.path

    # 2. Bronze verilerinden gerçek Silver pipeline'ı çalıştır.
    silver_path = (
        DATA_ROOT
        / "silver"
        / "evds"
        / "monthly"
        / "evds_monthly_2021-01_2021-02.csv"
    )

    silver_result = build_evds_silver_from_bronze(
        housing_rate_path=selected_raw_paths["TP.KTF12"],
        cpi_path=selected_raw_paths["TP.TUKFIY2025.GENEL"],
        housing_price_path=selected_raw_paths["TP.KFE.TR"],
        output_path=silver_path,
        start_period="2021-01",
        end_period="2021-02",
    )

    # 3. Doğrulanmış seri metadata bilgileri.
    series_metadata = {
        "TP.KTF12": {
            "silver_columns": [
                "housing_loan_interest_rate_pct",
                "weekly_observation_count",
            ],
            "unit": "percent",
            "native_frequency": "weekly",
            "target_frequency": "monthly",
            "base_year": None,
            "base_year_source": "not_applicable",
            "transformation": "mean",
        },
        "TP.TUKFIY2025.GENEL": {
            "silver_columns": ["cpi_index"],
            "unit": "index",
            "native_frequency": "monthly",
            "target_frequency": "monthly",
            "base_year": 2025,
            "base_year_source": "tcmb",
            "transformation": "level",
        },
        "TP.KFE.TR": {
            "silver_columns": ["housing_price_index"],
            "unit": "index",
            "native_frequency": "monthly",
            "target_frequency": "monthly",
            "base_year": 2023,
            "base_year_source": "tcmb",
            "transformation": "level",
        },
    }

    # 4. Manifest sözlüğünü oluştur.
    manifest = build_evds_manifest(
        silver_path=silver_path,
        selected_raw_paths=selected_raw_paths,
        series_metadata=series_metadata,
        request_start=REQUEST_START,
        request_end=REQUEST_END,
        project_root=FIXTURE_ROOT,
        data_root=DATA_ROOT,
    )

    # 5. JSON manifestini kaydet.
    manifest_path = silver_path.parent / "manifest.json"

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print("EVDS fixture oluşturuldu.")
    print(f"Manifest: {manifest_path}")
    print(f"Silver: {silver_path}")
    print(f"Satır sayısı: {silver_result.row_count}")
    print(f"Silver SHA256: {silver_result.sha256}")
    print(f"Seri sayısı: {len(manifest['series'])}")


if __name__ == "__main__":
    main()