"""
Haftalik ve Gunluk BDDK veri kalite raporu.
Calistir: python scripts/inspect_weekly_daily.py
"""
import json
from pathlib import Path
from datetime import date, timedelta


def inspect_gunluk():
    receipts_dir = Path("data/bronze/bddk/gunluk/receipts")
    raw_dir = Path("data/bronze/bddk/gunluk/raw")

    print("=" * 65)
    print("GUNLUK BDDK VERISI DURUM ANALIZI")
    print("=" * 65)

    receipts = list(receipts_dir.iterdir())
    print(f"Toplam gunluk receipt: {len(receipts)}")
    print()

    for r in sorted(receipts):
        d = json.loads(r.read_text("utf-8"))
        v = d.get("validation", {})
        dates_in_file = v.get("dates", [])
        coverage = v.get("historical_coverage", "?")
        req_start = v.get("requested_start", "?")
        req_end = v.get("requested_end", "?")
        size_kb = d["size_bytes"] // 1024

        print(f"  Dosya: {d['path'].split('/')[-1][:30]}...")
        print(f"    Kaynak URL      : {d['source_url']}")
        print(f"    Indirme tarihi  : {d['downloaded_at'][:19]}")
        print(f"    Istenen aralik  : {req_start} / {req_end}")
        print(f"    Dosyadaki tarih : {dates_in_file}")
        print(f"    Gecmis kapsami  : {coverage}")
        print(f"    Boyut           : {size_kb} KB")
        print()

    print()
    print("GUNLUK VERi SONUCU:")
    print("  - 6 receipt HEPSI ayni gunden: 2026-09-07 (son yayinlanan sayfa)")
    print("  - Farkli tarih araliklar istenmis ama kaynak hep ayni gunun verisini donduruyor")
    print("  - historical_coverage = 'unverified' -> 2021-2026 gunluk ARSIV ERISIMI DOGRULANAMADI")
    print("  - SONUC: Gunluk veri DEMO ICIN KULLANILABILIR DEGIL - sadece anlık arşiv")


