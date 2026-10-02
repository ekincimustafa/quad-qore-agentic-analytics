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


def _make_mock_raw_json(toplam=1000.0, caption=None, include_target_row=True, tp=1000.0, yp=0.0, year=2021, month=1):
    if caption is None:
        caption = f"Tüketici Kredileri (milyon TL), Dönem:{year}/{month}"
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
                           downloaded_at="2026-09-11T12:00:00Z", corrupt_receipt=False,
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
        "sha256": raw_hash if modify_sha is None else modify_sha,
        # validation bloğu: period çapraz kontrolü için zorunlu (Hata 2)
        "validation": {
            "period": f"{year:04d}-{month:02d}",
            "period_confirmation": "response_caption",
            "caption": "Tüketici Kredileri (milyon TL)",
        },
    }

    rec_content = json.dumps(receipt)
    if corrupt_receipt:
        rec_content = rec_content[:-1]  # break JSON

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


# ── Hata 1: Receipt schema fail-closed + downloaded_at + bool tuzağı ─────────

def test_size_bytes_bool_true_is_rejected(bronze_env):
    """size_bytes=True must be rejected. bool is a subclass of int;
    isinstance(True, int) == True, so a strict type() check is required."""
    _, receipts_dir, raw_dir = bronze_env
    # True == 1 in Python; a file of 1 byte would pass naive isinstance check
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                           modify_size=True)
    with pytest.raises(SilverDataError, match="Invalid expected size"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_size_bytes_bool_false_is_rejected(bronze_env):
    """size_bytes=False (== 0) must also be rejected."""
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                           modify_size=False)
    with pytest.raises(SilverDataError, match="Invalid expected size"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_catalog_receipt_without_parameters_skipped_silently(bronze_env):
    """A receipt with NO 'parameters' key is a catalog — must be skipped silently,
    not fail-closed. Only one valid monthly receipt is present, so Silver succeeds."""
    _, receipts_dir, raw_dir = bronze_env
    # Catalog receipt: has request_key but no parameters key at all
    catalog = {
        "request_key": "catalog_req",
        "downloaded_at": "2026-09-11T12:00:00Z",
        "path": "aylik/raw/does_not_matter.json",
        "size_bytes": 100,
        "sha256": "a" * 64,
    }
    (receipts_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    # Also write one valid monthly receipt so Silver can produce 1 row
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1))

    df = build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")
    assert len(df) == 1


