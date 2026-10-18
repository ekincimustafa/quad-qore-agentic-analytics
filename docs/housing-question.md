# Sınırlı soru → plan → konut analizi çekirdeği

Takip: #42. Python servis çekirdeği ve normalize edilmiş satırları kabul eden soru
HTTP endpoint'i mevcut. Ayrı [yerel dosya wrapper'ı](housing-question-files.md)
sunucu yapılandırmalı BDDK/EVDS paketini modelden önce doğrular. Gerçek veri kabulü
ve bu wrapper'ın HTTP bağlantısı açık kalır.

## Görev paylaşımı

`app/services/housing_question.py` içindeki `run_housing_question()`:

1. Soruyu ve sunucunun sağladığı veri kapsamını modele verir.
2. Tek JSON kararını Pydantic ile doğrular; ek alanları kabul etmez.
3. Yalnızca `housing_rate_down_real_credit_not_up` planını çalıştırabilir.
4. Dönem sunucunun verdiği kapsam içindeyse mevcut `run_housing_analysis()`
   servisini bir kez çağırır. Gold formülleri burada yeniden uygulanmaz.
5. Evidence/grafik ve açıkça istenmişse mevcut narrator sonucunu döndürür.

Planlama için en fazla bir model çağrısı vardır; otomatik retry, araç seçme
döngüsü ve serbest kod/SQL çalıştırma yoktur. `narrator=None` varsayılanıyla
anlatım çağrısı yapılmaz. Gerçek LLM narrator ayrıca verilirse onun çağrısı
planlama isteğine eklenir.

Model yalnızca soruyu, kullanılabilir dönem sınırlarını ve karar şemasını görür;
BDDK/EVDS tabloları veya yerel kaynak yolları planlama istemine konmaz.

## Kararlar ve dönem politikası

| Karar | Alanlar / davranış |
| --- | --- |
| `ready` | Tek izinli `analysis_id`, `start_period`, `end_period`; analiz çalışır |
| `clarification_required` | `period_required`, `metric_ambiguous`, `question_ambiguous` veya `outside_coverage`; analiz çalışmaz |
| `unsupported` | `unsupported_analysis`; analiz çalışmaz |

Örnek çalıştırılabilir model planı:

```json
{
  "status": "ready",
  "analysis_id": "housing_rate_down_real_credit_not_up",
  "start_period": "2021-01",
  "end_period": "2021-03"
}
```

İstem, yıl aralığının tam aylara açılmasını tarif eder (`2021-2025` için
`2021-01`–`2025-12`). Dönem verilmediğinde varsayılan dönem uydurulmamalıdır.
Reel/nominal ayrımı belirsizse açıklama istenir. Enflasyon özeti, dönem
karşılaştırması, web araştırması, tahmin ve nedensellik bu ilk araç kapsamında
desteklenmez; bunların uygulanmış olduğu iddia edilmemelidir.

Kod takvim biçimini, yılın geçerliliğini ve başlangıç/bitiş sırasını doğrular.
Geçerli biçimdeki plan veri kapsamı dışındaysa aralık kırpılmaz;
`outside_coverage` döner. Bozuk JSON, bilinmeyen araç/alan ve geçersiz dönem
`HousingPlanValidationError` üretir. Model çağrısı hatasında ham hata mesajı
aktarılmadan `HousingPlanningError` yükseltilir; analiz çalışmaz.

## Güvenilen girdiler ve mevcut analiz semantiği

