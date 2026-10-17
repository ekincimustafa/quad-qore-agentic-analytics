"""Build EVDS manifests for the full dataset or 60-month demo."""

import argparse
import json
from pathlib import Path

from tempfile import TemporaryDirectory
from app.lakehouse.evds_manifest_producer import build_evds_manifest
from app.lakehouse.evds_pipeline import build_evds_silver_from_bronze
from scripts.build_evds_silver import _find_bronze_for_request


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="60 aylık demo manifestini üret.",
    )
    args = parser.parse_args(argv)

    # Proje ve veri klasörleri
    project_root = Path(__file__).resolve().parents[1]
    data_root = project_root / "data"

    # Demo veya tam veri setini seç
    silver_filename = (
        "evds_monthly_2021-01_2025-12.csv"
        if args.demo
        else "evds_monthly_2021-01_2026-06.csv"
    )

    silver_path = (
        data_root
        / "silver"
        / "evds"
        / "monthly"
        / silver_filename
    )

    request_start = "2021-01-01"
    request_end = "2026-06-30"

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

    # Silver üretimindeki kuralla aynı Bronze dosyalarını seç.
    selected_raw_paths = {}

    for series_code in series_metadata:
        selected = _find_bronze_for_request(
            data_root=data_root,
            series_code=series_code,
            request_start=request_start,
            request_end=request_end,
        )

        if selected is None:
            raise ValueError(
                f"Bronze source not found: {series_code}"
            )

        selected_raw_paths[series_code] = selected

    # Demo modunda 60 aylık Silver CSV ve coverage raporu üret.
    if args.demo:
        demo_result = build_evds_silver_from_bronze(
            housing_rate_path=selected_raw_paths["TP.KTF12"],
            cpi_path=selected_raw_paths["TP.TUKFIY2025.GENEL"],
            housing_price_path=selected_raw_paths["TP.KFE.TR"],
            output_path=silver_path,
            start_period="2021-01",
            end_period="2025-12",
        )

        if demo_result.row_count != 60:
            raise ValueError(
                "Demo Silver must contain exactly 60 months."
            )

        print("60 aylık demo Silver ve coverage raporu oluşturuldu.")

    else:
        # Normal modda mevcut Silver'ın seçilen Bronze
        # dosyalarından üretildiğini bağımsız olarak doğrula.
        with TemporaryDirectory() as temp:
            temp_csv = Path(temp) / silver_path.name

            build_evds_silver_from_bronze(
                housing_rate_path=selected_raw_paths["TP.KTF12"],
                cpi_path=selected_raw_paths[
                    "TP.TUKFIY2025.GENEL"
                ],
                housing_price_path=selected_raw_paths["TP.KFE.TR"],
                output_path=temp_csv,
                start_period="2021-01",
                end_period="2026-06",
            )

            if temp_csv.read_bytes() != silver_path.read_bytes():
                raise ValueError(
                    "Existing Silver CSV does not match "
                    "the selected Bronze sources."
                )

            expected_coverage = json.loads(
                temp_csv.with_suffix(
                    ".coverage.json"
                ).read_text(encoding="utf-8")
            )

            actual_coverage = json.loads(
                silver_path.with_suffix(
                    ".coverage.json"
                ).read_text(encoding="utf-8")
            )

            if expected_coverage != actual_coverage:
                raise ValueError(
                    "Existing coverage report does not match "
                    "the selected Bronze sources."
                )

        print("Silver–Bronze kaynak tutarlılığı doğrulandı.")

    # Bronze, Silver ve haftalık kapsam bilgilerini doğrula.
    manifest = build_evds_manifest(
        silver_path=silver_path,
        selected_raw_paths=selected_raw_paths,
        series_metadata=series_metadata,
        request_start=request_start,
        request_end=request_end,
        project_root=project_root,
        data_root=data_root,
    )

    manifest_filename = (
        "manifest_2021-01_2025-12.json"
        if args.demo
        else "manifest.json"
    )

    manifest_path = silver_path.parent / manifest_filename

    # Bütün doğrulamalar başarılı olduktan sonra yaz.
    manifest_bytes = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
    ).encode("utf-8")

    temporary = manifest_path.with_suffix(".json.part")
    temporary.write_bytes(manifest_bytes)
    temporary.replace(manifest_path)

    rate = next(
        series
        for series in manifest["series"]
        if series["series_code"] == "TP.KTF12"
    )

    print("EVDS manifest başarıyla oluşturuldu.")
    print(f"Manifest: {manifest_path}")
    print(f"Silver satır sayısı: {manifest['silver']['row_count']}")
    print(f"Silver SHA256: {manifest['silver']['sha256']}")
    print(f"Seri sayısı: {len(manifest['series'])}")
    print(
        "Haftalık kapsam ayı:",
        len(rate["weekly_coverage"]["months"]),
    )


if __name__ == "__main__":
    main()