import json
import pandas as pd
import pytest
from pathlib import Path
import hashlib
from scripts.bddk.verify_silver_samples import verify_samples

@pytest.fixture
def setup_dirs(tmp_path):
    silver_path = tmp_path / "silver.parquet"
    receipts_dir = tmp_path / "receipts"
    raw_dir = tmp_path / "aylik" / "raw"
    receipts_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)

    # Dummy silver data
    df = pd.DataFrame([
        {"period": "2021-01", "nominal_housing_loan_mn_try": 276785.0, "bddk_source_ref": "req1", "housing_loan_unit": "Milyon TL"},
        {"period": "2023-06", "nominal_housing_loan_mn_try": 438466.0, "bddk_source_ref": "req2", "housing_loan_unit": "Milyon TL"},
        {"period": "2025-12", "nominal_housing_loan_mn_try": 678970.0, "bddk_source_ref": "req3", "housing_loan_unit": "Milyon TL"},
    ])
    df.to_parquet(silver_path)

    def write_receipt_and_raw(req_id, period, total_val, raw_name, y, m):
        raw_dict = {
            "Json": {
                "caption": f"Dönem:{y}/{m} (Milyon TL)",
                "colModels": [{"name": "ad"}, {"name": "tp"}, {"name": "yp"}, {"name": "toplam"}],
                "data": {
                    "rows": [
                        {"cell": ["Tüketici Kredileri - Konut", total_val, 0, total_val]}
                    ]
                }
            }
        }
        raw_payload = json.dumps(raw_dict).encode("utf-8")
        raw_file = raw_dir / raw_name
        raw_file.write_bytes(raw_payload)
        h = hashlib.sha256(raw_payload).hexdigest()

        receipt_data = {
            "request_key": req_id,
            "path": f"aylik/raw/{raw_name}",
            "sha256": h,
            "parameters": {"yil": y, "ay": m}
        }
        (receipts_dir / f"{req_id}.json").write_text(json.dumps(receipt_data), encoding="utf-8")

    write_receipt_and_raw("req1", "2021-01", 276785.0, "raw1.json", 2021, 1)
    write_receipt_and_raw("req2", "2023-06", 438466.0, "raw2.json", 2023, 6)
    write_receipt_and_raw("req3", "2025-12", 678970.0, "raw3.json", 2025, 12)

    return silver_path, receipts_dir, raw_dir

def test_verify_success(setup_dirs):
    silver, receipts, raw = setup_dirs
    assert verify_samples(silver, ["2021-01", "2023-06", "2025-12"], receipts, raw) == 0

def test_verify_less_than_3_periods(setup_dirs):
    silver, receipts, raw = setup_dirs
    assert verify_samples(silver, ["2021-01", "2023-06"], receipts, raw) == 1

def test_verify_silver_not_found(setup_dirs):
    silver, receipts, raw = setup_dirs
    silver.unlink()
    assert verify_samples(silver, ["2021-01", "2023-06", "2025-12"], receipts, raw) == 1

def test_verify_mismatch_value(setup_dirs):
    silver, receipts, raw = setup_dirs
    raw_file = raw / "raw2.json"
    raw_dict = {
        "Json": {
            "caption": "Dönem:2023/6 (Milyon TL)",
            "colModels": [{"name": "ad"}, {"name": "tp"}, {"name": "yp"}, {"name": "toplam"}],
            "data": {
                "rows": [
                    {"cell": ["Tüketici Kredileri - Konut", 123.0, 0, 123.0]}
                ]
            }
        }
    }
    raw_payload = json.dumps(raw_dict).encode("utf-8")
    raw_file.write_bytes(raw_payload)
    # Update hash in receipt so it passes hash check but fails value match
    h = hashlib.sha256(raw_payload).hexdigest()
    rec_file = receipts / "req2.json"
    data = json.loads(rec_file.read_text())
    data["sha256"] = h
    rec_file.write_text(json.dumps(data))

    assert verify_samples(silver, ["2021-01", "2023-06", "2025-12"], receipts, raw) == 1

def test_verify_hash_mismatch(setup_dirs):
    silver, receipts, raw = setup_dirs
    raw_file = raw / "raw2.json"
    raw_file.write_bytes(b'{"different": "content"}')
    # Hash doesn't match receipt now
    assert verify_samples(silver, ["2021-01", "2023-06", "2025-12"], receipts, raw) == 1

def test_verify_caption_period_mismatch(setup_dirs):
    silver, receipts, raw = setup_dirs
    raw_file = raw / "raw2.json"
    # Modify caption period to Dönem:1999/1
    raw_dict = {
        "Json": {
            "caption": "Dönem:1999/1 (Milyon TL)",
            "colModels": [{"name": "ad"}, {"name": "tp"}, {"name": "yp"}, {"name": "toplam"}],
            "data": {
                "rows": [
                    {"cell": ["Tüketici Kredileri - Konut", 438466.0, 0, 438466.0]}
                ]
            }
        }
    }
    raw_payload = json.dumps(raw_dict).encode("utf-8")
    raw_file.write_bytes(raw_payload)
    h = hashlib.sha256(raw_payload).hexdigest()
    rec_file = receipts / "req2.json"
    data = json.loads(rec_file.read_text())
    data["sha256"] = h
    rec_file.write_text(json.dumps(data))

    # Must fail because raw header period is 1999-01, not 2023-06
    assert verify_samples(silver, ["2021-01", "2023-06", "2025-12"], receipts, raw) == 1

def test_verify_caption_missing_unit(setup_dirs):
    silver, receipts, raw = setup_dirs
    raw_file = raw / "raw2.json"
    # Missing Milyon TL in caption
    raw_dict = {
        "Json": {
            "caption": "Dönem:2023/6",
            "colModels": [{"name": "ad"}, {"name": "tp"}, {"name": "yp"}, {"name": "toplam"}],
            "data": {
                "rows": [
                    {"cell": ["Tüketici Kredileri - Konut", 438466.0, 0, 438466.0]}
                ]
            }
        }
    }
    raw_payload = json.dumps(raw_dict).encode("utf-8")
    raw_file.write_bytes(raw_payload)
    h = hashlib.sha256(raw_payload).hexdigest()
    rec_file = receipts / "req2.json"
    data = json.loads(rec_file.read_text())
    data["sha256"] = h
    rec_file.write_text(json.dumps(data))

    assert verify_samples(silver, ["2021-01", "2023-06", "2025-12"], receipts, raw) == 1

def test_verify_silver_unit_mismatch(setup_dirs):
    silver, receipts, raw = setup_dirs
    # Modify unit in Silver parquet
    df = pd.read_parquet(silver)
    df.loc[df["period"] == "2023-06", "housing_loan_unit"] = "Bin TL"
    df.to_parquet(silver)

    assert verify_samples(silver, ["2021-01", "2023-06", "2025-12"], receipts, raw) == 1
