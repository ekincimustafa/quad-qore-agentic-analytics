# TÜFE HTML raporu ve offline CLI

`app/tools/inflation_report.py`, mevcut `InflationEvidence` ve
`build_inflation_chart` çıktısını tek dosyalık, internetsiz açılan bir HTML
raporuna dönüştürür. Grafik, tablo, dönem ve ilk-son özeti aynı evidence'dan
gelir; hesaplar yeniden yazılmaz. Plotly.js HTML'e gömülüdür; CDN, sunucu,
model anahtarı veya yeni paket gerekmez. Rapor dar ekranlarda da sayfa taşmadan
açılır; geniş tablo kendi içinde yatay kaydırılır.

Aylık değişim önceki takvim ayına, yıllık değişim önceki yılın aynı ayına göre
gösterilir. İlk-son endeks değişimi yıllık enflasyon değildir. Eksik geçmiş
`—` olarak kalır ve nedeni açıklanır; tek ay seçiminde ilk-son değerinin `%0`
olması o ayın aylık enflasyonunun sıfır olduğu anlamına gelmez.

## Sentetik varsayılan

```powershell
.\.venv\Scripts\python.exe -m scripts.render_inflation_report
```

Varsayılan çıktı `out/inflation-report/synthetic-2023.html` olur. Komut yalnız
2019-01–2023-12 arası yapay endekslerden 2023 Ocak–Aralık evidence'ı üretir;
ağ, EVDS, LLM veya anahtar kullanmaz. Rapor `SENTETİK DEMO` etiketi taşır.

Farklı dönem veya çıktı:

```powershell
.\.venv\Scripts\python.exe -m scripts.render_inflation_report `
  --start-period 2023-01 --end-period 2023-06 `
  --output out/inflation-report/synthetic-2023-ilk-yari.html
```

## Doğrulanmış yerel EVDS paketi

`--manifest` verildiğinde mevcut `load_and_validate_manifest` fiziksel
raw/receipt/Silver boyut ve SHA-256 kontrollerini çalıştırır. CSV, doğrulamadan
sonra yeniden okunur; okunan baytlar manifest hash'iyle eşleşmezse rapor
üretilmez. BDDK dosyası gerekmez. Varsayılan olarak 2023-01–2023-12 seçilir.

```powershell
.\.venv\Scripts\python.exe -m scripts.render_inflation_report `
  --root out/housing-acceptance-20261018/inputs `
  --manifest out/housing-acceptance-20261018/inputs/data/silver/evds/monthly/manifest.json `
  --start-period 2023-01 --end-period 2023-12
```

Çıktı `out/inflation-report/evds-2023-01-2023-12.html` olur. Rapor
`YEREL DOĞRULANMIŞ EVDS PAKETİ` etiketi taşır; HTML tek başına kaynak
gerçekliğini kanıtlamaz. 2023 için beklenen örnek: 12 ay, ilk-son endeks
değişimi **%54,5003**, Aralık yıllık TÜFE **%64,7729**. Bu değerler koda
sabitlenmemiştir.

## Girdi ve çıktı koruması

- Çıktı hedefi manifest, Silver CSV, Bronze raw/receipt veya bunların bulunduğu
  dizinle çakışırsa komut reddeder; mevcut girdiler değişmez.
- Rapor önce geçici dosyaya yazılır, tamamlanınca hedefe taşınır. Yazma veya
  taşıma başarısızsa önceki çıktı korunur.
- Sentetik ve doğrulanmış yerel etiketler karıştırılmaz; rapor yeni veri
  indirmez ve hash düzeltmez.
- Kaynak, yöntem, sınırlama ve evidence JSON metinleri HTML'e escape edilerek
  yerleştirilir; Plotly.js verisi gömülü JSON olarak yüklenir.

## Kontroller

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_inflation_report.py tests/test_inflation_chart.py -q
```

Odaklı testler grafik/tablo/evidence eşitliğini, null ve tek ay davranışını,
güvenli dinamik metni, manifest sonrası CSV değişimini, çakışan çıktıyı ve
başarısız yazmada önceki çıktının korunmasını kapsar. Gerçek rapor `out/`
altında kalır ve Git'e eklenmez.
