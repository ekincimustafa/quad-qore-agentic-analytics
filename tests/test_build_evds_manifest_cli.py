"""Offline integration test for the EVDS demo manifest CLI."""

import csv
import hashlib
import json

from app.connectors.evds import (
    EvdsRawResponse,
    store_raw_response_in_bronze,
)
from app.lakehouse.bronze import BronzeStore
from app.lakehouse.evds_manifest_producer import (
    build_bronze_manifest_entry,
    build_silver_manifest_entry,
    build_weekly_coverage_manifest_entry,
)
from app.lakehouse.layout import LakehouseLayout
from scripts import build_evds_manifest as manifest_cli


def test_demo_cli_generates_60_months_offline(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    scripts_dir = project_root / "scripts"
    scripts_dir.mkdir(parents=True)

    # CLI'nin gerçek data/ klasörümüz yerine
    # geçici test klasörünü kullanmasını sağla.
    monkeypatch.setattr(
        manifest_cli,
        "__file__",
        str(scripts_dir / "build_evds_manifest.py"),
    )

    months = [
        (year, month)
        for year in range(2021, 2026)
        for month in range(1, 13)
    ]

    rate_items = []
    cpi_items = []
    kfe_items = []

    for index, (year, month) in enumerate(months):
        for day, value in [(1, "10"), (15, "20")]:
            rate_items.append({
                "Tarih": f"{day:02d}-{month:02d}-{year}",
                "TP_KTF12": value,
            })

        cpi_items.append({
            "Tarih": f"{year}-{month}",
            "TP_TUKFIY2025_GENEL": str(100 + index),
        })

        kfe_items.append({
            "Tarih": f"{year}-{month}",
            "TP_KFE_TR": str(200 + index),
        })

    store = BronzeStore(LakehouseLayout(data_root))

    for code, frequency, items in [
        ("TP.KTF12", "weekly", rate_items),
        ("TP.TUKFIY2025.GENEL", "monthly", cpi_items),
        ("TP.KFE.TR", "monthly", kfe_items),
    ]:
        body = json.dumps(
            {"totalCount": len(items), "items": items},
            sort_keys=True,
        ).encode("utf-8")

        response = EvdsRawResponse(
            series_code=code,
            frequency=frequency,
            request_start="2021-01-01",
            request_end="2026-06-30",
            source_url="https://example.invalid/evds/test",
            downloaded_at="2026-09-19T10:00:00+00:00",
            content_type="application/json",
            body=body,
        )

        store_raw_response_in_bronze(response, store)

    silver_dir = data_root / "silver" / "evds" / "monthly"
    silver_dir.mkdir(parents=True, exist_ok=True)

    # Demo üretimi 66 aylık ana dosyalara dokunmamalı.
    full_csv = silver_dir / "evds_monthly_2021-01_2026-06.csv"
    full_manifest = silver_dir / "manifest.json"

    full_csv.write_bytes(b"original-full-csv")
    full_manifest.write_bytes(b"original-full-manifest")

    # Demo CSV, kapsam raporu ve manifesti üret.
    manifest_cli.main(["--demo"])

    demo_csv = silver_dir / "evds_monthly_2021-01_2025-12.csv"
    demo_report = demo_csv.with_suffix(".coverage.json")
    demo_manifest = silver_dir / "manifest_2021-01_2025-12.json"

    assert demo_csv.is_file()
    assert demo_report.is_file()
    assert demo_manifest.is_file()

    with demo_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 60
    assert rows[0]["period"] == "2021-01"
    assert rows[-1]["period"] == "2025-12"

    manifest = json.loads(
        demo_manifest.read_text(encoding="utf-8")
    )

    assert manifest["silver"] == build_silver_manifest_entry(
        silver_path=demo_csv,
        project_root=project_root,
        data_root=data_root,
    )

    assert manifest["silver"]["row_count"] == 60
    assert len(manifest["series"]) == 3

    for series in manifest["series"]:
        for bronze in series["bronze"]:
            verified = build_bronze_manifest_entry(
                selected_raw_path=project_root / bronze["raw_path"],
                series_code=series["series_code"],
                request_start=bronze["request_start"],
                request_end=bronze["request_end"],
                project_root=project_root,
                data_root=data_root,
            )
            assert bronze == verified

    rate = next(
        series for series in manifest["series"]
        if series["series_code"] == "TP.KTF12"
    )

    assert rate["weekly_coverage"] == (
        build_weekly_coverage_manifest_entry(
            coverage_path=demo_report,
            silver_path=demo_csv,
        )
    )
    assert len(rate["weekly_coverage"]["months"]) == 60

    # Üretim tekrarlandığında sonuçlar aynı olmalı.
    original_sha = hashlib.sha256(demo_csv.read_bytes()).hexdigest()
    manifest_cli.main(["--demo"])

    assert hashlib.sha256(demo_csv.read_bytes()).hexdigest() == original_sha

    assert full_csv.read_bytes() == b"original-full-csv"
    assert full_manifest.read_bytes() == b"original-full-manifest"