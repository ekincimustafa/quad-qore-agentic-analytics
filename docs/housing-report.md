# Offline Housing HTML raporu

Rapor mevcut `HousingAnalysisRun` içindeki evidence ve Plotly grafiğini sunar.
Finansal hesaplar yeniden yapılmaz. Yeni bağımlılık eklenmez.

## Sentetik örneği çalıştırma

Python 3.12 ortamında mevcut `requirements.txt` bağımlılıklarını kurun.
Bu örnek 2021-01–2025-12 için 60 yapay gözlem oluşturur; gerçek BDDK/EVDS
verisi, manifest kontrolü veya 66→60 gerçek veri kabul kaydı değildir.
Haftalık gözlem sayıları da yapaydır. İnternet, MIA veya EVDS anahtarı gerekmez.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m scripts.render_housing_sample
Start-Process .\out\housing-sample.html
.\.venv\Scripts\python.exe -m pytest tests/test_housing_report.py -q
```

Linux:

```bash
.venv/bin/python -m scripts.render_housing_sample
.venv/bin/python -m pytest tests/test_housing_report.py -q
```

Tarayıcıda `out/housing-sample.html` dosyasını açın. Grafik kütüphanesi HTML'e
gömülüdür; CDN, harici font veya sunucu gerekmez. Tek HTML dosyası bu nedenle
birkaç MB büyüklüğündedir. Farklı çıktı yolu için `--output path/report.html`
kullanılabilir. Üretilen `out/` dosyaları Git'e eklenmez.

## Dosya tabanlı demo ile entegrasyon

PR #43'ün doğrulanmış demo sonucu için çağrı:

```python
html = render_housing_report(run, dataset_kind="local", run_summary=summary)
```

`run`, mevcut servisin `HousingAnalysisRun` sonucudur; `summary` opsiyoneldir.
Bu değişiklik PR #43'ün CLI veya manifest kodunu değiştirmez. Gerçek dosya
akışına bağlanması ve kabul kaydı #40/#39 teslimatlarından sonra tamamlanır.
`local` etiketi verinin gerçekliği veya kaynak bütünlüğü için onay değildir.

Rapor, grafik serilerinin aylık kapsamını, x/y uzunluklarını ve sonlu sayıları
kontrol eder. Eşleşen aylar ve bu aylardaki grafik değerleri evidence ile aynı
olmalıdır. Eşleşmeyen aylardaki değerlerin doğruluğu upstream analiz/veri
hattının sorumluluğundadır; evidence bu aylardaki tüm değerleri içermez.
Kaynak, kalite ve çalıştırma özeti metinleri HTML'e escape edilerek eklenir.
Özet içindeki hash'ler rapor tarafından yeniden doğrulanmaz.

## Kısa gösterim

Komutu çalıştırın → HTML'i açın → sentetik veri uyarısını gösterin → bir
eşleşen ayın faiz/reel değişimini tablo ve grafikte karşılaştırın → kaynak,
yöntem, kalite ve nedensellik sınırlamasını gösterin.

Bu PR #46'nın yalnızca rapor parçasını tamamlar; release veya gerçek veri
kabul kontrolünü tamamlamış sayılmaz.