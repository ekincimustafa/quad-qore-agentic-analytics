"""
BronzeStore ve BronzeAsset testleri.

ÖNCE (4 test — Mustafa'nın orijinal testleri, değiştirilmedi):
  - test_stores_file_in_bronze_layer
  - test_storing_same_file_is_idempotent
  - test_rejects_different_content_at_existing_path
  - test_rejects_missing_source_file

SONRA — yeni özellikler (4 yeni test):
  - test_bronze_asset_provenance_fields_default_to_none
  - test_bronze_asset_has_provenance_true_when_all_fields_filled
  - test_bronze_asset_has_provenance_false_when_partial
  - test_store_file_passes_provenance_to_asset
"""
from hashlib import sha256
from pathlib import Path

import pytest

from app.lakehouse.bronze import BronzeStore
from app.lakehouse.layout import LakehouseLayout


# ---------------------------------------------------------------------------
# ORIJINAL TESTLER (Mustafa) — degistirilmedi, hepsi gecmeli
# ---------------------------------------------------------------------------

def test_stores_file_in_bronze_layer(tmp_path: Path) -> None:
    source_file = tmp_path / "Bilanco_2026_7.xlsx"
    content = b"example-bddk-content"
    source_file.write_bytes(content)

    store = BronzeStore(LakehouseLayout(tmp_path / "data"))

    result = store.store_file(
        source_file=source_file,
        source="bddk",
        dataset="bilanco",
    )

    expected_path = (
        tmp_path / "data" / "bronze" / "bddk" / "bilanco" / "Bilanco_2026_7.xlsx"
    )

    assert result.path == expected_path
    assert result.path.read_bytes() == content
    assert result.sha256 == sha256(content).hexdigest()
    assert result.size_bytes == len(content)


def test_storing_same_file_is_idempotent(tmp_path: Path) -> None:
    source_file = tmp_path / "source.xlsx"
    source_file.write_bytes(b"same-content")

    store = BronzeStore(LakehouseLayout(tmp_path / "data"))

    first_result = store.store_file(source_file, "bddk", "bilanco")
    second_result = store.store_file(source_file, "bddk", "bilanco")

    assert first_result == second_result


def test_rejects_different_content_at_existing_path(tmp_path: Path) -> None:
    first_file = tmp_path / "first.xlsx"
    second_file = tmp_path / "second.xlsx"

    first_file.write_bytes(b"first-content")
    second_file.write_bytes(b"different-content")

    store = BronzeStore(LakehouseLayout(tmp_path / "data"))

    store.store_file(
        first_file,
        source="bddk",
        dataset="bilanco",
        filename="snapshot.xlsx",
    )

    with pytest.raises(FileExistsError):
        store.store_file(
            second_file,
            source="bddk",
            dataset="bilanco",
            filename="snapshot.xlsx",
        )


def test_rejects_missing_source_file(tmp_path: Path) -> None:
    store = BronzeStore(LakehouseLayout(tmp_path / "data"))

    with pytest.raises(FileNotFoundError):
        store.store_file(
            tmp_path / "missing.xlsx",
            source="bddk",
            dataset="bilanco",
        )


# ---------------------------------------------------------------------------
# YENI TESTLER — provenance
# ---------------------------------------------------------------------------

def test_bronze_asset_provenance_fields_default_to_none(tmp_path: Path) -> None:
    """Provenance alanları belirtilmezse None olmalı — geriye dönük uyumluluk."""
    source_file = tmp_path / "dosya.json"
    source_file.write_bytes(b"veri")

    store = BronzeStore(LakehouseLayout(tmp_path / "data"))
    asset = store.store_file(source_file, "bddk", "aylik")

    assert asset.source_url is None
    assert asset.downloaded_at is None
    assert asset.data_period is None
    assert asset.content_type is None
    assert asset.has_provenance() is False


def test_bronze_asset_has_provenance_true_when_all_fields_filled(tmp_path: Path) -> None:
    """Tüm provenance alanları doluysa has_provenance() True döner."""
    source_file = tmp_path / "dosya.json"
    source_file.write_bytes(b"veri")

    store = BronzeStore(LakehouseLayout(tmp_path / "data"))
    asset = store.store_file(
        source_file,
        source="bddk",
        dataset="aylik",
        source_url="https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir",
        downloaded_at="2026-09-10T20:32:06+00:00",
        data_period="2021-01",
        content_type="application/json",
    )

    assert asset.has_provenance() is True
    assert asset.source_url == "https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir"
    assert asset.downloaded_at == "2026-09-10T20:32:06+00:00"
    assert asset.data_period == "2021-01"
    assert asset.content_type == "application/json"


def test_bronze_asset_has_provenance_false_when_partial(tmp_path: Path) -> None:
    """Provenance alanları eksikse has_provenance() False döner."""
    source_file = tmp_path / "dosya.json"
    source_file.write_bytes(b"veri")

    store = BronzeStore(LakehouseLayout(tmp_path / "data"))
    asset = store.store_file(
        source_file,
        source="bddk",
        dataset="aylik",
        source_url="https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir",
        # downloaded_at, data_period, content_type eksik
    )

    assert asset.has_provenance() is False


def test_store_file_passes_provenance_to_asset(tmp_path: Path) -> None:
    """store_file provenance alanlarını BronzeAsset'e doğru aktarır."""
    source_file = tmp_path / "haftalik.html"
    source_file.write_bytes(b"<html>haftalik veri</html>")

    store = BronzeStore(LakehouseLayout(tmp_path / "data"))
    asset = store.store_file(
        source_file,
        source="bddk",
        dataset="haftalik",
        source_url="https://www.bddk.org.tr/BultenHaftalik/tr/Gelismis/GelismisRaporGetir",
        downloaded_at="2026-09-10T20:40:11+00:00",
        data_period="2021-01",
        content_type="text/html",
    )

    summary = asset.provenance_summary()
    assert summary["source_url"].startswith("https://www.bddk.org.tr")
    assert summary["data_period"] == "2021-01"
    assert summary["content_type"] == "text/html"
