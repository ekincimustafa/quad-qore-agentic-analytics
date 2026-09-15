"""
Bronze BDDK Aylik Veri Kalite ve Tutarlilik Denetimi.

Calistir: python -m scripts.bddk.inspect_bronze
Gereksinimler: Yalnizca Python standart kutuphanesi.

Exit Code:
  0: Tum kontroller basarili, beklenen aylar eksiksiz ve semaya uygun.
  1: Eksik ay, sema degisimi, dosya okuma hatasi veya dogrulama basarisizligi.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from app.connectors.bddk import extract_housing_loan_data


def generate_expected_months(start_year: int, start_month: int, end_year: int, end_month: int) -> list[tuple[int, int]]:
    """Standart kutuphane ile beklenen (yil, ay) ciftleri listesi olusturur."""
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


def resolve_secure_raw_path(base_dir: Path, rel_path: str, use_filename_only: bool = False) -> Path | None:
    """Path traversal ve guvensiz dosya erisimini onleyen guvenli yol cozucu."""
    if not rel_path or not isinstance(rel_path, str) or isinstance(rel_path, bool):
        return None
    # Surucu harfleri (C:), URI semalari veya gecersiz karakterleri dogrudan reddet
    if ":" in rel_path:
        return None
    try:
        # Cross-platform separator normalizasyonu (Windows \ -> POSIX /)
        clean_rel = rel_path.replace("\\", "/").strip()
        if clean_rel.startswith("/") or clean_rel.startswith("\\"):
            return None
        parts = [p for p in clean_rel.split("/") if p]
        if not parts or any(p in (".", "..") for p in parts):
            return None

        base_resolved = base_dir.resolve()
        if use_filename_only:
            clean_name = parts[-1]
            if not clean_name or clean_name in (".", ".."):
                return None
            target = (base_resolved / clean_name).resolve()
        else:
            target = (base_resolved / "/".join(parts)).resolve()

        target.relative_to(base_resolved)
        return target
    except (ValueError, OSError):
        return None


def main(receipts_dir: Path | None = None, raw_dir: Path | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    base_receipts = Path(receipts_dir) if receipts_dir else Path("data/bronze/bddk/aylik/receipts")
    base_raw = Path(raw_dir) if raw_dir else Path("data/bronze/bddk/aylik/raw")

    print("=" * 65)
    print("BDDK BRONZE AYLIK VERI KALITE DENETIMI")
    print("=" * 65)

    if not base_receipts.is_dir():
        print(f"[HATA] Makbuz klasoru bulunamadi: {base_receipts}")
        return 1

    receipt_files = sorted(base_receipts.glob("*.json"))
    if not receipt_files:
        print(f"[HATA] {base_receipts} altinda makbuz (.json) dosyasi yok.")
        return 1

    all_raw_receipts = []
    okuma_hatalari = []
    for r in receipt_files:
        try:
            data = json.loads(r.read_text("utf-8"))
            all_raw_receipts.append(data)
        except Exception as exc:
            okuma_hatalari.append((r.name, str(exc)))

    is_valid = True

    if okuma_hatalari:
        print(f"[HATA] {len(okuma_hatalari)} makbuz okunamadi veya bozuk JSON iceriyor:")
        for name, err in okuma_hatalari:
            print(f"  {name}: {err}")
        is_valid = False

    # -----------------------------------------------------------------------
    # Idempotent Deduplication: Ayni request_key icin en son makbuzu sec
    # -----------------------------------------------------------------------
    deduped_by_key: dict[str, dict] = {}
    for r in all_raw_receipts:
        key = r.get("request_key")
        if not key:
            continue
        ts = r.get("downloaded_at", "")
        if key not in deduped_by_key or ts > deduped_by_key[key].get("downloaded_at", ""):
            deduped_by_key[key] = r

    unique_receipts = list(deduped_by_key.values())
    duplicate_count = len(all_raw_receipts) - len(unique_receipts)

    # Tablo bazli makbuz dagilimi (tekillestirilmis)
    tablo_sayac: dict[str, int] = {}
    for r in unique_receipts:
        params = r.get("parameters") or {}
        tablo_no = str(params.get("tabloNo", "(katalog/GET)")) if params else "(katalog/GET)"
        tablo_sayac[tablo_no] = tablo_sayac.get(tablo_no, 0) + 1

    print(f"Toplam Makbuz Dosyasi : {len(all_raw_receipts)}")
    print(f"Tekil Istek Sayisi    : {len(unique_receipts)} ({duplicate_count} eski/refresh makbuz elendi)")
    print("Tablo Dagilimi (Tekil):")
    for k, v in sorted(tablo_sayac.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        print(f"  Tablo {k:>15}: {v:>4} istek")

    # -----------------------------------------------------------------------
    # Demo Serisi: Tablo 4, Sektor (10001), TL
    # Donem (yil, ay) bazinda tekillestir
    # -----------------------------------------------------------------------
    by_period: dict[tuple[int, int], dict] = {}
    for r in unique_receipts:
        p = r.get("parameters") or {}
        if not p:
            continue
        if (str(p.get("tabloNo")) == "4"
                and p.get("taraf") == ["10001"]
                and p.get("paraBirimi") == "TL"):
            period = (int(p["yil"]), int(p["ay"]))
            ts = r.get("downloaded_at", "")
            if period not in by_period or ts > by_period[period].get("downloaded_at", ""):
                by_period[period] = r

    tablo4_sektor_tl = sorted(by_period.values(), key=lambda x: (x["parameters"]["yil"], x["parameters"]["ay"]))

    beklenen_aylar = generate_expected_months(2021, 1, 2026, 7)
    mevcut_aylar = {(r["parameters"]["yil"], r["parameters"]["ay"]) for r in tablo4_sektor_tl}
    eksik_aylar = [a for a in beklenen_aylar if a not in mevcut_aylar]

    print()
    print("=" * 65)
    print("DEMO SERISI: Tablo 4 / Sektor(10001) / TL")
    print("=" * 65)
    print(f"Beklenen Donem Sayisi (2021-01 .. 2026-07) : {len(beklenen_aylar)}")
    print(f"Mevcut Tekil Donem Sayisi                  : {len(tablo4_sektor_tl)}")

    if eksik_aylar:
        print(f"[HATA] EKSIK DONEMLER ({len(eksik_aylar)} adet): {eksik_aylar}")
        is_valid = False
    else:
        print("[OK] Eksik donem yok: 2021-01'den 2026-07'ye kadar tum aylar mevcut.")

    # Satir sayisi kontrolu (Tablo 4 icin 41 satir)
    row_counts: dict[int, int] = {}
    for r in tablo4_sektor_tl:
        rows = r.get("validation", {}).get("rows", 0)
        row_counts[rows] = row_counts.get(rows, 0) + 1

    print()
    print("Satir Sayisi Dagilimi (beklenen: 41 satir):")
    for k, v in sorted(row_counts.items()):
        durum = "OK" if k == 41 else "HATALI"
        if k != 41:
            is_valid = False
        print(f"  {k} satir : {v} ay [{durum}]")

    # Donem dogrulama guvencesi
    dogrulama_tipler: dict[str, int] = {}
    for r in tablo4_sektor_tl:
        tip = r.get("validation", {}).get("period_confirmation", "belirtilmedi")
        dogrulama_tipler[tip] = dogrulama_tipler.get(tip, 0) + 1

    print()
    print("Donem Dogrulama Yontemi:")
    for k, v in dogrulama_tipler.items():
        guvence = "Guclu (kaynak response_caption ile teyitli)" if k == "response_caption" else "Zayif (sadece istek parametresi)"
        print(f"  {k}: {v} ay -> {guvence}")

    # -----------------------------------------------------------------------
    # Dinamik Sema-Duyarli Veri Ayristirma ve Fiziksel Dosya Dogrulamasi
    # -----------------------------------------------------------------------
    print()
    print("=" * 65)
    print("SERI ANALIZI (Dinamik colModels & Gosterge Etiketiyle)")
    print("=" * 65)
    print(f"  {'Donem':<10}  {'TP (mn TL)':>12}  {'YP (mn TL)':>12}  {'Toplam (mn TL)':>15}  {'Degisim %':>12}")
    print(f"  {'-'*8:<10}  {'-'*12:>12}  {'-'*12:>12}  {'-'*15:>15}  {'-'*12:>12}")

    onceki_toplam = None
    parse_hatalari = []
    anomali_aylar = []

    for r in tablo4_sektor_tl:
        p = r["parameters"]
        donem_str = f"{p['yil']}-{p['ay']:02d}"
        rel_path = r.get("path", "")
        # Raw file path resolution
        base_dir = base_raw if raw_dir else Path("data/bronze/bddk")
        raw_file = resolve_secure_raw_path(base_dir, rel_path, use_filename_only=bool(raw_dir))

        if raw_file is None or not raw_file.is_file():
            parse_hatalari.append((donem_str, f"Fiziksel ham dosya bulunamadi veya guvensiz yol: {rel_path}"))
            is_valid = False
            continue

        try:
            actual_size = raw_file.stat().st_size
            raw_bytes = raw_file.read_bytes()
        except OSError as exc:
            parse_hatalari.append((donem_str, f"Fiziksel dosya okuma hatasi: {exc}"))
            is_valid = False
            continue

        expected_size = r.get("size_bytes")
        if expected_size is None or type(expected_size) is not int or expected_size <= 0 or actual_size != expected_size:
            parse_hatalari.append(
                (donem_str, f"Boyut uyusmazligi veya gecersiz size_bytes: diskte {actual_size} bayt, makbuzda {expected_size}")
            )
            is_valid = False
            continue

        expected_sha = r.get("sha256")
        if not expected_sha or not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha):
            parse_hatalari.append(
                (donem_str, f"Gecersiz veya eksik SHA-256 metadata: {expected_sha!r}")
            )
            is_valid = False
            continue

        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        if actual_sha != expected_sha.lower():
            parse_hatalari.append(
                (donem_str,
                 f"SHA-256 uyusmazligi: diskte {actual_sha[:16]}..., makbuzda {expected_sha[:16]}...")
            )
            is_valid = False
            continue

        try:
            raw_payload = json.loads(raw_bytes.decode("utf-8"))
            parsed = extract_housing_loan_data(raw_payload)
            tp = parsed["tp"]
            yp = parsed["yp"]
            toplam = parsed["toplam"]

            degisim_str = "-"
            if onceki_toplam is not None and onceki_toplam > 0:
                degisim = (toplam - onceki_toplam) / onceki_toplam * 100
                degisim_str = f"{degisim:+.2f}%"
                if abs(degisim) > 30.0:
                    anomali_aylar.append((donem_str, degisim))

            onceki_toplam = toplam
            print(f"  {donem_str:<10}  {tp:>12,.0f}  {yp:>12,.0f}  {toplam:>15,.0f}  {degisim_str:>12}")

        except Exception as exc:
            parse_hatalari.append((donem_str, str(exc)))
            is_valid = False

    if parse_hatalari:
        print()
        print(f"[HATA] PARSE / DOSYA HATALARI ({len(parse_hatalari)} adet):")
        for donem, err in parse_hatalari:
            print(f"  {donem}: {err}")

    if anomali_aylar:
        print()
        print(f"[UYARI] AYDAN AYA >%30 DEGISIM BULUNAN AYLAR ({len(anomali_aylar)} adet):")
        for donem, d in anomali_aylar:
            print(f"  {donem}: {d:+.2f}%")

    print()
    print("=" * 65)
    print("SONUC RAPORU")
    print("=" * 65)
    if is_valid and not okuma_hatalari and not parse_hatalari and len(tablo4_sektor_tl) == len(beklenen_aylar):
        print(f"[BASARILI] Tum {len(tablo4_sektor_tl)} donem eksiksiz, tekillestirilmis ve dinamik sema ile dogrulandi.")
        return 0
    else:
        print("[HATA] DENETIM BASARISIZ: Veri setinde eksiklik, bozuk makbuz veya dosya tutarsizligi saptandi.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
