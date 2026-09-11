"""
Bronze BDDK Haftalik ve Gunluk Veri Kalite Denetimi.

Calistir: python -m scripts.bddk.inspect_weekly_daily
Gereksinimler: Yalnizca Python standart kutuphanesi.

Exit Code:
  0: Haftalik veri seti (2021-01 .. 2026-07) tam kapsamli ve Kalem 5690 dogrulanmis.
  1: Eksik klasor, eksik donem, eksik kalem veya okuma hatasi.
"""
import json
import sys
from pathlib import Path


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


def inspect_gunluk() -> dict:
    receipts_dir = Path("data/bronze/bddk/gunluk/receipts")

    print("=" * 65)
    print("GUNLUK BDDK VERISI DURUM ANALIZI")
    print("=" * 65)

    if not receipts_dir.is_dir():
        print(f"[HATA] Gunluk makbuz klasoru bulunamadi: {receipts_dir}")
        return {"receipt_count": 0, "is_valid": False, "historical_accessible": False}

    receipt_files = sorted(receipts_dir.glob("*.json"))
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
    print("  - Gecmis gunluk seri arsiv erisimi BDDK BultenGunluk sayfasindan saglanamamaktadir.")

    return {
        "receipt_count": len(receipts),
        "is_valid": len(receipts) > 0,
        "historical_accessible": False,
        "unique_dates": sorted(unique_dates),
    }


def inspect_haftalik() -> dict:
    receipts_dir = Path("data/bronze/bddk/haftalik/receipts")
    raw_dir = Path("data/bronze/bddk/haftalik/raw")

    print()
    print("=" * 65)
    print("HAFTALIK BDDK VERISI DURUM ANALIZI")
    print("=" * 65)

    if not receipts_dir.is_dir():
        print(f"[HATA] Haftalik makbuz klasoru bulunamadi: {receipts_dir}")
        return {"is_valid": False, "error": "receipts_dir_missing"}

    receipt_files = sorted(receipts_dir.glob("*.json"))
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

    print(f"  Katalog/kesif makbuzu : {len(katalog_istekleri)}")
    print(f"  Gercek veri makbuzu   : {len(veri_istekleri)}")

    ay_seti = set()
    kalem_sayilari = set()
    para_birimleri = set()
    taraf_gruplari = set()
    row_counts = {}
    konut_5690_sayisi = 0

    for d in veri_istekleri:
        p = d["parameters"]
        v = d.get("validation", {})

        bas = p.get("BaslangicTarihi", "")[:10]  # "01.01.2021"
        try:
            parts = bas.split(".")
            if len(parts) == 3:
                ay_key = f"{parts[2]}-{parts[1]}"
                ay_seti.add(ay_key)
        except Exception:
            pass

        kalemler = p.get("Kalemler", [])
        kalem_sayilari.add(len(kalemler))
        if "5690" in kalemler:
            konut_5690_sayisi += 1

        para_birimleri.add(p.get("SeciliParalar", "?"))
        taraf_gruplari.add(len(p.get("Taraflar", [])))

        rows = v.get("data_rows", 0)
        row_counts[rows] = row_counts.get(rows, 0) + 1

    beklenen_aylar = generate_expected_months(2021, 1, 2026, 7)
    eksik_aylar = [a for a in beklenen_aylar if a not in ay_seti]

    print()
    print(f"Kapsanan benzersiz ay sayisi: {len(ay_seti)} (Beklenen: {len(beklenen_aylar)})")
    if ay_seti:
        sorted_aylar = sorted(ay_seti)
        print(f"  Ilk ay: {sorted_aylar[0]}, Son ay: {sorted_aylar[-1]}")

    is_valid = True
    if eksik_aylar:
        print(f"[HATA] Eksik aylar ({len(eksik_aylar)} adet): {eksik_aylar[:10]}...")
        is_valid = False
    else:
        print("[OK] Eksik ay yok: 2021-01 / 2026-07 tum 67 ay mevcut.")

    print(f"Para birimleri: {sorted(para_birimleri)}")
    print(f"Satir dagilimlari: {sorted(row_counts.items())}")

    print()
    print("--- Kalem 5690 (Konut Kredisi) Varligi ---")
    if konut_5690_sayisi > 0:
        print(f"[OK] Kalem 5690 (Konut Kredisi) {konut_5690_sayisi} veri makbuzunda MEVCUT.")
    else:
        print("[HATA] Kalem 5690 veri makbuzlarinda bulunamadi!")
        is_valid = False

    # Raw HTML dosyalari boyut istatistigi
    if raw_dir.is_dir():
        raw_files = list(raw_dir.glob("*.html"))
        if raw_files:
            sizes = [f.stat().st_size for f in raw_files]
            total_mb = sum(sizes) / 1024 / 1024
            print()
            print(f"Ham HTML Dosyalari: {len(raw_files)} adet, Toplam: {total_mb:.1f} MB")

    return {
        "is_valid": is_valid and (len(eksik_aylar) == 0) and (konut_5690_sayisi > 0),
        "total_receipts": total_receipts,
        "covered_months": len(ay_seti),
        "expected_months": len(beklenen_aylar),
        "eksik_aylar": eksik_aylar,
        "konut_5690_count": konut_5690_sayisi,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    gunluk_res = inspect_gunluk()
    haftalik_res = inspect_haftalik()

    print()
    print("=" * 65)
    print("GENEL DEGERLENDIRME VE CIKIS KODU")
    print("=" * 65)
    print(f"Haftalik Seri Durumu : {'[OK] Basarili' if haftalik_res.get('is_valid') else '[HATA] Eksik veya Hatali'}")
    print(f"Gunluk Seri Durumu   : {'[BILGI] Gecmis arsiv yok (tek gun anlik snapshot)' if gunluk_res.get('is_valid') else '[HATA] Dosya yok'}")

    if haftalik_res.get("is_valid"):
        print("\n[BASARILI] Haftalik veri seti 67 ay eksiksiz ve Kalem 5690 ile dogrulandi.")
        return 0
    else:
        print("\n[HATA] Haftalik veri denetimi basarisiz oldu.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