`HousingDataCoverage` sınırları sunucu tarafından kodla kontrol edilen veri
kapsamından oluşturulmalıdır. Kullanıcı/model ayrı bir coverage parametresiyle
bu sınırları değiştirememelidir. Mevcut soru API'si sınırları istek satırlarının
kontrolünden sonra ortak dönemlerden türetir; satırlar çağıranın sağladığı
girdilerdir ve resmî kaynaktan geldikleri fiziksel olarak doğrulanmış sayılmaz.
Bu sınıf iki sınırı doğrular; fiziksel dosya varlığı, hash, tüm ara aylar veya
kaynak zincirini doğrulamaz. Eksik/mükerrer ay ve sayısal kalite kontrolleri
mevcut Gold servisinde kalır. Fiziksel kontroller ayrı
[yerel dosya wrapper'ında](housing-question-files.md) uygulanır; normalize-satır
API'si otomatik olarak bu doğrulamayı yapmış sayılmaz. Gerçek kabul #39/#40 ve
#42'de açık kalır.

Mevcut servisin ilk ay davranışı korunur: seçilen aralığın ilk ayı için önceki
aya ait değişim ve koşul sonucu bulunmaz. Planlama servisi geçmiş ay ekleyerek
bu davranışı değiştirmez.

`run_housing_question()` karar ve analiz içeren `HousingQuestionRun` döndürür.
Açıklama isteği/unsupported kararda `analysis=None` olur. Çalıştırılan analiz
veya narrator hata verirse mevcut hata yükseltilir; yarım sonuç başarı diye
sunulmaz. HTTP sözleşmesi aşağıda açıklanmıştır.

## Soru API'si

`POST /analysis/housing/question`, `question`, `bddk_monthly`, `evds_monthly`,
`bddk_source_ref`, `evds_source_refs` ve opsiyonel `include_narration` alır.
`start_period`, `end_period`, `coverage`, model, anahtar, SQL veya dosya yolu
alanları kabul edilmez. Plan dönemi modelden gelir ve kodla sınırlandırılır.

Sunucu sayısal alanları mevcut satır modelleriyle doğrular. Takvim dönemi ve
tekillik kontrollerini iki girdiye uygular; ortak ayların kesintisiz olmasını
ister. Ortak aralık BDDK ve EVDS dönemlerinin kesişiminden türetilir. Bu
kontroller model çağrısından önce yapılır. Ortak aralığın dışındaki satırlar
istenen analiz kapsamını genişletmez. Kaynak referansları çağıranın etiketleridir;
dosya hash'i veya Bronze/Silver kaynak zinciri kanıtı yerine geçmez.

| HTTP | Durum / kod | Sonuç |
| --- | --- | --- |
| 200 | `status=ok` | `decision`, `available_period`, evidence, grafik ve opsiyonel mevcut anlatım |
| 200 | `status=clarification_required` | Sabit uygulama mesajı; evidence/grafik/anlatım null |
| 200 | `status=unsupported` | Desteklenen kapsamı açıklayan sabit mesaj; analiz yok |
| 422 | İstek şeması veya `invalid_analysis_input` | Geçersiz girdiler; başarı sonucu yok |
| 502 | `question_planning_failed` | Model/ayar/sağlayıcı çağrısı başarısız |
| 502 | `invalid_question_plan` | Model yanıtı izinli plan şemasına uymuyor |
| 502 | `narration_failed` | İstenen anlatım doğrulanamadı; yarım başarı dönmez |

Yeni endpoint hata mesajlarına ham sağlayıcı yanıtını veya model planını koymaz.
Mevcut `/analysis/housing` ve `/analysis/housing/demo` sözleşmeleri değişmez.
Her HTTP isteği bağımsızdır; açıklama isteğine cevap verirken tam soruyu yeniden
gönder. Sohbet geçmişi tutulmaz.

`include_narration=false`, yalnızca anlatım çağrısını kapatır. Soru planlaması
canlı LLM gerektirir. Varsayılanla bir planlama isteği; anlatım açılırsa ayrıca
mevcut narrator isteği yapılır. Aşağıdaki tek sentetik örneğin canlı planlama
kabulü 15 Ekim 2026'da kullanıcı ortamında tamamlandı. Offline HTTP testleri
sahte modelle gerçek analizi çalıştırır.

### PowerShell ile canlı deneme

Yerel `.env` dosyasında kendi ücretsiz projenin `LLM_*` ayarlarını yapılandır.
Önceki ayrı narration smoke kontrolü `gemini-3.5-flash-lite` ile doğrulandı.
Soru endpoint'inin kabul kaydı aşağıdadır; o HTTP çıktısında seçilmiş modelin
kimliği ayrıca gösterilmemiştir. Model kotası ve projenin ücretsiz durumu
hesap arayüzünden kontrol edilmelidir.

Birinci terminalde API'yi başlat:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

İkinci terminalde repo kökünden tek canlı planlama denemesi yap:

```powershell
$body = Get-Content .\docs\housing-question-api-example.json -Raw -Encoding UTF8
$result = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analysis/housing/question -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result.status
$result.decision
$result.evidence | Select-Object observed_month_count, matched_month_count, matched_periods
```

Örnek üç sentetik ay içerir; başarılı `ready` planı için beklenen analiz üç ay
ve yalnızca `2021-02` eşleşmesidir. Modelin gerçekten bu planı üretip üretmediği
canlı denemede ayrıca gözlenmelidir. Bu örnek gerçek ekonomik bulgu değildir.
Hata durumunda art arda istek üretme; anahtar ve `.env` içeriği paylaşılmamalıdır.

### Canlı soru kabul kaydı — 15 Ekim 2026

Kullanıcı, Windows PowerShell / mevcut venv ortamında API'yi Uvicorn ile
başlattı ve `housing-question-api-example.json` içeriğini UTF-8 olarak gönderdi.
Yerel `LLM_*` yapılandırması kullanıldı; anahtar paylaşılmadı.

- HTTP yanıtı: `200`; uygulama durumu: `ok`.
- Karar: `ready`, analiz: `housing_rate_down_real_credit_not_up`.
- Seçilen dönem: `2021-01`–`2021-03`.
- Evidence: 3 gözlem, 1 eşleşme; eşleşen dönem `2021-02`.
- Kullanıcının tam test sonucu: **429 passed, 1 skipped, 2 warnings in 35.11s**;
  `git diff --check` temiz. Paylaşılan çıktı skip nedenini göstermiyor.

Bu kayıt yalnızca tek desteklenen sorunun sentetik veriyle canlı akışını
doğrular. Model başarı oranı, diğer soru türlerinin canlı davranışı, gerçek
ekonomik veri kabulü veya serbest yorumlama kalitesi ölçülmüş sayılmaz.

## Doğrulamanın sınırı

Şema ve izin kontrolleri, modelin kullanıcının niyetini doğru anladığını
kanıtlamaz. Şemaya uyan yanlış bir dönem/niyet modeli de ayrıca gerçek sorularla
değerlendirilmelidir. İstemdeki talimatlar tek başına prompt injection koruması
veya anlamsal doğruluk garantisi değildir; çalıştırma sınırı kodla uygulanır.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_housing_question.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_housing_question_api.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Yeni testler socket erişimini engeller; sahte model yanıtıyla gerçek analiz
servisine kadar gider. Doğrudan servisle sayısal/grafik eşitliği, dönem aktarımı,
araç çağrısının yapılmaması gereken durumlar, bozuk planlar, eksik veri ve
narrator hatası kontrol edilir. Bunlar canlı model başarı oranı ölçmez.
`evals/golden_cases.json` içindeki geniş taslak vakalar bu teslimatta çalıştırılmış
sayılmaz. HTTP testleri harici HTTP taşıyıcısını engeller; üç cevap durumu,
istek/model/narrator hataları, modelden önce veri kontrolleri ve mevcut analizle
sayısal/grafik eşitliği kapsanır. Dokuz vakalık ayrı set ve açık bütçeli
[değerlendirme komutu](housing-question-evals.md) hazırdır; offline mod model
başarı oranı ölçmez. Daha geniş canlı soru davranış değerlendirmesi ve gerçek
dosya tabanlı entegrasyon açık kalır.
