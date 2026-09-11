"""
Bronze BDDK veri kalite ve tutarlilik raporu.
Calistir: python scripts/inspect_bronze.py
"""
import json
from pathlib import Path


def main():
    receipts_dir = Path("data/bronze/bddk/aylik/receipts")
    raw_dir = Path("data/bronze/bddk/aylik/raw")

    # --------------------------------------------------------
    # 1. Tum receipt'lari yükle, Tablo 4 Sektor TL olanları filtrele
    # --------------------------------------------------------
    all_receipts = []
    for r in sorted(receipts_dir.iterdir()):
        try:
            data = json.loads(r.read_text("utf-8"))
            all_receipts.append(data)
        except Exception as e:
            print(f"HATA receipt okunurken: {r.name} -> {e}")

    # Frekans ve tablo dagilimi
    tablo_sayac = {}
    for r in all_receipts:
        params = r.get("parameters") or {}
        tablo_no = params.get("tabloNo", "?") if params else "(katalog/GET)"
        tablo_sayac[tablo_no] = tablo_sayac.get(tablo_no, 0) + 1

    print("=" * 60)
    print("BDDK BRONZE AYLIK - GENEL TABLO DAGILIMU")
    print("=" * 60)
    for k, v in sorted(tablo_sayac.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        print(f"  Tablo {k:>3}: {v:>4} receipt")

    # --------------------------------------------------------
    # 2. Tablo 4, Sektor (10001), TL - 67 aylik ana serimiz
    # --------------------------------------------------------
    tablo4_sektor_tl = []
    for r in all_receipts:
        p = r.get("parameters") or {}
        if not p:
            continue
        taraflar = p.get("taraf", [])
        if (p.get("tabloNo") == "4"
                and taraflar == ["10001"]
                and p.get("paraBirimi") == "TL"):
            tablo4_sektor_tl.append(r)

    tablo4_sektor_tl.sort(key=lambda x: (x["parameters"]["yil"], x["parameters"]["ay"]))

    print()
    print("=" * 60)
    print(f"DEMO SERISI: Tablo4 / Sektor(10001) / TL  => {len(tablo4_sektor_tl)} kayit")
    print("=" * 60)

    # Eksik ayları bul (2021-01 -> 2026-07)
    ay_listesi = set()
    for r in tablo4_sektor_tl:
        p = r["parameters"]
        ay_listesi.add((p["yil"], p["ay"]))

    from datetime import date
    from dateutil.relativedelta import relativedelta

    try:
        beklenen = []
        dt = date(2021, 1, 1)
        bitis = date(2026, 7, 1)
        while dt <= bitis:
            beklenen.append((dt.year, dt.month))
            dt += relativedelta(months=1)

        eksik = [a for a in beklenen if a not in ay_listesi]
        print(f"Beklenen ay sayisi (2021-01 / 2026-07): {len(beklenen)}")
        print(f"Mevcut ay sayisi: {len(tablo4_sektor_tl)}")
        if eksik:
            print(f"EKSIK AYLAR: {eksik}")
        else:
            print("Eksik ay YOK - tam kapsam.")
    except ImportError:
        print("(dateutil yuklü degil, sadece mevcut kayitlar listeleniyor)")

    # --------------------------------------------------------
    # 3. Her ayin row sayisi tutarli mi? (hepsi 41 olmali)
    # --------------------------------------------------------
    print()
    print("=" * 60)
    print("SATIR SAYISI TUTARLILIGI (hepsi 41 olmali)")
    print("=" * 60)
    row_counts = {}
    for r in tablo4_sektor_tl:
        rows = r.get("validation", {}).get("rows")
        row_counts[rows] = row_counts.get(rows, 0) + 1
    for k, v in row_counts.items():
        status = "OK" if k == 41 else "DIKKAT"
        print(f"  row={k}: {v} ay  [{status}]")

    # --------------------------------------------------------
    # 4. Donem dogrulama yontemi
    # --------------------------------------------------------
    print()
    print("=" * 60)
    print("DONEM DOGRULAMA YONTEMI (dogruluk guvencesi)")
    print("=" * 60)
    dogrulama_tipler = {}
    for r in tablo4_sektor_tl:
        tip = r.get("validation", {}).get("period_confirmation", "yok")
        dogrulama_tipler[tip] = dogrulama_tipler.get(tip, 0) + 1
    for k, v in dogrulama_tipler.items():
        gosterge = "GUCLU (kaynak response_caption ile onaylandi)" if k == "response_caption" else "ZAYIF (sadece istek parametresi)"
        print(f"  {k}: {v} ay  -> {gosterge}")

    # --------------------------------------------------------
    # 5. Ucbirinde ham deger kontrolu (konut kredisi)
    # --------------------------------------------------------
    print()
    print("=" * 60)
    print("UC DONEM HAM DEGER KONTROLU (rows[1] - Konut Kredisi)")
    print("=" * 60)
    kontrol_donemler = [(2021, 1), (2023, 7), (2026, 7)]
    for yil, ay in kontrol_donemler:
        eşles = [r for r in tablo4_sektor_tl
                 if r["parameters"]["yil"] == yil and r["parameters"]["ay"] == ay]
        if not eşles:
            print(f"  {yil}-{ay:02d}: BULUNAMADI!")
            continue
        r = eşles[0]
        raw_path = raw_dir / r["path"].replace("aylik/raw/", "")
        try:
            raw = json.loads(raw_path.read_text("utf-8"))
            rows = raw["Json"]["data"]["rows"]
            # rows[1] = "Tüketici Kredileri - Konut"
            konut_row = rows[1]["cell"]
            ad = konut_row[2]
            tp = konut_row[4]
            yp = konut_row[5]
            toplam = konut_row[6]
            caption = raw["Json"]["caption"]
            print(f"  {yil}-{ay:02d} | {ad}")
            print(f"         TP={tp:>10,.0f}  YP={yp:>10,.0f}  Toplam={toplam:>10,.0f}  mn TL")
            print(f"         Kaynak caption: '{caption}'")
        except Exception as e:
            print(f"  {yil}-{ay:02d}: RAW OKUNAMADI -> {e}")

    # --------------------------------------------------------
    # 6. Konut serisinin ham trendi (tum 67 ay)
    # --------------------------------------------------------
    print()
    print("=" * 60)
    print("67 AYLIK KONUT KREDISI BAKIYE TRENDI (mn TL)")
    print("=" * 60)
    print(f"  {'Donem':<10}  {'TP':>10}  {'YP':>8}  {'Toplam':>10}  {'Dogrulama':>18}")
    print(f"  {'-'*8:<10}  {'-'*10:>10}  {'-'*8:>8}  {'-'*10:>10}  {'-'*18:>18}")
    onceki_toplam = None
    uyari_aylar = []
    for r in tablo4_sektor_tl:
        p = r["parameters"]
        raw_path = raw_dir / r["path"].replace("aylik/raw/", "")
        dogrulama = r.get("validation", {}).get("period_confirmation", "param_only")
        try:
            raw = json.loads(raw_path.read_text("utf-8"))
            rows = raw["Json"]["data"]["rows"]
            konut_row = rows[1]["cell"]
            tp = konut_row[4]
            yp = konut_row[5]
            toplam = konut_row[6]
            # Anomali: bir onceki aydan %30'dan fazla fark var mi?
            flag = ""
            if onceki_toplam is not None:
                degisim = (toplam - onceki_toplam) / onceki_toplam * 100
                if abs(degisim) > 30:
                    flag = f"  !! ANOMALI {degisim:+.1f}%"
                    uyari_aylar.append((p["yil"], p["ay"], degisim))
            onceki_toplam = toplam
            print(f"  {p['yil']}-{p['ay']:02d}  {tp:>10,.0f}  {yp:>8,.0f}  {toplam:>10,.0f}  {dogrulama:>18}{flag}")
        except Exception as e:
            print(f"  {p['yil']}-{p['ay']:02d}: OKUNAMADI -> {e}")

    if uyari_aylar:
        print()
        print("UYARI: Bir önceki aya göre >%30 fark bulunan aylar:")
        for yil, ay, d in uyari_aylar:
            print(f"  {yil}-{ay:02d}: {d:+.1f}%")
    else:
        print()
        print("Anomali kontrolu gecti - hicbir ayda +/-30% asimi yok.")

    print()
    print("Rapor tamamlandi.")


if __name__ == "__main__":
    main()