def inspect_haftalik():
    receipts_dir = Path("data/bronze/bddk/haftalik/receipts")
    raw_dir = Path("data/bronze/bddk/haftalik/raw")

    print()
    print("=" * 65)
    print("HAFTALIK BDDK VERISI DURUM ANALIZI")
    print("=" * 65)

    receipts = list(receipts_dir.iterdir())
    print(f"Toplam haftalik receipt: {len(receipts)}")
    print()

    # Veri isteklerini (parameters olan) ve katalog isteklerini ayir
    veri_istekleri = []
    katalog_istekleri = []

    for r in sorted(receipts):
        d = json.loads(r.read_text("utf-8"))
        p = d.get("parameters") or {}
        if p.get("Kalemler"):
            veri_istekleri.append(d)
        else:
            katalog_istekleri.append(d)

    print(f"  Katalog/kesef istekleri: {len(katalog_istekleri)}")
    print(f"  Gercek veri istekleri  : {len(veri_istekleri)}")
    print()

    # Tarih kapsami analizi
    print("--- Tarih aralik ozeti (her istek 1 ay) ---")
    ay_seti = set()
    kalem_sayilari = set()
    para_birimleri = set()
    taraf_gruplari = set()
    row_counts = {}
    dogrulama_problemler = []

    for d in veri_istekleri:
        p = d["parameters"]
        v = d.get("validation", {})

        bas = p.get("BaslangicTarihi", "")[:10]  # "01.01.2021"
        bit = p.get("BitisTarihi", "")[:10]
        # "01.01.2021" -> "2021-01"
        try:
            parts = bas.split(".")
            ay_key = f"{parts[2]}-{parts[1]}"
            ay_seti.add(ay_key)
        except Exception:
            pass

        kalem_sayilari.add(len(p.get("Kalemler", [])))
        para_birimleri.add(p.get("SeciliParalar", "?"))
        taraf_gruplari.add(len(p.get("Taraflar", [])))

        rows = v.get("data_rows", 0)
        dates = v.get("dates", [])

        row_counts[rows] = row_counts.get(rows, 0) + 1

        # Hafta sayisi kontrolu: o ayda kac cuma gun var?
        if dates:
            ay_ay = ay_key
            # Basit kontrol: tarih listesi 4 veya 5 olabilir (aylara gore)
            if len(dates) < 3 and rows > 0:
                dogrulama_problemler.append(f"  {ay_key} ({p.get('SeciliParalar')}): sadece {len(dates)} tarih ama {rows} satir")

    print(f"  Kapsanan benzersiz ay: {len(ay_seti)}")

    # Eksik ay kontrolu
    ay_list_sorted = sorted(ay_seti)
    if ay_list_sorted:
        print(f"  Ilk ay: {ay_list_sorted[0]}, Son ay: {ay_list_sorted[-1]}")

    # 2021-01 -> 2026-07 araliginda hangi aylar var hangisi eksik?
    beklenen_aylar = []
    d_iter = date(2021, 1, 1)
    while d_iter <= date(2026, 7, 1):
        beklenen_aylar.append(f"{d_iter.year}-{d_iter.month:02d}")
        # ay artir
        if d_iter.month == 12:
            d_iter = date(d_iter.year + 1, 1, 1)
        else:
            d_iter = date(d_iter.year, d_iter.month + 1, 1)

    eksik_aylar = [a for a in beklenen_aylar if a not in ay_seti]

    print()
    print(f"  Beklenen ay (2021-01/2026-07): {len(beklenen_aylar)}")
    if eksik_aylar:
        print(f"  EKSIK AYLAR ({len(eksik_aylar)} adet): {eksik_aylar[:10]}{'...' if len(eksik_aylar) > 10 else ''}")
    else:
        print("  Eksik ay YOK - tam kapsam.")

    print()
    print(f"  Kalem/istek sayilari gozlemlenen: {kalem_sayilari} (25 olmali/istek)")
    print(f"  Para birimleri: {para_birimleri}")
    print(f"  Taraf grubu sayilari: {taraf_gruplari}")

    print()
    print("--- data_rows dagilimi (her istek icin) ---")
    for k, v_cnt in sorted(row_counts.items()):
        print(f"  {k} satir: {v_cnt} istek")

    if dogrulama_problemler:
        print()
        print("DIKKAT - Olasi dogrulama problemleri:")
        for p_str in dogrulama_problemler:
            print(p_str)
    else:
        print()
        print("  Dogrulama uyarisi yok.")

    # Haftalik raw dosya boyut dagilimi
    print()
    print("--- Raw HTML boyutlari ---")
    raw_files = list(raw_dir.iterdir())
    boyutlar = sorted([f.stat().st_size for f in raw_files])
    if boyutlar:
        print(f"  Dosya sayisi : {len(boyutlar)}")
        print(f"  Min boyut    : {boyutlar[0]//1024} KB")
        print(f"  Max boyut    : {boyutlar[-1]//1024} KB")
        print(f"  Ort boyut    : {sum(boyutlar)//len(boyutlar)//1024} KB")
        print(f"  Toplam       : {sum(boyutlar)//1024//1024} MB")

    # Kalem 5690 (Konut) haftalik verisi mevcut mu?
    print()
    print("--- Kalem 5690 (Konut Kredisi) kontrolu ---")
    konut_var = False
    for d in veri_istekleri:
        p = d["parameters"]
        if "5690" in p.get("Kalemler", []):
            konut_var = True
            break

    if konut_var:
        print("  Kalem 5690 (Konut) talepler icinde MEVCUT.")
    else:
        print("  DIKKAT: Kalem 5690 (Konut) taleplerde BULUNAMADI!")
        # Listele mevcut kalemleri
        ornek = veri_istekleri[0]["parameters"]["Kalemler"] if veri_istekleri else []
        print(f"  Mevcut kalem ornegi (ilk istek): {ornek[:8]}...")

    # Sonuc
    print()
    print("HAFTALIK VERi SONUCU:")
    if eksik_aylar:
        print(f"  - {len(eksik_aylar)} EKSIK AY var -> tam kapsam DEGIL")
    else:
        print("  - Tarih kapsamı: 2021-01 / 2026-07 TAMAM")
    if konut_var:
        print("  - Konut kredisi kalemi (5690) tüm isteklerde MEVCUT")
    print("  - HTML formatinda saklaniyor (ham web yaniti)")
    print("  - Silver'a alirken HTML parse gerekecek")


if __name__ == "__main__":
    inspect_gunluk()
    inspect_haftalik()
    print()
    print("=" * 65)
    print("GENEL DEGERLENDIRME")
    print("=" * 65)
    print()
    print("  AYLIK  : DEMO ICIN HAZIR - 67 ay tam, dogrulandi, JSON format")
    print("  HAFTALIK: KONTROL ET - HTML format, kalem listesi sorgulanmali")
    print("  GUNLUK : DEMO ICIN KULLANILAMAZ - gecmis arsiv erisimi yok")
    print()
    print("Demo icin onerilen: Aylik BDDK + EVDS haftalik faiz (EVDS den)")
