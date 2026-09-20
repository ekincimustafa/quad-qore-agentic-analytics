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

## Testler

Offline testler gerçek internet bağlantısı veya gerçek API anahtarı gerektirmez.

Canlı doğrulamada üç seri için download, Bronze kayıt, idempotency, API key sızıntısı olmaması ve 66 aylık Silver output doğrulanmıştır.
