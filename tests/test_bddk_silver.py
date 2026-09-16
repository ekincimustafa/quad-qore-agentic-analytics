import datetime
import hashlib
import json
import tempfile
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

from app.lakehouse.bddk_silver import (
    SilverDataError,
    build_bddk_monthly_silver_table,
    validate_bddk_monthly_silver,
)
from app.lakehouse.core_validators import parse_period_to_date, resolve_secure_raw_path


def _make_mock_raw_json(toplam=1000.0, caption="Tüketici Kredileri (milyon TL)", include_target_row=True, tp=1000.0, yp=0.0):
    rows = []
    if include_target_row:
        rows.append({"cell": ["Tüketici Kredileri - Konut", tp, yp, toplam]})
    return json.dumps({
        "Json": {
            "caption": caption,
            "colModels": [
                {"name": "ad"},
                {"name": "tp"},
                {"name": "yp"},
                {"name": "toplam"}
            ],
            "data": {"rows": rows}
        }
    }).encode("utf-8")


@pytest.fixture
def bronze_env():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        bddk_base = base / "data" / "bronze" / "bddk"
        receipts_dir = bddk_base / "aylik" / "receipts"
        raw_dir = bddk_base / "aylik" / "raw"
        
        receipts_dir.mkdir(parents=True)
        raw_dir.mkdir(parents=True)
        
        yield base, receipts_dir, raw_dir


def create_receipt_and_raw(receipts_dir, raw_dir, year, month, raw_content, 
                          request_key=None, tabloNo="4", taraf="10001", paraBirimi="TL", 
                          downloaded_at="2026-09-11T12:00:00", corrupt_receipt=False, 
                          modify_size=None, modify_sha=None):
    if request_key is None:
        request_key = f"mock_req_{year}_{month}"
        
    raw_hash = hashlib.sha256(raw_content).hexdigest()
    raw_size = len(raw_content)
    raw_filename = f"raw_{year}_{month}_{raw_hash}.json"
    
    (raw_dir / raw_filename).write_bytes(raw_content)
    
    receipt = {
        "request_key": request_key,
        "parameters": {
            "tabloNo": tabloNo,
            "taraf": [taraf] if isinstance(taraf, str) else taraf,
            "paraBirimi": paraBirimi,
            "yil": year,
            "ay": month
        },
        "path": f"aylik/raw/{raw_filename}",
        "downloaded_at": downloaded_at,
        "size_bytes": raw_size if modify_size is None else modify_size,
        "sha256": raw_hash if modify_sha is None else modify_sha
    }
    
    rec_content = json.dumps(receipt)
    if corrupt_receipt:
        rec_content = rec_content[:-1] # break JSON
        
    (receipts_dir / f"rec_{year}_{month}.json").write_text(rec_content, encoding="utf-8")
    return receipt


from app.lakehouse.core_validators import IntegrityError


def test_parse_period():
    assert parse_period_to_date("2021-01") == datetime.date(2021, 1, 1)
    with pytest.raises(IntegrityError):
        parse_period_to_date("2021-13")
    with pytest.raises(IntegrityError):
        parse_period_to_date("invalid")


def test_resolve_secure_raw_path():
    base = Path("/secure/base")
    # Must fail on traversal
    with pytest.raises(IntegrityError):
        resolve_secure_raw_path(base, "../etc/passwd")
    with pytest.raises(IntegrityError):
        resolve_secure_raw_path(base, "/absolute/path")
    with pytest.raises(IntegrityError):
        resolve_secure_raw_path(base, "C:\\Windows")


def test_validate_silver_happy_path():
    df = pd.DataFrame({
        "period": ["2021-01", "2021-02"],
        "housing_loan_amount": [100.0, 105.0],
        "housing_loan_unit": ["Milyon TL", "Milyon TL"],
        "bddk_source_ref": ["req1", "req2"],
        "data_quality_note": ["ok", "ok"]
    })
    validated = validate_bddk_monthly_silver(df, "2021-01", "2021-02")
    assert len(validated) == 2


