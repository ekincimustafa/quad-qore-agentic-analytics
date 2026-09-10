from hashlib import sha256
from pathlib import Path

import pytest

from app.lakehouse.bronze import BronzeStore
from app.lakehouse.layout import LakehouseLayout


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
        tmp_path
        / "data"
        / "bronze"
        / "bddk"
        / "bilanco"
        / "Bilanco_2026_7.xlsx"
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