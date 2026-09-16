# BDDK Silver Veri Katmanı

Bu belge, Quad-Qore Agentic Analytics projesindeki BDDK konut kredisi **Silver** veri katmanının üretim ve doğrulama mekanizmalarını açıklar.

## Kapsam ve Seçim Gerekçeleri

- **Hedef Gösterge:** BDDK Aylık Bülten > Tablo 4 (Tüketici Kredileri) > Sektör (10001) > TL > `Tüketici Kredileri - Konut`
- **Kullanılan Değer (`toplam`):** Tüketici kredileri tablosunda TP (Türk Parası) ve YP (Yabancı Para) ayrımı yapılsa da hanehalkına (bireylere) yönelik döviz kredisi yasal olarak kısıtlandığı için konut kredisindeki asıl büyüklüğü ifade eden metrik `toplam` sütunudur.
- **Kapsam:** 
  - **Varsayılan Silver Kapsamı:** `2021-01` ile `2026-06` (Toplam 66 ay)
  - **Demo (Analiz) Kapsamı:** `2021-01` ile `2025-12` (Toplam 60 ay)
- **2026-07 Bronze İstisnası:** Bronze katmanında 2026-07 ayına ait veri saklanmakta olup, bu veri Bronze varlıkları arasında korunur; ancak, Afra tarafından yönetilen EVDS Silver veri setiyle çakışmaması ve Gold katmanında uyumsuzluk yaratmaması için Silver ve Demo katmanlarında 2026-07 analize dahil edilmez.

## Sorumluluk Ayrımı (Silver vs Gold)

Quad-Qore "Harness-First" (Kanıt Odaklı) mimarisinde Silver ve Gold katmanları arasında kesin bir sorumluluk ayrımı vardır:

- **Silver (Bu Modül):** BDDK'dan gelen ham verileri okur, makbuz (receipt) dosyalarını doğrular (SHA-256, dosya boyutu, JSON bütünlüğü), hataları ve eksikleri **fail-closed** olarak reddeder. Resmî birimi teyit eder ve mükerrer kayıtları tekilleştirerek Parquet tablosuna döker. Silver **matematiksel işlem veya hesaplama yapmaz**.
- **Gold (`app/lakehouse/gold.py`):** Silver tablolarını EVDS makro verileriyle (Enflasyon, Faiz vs.) birleştirir. Reel tutara (2025 bazlı) indirgeme, aylık yüzde değişim hesaplama ve `rate_down_real_credit_not_up` (faiz düştüğü halde kredinin artmadığı) analiz mantıklarını işletir.

## Çıktı Şeması (Silver Contract)

Üretilen Parquet dosyasındaki (`data/silver/bddk/housing_loans.parquet`) kolonlar:

| Kolon Adı | Veri Tipi | Açıklama ve Kural |
|---|---|---|
| `period` | string | `YYYY-MM` formatında ardışık, eksiksiz takvim ayları. |
| `housing_loan_amount` | float | 'toplam' alanından alınan konut kredisi stoku. (Her zaman > 0, sonlu ve numeric) |
| `nominal_housing_loan_mn_try` | float | Gold katmanı ile doğrudan geriye dönük uyumluluk sağlamak için `housing_loan_amount`'un alias'ıdır. |
| `housing_loan_unit` | string | Resmî bültendeki başlıktan doğrulanan veri birimi. Her zaman `"Milyon TL"` şeklindedir. Tahmin yapılamaz. |
| `bddk_source_ref` | string | Analizin hangi indirilen ham makbuza dayandığını gösteren `request_key`. |
| `data_quality_note` | string | Uygulanan fail-closed kalite kontrollerinin kısa bir log kaydı. |

## CLI Kullanım Kılavuzu

Tek komutla doğrulanmış Silver çıktısı üretebilirsiniz:

```powershell
python -m scripts.build_bddk_silver
```

Bu, `2021-01`'den `2026-06`'ya kadar olan 66 aylık varsayılan hedefi okur ve Parquet olarak yazar.

**Sadece Demo Kapsamını Üretmek (2021-01 .. 2025-12):**
```powershell
python -m scripts.build_bddk_silver --demo
```

**Belirli Bir Tarih Aralığı Seçmek:**
```powershell
python -m scripts.build_bddk_silver --start-period 2023-01 --end-period 2024-12 --output path/to/custom.parquet
```

Başarılı çalışmada konsola bir `[SUCCESS]` onay mesajı ve üretilen Parquet'nin SHA-256 hash'i yazdırılır. Bronze katmanında bir veri arızası (corrupted bytes, missing month, negative amount) varsa işlem `SilverDataError` fırlatır ve komut 1 çıkış koduyla durur.
