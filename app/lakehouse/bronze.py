from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from shutil import copy2
from typing import Optional

from .layout import DataLayer, LakehouseLayout


@dataclass(frozen=True)
class BronzeAsset:
    """Metadata describing one immutable Bronze asset.

    Temel alanlar (her zaman dolu):
        path       : Diskteki tam yol
        sha256     : Dosya içeriğinin SHA-256 özeti (bütünlük garantisi)
        size_bytes : Bayt cinsinden boyut

    Provenance alanları (opsiyonel — issue #4 Bronze kalite ölçütleri):
        source_url    : Verinin çekildiği kaynak URL
        downloaded_at : İndirme zamanı (ISO 8601, UTC)
        data_period   : Verinin temsil ettiği dönem (ör. "2021-01" ya da "2021-01/2021-01-29")
        content_type  : MIME türü (ör. "application/json", "text/html")
    """

    path: Path
    sha256: str
    size_bytes: int

    # Provenance — issue #4 Bronze kalite ölçütleri
    source_url: Optional[str] = field(default=None, compare=False)
    downloaded_at: Optional[str] = field(default=None, compare=False)
    data_period: Optional[str] = field(default=None, compare=False)
    content_type: Optional[str] = field(default=None, compare=False)

    def has_provenance(self) -> bool:
        """Tüm provenance alanları doluysa True döner."""
        return all([
            self.source_url,
            self.downloaded_at,
            self.data_period,
            self.content_type,
        ])

    def provenance_summary(self) -> dict:
        """İnsan okunabilir provenance özeti."""
        return {
            "source_url": self.source_url or "(bilinmiyor)",
            "downloaded_at": self.downloaded_at or "(bilinmiyor)",
            "data_period": self.data_period or "(bilinmiyor)",
            "content_type": self.content_type or "(bilinmiyor)",
        }


def calculate_sha256(file_path: str | Path) -> str:
    """Dosyayı belleğe tamamen yüklemeden SHA-256 özeti hesaplar."""
    path = Path(file_path)
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BronzeStore:
    """Bronze katmanı için dosya kayıt ve denetim sınıfı.

    Sorumluluklar:
        - Kaynak dosyayı doğru lakehouse yoluna kopyalamak (store_file)
        - SHA-256 ile bütünlük garantisi vermek
        - İmmutability: aynı yola farklı içerik yazılmasını engellemek

    Bu sınıf veri INDIRMEZ. Ağ erişimi, API çağrısı veya HTTP isteği yapmaz.
    İndirme sorumluluğu connector'lara aittir (ör. app/connectors/bddk.py).
    """

    def __init__(self, layout: LakehouseLayout) -> None:
        self.layout = layout

    def store_file(
        self,
        source_file: str | Path,
        source: str,
        dataset: str,
        filename: str | None = None,
        source_url: str | None = None,
        downloaded_at: str | None = None,
        data_period: str | None = None,
        content_type: str | None = None,
    ) -> BronzeAsset:
        """Kaynak dosyayı Bronze katmanına kopyalar ve BronzeAsset döner.

        Dosya zaten varsa ve içerik aynıysa idempotent davranır (tekrar kopyalamaz).
        Farklı içerikle aynı yola yazma girişiminde FileExistsError fırlatır.

        Args:
            source_file   : Kopyalanacak kaynak dosya yolu.
            source        : Veri kaynağı adı (ör. "bddk", "evds").
            dataset       : Veri seti adı (ör. "tuketici_kredileri").
            filename      : Hedef dosya adı; verilmezse kaynak adı kullanılır.
            source_url    : Verinin çekildiği URL (provenance).
            downloaded_at : İndirme zamanı ISO 8601 (provenance).
            data_period   : Verinin temsil ettiği dönem (provenance).
            content_type  : MIME türü (provenance).
        """
        source_path = Path(source_file)
        if not source_path.is_file():
            raise FileNotFoundError(f"Kaynak dosya bulunamadı: {source_path}")

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
                    f"Bronze hedef bir dosya değil: {destination}"
                )
            destination_checksum = calculate_sha256(destination)
            if destination_checksum != source_checksum:
                raise FileExistsError(
                    f"Bronze'da farklı içerikli dosya zaten var: {destination}"
                )
            return BronzeAsset(
                path=destination,
                sha256=destination_checksum,
                size_bytes=destination.stat().st_size,
                source_url=source_url,
                downloaded_at=downloaded_at,
                data_period=data_period,
                content_type=content_type,
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(source_path, destination)

        return BronzeAsset(
            path=destination,
            sha256=source_checksum,
            size_bytes=destination.stat().st_size,
            source_url=source_url,
            downloaded_at=downloaded_at,
            data_period=data_period,
            content_type=content_type,
        )
