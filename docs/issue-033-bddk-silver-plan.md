# Quad-Qore: BDDK Silver Katmanı Dönüşümü Detaylı Uygulama ve Doğrulama Planı (Issue #33)

**İlgili Görev:** [ekincimustafa/quad-qore-agentic-analytics#33](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/33)
**Sorumlu:** Osman (BDDK Veri Mühendisliği & Lakehouse Silver Hattı)
**Tarih:** 2026-09-16

---

## 1. Proje Mimarisi ve Konsept Özeti: "Harness-First" Yaklaşımı

Quad-Qore Agentic Analytics projesinde **"Harness-First" (Kanıt Odaklı)** bir mimari uygulanır. Temel ilke şudur:
> **Yapay Zeka (MIA LLM) asla ham veriler üzerinde serbest matematik hesabı yapmaz, ham web sayfalarını kafasına göre yorumlamaz ve veri uydurmaz (hallucination engeli).**

Bunun yerine deterministik (kuralları katı, test edilmiş, matematiksel olarak doğrulanmış) veri boru hatları inşa edilir:
1. **Bronze Katmanı (Ham Veri & Makbuzlar):**
   - Kaynaklardan (BDDK, EVDS) gelen verinin orijinal hâlidir (JSON / HTML).
   - Her veri dosyası ile birlikte bir `receipt` (makbuz) tutulur: `request_key`, `parameters`, `size_bytes`, `sha256`, `downloaded_at`.
   - Bronze verisi değiştirilemez (immutable) ve denetlenebilir (auditable) yapıdadır.
2. **Silver Katmanı (Doğrulanmış & Temizlenmiş Veri Tabloları - Bu Görevin Kapsamı):**
   - Bronze varlıklarını çalışma anında (runtime) sıkı güvenlik ve bütünlük kontrollerinden geçirir.
   - Mükerrer/yenilenmiş (refresh) indirmeleri tekilleştirir.
   - Veriyi standart kolonlara, tiplere ve şemaya (Parquet) dönüştürür.
   - Fail-closed doğrulayıcı ile eksik ay, sıfır/negatif değer, bozuk hash veya şema sapmalarını kesinlikle reddeder.
3. **Gold Katmanı (Analitik ve İş Mantığı Tabloları):**
   - BDDK konut kredisi verisi ile EVDS makro göstergelerini (TÜFE/CPI, Konut Fiyat Endeksi/KFE, Konut Kredi Faizi) birleştirir.
   - Enflasyondan arındırılmış reel kredi hacmini ve aylık değişimleri hesaplar.
   - Demo hipotezi olan `rate_down_real_credit_not_up` (faiz düştüğü halde reel kredinin artmadığı dönemler) mantığını işletir.
4. **Evidence Engine & MIA LLM:**
   - Gold tablodan üretilen deterministik özet "Evidence Package" (Kanıt Paketi) olarak MIA LLM'e verilir. LLM yalnızca bu kanıtları referans vererek nihai analist raporunu üretir.

---

## 2. Görev Kapsamı ve Veri Kaynağı Analizi (Issue #33)

### 2.1. Amaç ve Hat İzolasyonu
- Osman tarafından tamamlanan BDDK indirme ve Bronze denetim altyapısının doğal devamı olarak, ilk demo senaryosunda kullanılacak aylık konut kredisi **Silver** veri setini üretmek.
- **İzolasyon Kuralı:** Afra’nın geliştirdiği EVDS hattıyla çakışmaması için BDDK Silver uygulaması tamamen bağımsız bir modülde (`app/lakehouse/bddk_silver.py`) geliştirilecektir.

### 2.2. Veri Kaynağı ve Filtre Parametreleri
- **Kaynak Bülten:** BDDK Aylık Bankacılık Bülteni
- **Tablo Numarası:** `4` (Tüketici Kredileri)
- **Taraf:** `10001` (Sektör - Yurtiçi Yerleşikler)
- **Para Birimi:** `TL`
- **Hedef Gösterge:** `Tüketici Kredileri - Konut`
- **Kullanılacak Metrik:** `toplam` (Total konut kredisi)
- **Neden 'toplam'?:** Tüketici kredileri tablosunda TP (Türk Parası) ve YP (Yabancı Para) ayrımı yer alır; ancak tüketici konut kredilerinde mevzuat gereği hanehalkına döviz kredisi kısıtlandığından ana risk büyüklüğünü ve toplam kredi hacmini temsil eden `toplam` sütunudur.

### 2.3. Dönem Kapsamı ve 2026-07 Özel Durumu
- **Silver Varsayılan Kapsamı:** `2021-01` – `2026-06` (66 benzersiz ay). EVDS göstergeleriyle ortak en geniş penceredir.
- **Demo Analiz Kapsamı:** `2021-01` – `2025-12` (60 benzersiz ay). İlk aşama demo doğrulaması bu 5 yıllık pencereye kilitlenir.
- **2026-07 Kuralı:** Bronze katmanında 2026-07 verisi bulunmaktadır ve korunacaktır; ancak EVDS serileri ile ortak varsayılan Silver kapsamına (2021-01 .. 2026-06) dahil **edilmeyecektir**. CLI argümanı ile istenirse harici aralık seçilebilir.

---

## 3. Mimari Bileşenler ve Teknik Yapılacaklar

### 3.1. Modül Tasarımı: `app/lakehouse/bddk_silver.py`
Bu modül tek başına Silver dönüşümünün ve doğrulamalarının kalbidir:
1. **Bronze Tarama ve Yükleme:**
   - `data/bronze/bddk/aylik/receipts` altındaki makbuz dosyalarını okur.
2. **Çalışma Anı (Runtime) Bronze Bütünlük Doğrulaması:**
   - Silver üretimi, `inspect_bronze.py` betiğinin önceden çalıştırıldığını **varsaymaz**.
   - Her Bronze varlığı için aşağıdaki kontrolleri çalışma anında yeniden gerçekleştirir:
     1. Makbuz JSON kökü geçerli bir `dict` olmalıdır.
     2. `request_key` dolu bir `str` olmalıdır.
     3. `parameters` alanı bir `dict` olmalıdır; `tabloNo == "4"`, `taraf == ["10001"]`, `paraBirimi == "TL"` parametrelerini doğrulamalıdır.
     4. `yil` (2021..2030) ve `ay` (1..12) gerçek bir takvim ayı oluşturmalıdır (`datetime.date(yil, ay, 1)` ile doğrulanır).
     5. `path` güvenli yol çözümlemesinden geçmeli, dizin dışına çıkmamalı (path traversal koruması).
     6. Ham JSON dosyası diskte fiziksel olarak mevcut olmalıdır.
     7. `size_bytes` pozitif bir tam sayı olmalı ve diskteki dosyanın gerçek boyutuyla (`stat().st_size`) bitine kadar eşleşmelidir.
     8. `sha256` 64 karakterli geçerli bir hex dize olmalı ve diskteki dosyanın hesaplanan SHA-256 hash'iyle eşleşmelidir.
     9. Ham dosya JSON olarak başarıyla ayrıştırılabilmelidir.
     10. `extract_housing_loan_data()` ile `Tüketici Kredileri - Konut` satırı tam olarak 1 kez bulunmalıdır.
     11. Ayrıştırılan `tp`, `yp` ve `toplam` değerleri sayısal, sonlu (`math.isfinite`) ve toplam tutar pozitif (> 0) olmalıdır.
   - **Fail-Closed İlkesi:** Eksik, bozuk veya doğrulanamayan tek bir ay bile sessizce atlanamaz (`skip` yapılamaz); süreç anında hata fırlatmalıdır (`SilverDataError` / `ValueError`).
3. **İdempotent Tekilleştirme (Deduplication):**
   - Aynı `request_key` veya aynı dönem (`yil`, `ay`) için birden fazla makbuz (refresh veya tekrar indirme) varsa, ISO-8601 zaman damgası `downloaded_at` en güncel olan geçerli kayıt seçilir.
4. **Resmî Veri Birimi Doğrulaması (housing_loan_unit):**
   - Ham JSON içerisindeki `caption` alanından veya tablo üstbilgisinden birim doğrulanır: `Tüketici Kredileri (milyon TL)`.
   - Birim asla tahmin edilmez; açıkça `"Milyon TL"` (veya `"milyon TL"`) olarak kaydedilir ve belgelenir.
   - Herhangi bir katsayı dönüşümü yapılırsa (örn. TL'ye çevrim), dönüşüm katsayısı açıkça belgelenmeli ve test edilmelidir.
5. **Silver Çıktı Sözleşmesi (Schema Contract):**
   Çıktı en az şu 5 zorunlu kolonu içerecektir:
   - `period`: `YYYY-MM` formatında string (örn: `"2021-01"`), kronolojik sırada.
   - `housing_loan_amount`: BDDK `toplam` değeri (float, sonlu, strictly > 0).
   - `housing_loan_unit`: `"Milyon TL"` (tüm satırlarda tutarlı).
   - `bddk_source_ref`: İlgili BDDK kaynağını/Bronze varlığını tanımlayan referans (örn: makbuz yolu veya request_key).
   - `data_quality_note`: Uygulanan kalite kontrolünün kısa özeti (örn: `"verified:sha256,size,finite"`).
   - *(Gold Uyumluluk Kolonu)*: Mevcut Gold hesaplayıcının doğrudan tüketebilmesi için `nominal_housing_loan_mn_try` kolonu da (housing_loan_amount değerine eşit olarak) tabloya eklenir veya eşlenir.

---

### 3.2. Bağımsız Silver Doğrulayıcısı: `validate_bddk_monthly_silver()`
Dönüştürülen veri seti (DataFrame veya dict listesi), diske yazılmadan önce bağımsız bir doğrulayıcıdan geçirilir:
```python
def validate_bddk_monthly_silver(
    data: pd.DataFrame,
    start_period: str = "2021-01",
    end_period: str = "2026-06",
) -> pd.DataFrame: ...
```
**Fail-Closed Kontrol Kuralları:**
- Zorunlu kolonların (`period`, `housing_loan_amount`, `housing_loan_unit`, `bddk_source_ref`, `data_quality_note`) varlığı.
- `start_period > end_period` durumunun reddedilmesi.
- `period` kolonunun katı `YYYY-MM` formatı ve takvim ayı kontrolü.
- Belirtilen `[start_period, end_period]` aralığında **eksik ay (gap)** bulunmasının reddedilmesi.
- Belirtilen aralık dışında **beklenmeyen/fazladan ay** bulunmasının reddedilmesi.
- Tabloda **mükerrer dönem** (duplicate period) bulunmasının reddedilmesi.
- `housing_loan_amount` kolonunda `NaN`, `None`, `Inf`, `-Inf`, sıfır (`0`) veya negatif (`< 0`) değerlerin reddedilmesi (değerler kesinlikle pozitif ve sonlu olmalıdır).
- `housing_loan_unit` kolonunun boş olması veya satırlar arasında tutarsız birimler içermesinin reddedilmesi.
- `bddk_source_ref` alanlarının boş veya geçersiz olmasının reddedilmesi.

---

### 3.3. CLI Betiği: `scripts/build_bddk_silver.py`
Tek bir komutla uçtan uca Silver çıktısını üreten komut satırı arayüzü:
- **Kullanım:**
  ```powershell
  python -m scripts.build_bddk_silver [--start-period YYYY-MM] [--end-period YYYY-MM] [--output PATH]
  ```
- **Varsayılan Parametreler:**
  - `--start-period`: `2021-01`
  - `--end-period`: `2026-06` (66 ay)
  - `--output`: `data/silver/bddk/housing_loans.parquet`
- **Demo Modu Kolaylığı:**
  - `--demo` bayrağı veya `--start-period 2021-01 --end-period 2025-12` (60 ay).
- **Raporlama ve Çıkış:**
  - Standart çıktıya: Üretilen dosya yolu, satır sayısı, dönem kapsamı ve üretilen Parquet dosyasının SHA-256 hash'i yazdırılır.
  - Hata durumunda stderr'e açıklayıcı hata mesajı yazılır ve sıfırdan farklı exit code (`1`) döner. Başarıda exit code `0` döner.

---

### 3.4. Gold Katmanı Uyumluluğu ve Sorumluluk Ayrımı
- `app/lakehouse/gold.py` içindeki `build_housing_gold_table()` fonksiyonu doğrudan test edilecek ve Silver çıktısını girdi olarak alacaktır.
- **Kural:** Gold kodu ve analiz kuralları bu görev kapsamında kesinlikle **değiştirilmeyecektir**.
- Eğer Silver çıktısı ile Gold arasında bir şema beklentisi farkı oluşursa (örneğin kolon adı `housing_loan_amount` vs `nominal_housing_loan_mn_try`), Silver tablosuna Gold'un beklediği kolon da eşlenerek tam uyumluluk sağlanacak ve bu durum dokümante edilecektir.
- **Sorumluluk Ayrımı:**
  - **Silver Sorumluluğu:** BDDK'dan gelen ham konut kredisi verisini doğrulamak, temizlemek, tekilleştirmek, birimini teyit etmek ve Parquet olarak sunmak.
  - **Gold Sorumluluğu:** Aylık nominal değişim yüzdesi, TÜFE ile reel tutara indirgeme, reel değişim yüzdesi, faiz farkı (`diff`) ve `rate_down_real_credit_not_up` hesaplamalarını yürütmek.

---

## 4. Test Stratejisi ve Test Matrisi (`tests/test_bddk_silver.py`)

Testler **asla dış ağa (BDDK sunucularına) veya diske sabitlenmiş büyük dosyalara bağımlı olmayacak**, izole `pytest` fixture'ları ve `tempfile` mock verileri ile saniyeler içinde koşacaktır.

### 4.1. Kapsanacak Test Senaryoları Matrisi

| # | Test Senaryosu | Beklenen Davranış / Assert |
|---|---|---|
| 1 | **66 Aylık Tam Kapsam (Happy Path)** | `2021-01`..`2026-06` sentetik Bronze verisinden 66 satırlık Silver Parquet başarıyla üretilmeli. |
| 2 | **60 Aylık Demo Kapsamı** | `2021-01`..`2025-12` parametresiyle çağrıldığında tam 60 satır üretilmeli ve doğrulanmalı. |
| 3 | **2026-07 İzolasyonu** | Bronze'da 2026-07 verisi olsa bile varsayılan 66 aylık kapsamda yer almamalı. |
| 4 | **Eksik Ay (Gap in periods)** | Bir ay eksik olduğunda doğrulayıcı `SilverDataError` fırlatmalı, sessizce geçmemeli. |
| 5 | **Beklenmeyen / Fazladan Ay** | İstenen aralık dışında (örn: 2020-12 veya 2026-08) veri geldiğinde reddedilmeli. |
| 6 | **Mükerrer Ay (Duplicate period)** | Nihai veride aynı aya ait birden fazla satır bulunursa reddedilmeli. |
| 7 | **Geçersiz Yıl veya Ay** | `ay = 13` veya `yil = 1800` gibi geçersiz değerlerde hata verilmeli. |
| 8 | **start_period > end_period** | Ters tarih aralığı verildiğinde doğrulayıcı anında hata fırlatmalı. |
| 9 | **Bozuk veya Kökü Dict Olmayan Makbuz** | Makbuz JSON listesi veya string olduğunda hata fırlatmalı. |
| 10 | **Eksik veya Boş request_key** | `request_key` alanı eksik veya boşluklardan oluşuyorsa reddedilmeli. |
| 11 | **Geçersiz parameters Alanı** | `parameters` alanı dict değilse veya Tablo 4 dışı bir tabloysa reddedilmeli. |
| 12 | **Güvensiz Dosya Yolu (Path Traversal)** | `path = "../../etc/passwd"` veya `C:\Windows` içerdiğinde güvenli çözücü reddetmeli. |
| 13 | **Fiziksel Dosya Yokluğu** | Makbuzda adı geçen raw JSON diskte yoksa fail-closed durmalı. |
| 14 | **Boyut Uyuşmazlığı (`size_bytes`)** | Makbuzdaki `size_bytes` diskteki dosya boyutuyla uyuşmuyorsa hata fırlatmalı. |
| 15 | **SHA-256 Hash Uyuşmazlığı** | Dosya içeriği değiştirilmişse hash kontrolü yakalamalı ve hata fırlatmalı. |
| 16 | **Bozuk Ham JSON İçeriği** | Ham dosya geçerli bir JSON değilse ayrıştırma aşamasında yakalanmalı. |
| 17 | **Konut Kredisi Satırı Bulunamaması** | Ham veride `"Tüketici Kredileri - Konut"` satırı yoksa hata fırlatmalı. |
| 18 | **Birden Fazla Gösterge Satırı** | Aynı gösterge birden fazla satırda çıkarsa (ambiguity) hata fırlatmalı. |
| 19 | **Sayısal Olmayan / NaN / Inf Değerler** | `toplam = float("nan")` veya `float("inf")` olduğunda fail-closed reddedilmeli. |
| 20 | **Sıfır veya Negatif Tutar** | `toplam <= 0` olduğunda kredi büyüklüğü kuralı gereği reddedilmeli. |
| 21 | **Boş veya Tutarsız Birim** | `housing_loan_unit` boş string veya farklı satırlarda farklıysa reddedilmeli. |
| 22 | **Boş bddk_source_ref** | Kaynak referansı boş bırakılmışsa reddedilmeli. |
| 23 | **Refresh Makbuzlarının Tekilleştirilmesi** | Aynı ay için eski ve yeni iki makbuz varsa, en son `downloaded_at` olan seçilmeli. |
| 24 | **Gold Builder Entegrasyonu** | Üretilen Silver DataFrame'i `build_housing_gold_table()` fonksiyonuna verildiğinde hatasız çalışmalı. |
| 25 | **CLI Başarı ve Hata Kodları** | Komut satırı başarılı koşuda exit code `0`, bozuk veride exit code `1` döndürmeli. |

---

## 5. Dokümantasyon Planı (`docs/bddk-silver.md`)

Mevcut `docs/bddk-ingestion.md` dosyasını tamamlayacak şekilde yeni bir `docs/bddk-silver.md` dokümanı hazırlanacaktır:
1. **Veri Kaynağı Tanımı:** BDDK Tablo 4, Sektör (10001), TL para birimi, Tüketici Kredileri - Konut kalemi.
2. **Metrik Tercihi:** Neden `toplam` sütunu seçildiğinin finansal ve yasal gerekçesi.
3. **Birim Doğrulaması:** Resmî bülten caption'ında yer alan `"Milyon TL"` biriminin kaynağı.
4. **CLI Kullanım Rehberi:** `python -m scripts.build_bddk_silver` komutu ve argümanları.
5. **Şema Sözleşmesi:** Sütun adları, veri tipleri ve null kuralları.
6. **Kapsam Açıklaması:** 66 aylık varsayılan kapsam (2021-01 .. 2026-06) ile 60 aylık demo kapsamı (2021-01 .. 2025-12) arasındaki fark.
7. **Sorumluluk Matrisi:** Bronze, Silver ve Gold katmanlarının net sınırları.

---

## 6. Kapsam Dışı Konular (Out of Scope)
- `app/connectors/bddk.py` içindeki mevcut connector ve indirme mantığının değiştirilmesi veya yeniden yazılması.
- EVDS connector veya EVDS Silver kodlarına müdahale edilmesi (Afra'nın sorumluluğundadır).
- `app/lakehouse/gold.py` içindeki analiz kurallarının veya matematik formüllerinin değiştirilmesi.
- MIA LLM anlatım (narrator/prompt) katmanı.
- Web API endpoint'leri veya kullanıcı arayüzü bileşenleri.
- Ham veri dosyalarının (JSON/HTML/Parquet) Git repoya commit edilmesi (`.gitignore` ile korunacaktır).

---

## 7. Dinamik Takip Listesi (Checklist)

- [ ] **Aşama 1: Kapsam ve Mimari Onayı**
  - [x] Detaylı görev analizi ve mimari plan hazırlandı (`docs/issue-033-bddk-silver-plan.md`).
  - [ ] Kullanıcıdan onay alındı.
- [ ] **Aşama 2: Silver Dönüşüm Modülü (`app/lakehouse/bddk_silver.py`)**
  - [ ] `SilverDataError` özel hata sınıfının tanımlanması.
  - [ ] Güvenli yol çözümleyici (`resolve_secure_raw_path`) entegrasyonu.
  - [ ] Çalışma anı Bronze makbuz ve ham dosya bütünlük denetleyicisi (SHA256, size, JSON kontrolü).
  - [ ] `downloaded_at` tabanlı tekilleştirme mekanizması.
  - [ ] `extract_housing_loan_data` ile 'toplam' metrik çıkarımı ve sonlu pozitiflik kontrolü.
  - [ ] `validate_bddk_monthly_silver` bağımsız doğrulama fonksiyonu.
  - [ ] Parquet ve DataFrame üretim fonksiyonları (`build_bddk_monthly_silver_table`).
- [ ] **Aşama 3: CLI Betiği (`scripts/build_bddk_silver.py`)**
  - [ ] `argparse` ile `--start-period`, `--end-period`, `--output`, `--demo` parametrelerinin tanımlanması.
  - [ ] Çalıştırma çıktısı olarak yol, satır sayısı, kapsam ve Parquet SHA-256 hash raporlaması.
  - [ ] Başarıda 0, hata durumunda 1 exit code yönetimi.
- [ ] **Aşama 4: Kapsamlı Test Paketi (`tests/test_bddk_silver.py`)**
  - [ ] Mock verilerle Happy Path (66 ay ve 60 ay) testleri.
  - [ ] 20'den fazla negatif test (Eksik ay, mükerrer ay, SHA uyumsuzluğu, boyut uyumsuzluğu, NaN, negatif tutar, vb.).
  - [ ] CLI exit code testleri (`runner` / `subprocess` / `main`).
  - [ ] `build_housing_gold_table` entegrasyon testi.
- [ ] **Aşama 5: Dokümantasyon ve Doğrulama**
  - [ ] `docs/bddk-silver.md` dokümanının yazılması.
  - [ ] `pytest` ile tüm test paketinin (117+ test) yeşil koştuğunun teyidi.
  - [ ] `git diff --check` ve `.gitignore` kontrolleri.