def test_validate_silver_missing_gap():
    df = pd.DataFrame({
        "period": ["2021-01", "2021-03"], # Missing 2021-02
        "housing_loan_amount": [100.0, 105.0],
        "housing_loan_unit": ["Milyon TL", "Milyon TL"],
        "bddk_source_ref": ["req1", "req2"],
        "data_quality_note": ["ok", "ok"]
    })
    with pytest.raises(SilverDataError, match="Missing continuous periods"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-03")


def test_validate_silver_unexpected_period():
    df = pd.DataFrame({
        "period": ["2021-01", "2021-02", "2021-03"],
        "housing_loan_amount": [100.0, 105.0, 110.0],
        "housing_loan_unit": ["Milyon TL", "Milyon TL", "Milyon TL"],
        "bddk_source_ref": ["req1", "req2", "req3"],
        "data_quality_note": ["ok", "ok", "ok"]
    })
    with pytest.raises(SilverDataError, match="outside expected range"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-02")


def test_validate_silver_negative_amount():
    df = pd.DataFrame({
        "period": ["2021-01"],
        "housing_loan_amount": [-100.0],
        "housing_loan_unit": ["Milyon TL"],
        "bddk_source_ref": ["req1"],
        "data_quality_note": ["ok"]
    })
    with pytest.raises(SilverDataError, match="strictly positive"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-01")


def test_validate_silver_inconsistent_units():
    df = pd.DataFrame({
        "period": ["2021-01", "2021-02"],
        "housing_loan_amount": [100.0, 105.0],
        "housing_loan_unit": ["Milyon TL", "Bin TL"],
        "bddk_source_ref": ["req1", "req2"],
        "data_quality_note": ["ok", "ok"]
    })
    with pytest.raises(SilverDataError, match="inconsistent"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-02")


def test_build_silver_deduplication(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    content = _make_mock_raw_json()
    # Create old receipt
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, content, downloaded_at="2026-09-10T12:00:00", request_key="req1")
    # Create newer receipt for same period
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, content, downloaded_at="2026-09-11T12:00:00", request_key="req1_new")
    
    df = build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")
    assert len(df) == 1
    assert df["bddk_source_ref"].iloc[0] == "req1_new"


def test_build_silver_missing_raw_file(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json())
    # Delete the raw file
    for f in raw_dir.glob("*.json"):
        f.unlink()
        
    with pytest.raises(SilverDataError, match="Physical file missing"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_build_silver_sha_mismatch(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(), modify_sha="a"*64)
    with pytest.raises(SilverDataError, match="SHA-256 mismatch"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_build_silver_size_mismatch(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(), modify_size=9999)
    with pytest.raises(SilverDataError, match="File size mismatch"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_build_silver_missing_target_row(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    content = _make_mock_raw_json(include_target_row=False)
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, content)
    with pytest.raises(SilverDataError, match="Failed to extract housing loan data"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_gold_compatibility(bronze_env):
    from app.lakehouse.gold import build_housing_gold_table
    _, receipts_dir, raw_dir = bronze_env
    
    # 3 periods
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(toplam=100.0))
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 2, _make_mock_raw_json(toplam=110.0))
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 3, _make_mock_raw_json(toplam=120.0))
    
    silver_df = build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-03")
    
    # Mock EVDS
    evds_df = pd.DataFrame({
        "period": ["2021-01", "2021-02", "2021-03"],
        "housing_loan_interest_rate_pct": [18.0, 19.0, 20.0],
        "weekly_observation_count": [4, 4, 4],
        "cpi_index": [100.0, 102.0, 105.0],
        "housing_price_index": [100.0, 101.0, 103.0],
    })
    
    gold_df = build_housing_gold_table(silver_df, evds_df, start_period="2021-01", end_period="2021-03")
    assert len(gold_df) == 3
    assert "real_housing_loan_2025_mn_try" in gold_df.columns


def test_cli_success(bronze_env):
    import sys
    
    base, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json())
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 2, _make_mock_raw_json())
    
    out_path = base / "out.parquet"
        
def test_cli_main_success(bronze_env, monkeypatch, capsys):
    from scripts.build_bddk_silver import main
    base, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json())
    out_path = base / "out.parquet"
    
    monkeypatch.setattr("sys.argv", ["scripts.build_bddk_silver", "--start-period", "2021-01", "--end-period", "2021-01", "--output", str(out_path)])
    
    # We must patch the hardcoded paths in main
    import scripts.build_bddk_silver
    # Note: main uses Path("data/bronze/bddk/aylik/receipts") directly.
    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table

    base_receipts, base_raw = receipts_dir, raw_dir
    def mock_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)
        
    monkeypatch.setattr(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", mock_build)
    
    # We must patch to_parquet because pyarrow isn't installed in the CI env.
    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda self, path, index=False: Path(path).write_bytes(b"dummy"))
    
    exit_code = main()
    assert exit_code == 0
    assert out_path.exists()
    
    captured = capsys.readouterr()
    assert "[SUCCESS] Built Silver dataset" in captured.out
    
def test_cli_main_failure(bronze_env, monkeypatch, capsys):
    from scripts.build_bddk_silver import main
    base, receipts_dir, raw_dir = bronze_env
    # Missing gap
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json())
    out_path = base / "out.parquet"
    
    monkeypatch.setattr("sys.argv", ["scripts.build_bddk_silver", "--start-period", "2021-01", "--end-period", "2021-02", "--output", str(out_path)])
    
    import scripts.build_bddk_silver
    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir
    def mock_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        # Ignore the ones passed by main(), use the fixture ones!
        return original_build(base_receipts, base_raw, start_period, end_period)
        
    monkeypatch.setattr(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", mock_build)
    
    exit_code = main()
    assert exit_code == 1
    
    captured = capsys.readouterr()
    assert "[FAIL-CLOSED ERROR]" in captured.err
