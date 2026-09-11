"""
Bronze BDDK Aylik Veri Kalite ve Tutarlilik Denetimi.

Calistir: python -m scripts.bddk.inspect_bronze
Gereksinimler: Yalnizca Python standart kutuphanesi.

Exit Code:
  0: Tum kontroller basarili, beklenen aylar eksiksiz ve semaya uygun.
  1: Eksik ay, sema degisimi, dosya okuma hatasi veya dogrulama basarisizligi.
"""
import json
import sys
from pathlib import Path


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


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    receipts_dir = Path("data/bronze/bddk/aylik/receipts")
    raw_dir = Path("data/bronze/bddk/aylik/raw")

    print("=" * 65)
    print("BDDK BRONZE AYLIK VERI KALITE DENETIMI")
    print("=" * 65)

    if not receipts_dir.is_dir():
        print(f"[HATA] Makbuz klasoru bulunamadi: {receipts_dir}")
        return 1

    receipt_files = sorted(receipts_dir.glob("*.json"))
    if not receipt_files:
        print(f"[HATA] {receipts_dir} altinda makbuz (.json) dosyasi yok.")
        return 1

    all_receipts = []
    okuma_hatalari = []
    for r in receipt_files:
        try:
            data = json.loads(r.read_text("utf-8"))
            all_receipts.append(data)
        except Exception as exc:
            okuma_hatalari.append((r.name, str(exc)))

    if okuma_hatalari:
        print(f"[UYARI] {len(okuma_hatalari)} makbuz okunamadi!")
        for name, err in okuma_hatalari:
            print(f"  {name}: {err}")

    # Tablo bazli makbuz dagilimi
    tablo_sayac: dict[str, int] = {}
    for r in all_receipts:
        params = r.get("parameters") or {}
        tablo_no = str(params.get("tabloNo", "(katalog/GET)")) if params else "(katalog/GET)"
        tablo_sayac[tablo_no] = tablo_sayac.get(tablo_no, 0) + 1

    print(f"Toplam Makbuz Sayisi : {len(all_receipts)}")
    print("Tablo Dagilimi       :")
    for k, v in sorted(tablo_sayac.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        print(f"  Tablo {k:>15}: {v:>4} makbuz")

    # -----------------------------------------------------------------------
    # Demo Serisi: Tablo 4, Sektor (10001), TL
    # -----------------------------------------------------------------------
    tablo4_sektor_tl = []
    for r in all_receipts:
        p = r.get("parameters") or {}
        if not p:
            continue
        if (str(p.get("tabloNo")) == "4"
                and p.get("taraf") == ["10001"]
                and p.get("paraBirimi") == "TL"):
            tablo4_sektor_tl.append(r)

    tablo4_sektor_tl.sort(key=lambda x: (x["parameters"]["yil"], x["parameters"]["ay"]))

    beklenen_aylar = generate_expected_months(2021, 1, 2026, 7)
    mevcut_aylar = {(r["parameters"]["yil"], r["parameters"]["ay"]) for r in tablo4_sektor_tl}
    eksik_aylar = [a for a in beklenen_aylar if a not in mevcut_aylar]

    print()
    print("=" * 65)
    print("DEMO SERISI: Tablo 4 / Sektor(10001) / TL")
    print("=" * 65)
    print(f"Beklenen Donem Sayisi (2021-01 .. 2026-07) : {len(beklenen_aylar)}")
    print(f"Mevcut Donem Sayisi                        : {len(tablo4_sektor_tl)}")

    is_valid = True

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
    # Dinamik Sema-Duyarli Veri Ayristirma (extract_housing_loan_data)
    # -----------------------------------------------------------------------
    from app.connectors.bddk import extract_housing_loan_data

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
        raw_file = Path("data/bronze/bddk") / rel_path

        if not raw_file.is_file():
            parse_hatalari.append((donem_str, f"Ham dosya bulunamadi: {raw_file}"))
            is_valid = False
            continue

        try:
            raw_payload = json.loads(raw_file.read_text("utf-8"))
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
        print(f"[HATA] PARSE HATALARI ({len(parse_hatalari)} adet):")
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
        print(f"[BASARILI] Tum {len(tablo4_sektor_tl)} donem eksiksiz, dinamik sema ile dogrulandi.")
        return 0
    else:
        print("[HATA] DENETIM BASARISIZ: Veri setinde eksiklik veya tutarsizlik saptandi.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
