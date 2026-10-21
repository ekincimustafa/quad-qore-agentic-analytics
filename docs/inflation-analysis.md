# TÜFE değişim analizi

Takip: [#56](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/56).

`POST /analysis/inflation`, mevcut EVDS serisi `TP.TUKFIY2025.GENEL`
(2025=100 genel TÜFE endeksi) için aylık ve geçen yılın aynı ayına göre
değişimleri Python'da hesaplar. Yeni veri kaynağı, bağımlılık veya LLM çağrısı
eklemez. Servis: `app/services/inflation_analysis.py::build_inflation_evidence`.

Bu teslimat normalize edilmiş satırları alan hesaplama servisi ve HTTP
endpoint'idir. Konut soru endpoint'i hâlâ tek Housing analizine izin verir;
enflasyon sorusunu bu endpoint'e yönlendirme, grafik/HTML sunumu, serbest LLM
yorumu ve doğrulanmış dosya/manifest bağlantısı henüz eklenmemiştir.

İki analizli soru yönlendirmesi ayrı
[`POST /analysis/economic/question`](economic-question.md) endpoint'indedir;
mevcut Housing soru endpoint'inin tek analizli davranışını genişletmez.

## Girdi ve çıktı

İstek dört alan içerir:

- `cpi_monthly`: `period` (`YYYY-MM`) ve pozitif/sonlu sayısal `cpi_index` satırları.
- `start_period`, `end_period`: zorunlu ve veri kapsamı içinde analiz dönemi.
- `source_ref`: zorunlu kaynak referansı. Bu metin, dosya veya kaynak doğrulaması değildir.

Diğer EVDS kolonlarının gönderilmesi gerekmez. Mevcut EVDS Silver tablosundan
servise `period` ve `cpi_index` kolonları verilebilir; servis diğer kolonları
kullanmaz. HTTP satırları bu iki alanla sınırlıdır. İstekle dosya yolu, model,
anahtar, baz yıl veya narration seçeneği kabul edilmez. HTTP sayısal alanı
boolean veya sayı biçiminde string kabul etmez; CSV okuyan Python servisinde
sayısal dönüştürme yapılır. Sağlanan tüm aylar tekil ve kesintisiz olmalıdır.
Sıralanmamış girdi sıralanır, eksik ay doldurulmaz ve veri değiştirilmez.

Başarılı yanıt `status: "ok"` ve `evidence` içerir. Evidence içinde:

- Seçilen/verilen dönem kapsamı, seçilen ay sayısı ve kaynak referansı;
- Her ayın endeksi, `monthly_inflation_pct` ve `annual_inflation_pct`;
- Seçilen ilk/son endeks ile `first_to_last_index_change_pct`;
- Kullanılan formüller ve sınırlamalar bulunur.

Veri veya istek hatası HTTP 422 / `invalid_inflation_input` döndürür. Yanıtta
ham girdi/hata gövdesi gösterilmez. NaN/Infinity içeren veya bozuk JSON da bu
endpoint'in kontrollü hata yoluna girer; diğer endpoint'lerin hata davranışı
bu teslimatta değiştirilmez.

## Hesaplama kuralları

| Alan | Formül | Geçmiş gereksinimi |
| --- | --- | --- |
| Aylık enflasyon (%) | `(TÜFE[t] / TÜFE[t-1] - 1) × 100` | Önceki takvim ayı |
| Yıllık enflasyon (%) | `(TÜFE[t] / TÜFE[t-12] - 1) × 100` | Geçen yılın aynı ayı |
| İlk-son endeks değişimi (%) | `(seçilen son ay / seçilen ilk ay - 1) × 100` | Seçilen iki uç ay |

Seçilen dönemden önce gönderilen aylar karşılaştırma geçmişi olarak kullanılır;
yanıtta yalnızca seçilen aylar yer alır. Dolayısıyla ilk seçilen ayın aylık oranı,
önceki ay girdide varsa hesaplanır. Bu davranış, Housing analizinin ilk ay
değişimlerini null bırakan sözleşmesinden farklıdır ve onu değiştirmez.

Karşılaştırma ayı girdiden önceyse ilgili oran `null` olur; sıfır veya tahmin
üretilmez. Yıllık değişimin ilk değeri için aynı ayı iki yılda da içeren en az
13 ardışık gözlem gerekir. Yıllık oran, 12 aylık ortalama veya aylık oranın
yıllıklandırılması değildir. Aylık oranlar toplanmaz. Örneğin endeks
100 → 110 → 99 olduğunda aylık oranlar %10 ve %-10, ilk-son değişimi %-1'dir.

Tek ay seçilirse ilk-son endeks değişimi sıfırdır; o ayın aylık enflasyonu
ayrı hesaplanır ve sıfır olmak zorunda değildir. Seçilen ilk ay ile önceki
ayı arasındaki değişim ilk-son endeks değişimine dahil değildir. Hesaplar
çıktıda yuvarlanmaz; sunum katmanı gerekirse yuvarlayabilir.

## İki yıl karşılaştırması

`app/services/inflation_comparison.py::compare_inflation_years`, aylık TÜFE
tablosunu, `first_year` ve `second_year` yıllarını ve `source_ref` değerini alır.
Her iki yılın Ocak–Aralık sonuçlarını mevcut `build_inflation_evidence` kanıt
yapısıyla, verilen yıl sırasını koruyarak döndürür. Girdi yalnızca seçilen
yıllara kesilmez; önceki Aralık ayı gerektiğinde yıllık oran için kullanılabilir.
Aynı yılın iki kez verilmesi ve bool, tam sayı olmayan veya 1–9999 aralığı dışındaki
yıl girdileri açık hatayla reddedilir.

`second_minus_first_december_annual_inflation_pp` alanı, ikinci yılın Aralık
yıllık enflasyonundan birinci yılın Aralık yıllık enflasyonunu çıkarır ve yüzde
puan cinsindendir. Yıllar ters verilirse farkın işareti de tersine döner.
Gerekli önceki Aralık yoksa ilgili yıllık oran ve karşılaştırma farkı `null`
olur. Ocak–Aralık endeks değişimi ayrı alanlardır; Aralık yıllık enflasyonuyla
karıştırılmaz ve aylık oranlar toplanmaz. Bu çekirdek yeni bir HTTP endpoint'i
eklemez.

## Sentetik örneği çalıştırma

API'yi başlat:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Başka terminalde:

```powershell
$body = Get-Content .\docs\inflation-api-example.json -Raw -Encoding UTF8
$result = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analysis/inflation -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result.evidence.observations | Format-Table period, cpi_index, monthly_inflation_pct, annual_inflation_pct
$result.evidence.first_to_last_index_change_pct
```

Linux:

```bash
curl -f -H 'Content-Type: application/json' --data-binary @docs/inflation-api-example.json http://127.0.0.1:8000/analysis/inflation
```

Örnek **sentetiktir**. Üç ay için endeksler 100, 110, 99; aylık oranlar
null, yaklaşık 10, -10; yıllık oranların tamamı null; ilk-son değişimi
yaklaşık -1 olur. Bunlar Türkiye enflasyonuna ilişkin gerçek bulgular değildir.
API anahtarı ve `.env` gerekmez.

## Doğrulama kapsamı

Testler elle hesaplanmış oranları, seçilen aralığın dışındaki geçmişi, yıllık
karşılaştırma için 13 gözlem sınırını, tek aylık seçimi, girdi değişmezliğini,
eksik/mükerrer ayları, pozitif/sonlu sayı koşulunu ve HTTP hata davranışını
kapsar. API testlerinde dış HTTP ve model/LLM ayarı erişimi engellenir.
Gerçek resmî veri kabulü veya ekonomik neden/tahmin doğrulaması yapılmış sayılmaz.

## Yerel kabul kaydı — 16 Ekim 2026

Ana dal `48cdb75` üzerine hazırlanan değişiklikte Python 3.12 ile 64 yeni
kontrol geçti. Tam paket: **534 passed, 1 warning in 11.74s**; uyarı mevcut
Housing endpoint'indeki eski HTTP 422 sabitine aittir.

Yerel Uvicorn sunucusunda gerçek HTTP isteğiyle üç aylık sentetik örnek
HTTP 200 döndürdü: aylık oranlar null / yaklaşık %10 / %-10, ilk-son
değişimi yaklaşık %-1. Ayrıca 2020-01–2021-03 sentetik geçmişiyle seçilen
2021-01 ayının yıllık oranı yaklaşık %30 olarak doğrulandı. Eksik ay ve
Infinity girdisi HTTP 422 döndürdü. Mevcut Housing örneği HTTP 200 ve
2021-02 eşleşmesini korudu. Sunucu deneme sonunda kapatıldı.

Bu kontrollerde canlı model çağrısı yapılmadı. Bu kayıt kullanıcı Windows
ortamındaki doğrulamayı, resmî kaynak verisinin kabulünü veya doğal dil
enflasyon sorusu yönlendirmesini tamamlanmış saymaz.


## Windows kullanıcı kontrolü — 16 Ekim 2026

Mustafa'nın Windows / PowerShell ortamından paylaştığı çıktılara göre:

- Tam paket: **533 passed, 1 skipped, 2 warnings in 60.67s**.
  Atlanan testin gerekçesi paylaşılan çıktıda görünmüyor. `git diff --check` temiz.
- Belgelenen sentetik API örneğinin döndürdüğü JSON'da gözlem sayısı 3;
  endeksler 100 / 110 / 99; aylık değişimler null / yaklaşık %10 / %-10;
  ilk-son endeks değişimi yaklaşık %-1; yıllık değişimlerin tamamı null.
- Paylaşılan kayan nokta değerleri beklenen tolerans içinde: örneğin
  ilk-son değişimi `-1.0000000000000009`. Hesap çıktısı yuvarlanmadan korunur.

Bu kullanıcı kontrolü sentetik örnek ve yerel test paketi içindir; gerçek
EVDS dosya/manifest kabulü, yıllık oran için ayrı bir Windows HTTP denemesi
ve doğal dil soru yönlendirmesi bu kayıtla tamamlanmış sayılmaz.