def test_broken_parameters_type_fails_closed(bronze_env):
    """A receipt that HAS a 'parameters' key but the value is not a dict is a
    schema corruption — must raise SilverDataError, not silently skip."""
    _, receipts_dir, raw_dir = bronze_env
    broken = {
        "request_key": "broken_req",
        "downloaded_at": "2026-09-11T12:00:00Z",
        "parameters": "this-should-be-a-dict",   # string instead of dict
        "path": "aylik/raw/x.json",
        "size_bytes": 100,
        "sha256": "a" * 64,
    }
    (receipts_dir / "broken.json").write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(SilverDataError, match="malformed 'parameters'"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_broken_parameters_as_list_fails_closed(bronze_env):
    """parameters=[...] (list) should also be rejected as malformed."""
    _, receipts_dir, raw_dir = bronze_env
    broken = {
        "request_key": "broken_list_req",
        "downloaded_at": "2026-09-11T12:00:00Z",
        "parameters": [{"tabloNo": "4"}],         # list instead of dict
        "path": "aylik/raw/x.json",
        "size_bytes": 100,
        "sha256": "a" * 64,
    }
    (receipts_dir / "broken_list.json").write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(SilverDataError, match="malformed 'parameters'"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_missing_downloaded_at_fails_closed(bronze_env):
    """A receipt with no downloaded_at field must be rejected (cannot dedup safely)."""
    _, receipts_dir, raw_dir = bronze_env
    content = _make_mock_raw_json()
    # Write raw file manually so we can craft a receipt without downloaded_at
    raw_hash = hashlib.sha256(content).hexdigest()
    raw_filename = f"raw_no_ts_{raw_hash}.json"
    (raw_dir / raw_filename).write_bytes(content)
    receipt = {
        "request_key": "no_ts_req",
        "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": 2021, "ay": 1},
        "path": f"aylik/raw/{raw_filename}",
        # downloaded_at intentionally omitted
        "size_bytes": len(content),
        "sha256": raw_hash,
    }
    (receipts_dir / "no_ts.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(SilverDataError, match="downloaded_at"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_invalid_downloaded_at_fails_closed(bronze_env):
    """'zzz' or other garbage in downloaded_at must be rejected,
    not silently win deduplication due to lexicographic string comparison."""
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                           downloaded_at="zzz-not-a-timestamp")
    with pytest.raises(SilverDataError, match="downloaded_at"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_naive_downloaded_at_fails_closed(bronze_env):
    """Timestamps without timezone information must be rejected."""
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                           downloaded_at="2026-09-11T12:00:00")
    with pytest.raises(SilverDataError, match="must include timezone information"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_date_only_downloaded_at_fails_closed(bronze_env):
    """Dates without time/timezone must be rejected."""
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                           downloaded_at="2026-09-11")
    with pytest.raises(SilverDataError, match="must include timezone information"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_deduplication_uses_datetime_not_string(bronze_env):
    """Deduplication must be based on parsed datetime, not raw string.
    With string comparison 'Z' suffix could behave unexpectedly; datetime is unambiguous."""
    _, receipts_dir, raw_dir = bronze_env
    content = _make_mock_raw_json()
    # older receipt: explicit UTC suffix
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, content,
                           downloaded_at="2026-09-10T10:00:00Z", request_key="older")
    # newer receipt: local time without Z — string comparison could flip this
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, content,
                           downloaded_at="2026-09-11T09:00:00+00:00", request_key="newer")

    df = build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")
    assert len(df) == 1
    assert df["bddk_source_ref"].iloc[0] == "newer"


def test_validate_silver_happy_path():
    df = pd.DataFrame({
        "period": ["2021-01", "2021-02"],
        "housing_loan_amount": [100.0, 105.0],
        "nominal_housing_loan_mn_try": [100.0, 105.0],
        "housing_loan_unit": ["Milyon TL", "Milyon TL"],
        "bddk_source_ref": ["req1", "req2"],
        "data_quality_note": ["ok", "ok"]
    })
    validated = validate_bddk_monthly_silver(df, "2021-01", "2021-02")
    assert len(validated) == 2


# ── Hata 2: Receipt dönemi ile ham JSON dönemi çapraz kontrolü ────────────────

