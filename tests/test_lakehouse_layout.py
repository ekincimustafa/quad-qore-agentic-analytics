from pathlib import Path

import pytest

from app.lakehouse.layout import (
    DataLayer,
    InvalidPathSegmentError,
    LakehouseLayout,
)


def test_builds_expected_asset_path(tmp_path: Path) -> None:
    layout = LakehouseLayout(tmp_path)

    result = layout.asset_path(
        layer=DataLayer.BRONZE,
        source="bddk",
        dataset="bilanco",
        filename="Bilanco_2026_7.xlsx",
    )

    assert result == (
        tmp_path
        / "bronze"
        / "bddk"
        / "bilanco"
        / "Bilanco_2026_7.xlsx"
    )


def test_creates_all_base_layer_directories(tmp_path: Path) -> None:
    layout = LakehouseLayout(tmp_path)

    created = layout.ensure_base_directories()

    assert set(created) == set(DataLayer)
    assert all(directory.is_dir() for directory in created.values())


def test_creates_dataset_directory_idempotently(tmp_path: Path) -> None:
    layout = LakehouseLayout(tmp_path)

    first_result = layout.ensure_dataset_directory(
        DataLayer.SILVER,
        source="evds",
        dataset="macro_series",
    )
    second_result = layout.ensure_dataset_directory(
        DataLayer.SILVER,
        source="evds",
        dataset="macro_series",
    )

    assert first_result == second_result
    assert first_result.is_dir()


@pytest.mark.parametrize(
    ("source", "dataset", "filename"),
    [
        ("../bddk", "bilanco", "file.xlsx"),
        ("bddk", "../bilanco", "file.xlsx"),
        ("bddk", "bilanco", "../file.xlsx"),
        ("bddk", "bilanco", r"folder\file.xlsx"),
    ],
)
def test_rejects_unsafe_path_segments(
    tmp_path: Path,
    source: str,
    dataset: str,
    filename: str,
) -> None:
    layout = LakehouseLayout(tmp_path)

    with pytest.raises(InvalidPathSegmentError):
        layout.asset_path(
            DataLayer.BRONZE,
            source=source,
            dataset=dataset,
            filename=filename,
        )