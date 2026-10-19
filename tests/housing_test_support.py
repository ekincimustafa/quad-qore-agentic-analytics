"""Synthetic BDDK package producer shared by offline file-question tests."""

import hashlib
import json

from app.lakehouse.bddk_silver import build_bddk_monthly_silver_table


def write_bddk(root, periods):
    bronze = root / "data/bronze/bddk/aylik"
    (bronze / "raw").mkdir(parents=True, exist_ok=True)
    (bronze / "receipts").mkdir(parents=True, exist_ok=True)
    for period in periods:
        year, month = map(int, period.split("-"))
        raw = json.dumps({"Json": {
            "caption": f"Tüketici Kredileri (milyon TL), Dönem:{year}/{month}",
            "colModels": [{"name": name} for name in ("ad", "tp", "yp", "toplam")],
            "data": {"rows": [{"cell": ["Tüketici Kredileri - Konut", 1000, 0, 1000]}]},
        }}, ensure_ascii=False).encode("utf-8")
        (bronze / "raw" / f"{period}.json").write_bytes(raw)
        receipt = {
            "request_key": f"synthetic-bddk-{period}",
            "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": year, "ay": month},
            "path": f"aylik/raw/{period}.json", "downloaded_at": "2026-10-17T10:00:00Z",
            "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "validation": {"period": period, "period_confirmation": "response_caption"},
        }
        (bronze / "receipts" / f"{period}.json").write_text(json.dumps(receipt), encoding="utf-8")
    silver = build_bddk_monthly_silver_table(
        bronze / "receipts", bronze / "raw", periods[0], periods[-1],
    )
    output = root / "data/silver/bddk/housing_loans.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(output, index=False)
