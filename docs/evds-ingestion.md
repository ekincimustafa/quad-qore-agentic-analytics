# EVDS Ingestion

Bu akış TCMB EVDS verilerini güvenli ve tekrar üretilebilir şekilde Bronze katmanına indirir ve mevcut Silver dönüşümlerini kullanarak aylık veri setini üretir.

## Kullanılan seriler

| Seri | Açıklama | Doğal frekans |
|---|---|---|
| `TP.KTF12` | Konut kredisi faiz oranı | Haftalık |
| `TP.TUKFIY2025.GENEL` | TÜFE genel endeksi, 2025=100 | Aylık |
| `TP.KFE.TR` | Türkiye Konut Fiyat Endeksi, 2023=100 | Aylık |

Canlı EVDS API yanıtında doğrulanan değer alanları:

- `TP.KTF12` -> `TP_KTF12`
- `TP.TUKFIY2025.GENEL` -> `TP_TUKFIY2025_GENEL`
- `TP.KFE.TR` -> `TP_KFE_TR`

## API anahtarı

EVDS API anahtarı yalnızca `EVDS_API_KEY` ortam değişkeninden okunur.

Gerçek anahtar kaynak koda, URL'ye, loglara, Bronze dosyalarına veya receipt dosyalarına yazılmamalı ve Git'e commit edilmemelidir.

`.env.example` yalnızca boş placeholder içerir:

`EVDS_API_KEY=`

## EVDS servisi

Kullanılan servis:

`https://evds3.tcmb.gov.tr/igmevdsms-dis`

API anahtarı HTTP `key` header'ı ile gönderilir.

## Bronze indirme

Varsayılan dönem 2021-01 ile 2026-06 arasıdır.

    python -m scripts.download_evds --start-period 2021-01 --end-period 2026-06

Ham API yanıtları değiştirilmeden mevcut `BronzeStore` ile `data/bronze/evds/` altında saklanır.

Receipt içinde seri kodu, doğal frekans, API key içermeyen source URL, request başlangıç ve bitiş tarihleri, indirme zamanı, content type, SHA-256, dosya boyutu, veri dönemi ve raw dosya yolu tutulur.

Aynı request ve aynı içerik tekrar işlendiğinde gereksiz yeni raw kopyası oluşturulmaz.

## Bronze -> Silver

    python -m scripts.build_evds_silver --start-period 2021-01 --end-period 2026-06

Script ilgili döneme ait Bronze receipt dosyalarını bulur ve raw dosyanın SHA-256 ile boyutunu doğrular.

Makbuz seçiminde `downloaded_at` timezone içeren ISO-8601 zaman olarak parse
edilir ve UTC anına göre en yenisi seçilir. Aynı UTC anındaki makbuzlarda
dosya adı leksikografik olarak en büyük olan seçilir. Eksik, bozuk veya timezone
içermeyen timestamp işlemi durdurur; string sıralamasına veya sessiz fallback'e
dönülmez. Bu seçim aylık faiz ortalaması formülünü değiştirmez.

API response yapısı `app/lakehouse/evds_adapter.py` tarafından mevcut Silver fonksiyonlarının beklediği forma çevrilir. Analitik kurallar adapter içinde yeniden uygulanmaz.

Kullanılan mevcut Silver fonksiyonları:

- `monthly_housing_loan_interest_rate`
- `monthly_cpi_index`
- `monthly_housing_price_index`
- `merge_monthly_evds_series`
- `validate_monthly_evds_data`

`TP.KTF12` Bronze katmanında haftalık tutulur. Silver katmanında haftalık gözlemlerin aritmetik ortalaması alınarak aylık faiz oranı oluşturulur.

## Silver çıktı

Varsayılan çıktı:

`data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv`

Kolonlar:

- `period`
- `housing_loan_interest_rate_pct`
- `weekly_observation_count`
- `cpi_index`
- `housing_price_index`

2021-01 ile 2026-06 arasında beklenen satır sayısı 66'dır.

Pipeline eksik ay, duplicate ay, non-numeric değer, bozuk Bronze SHA-256 veya beklenmeyen API şeması durumlarında fail-closed davranır.

## Haftalık kapsam ve manifest

CSV'nin beş kolonu korunur. Yanındaki `.coverage.json`, `schema_version`,
`silver_sha256`, `overall_status`, `calendar_verification` ve aylık `months`
kayıtlarını içerir. Gözlenen haftalık tarihler ve sayıları gerçek girdiden
alınır; her ayda dört veya beş yayın olduğu varsayılmaz.

Doğrulanmış resmî yayın takvimi bulunmadığından mevcut politika
`overall_status: "unverified"`, `calendar_verification: "not_available"`,
aylık `status: "unverified"` ve `expected_count: null` değerleridir.
`expected_dates` veya `missing_dates` üretilmez. Tek haftalık gözlem aylık
ortalama verebilir; bu durum haftalık kapsamın tam olduğunu göstermez.

Yerel Bronze ve tam Silver hazırlandıktan sonra, ağ/LLM gerektirmeden:

```bash
python -m scripts.build_evds_manifest
python -m scripts.build_evds_manifest --demo
```

Normal komut 2021-01–2026-06 Silver CSV ve kapsam raporunu seçilen Bronze
dosyalarından geçici alanda yeniden hesaplanan sonuçla karşılaştırır.
Uyuşmazlıkta yeni manifest yayımlanmaz, mevcut dosyalar korunur. `--demo`,
aynı Bronze kaynaklarından 2021-01–2025-12 CSV/raporu ve ayrı
`manifest_2021-01_2025-12.json` üretir. Ana manifest `manifest.json` olur.

Manifest üreticisi raporun Silver hash'ini doğrular ve yalnızca
`overall_status`, `calendar_verification`, `months` alanlarını
`series[TP.KTF12].weekly_coverage` altında taşır. Tüketici tam CSV dönemi
boyunca ay/tarih/sayı uyumunu doğrular. Offline demo CLI kapsamı çalıştırma
özetine, belirsizlik notunu evidence ve HTML'e aktarır; kullanım için
[Housing demo belgesine](housing-demo.md) bakınız.

Üretici/tüketici fixture testleri sentetiktir. Gerçek 66 aylık dosyaların
teslimi ve 60 aylık demo/üç örnek ay kabulü #39/#40 kapsamında ayrıca
kaydedilmelidir. Aşağıdaki eski canlı ingestion kaydı bu son kabulün yerine geçmez.

## Testler

Offline testler gerçek internet bağlantısı veya gerçek API anahtarı gerektirmez.

Canlı doğrulamada üç seri için download, Bronze kayıt, idempotency, API key sızıntısı olmaması ve 66 aylık Silver output doğrulanmıştır.
