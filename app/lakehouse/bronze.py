from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copy2

from .layout import DataLayer, LakehouseLayout


@dataclass(frozen=True)
class BronzeAsset:
    """Metadata describing one immutable Bronze asset."""

    path: Path
    sha256: str
    size_bytes: int


def calculate_sha256(file_path: str | Path) -> str:
    """Calculate a file checksum without loading the whole file into memory."""

    path = Path(file_path)
    digest = sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


class BronzeStore:
    """Store immutable copies of raw source files in the Bronze layer."""

    def __init__(self, layout: LakehouseLayout) -> None:
        self.layout = layout

    def store_file(
        self,
        source_file: str | Path,
        source: str,
        dataset: str,
        filename: str | None = None,
    ) -> BronzeAsset:
        source_path = Path(source_file)

        if not source_path.is_file():
            raise FileNotFoundError(f"Source file does not exist: {source_path}")

        target_filename = filename or source_path.name
        destination = self.layout.asset_path(
            layer=DataLayer.BRONZE,
            source=source,
            dataset=dataset,
            filename=target_filename,
        )

        source_checksum = calculate_sha256(source_path)

        if destination.exists():
            if not destination.is_file():
                raise FileExistsError(
                    f"Bronze destination is not a file: {destination}"
                )

            destination_checksum = calculate_sha256(destination)

            if destination_checksum != source_checksum:
                raise FileExistsError(
                    "Bronze asset already exists with different content: "
                    f"{destination}"
                )

            return BronzeAsset(
                path=destination,
                sha256=destination_checksum,
                size_bytes=destination.stat().st_size,
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(source_path, destination)

        return BronzeAsset(
            path=destination,
            sha256=source_checksum,
            size_bytes=destination.stat().st_size,
        )