def _make_receipt_dict(receipts_dir, raw_dir, year, month, raw_content,
                       validation_period=None, period_confirmation="response_caption",
                       raw_path_override=None, request_key=None, downloaded_at="2026-09-11T12:00:00Z"):
    """Helper: tam kontrol edilebilir bir receipt yazar."""
    if request_key is None:
        request_key = f"req_{year}_{month}"
    raw_hash = hashlib.sha256(raw_content).hexdigest()
    raw_size = len(raw_content)
    raw_filename = f"raw_{year}_{month}_{raw_hash}.json"
    (raw_dir / raw_filename).write_bytes(raw_content)

    if validation_period is None:
        validation_period = f"{year:04d}-{month:02d}"

    rel_path = raw_path_override or f"aylik/raw/{raw_filename}"
    receipt = {
        "request_key": request_key,
        "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL",
                       "yil": year, "ay": month},
        "downloaded_at": downloaded_at,
        "path": rel_path,
        "size_bytes": raw_size,
        "sha256": raw_hash,
        "validation": {
            "period": validation_period,
            "period_confirmation": period_confirmation,
            "caption": "Tüketici Kredileri (milyon TL)",
        },
    }
    (receipts_dir / f"rec_{year}_{month}.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )


def test_period_mismatch_fails_closed(bronze_env):
    """Receipt parameters diyor Ocak, ama validation.period diyor Şubat.
    Bu, raw dosyanın farklı bir aya ait olduğuna işaret eder — fail-closed."""
    _, receipts_dir, raw_dir = bronze_env
    _make_receipt_dict(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                       validation_period="2021-02")  # ← kasıtlı uyuşmazlık
    with pytest.raises(SilverDataError, match="Period mismatch"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_missing_validation_block_fails_closed(bronze_env):
    """validation alanı hiç yoksa receipt güvenilmez — fail-closed."""
    _, receipts_dir, raw_dir = bronze_env
    content = _make_mock_raw_json()
    raw_hash = hashlib.sha256(content).hexdigest()
    raw_filename = f"raw_no_val_{raw_hash}.json"
    (raw_dir / raw_filename).write_bytes(content)
    receipt_no_val = {
        "request_key": "no_val_req",
        "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL",
                       "yil": 2021, "ay": 1},
        "downloaded_at": "2026-09-11T12:00:00Z",
        "path": f"aylik/raw/{raw_filename}",
        "size_bytes": len(content),
        "sha256": raw_hash,
        # validation alanı kasıtlı olarak yok
    }
    (receipts_dir / "rec_no_val.json").write_text(
        json.dumps(receipt_no_val), encoding="utf-8"
    )
    with pytest.raises(SilverDataError, match="missing 'validation'"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_period_confirmation_not_response_caption_fails_closed(bronze_env):
    """validation.period_confirmation 'response_caption' değilse (örn. 'manual' veya None)
    period güvenilmez — fail-closed."""
    _, receipts_dir, raw_dir = bronze_env
    _make_receipt_dict(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                       period_confirmation="manual")
    with pytest.raises(SilverDataError, match="period_confirmation"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_raw_path_outside_aylik_raw_fails_closed(bronze_env):
    """path alanı 'aylik/raw/' dışında bir konuma işaret ediyorsa fail-closed.
    BDDK kökü içinde kalmak yeterli değil; tam olarak doğru alt klasörde olmalı."""
    _, receipts_dir, raw_dir = bronze_env
    _make_receipt_dict(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1),
                       raw_path_override="aylik/haftalik/some_file.json")
    with pytest.raises(SilverDataError, match="outside expected 'aylik/raw/'"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_valid_receipt_with_all_checks_passes(bronze_env):
    """Tüm Hata 2 kontrolleri geçen, tam geçerli bir receipt başarılı Silver üretmeli."""
    _, receipts_dir, raw_dir = bronze_env
    _make_receipt_dict(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1))
    df = build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")
    assert len(df) == 1
    assert df["period"].iloc[0] == "2021-01"


def test_wrong_month_in_raw_caption_rejected(bronze_env):
    """Ham dosyanın içeriğindeki caption başka bir döneme aitse (örn. Dönem:2021/2),
    receipt 2021-01 istiyor olsa bile fail-closed reddedilmeli."""
    _, receipts_dir, raw_dir = bronze_env
    # Raw JSON contains caption for month 2, while receipt is for month 1
    raw_with_wrong_caption = _make_mock_raw_json(caption="Tüketici Kredileri (milyon TL), Dönem:2021/2")
    _make_receipt_dict(receipts_dir, raw_dir, 2021, 1, raw_with_wrong_caption)
    with pytest.raises(SilverDataError, match="Raw payload caption period mismatch"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_validate_silver_missing_gap():
    df = pd.DataFrame({
        "period": ["2021-01", "2021-03"], # Missing 2021-02
        "housing_loan_amount": [100.0, 105.0],
        "nominal_housing_loan_mn_try": [100.0, 105.0],
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
        "nominal_housing_loan_mn_try": [100.0, 105.0, 110.0],
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
        "nominal_housing_loan_mn_try": [-100.0],
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
        "nominal_housing_loan_mn_try": [100.0, 105.0],
        "housing_loan_unit": ["Milyon TL", "Bin TL"],
        "bddk_source_ref": ["req1", "req2"],
        "data_quality_note": ["ok", "ok"]
    })
    with pytest.raises(SilverDataError, match="contract violation"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-02")


# ── Hata 3: Silver validator sözleşme kontrolleri ─────────────────────────────

def test_validate_silver_all_wrong_units_rejected():
    """Tüm satırlar 'Bin TL' olsa bile (yani tutarlı olsa bile)
    sözleşme gereği 'Milyon TL' olmak zorunda — fail-closed."""
    df = pd.DataFrame({
        "period": ["2021-01", "2021-02"],
        "housing_loan_amount": [100.0, 105.0],
        "nominal_housing_loan_mn_try": [100.0, 105.0],
        "housing_loan_unit": ["Bin TL", "Bin TL"],  # Tutarlı ama yanlış birim
        "bddk_source_ref": ["req1", "req2"],
        "data_quality_note": ["ok", "ok"]
    })
    with pytest.raises(SilverDataError, match="contract violation.*expected 'Milyon TL'"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-02")


def test_validate_silver_null_unit_rejected():
    """housing_loan_unit içinde None/NaN reddedilmeli."""
    df = pd.DataFrame({
        "period": ["2021-01"],
        "housing_loan_amount": [100.0],
        "nominal_housing_loan_mn_try": [100.0],
        "housing_loan_unit": [None],
        "bddk_source_ref": ["req1"],
        "data_quality_note": ["ok"]
    })
    with pytest.raises(SilverDataError, match="housing_loan_unit contains null"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-01")


def test_validate_silver_null_source_ref_rejected():
    """bddk_source_ref=None astype(str) ile 'None' olarak geçmemeli, fail-closed reddedilmeli."""
    df = pd.DataFrame({
        "period": ["2021-01"],
        "housing_loan_amount": [100.0],
        "nominal_housing_loan_mn_try": [100.0],
        "housing_loan_unit": ["Milyon TL"],
        "bddk_source_ref": [None],
        "data_quality_note": ["ok"]
    })
    with pytest.raises(SilverDataError, match="bddk_source_ref contains null"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-01")


def test_validate_silver_string_none_source_ref_rejected():
    """bddk_source_ref string 'None' veya 'nan' ise reddedilmeli."""
    df = pd.DataFrame({
        "period": ["2021-01"],
        "housing_loan_amount": [100.0],
        "nominal_housing_loan_mn_try": [100.0],
        "housing_loan_unit": ["Milyon TL"],
        "bddk_source_ref": ["None"],
        "data_quality_note": ["ok"]
    })
    with pytest.raises(SilverDataError, match="bddk_source_ref contains empty or invalid"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-01")


def test_validate_silver_null_data_quality_note_rejected():
    """data_quality_note boş veya None ise fail-closed reddedilmeli."""
    df = pd.DataFrame({
        "period": ["2021-01"],
        "housing_loan_amount": [100.0],
        "nominal_housing_loan_mn_try": [100.0],
        "housing_loan_unit": ["Milyon TL"],
        "bddk_source_ref": ["req1"],
        "data_quality_note": [None]
    })
    with pytest.raises(SilverDataError, match="data_quality_note contains null"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-01")


def test_validate_silver_missing_gold_alias_column_rejected():
    """nominal_housing_loan_mn_try Gold uyumluluk kolonu eksikse validator reddetmeli."""
    df = pd.DataFrame({
        "period": ["2021-01"],
        "housing_loan_amount": [100.0],
        # nominal_housing_loan_mn_try kasıtlı olarak yok
        "housing_loan_unit": ["Milyon TL"],
        "bddk_source_ref": ["req1"],
        "data_quality_note": ["ok"]
    })
    with pytest.raises(SilverDataError, match="missing required columns.*nominal_housing_loan_mn_try"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-01")


def test_validate_silver_mismatched_gold_alias_rejected():
    """nominal_housing_loan_mn_try ile housing_loan_amount eşit değilse reddedilmeli."""
    df = pd.DataFrame({
        "period": ["2021-01"],
        "housing_loan_amount": [100.0],
        "nominal_housing_loan_mn_try": [105.0],  # uyuşmazlık
        "housing_loan_unit": ["Milyon TL"],
        "bddk_source_ref": ["req1"],
        "data_quality_note": ["ok"]
    })
    with pytest.raises(SilverDataError, match="strictly equal"):
        validate_bddk_monthly_silver(df, "2021-01", "2021-01")


def test_build_silver_deduplication(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    content = _make_mock_raw_json()
    # Create old receipt
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, content, downloaded_at="2026-09-10T12:00:00Z", request_key="req1")
    # newer downloaded_at for the same period
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, content, downloaded_at="2026-09-11T12:00:00Z", request_key="req1_new")

    df = build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")
    assert len(df) == 1
    assert df["bddk_source_ref"].iloc[0] == "req1_new"


def test_build_silver_missing_raw_file(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1))
    # Delete the raw file
    for f in raw_dir.glob("*.json"):
        f.unlink()

    with pytest.raises(SilverDataError, match="Physical file missing"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_build_silver_sha_mismatch(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1), modify_sha="a"*64)
    with pytest.raises(SilverDataError, match="SHA-256 mismatch"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_build_silver_size_mismatch(bronze_env):
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1), modify_size=9999)
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
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(toplam=100.0, year=2021, month=1))
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 2, _make_mock_raw_json(toplam=110.0, year=2021, month=2))
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 3, _make_mock_raw_json(toplam=120.0, year=2021, month=3))

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


# ── Hata 4: Atomik Parquet yazımı + Hata 5: Gerçek round-trip + assert'li CLI ─

def test_cli_success(bronze_env):
    """test_cli_success artık assert'siz boş gövde değil —
    dosya varlığını, satır sayısını ve şemayı doğrular."""
    import scripts.build_bddk_silver
    from scripts.build_bddk_silver import main

    base, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1))
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 2, _make_mock_raw_json(year=2021, month=2))
    out_path = base / "out.parquet"

    # Route build function to fixture dirs
    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir


    def redirected_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    with mock.patch.object(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", redirected_build):
        with mock.patch("sys.argv", ["build_bddk_silver", "--start-period", "2021-01",
                                     "--end-period", "2021-02", "--output", str(out_path)]):
            exit_code = main()

    assert exit_code == 0, "CLI should exit 0 on success"
    assert out_path.exists(), "Output Parquet file must exist"
    # No temp .part file should remain after a successful write
    assert not out_path.with_suffix(".part").exists(), ".part temp file must not remain after success"
    # Actual row and column check
    result_df = pd.read_parquet(out_path)
    assert len(result_df) == 2, f"Expected 2 rows (2021-01 and 2021-02), got {len(result_df)}"
    assert "period" in result_df.columns
    assert "housing_loan_amount" in result_df.columns
    assert "nominal_housing_loan_mn_try" in result_df.columns


def test_parquet_real_round_trip(bronze_env):
    """Gerçek Parquet round-trip testi — to_parquet mock'suz, pyarrow ile.
    Yazılan dosya geri okunduğunda satır sayısı, kolon adları ve değerler
    birebir eşleşmeli. to_parquet mock'lansa bu test hiçbir şey doğrulamaz."""
    import tempfile
    _, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(toplam=1234.5, year=2021, month=1))

    df = build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        parquet_path = Path(f.name)

    try:
        df.to_parquet(parquet_path, index=False)
        reloaded = pd.read_parquet(parquet_path)

        assert len(reloaded) == 1
        assert list(reloaded.columns) == list(df.columns)
        assert reloaded["period"].iloc[0] == "2021-01"
        assert abs(reloaded["housing_loan_amount"].iloc[0] - 1234.5) < 0.001
        assert abs(reloaded["nominal_housing_loan_mn_try"].iloc[0] - 1234.5) < 0.001
        assert reloaded["housing_loan_unit"].iloc[0] == "Milyon TL"
    finally:
        parquet_path.unlink(missing_ok=True)


def test_atomic_write_failure_content_mismatch_preserves_old_output(bronze_env):
    """Parquet yazma sonrasi read-back check (icerik uyusmazligi) hata firlatirsa eski gecerli cikti korunmali."""
    import scripts.build_bddk_silver
    from scripts.build_bddk_silver import main
    import pandas as pd

    base, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(toplam=999.0, year=2021, month=1))
    out_path = base / "out.parquet"

    # Gecerli eski veri
    old_df = pd.DataFrame({"period": ["2020-12"], "housing_loan_amount": [10.0]})
    old_df.to_parquet(out_path)
    old_mtime = out_path.stat().st_mtime

    original_to_parquet = pd.DataFrame.to_parquet

    def corrupted_to_parquet(self, path, index=False):
        # Write corrupted/different data to simulate serialization issue
        corrupted_df = pd.DataFrame({"period": ["wrong_period"], "housing_loan_amount": [9999.9]})
        original_to_parquet(corrupted_df, path, index=False)

    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir

    def redirected_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    with mock.patch.object(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", redirected_build):
        with mock.patch("sys.argv", ["build_bddk_silver", "--start-period", "2021-01",
                                     "--end-period", "2021-01", "--output", str(out_path)]):
            with mock.patch.object(pd.DataFrame, "to_parquet", corrupted_to_parquet):
                exit_code = main()

    assert exit_code != 0
    assert out_path.exists()
    assert out_path.stat().st_mtime == old_mtime
    assert not out_path.with_suffix(".part").exists()


def test_atomic_write_failure_preserves_old_output(bronze_env):
    """Parquet yazma sırasında hata olursa eski geçerli çıktı korunmalı.
    .part geçici dosyası temizlenmeli; nihai hedef bozulmamalı."""
    import scripts.build_bddk_silver
    from scripts.build_bddk_silver import main

    base, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(toplam=999.0, year=2021, month=1))

    out_path = base / "safe.parquet"
    # Pre-populate with a valid "old" Parquet so we can verify it is preserved
    old_df = pd.DataFrame({"period": ["2020-01"], "value": [42.0]})
    old_df.to_parquet(out_path, index=False)
    old_mtime = out_path.stat().st_mtime

    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir

    def redirected_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    # Simulate mid-write failure by making to_parquet raise after the temp file is created
    original_to_parquet = pd.DataFrame.to_parquet

    def failing_to_parquet(self, path, index=False):
        Path(path).write_bytes(b"corrupted")
        raise OSError("Simulated disk full error")

    with mock.patch.object(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", redirected_build):
        with mock.patch("sys.argv", ["build_bddk_silver", "--start-period", "2021-01",
                                     "--end-period", "2021-01", "--output", str(out_path)]):
            with mock.patch.object(pd.DataFrame, "to_parquet", failing_to_parquet):
                exit_code = main()

    assert exit_code == 1, "CLI must exit 1 when write fails"
    # Old output must be untouched
    assert out_path.exists(), "Old valid output must still exist"
    assert out_path.stat().st_mtime == old_mtime, "Old output must not be modified"
    # Temp .part file must be cleaned up
    assert not out_path.with_suffix(".part").exists(), ".part temp file must be cleaned up on failure"



def test_atomic_write_exact_float_mismatch_preserves_old_output(bronze_env):
    """check_exact=True must catch small numeric differences (e.g. 1_000_000 vs 1_000_001).
    Old output must be preserved and .part cleaned up."""
    import scripts.build_bddk_silver
    from scripts.build_bddk_silver import main

    base, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(toplam=1_000_000.0, year=2021, month=1))
    out_path = base / "exact.parquet"

    old_df = pd.DataFrame({"period": ["2020-12"], "housing_loan_amount": [10.0]})
    old_df.to_parquet(out_path)
    old_mtime = out_path.stat().st_mtime

    original_to_parquet = pd.DataFrame.to_parquet

    def slightly_altered_to_parquet(self, path, index=False):
        # Write a df where one float value differs by exactly 1 — same shape/dtype, different value
        altered = self.copy()
        if "housing_loan_amount" in altered.columns:
            altered["housing_loan_amount"] = altered["housing_loan_amount"] + 1.0
        original_to_parquet(altered, path, index=False)

    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir

    def redirected_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    with mock.patch.object(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", redirected_build):
        with mock.patch("sys.argv", ["build_bddk_silver", "--start-period", "2021-01",
                                     "--end-period", "2021-01", "--output", str(out_path)]):
            with mock.patch.object(pd.DataFrame, "to_parquet", slightly_altered_to_parquet):
                exit_code = main()

    assert exit_code == 1, "CLI must fail when read-back value differs (exact comparison)"
    assert out_path.exists(), "Old output must be preserved"
    assert out_path.stat().st_mtime == old_mtime, "Old output must not be modified"
    assert not out_path.with_suffix(".part").exists(), ".part must be cleaned up"


def test_symlink_outside_raw_dir_rejected(bronze_env):
    """A symlink whose text path starts with aylik/raw/ but resolves outside raw_dir
    must be rejected with SilverDataError (symlink escape)."""
    import os
    _, receipts_dir, raw_dir = bronze_env

    # Create a real file OUTSIDE raw_dir (in a sibling directory)
    escape_dir = raw_dir.parent.parent / "escape"
    escape_dir.mkdir(parents=True, exist_ok=True)
    real_file = escape_dir / "secret.json"
    content = _make_mock_raw_json(year=2021, month=1)
    real_file.write_bytes(content)

    # Place a symlink inside raw_dir that points to the file outside
    symlink_name = f"raw_escape_{hashlib.sha256(content).hexdigest()}.json"
    symlink_path = raw_dir / symlink_name
    try:
        symlink_path.symlink_to(real_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this OS/filesystem")

    import hashlib as _hl
    raw_hash = _hl.sha256(content).hexdigest()
    receipt = {
        "request_key": "symlink_req",
        "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL",
                       "yil": 2021, "ay": 1},
        "downloaded_at": "2026-09-11T12:00:00Z",
        "path": f"aylik/raw/{symlink_name}",
        "size_bytes": len(content),
        "sha256": raw_hash,
        "validation": {"period": "2021-01", "period_confirmation": "response_caption"},
    }
    (receipts_dir / "rec_symlink.json").write_text(
        __import__("json").dumps(receipt), encoding="utf-8"
    )

    with pytest.raises(SilverDataError, match="resolves outside"):
        build_bddk_monthly_silver_table(receipts_dir, raw_dir, "2021-01", "2021-01")


def test_cli_main_success(bronze_env, monkeypatch, capsys):
    from scripts.build_bddk_silver import main
    base, receipts_dir, raw_dir = bronze_env
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1))
    out_path = base / "out.parquet"

    monkeypatch.setattr("sys.argv", ["scripts.build_bddk_silver", "--start-period", "2021-01",
                                     "--end-period", "2021-01", "--output", str(out_path)])

    import scripts.build_bddk_silver
    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table

    base_receipts, base_raw = receipts_dir, raw_dir

    def mock_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    monkeypatch.setattr(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", mock_build)

    exit_code = main()
    assert exit_code == 0
    assert out_path.exists()
    # Real Parquet was written — verify it is readable and has correct row count
    result_df = pd.read_parquet(out_path)
    assert len(result_df) == 1
    assert "period" in result_df.columns

    captured = capsys.readouterr()
    assert "[SUCCESS] Built Silver dataset" in captured.out


def test_cli_main_failure(bronze_env, monkeypatch, capsys):
    from scripts.build_bddk_silver import main
    base, receipts_dir, raw_dir = bronze_env
    # Missing gap
    create_receipt_and_raw(receipts_dir, raw_dir, 2021, 1, _make_mock_raw_json(year=2021, month=1))
    out_path = base / "out.parquet"

    monkeypatch.setattr("sys.argv", ["scripts.build_bddk_silver", "--start-period", "2021-01",
                                     "--end-period", "2021-02", "--output", str(out_path)])

    import scripts.build_bddk_silver
    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir

    def mock_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    monkeypatch.setattr(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", mock_build)

    exit_code = main()
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "[FAIL-CLOSED ERROR]" in captured.err


def test_cli_default_scope(bronze_env, monkeypatch):
    """Test generating Silver dataset using default scope (66 months)."""
    import scripts.build_bddk_silver
    from app.lakehouse.bddk_silver import DEFAULT_END_PERIOD, DEFAULT_START_PERIOD
    from scripts.build_bddk_silver import main

    base, receipts_dir, raw_dir = bronze_env

    # Generate from 2021-01 to 2026-07 (67 months total)
    for year in range(2021, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 7:
                break
            create_receipt_and_raw(receipts_dir, raw_dir, year, month, _make_mock_raw_json(year=year, month=month))

    out_path = base / "out.parquet"

    # No start/end arguments so it falls back to DEFAULT_START_PERIOD / DEFAULT_END_PERIOD
    monkeypatch.setattr("sys.argv", ["scripts.build_bddk_silver", "--output", str(out_path)])

    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir

    def mock_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    monkeypatch.setattr(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", mock_build)

    exit_code = main()
    assert exit_code == 0
    assert out_path.exists()

    df = pd.read_parquet(out_path)
    assert len(df) == 66  # 2021-01 to 2026-06 is exactly 66 months
    assert df["period"].min() == DEFAULT_START_PERIOD
    assert df["period"].max() == DEFAULT_END_PERIOD
    assert "2026-07" not in df["period"].values


def test_cli_demo_scope(bronze_env, monkeypatch):
    """Test generating Silver dataset using demo scope (60 months)."""
    import scripts.build_bddk_silver
    from app.lakehouse.bddk_silver import DEFAULT_START_PERIOD, DEMO_END_PERIOD
    from scripts.build_bddk_silver import main

    base, receipts_dir, raw_dir = bronze_env

    # Generate from 2021-01 to 2026-07 (67 months total)
    for year in range(2021, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 7:
                break
            create_receipt_and_raw(receipts_dir, raw_dir, year, month, _make_mock_raw_json(year=year, month=month))

    out_path = base / "out.parquet"

    # --demo flag uses DEMO_END_PERIOD
    monkeypatch.setattr("sys.argv", ["scripts.build_bddk_silver", "--demo", "--output", str(out_path)])

    original_build = scripts.build_bddk_silver.build_bddk_monthly_silver_table
    base_receipts, base_raw = receipts_dir, raw_dir

    def mock_build(receipts_dir=None, raw_dir=None, start_period=None, end_period=None):
        return original_build(base_receipts, base_raw, start_period, end_period)

    monkeypatch.setattr(scripts.build_bddk_silver, "build_bddk_monthly_silver_table", mock_build)

    exit_code = main()
    assert exit_code == 0
    assert out_path.exists()

    df = pd.read_parquet(out_path)
    assert len(df) == 60  # 2021-01 to 2025-12 is exactly 60 months
    assert df["period"].min() == DEFAULT_START_PERIOD
    assert df["period"].max() == DEMO_END_PERIOD
    assert "2026-01" not in df["period"].values
