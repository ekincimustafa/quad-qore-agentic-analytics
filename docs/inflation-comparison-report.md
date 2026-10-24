# İki tam yıl TÜFE karşılaştırması — grafik, offline HTML ve sentetik örnek

Takip: [Issue #110](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/110).

## Amaç ve sözleşme

Bu sunum katmanı, `app/services/inflation_comparison.py` içindeki
`InflationComparison` nesnesini **yeniden hesaplamadan** görselleştirir.
`compare_inflation_years` ve onun kullandığı `build_inflation_evidence`,
aylık/yıllık oranların ve iki yıl arasındaki Aralık yıllık enflasyon farkının
tek hesap kaynağıdır. Grafik ve HTML renderer'ı veri indirmez, model çağırmaz,
API'ye veya mevcut soru ekranına bağlanmaz.

- `app/tools/inflation_comparison_chart.py`:
  `build_inflation_comparison_chart(comparison: InflationComparison) -> dict`
  altı trace'li, JSON-güvenli Plotly spec üretir. Üç panelde sırasıyla
  **TÜFE endeksi (2025=100)**, **aylık değişim (%)**, **önceki yılın aynı ayına
  göre yıllık değişim (%)** yer alır. İki yılın 12 ayı ortak Ocak–Aralık
  eksenindedir; gerçek `YYYY-MM` bilgisi hover ve `customdata` içindedir.
- `app/tools/inflation_comparison_report.py`:
  `render_inflation_comparison_report(comparison, *, dataset_kind, title=...) -> str`
  bağımsız bir HTML döndürür. Plotly.js dosyanın içine gömülüdür; CDN veya
  sunucu gerekmez. Her yılın 12 satırlık tablosu, ilk–son endeks değişimi,
  Aralık yıllık enflasyonu, iki yılın Aralık oranları farkı (**yüzde puan**),
  kaynak, yöntem ve limitations aynı evidence'dan aktarılır.

**Sıra önemlidir.** `comparison.years` kullanıcı sırasındadır; 2024 → 2023
isteğinde sıralama değiştirilmez ve yüzde puan farkı *ikinci eksi birinci*
olarak alınır. İlk–son endeks değişimi Aralık yıllık oranı değildir.
Eksik geçmişte aylık/yıllık oran ve uygun olduğunda Aralık oranları farkı
`null` kalır; tabloda `—`, grafikte boşluk görünür. Önceki yıl geçmişi
uydurulmaz, sıfırla doldurulmaz.

## Anahtarsız sentetik HTML örneği

Proje kökünde mevcut Python 3.12 ve kurulu bağımlılıklarla:

```bash
python -m scripts.render_inflation_comparison_sample --first-year 2023 --second-year 2024 --output out/inflation-comparison/sample.html
```

Ardından `out/inflation-comparison/sample.html` dosyasını tarayıcıda normal bir
HTML dosyası olarak açın. Dosya internetsiz çalışır ve başlığında **SENTETİK
DEMO** yazar. Örnek `docs/economic-question-comparison-example.json` dosyasındaki
2022-12–2024-12 yapay veriyi **yalnız okur**; fixture'ı değiştirmez.

Ters yıl sırasını ayrı bir dosyada üretmek için:

```bash
python -m scripts.render_inflation_comparison_sample --first-year 2024 --second-year 2023 --output out/inflation-comparison/reversed.html
```

Yalnızca depo içindeki `out/` dizininde `.html` çıktısına izin verilir.
Mevcut çıktının üzerine **sessizce yazılmaz**: aynı yolu yeniden kullanmak için
`--overwrite` bayrağını açıkça belirtin. CLI HTML'yi önce aynı klasörde geçici
bir dosyaya tam yazar, ardından atomik olarak yayımlar; başarısız yazım
eski raporu bozmaz. Sembolik bağlantı üzerinden repo dışına yazılamaz.
2023/2024 dışındaki yıllar bu sınırlı fixture'da tam karşılanmadığından
ve aynı yıl kıyaslanamadığından güvenli hata verir.

## Kaynak, güvenlik ve doğrulama sınırları

Renderer'ın `dataset_kind="synthetic"` etiketi örneği gerçek EVDS bulgusu
olmaktan ayırır. `dataset_kind="verified_local"` yalnız **çağıran tarafın
bildirdiği** veri türünü ifade eder; HTML renderer'ı hiçbir fiziksel
manifest/raw/receipt/CSV hash zincirini kontrol etmez. Kaynak referansları,
yöntem ve sınırlamalar mevcut evidence içinden güvenli HTML-escape ile
aktarılır; kullanıcı/kaynak metni ham HTML olarak çalıştırılmaz. Grafikte
bilgi kaynaklı gerçek gözlem ekleme, interpolasyon veya yeni hesap yoktur.

```bash
python -m pytest -q tests/test_inflation_comparison_chart.py tests/test_inflation_comparison_report.py tests/test_render_inflation_comparison_sample.py
```

Testler altı trace'i, yıl sırasını, 24 satırı, tam hassasiyetli değerleri,
`null` boşluklarını, hatalı evidence reddini, escape'leri, çıktı yollarını,
atomik korumayı ve sentetik fixture değişmezliğini denetler. Bunlar offline
kod testleridir; gerçek kullanıcı/model/EVDS kabulü değildir.

Görev sonunda yalnız final kodda bir kez `python -m scripts.verify_project`
çalıştırılır ve son PR head'inin zorunlu CI'si ayrıca kontrol edilir.
Grafiklerin masaüstü/dar ekran görsel incelemesi yapılmadıysa bu eksiklik
açıkça raporlanır; mevcut masaüstü Chrome kendiliğinden açılmaz.
