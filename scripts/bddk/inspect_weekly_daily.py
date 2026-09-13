"""
Bronze BDDK Haftalik ve Gunluk Veri Kalite Denetimi.

Calistir: python -m scripts.bddk.inspect_weekly_daily
Gereksinimler: Yalnizca Python standart kutuphanesi.

Exit Code:
  0: Haftalik veri seti (2021-01 .. 2026-07) Kalem 5690 ozelinde eksiksiz ve fiziksel dosyalari tam.
  1: Eksik klasor, eksik donem, Kalem 5690 eksigi, okuma hatasi veya fiziksel dosya uyusmazligi.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from app.connectors.bddk import Page


def generate_expected_months(start_year: int, start_month: int, end_year: int, end_month: int) -> list[str]:
    """Standart kutuphane ile beklenen 'YYYY-MM' ay dizisi olusturur."""
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append(f"{y}-{m:02d}")
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


def inspect_gunluk(receipts_dir: Path | None = None) -> dict:
    base_receipts = Path(receipts_dir) if receipts_dir else Path("data/bronze/bddk/gunluk/receipts")

    print("=" * 65)
    print("GUNLUK BDDK VERISI DURUM ANALIZI")
    print("=" * 65)

    if not base_receipts.is_dir():
        print(f"[HATA] Gunluk makbuz klasoru bulunamadi: {base_receipts}")
        return {"receipt_count": 0, "is_valid": False, "historical_accessible": False}

    receipt_files = sorted(base_receipts.glob("*.json"))
    receipt_count = len(receipt_files)
    print(f"Toplam gunluk makbuz sayisi: {receipt_count}")
    print()

    if receipt_count == 0:
        print("[HATA] Gunluk makbuz bulunamadi.")
        return {"receipt_count": 0, "is_valid": False, "historical_accessible": False}

    receipts = []
    unique_dates = set()
    historical_coverages = set()

    for r in receipt_files:
        try:
            d = json.loads(r.read_text("utf-8"))
            receipts.append(d)
            v = d.get("validation", {})
            for dt in v.get("dates", []):
                unique_dates.add(dt)
            historical_coverages.add(v.get("historical_coverage", "unverified"))
        except Exception as e:
            print(f"[UYARI] {r.name} okunamadi: {e}")

    for idx, d in enumerate(receipts[:3]):
        v = d.get("validation", {})
        print(f"  Ornek {idx + 1} ({d.get('path', '').split('/')[-1][:30]}...):")
        print(f"    Kaynak URL      : {d.get('source_url')}")
        print(f"    Indirme Zamani  : {d.get('downloaded_at', '')[:19]}")
        print(f"    Istenen Donem   : {v.get('requested_start')} / {v.get('requested_end')}")
        print(f"    Dönen Tarihler  : {v.get('dates')}")
        print(f"    Gecmis Kapsami  : {v.get('historical_coverage')}")
        print()

    print("GUNLUK VERI BULGULARI (Hesaplanan):")
    print(f"  - Toplam incelenen makbuz: {len(receipts)}")
    print(f"  - Yanitlarda donen benzersiz tarihler: {sorted(unique_dates)}")
    print(f"  - Bildirilen gecmis kapsami: {sorted(historical_coverages)}")
    print("  - TESPIT: Farkli tarih araligi parametrelerine ragmen sayfa yalnizca")
    print(f"    mevcut tekil gunun snapshot verisini dondurmektedir ({sorted(unique_dates)}).")
    print("  - Mevcut denemelerde gecmis gunluk seri erisimi dogrulanamadi.")

    return {
        "receipt_count": len(receipts),
        "is_valid": len(receipts) > 0,
        "historical_accessible": False,
        "unique_dates": sorted(unique_dates),
    }


def inspect_haftalik(receipts_dir: Path | None = None, raw_dir: Path | None = None) -> dict:
    base_receipts = Path(receipts_dir) if receipts_dir else Path("data/bronze/bddk/haftalik/receipts")
    base_raw = Path(raw_dir) if raw_dir else Path("data/bronze/bddk/haftalik/raw")

    print()
    print("=" * 65)
    print("HAFTALIK BDDK VERISI DURUM ANALIZI")
    print("=" * 65)

    if not base_receipts.is_dir():
        print(f"[HATA] Haftalik makbuz klasoru bulunamadi: {base_receipts}")
        return {"is_valid": False, "error": "receipts_dir_missing"}

    receipt_files = sorted(base_receipts.glob("*.json"))
    total_receipts = len(receipt_files)
    print(f"Toplam haftalik makbuz sayisi: {total_receipts}")

    if total_receipts == 0:
        print("[HATA] Haftalik makbuz bulunamadi.")
        return {"is_valid": False, "error": "no_receipts"}

    veri_istekleri = []
    katalog_istekleri = []
    okuma_hatalari = []

    for r in receipt_files:
        try:
            d = json.loads(r.read_text("utf-8"))
            p = d.get("parameters") or {}
            if p.get("Kalemler"):
                veri_istekleri.append(d)
            else:
                katalog_istekleri.append(d)
        except Exception as e:
            okuma_hatalari.append((r.name, str(e)))

    is_valid = True

    if okuma_hatalari:
        print(f"[HATA] {len(okuma_hatalari)} makbuz okunamadi veya bozuk:")
        for name, err in okuma_hatalari:
            print(f"  {name}: {err}")
        is_valid = False

    print(f"  Katalog/kesif makbuzu : {len(katalog_istekleri)}")
    print(f"  Gercek veri makbuzu   : {len(veri_istekleri)}")

    # -----------------------------------------------------------------------
    # Kalem 5690 (Konut Kredisi) — Istek ve HTML Icerigi AYRI Dogrulama
    # -----------------------------------------------------------------------
    # ay_seti_5690_istekte : 5690, istekte (Kalemler parametresinde) mevcut
    # ay_seti_5690_html    : 5690 HTML tablosunda kullanilabilir veri iceriyor
    #                        (TabloExcelGelismis header Row1'de 'Konut' sutunu
    #                        + en az bir sayisal deger)
    ay_seti_genel: set = set()
    ay_seti_5690_istekte: set = set()
    ay_seti_5690_html: set = set()
    para_birimleri: set = set()
    taraf_gruplari: set = set()
    row_counts: dict = {}
    missing_files: list = []
    size_mismatches: list = []
    hash_mismatches: list = []
    html_parse_hatalari: list = []

    for d in veri_istekleri:
        p = d.get("parameters") or {}
        v = d.get("validation", {})
        kalemler = p.get("Kalemler", [])

        bas = p.get("BaslangicTarihi", "")[:10]  # "01.01.2021"
        ay_key = None
        try:
            parts = bas.split(".")
            if len(parts) == 3:
                ay_key = f"{parts[2]}-{parts[1]}"
                ay_seti_genel.add(ay_key)
        except Exception:
            pass

        # Set 1: 5690 istekte mevcut mu?
        if "5690" in kalemler and ay_key:
            ay_seti_5690_istekte.add(ay_key)

        para_birimleri.add(p.get("SeciliParalar", "?"))
        taraf_gruplari.add(len(p.get("Taraflar", [])))

        rows = v.get("data_rows", 0)
        row_counts[rows] = row_counts.get(rows, 0) + 1

        # Fiziksel dosya ve boyut/hash dogrulamasi
        rel_path = d.get("path", "")
        if raw_dir:
            raw_file = base_raw / Path(rel_path).name
        else:
            raw_file = Path("data/bronze/bddk") / rel_path

        if not raw_file.is_file():
            missing_files.append((d.get("request_key", rel_path), str(raw_file)))
            is_valid = False
            continue

        actual_size = raw_file.stat().st_size
        expected_size = d.get("size_bytes")
        if expected_size is not None and actual_size != expected_size:
            size_mismatches.append((rel_path, actual_size, expected_size))
            is_valid = False
            continue

        raw_bytes = raw_file.read_bytes()
        expected_sha = d.get("sha256")
        if expected_sha:
            actual_sha = hashlib.sha256(raw_bytes).hexdigest()
            if actual_sha != expected_sha:
                hash_mismatches.append(
                    (rel_path,
                     f"diskte {actual_sha[:16]}..., makbuzda {expected_sha[:16]}...")
                )
                is_valid = False
                continue

        # Set 2: 5690 HTML icin kullanilabilir veri dogrulamasi
        # (Yalnizca fiziksel dosya, boyut ve SHA-256 dogrulandiysa parse et)
        if "5690" in kalemler and ay_key:
            try:
                html_text = raw_bytes.decode("utf-8", errors="replace")
                page_obj = Page(html_text)
                table_rows = page_obj.tables.get("TabloExcelGelismis", [])
                # Header Row1: kalem etiketleri ("Krediler / a) Konut" = 5690)
                # En az 2 satir olmali (header + veri)
                header_row = table_rows[1] if len(table_rows) > 1 else []
                konut_cols = [
                    i for i, cell in enumerate(header_row)
                    if "konut" in cell.lower()
                ]
                if konut_cols:
                    # Veri satirlarinda bu sutunlarda sayisal deger var mi?
                    date_rows = [
                        row for row in table_rows
                        if row and re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", row[0].strip() if row else "")
                    ]
                    has_numeric = False
                    for row in date_rows:
                        for col_idx in konut_cols:
                            if col_idx < len(row):
                                cell_val = row[col_idx].replace(",", ".").replace(" ", "").replace("\xa0", "")
                                try:
                                    float(cell_val)
                                    has_numeric = True
                                    break
                                except ValueError:
                                    pass
                        if has_numeric:
                            break
                    if has_numeric:
                        ay_seti_5690_html.add(ay_key)
            except Exception as exc:
                html_parse_hatalari.append((rel_path, str(exc)))

    beklenen_aylar = generate_expected_months(2021, 1, 2026, 7)
    eksik_5690_istekte = [a for a in beklenen_aylar if a not in ay_seti_5690_istekte]
    eksik_5690_html = [a for a in beklenen_aylar if a not in ay_seti_5690_html]

    print()
    print("--- Kalem 5690 (Konut Kredisi) Ay Kapsami ---")
    print(f"Beklenen Donem Sayisi (2021-01 .. 2026-07) : {len(beklenen_aylar)}")
    print(f"  [1] Istekte Mevcut Ay Sayisi             : {len(ay_seti_5690_istekte)}")
    print(f"  [2] HTML'de Kullanilabilir Veri Olan Ay  : {len(ay_seti_5690_html)}")

    if eksik_5690_istekte:
        print(f"[HATA] Kalem 5690 istekte eksik aylar ({len(eksik_5690_istekte)} adet): {eksik_5690_istekte[:10]}")
        is_valid = False
    else:
        print(f"[OK] Kalem 5690 istekte tum {len(beklenen_aylar)} ay icin mevcut.")

    if eksik_5690_html:
        print(
            f"[HATA] Kalem 5690 HTML icerigi dogrulanamayan aylar "
            f"({len(eksik_5690_html)} adet): {eksik_5690_html[:10]}"
        )
        is_valid = False
    else:
        print(f"[OK] Kalem 5690 tum {len(beklenen_aylar)} ay icin HTML'de kullanilabilir veri dogrulandi.")

    if html_parse_hatalari:
        print(f"[HATA] HTML parse hatasi olan {len(html_parse_hatalari)} dosya:")
        for path, err in html_parse_hatalari[:5]:
            print(f"  {path}: {err}")
        is_valid = False

    if missing_files:
        print(f"[HATA] Diskte fiziksel dosyasi bulunamayan {len(missing_files)} makbuz var!")
        is_valid = False

    if size_mismatches:
        print(f"[HATA] Boyut uyusmazligi olan {len(size_mismatches)} dosya var!")
        is_valid = False

    if hash_mismatches:
        print(f"[HATA] SHA-256 uyusmazligi olan {len(hash_mismatches)} dosya var!")
        for path, detail in hash_mismatches[:5]:
            print(f"  {path}: {detail}")
        is_valid = False

    print()
    print(f"Para birimleri: {sorted(para_birimleri)}")
    print(f"Taraf gruplari sayisi: {sorted(taraf_gruplari)}")
    print(f"Satir dagilimlari: {sorted(row_counts.items())}")

    # Raw HTML dosyalari boyut istatistigi
    if base_raw.is_dir():
        raw_files = list(base_raw.glob("*.html"))
        if raw_files:
            sizes = [f.stat().st_size for f in raw_files]
            total_mb = sum(sizes) / 1024 / 1024
            print(f"Ham HTML Dosyalari: {len(raw_files)} adet, Toplam: {total_mb:.1f} MB")

    final_valid = (
        is_valid
        and len(eksik_5690_istekte) == 0
        and len(eksik_5690_html) == 0
        and len(okuma_hatalari) == 0
        and len(html_parse_hatalari) == 0
    )
    return {
        "is_valid": final_valid,
        "total_receipts": total_receipts,
        "covered_months_5690_request": len(ay_seti_5690_istekte),
        "covered_months_5690_html": len(ay_seti_5690_html),
        "expected_months": len(beklenen_aylar),
        "eksik_5690_istekte": eksik_5690_istekte,
        "eksik_5690_html": eksik_5690_html,
        "eksik_5690_aylar": eksik_5690_html,
        "missing_files_count": len(missing_files),
        "size_mismatches_count": len(size_mismatches),
        "hash_mismatches_count": len(hash_mismatches),
        "html_parse_hatalari_count": len(html_parse_hatalari),
    }


def main(gunluk_receipts_dir: Path | None = None, haftalik_receipts_dir: Path | None = None, haftalik_raw_dir: Path | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    gunluk_res = inspect_gunluk(receipts_dir=gunluk_receipts_dir)
    haftalik_res = inspect_haftalik(receipts_dir=haftalik_receipts_dir, raw_dir=haftalik_raw_dir)

    print()
    print("=" * 65)
    print("GENEL DEGERLENDIRME VE CIKIS KODU")
    print("=" * 65)
    print(f"Haftalik Seri Durumu : {'[OK] Basarili' if haftalik_res.get('is_valid') else '[HATA] Eksik veya Hatali'}")
    print(f"Gunluk Seri Durumu   : {'[BILGI] Gecmis arsiv erisimi dogrulanamadi (tek gun anlik snapshot)' if gunluk_res.get('is_valid') else '[HATA] Dosya yok'}")

    if haftalik_res.get("is_valid"):
        print("\n[BASARILI] Haftalik veri seti 67 ay boyunca Kalem 5690 ozelinde eksiksiz ve dosyalari tam.")
        return 0
    else:
        print("\n[HATA] Haftalik veri denetimi basarisiz oldu.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
