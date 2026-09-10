from __future__ import annotations

import re
from enum import Enum
from pathlib import Path


class DataLayer(str, Enum):
    """Supported lakehouse data layers."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class InvalidPathSegmentError(ValueError):
    """Raised when a path segment is empty or unsafe."""


_SAFE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_segment(value: str, field_name: str) -> str:
    candidate = value.strip()

    if not candidate or not _SAFE_SEGMENT_PATTERN.fullmatch(candidate):
        raise InvalidPathSegmentError(
            f"{field_name} must be a single safe path segment: {value!r}"
        )

    return candidate


class LakehouseLayout:
    """Build and create predictable paths for lakehouse assets."""

    def __init__(self, root: str | Path = "data") -> None:
        self.root = Path(root)

    def layer_directory(self, layer: DataLayer | str) -> Path:
        selected_layer = DataLayer(layer)
        return self.root / selected_layer.value

    def dataset_directory(
        self,
        layer: DataLayer | str,
        source: str,
        dataset: str,
    ) -> Path:
        safe_source = _validate_segment(source, "source")
        safe_dataset = _validate_segment(dataset, "dataset")

        return self.layer_directory(layer) / safe_source / safe_dataset

    def asset_path(
        self,
        layer: DataLayer | str,
        source: str,
        dataset: str,
        filename: str,
    ) -> Path:
        safe_filename = _validate_segment(filename, "filename")

        return self.dataset_directory(layer, source, dataset) / safe_filename

    def ensure_base_directories(self) -> dict[DataLayer, Path]:
        created_directories: dict[DataLayer, Path] = {}

        for layer in DataLayer:
            directory = self.layer_directory(layer)
            directory.mkdir(parents=True, exist_ok=True)
            created_directories[layer] = directory

        return created_directories

    def ensure_dataset_directory(
        self,
        layer: DataLayer | str,
        source: str,
        dataset: str,
    ) -> Path:
        directory = self.dataset_directory(layer, source, dataset)
        directory.mkdir(parents=True, exist_ok=True)
        return directory