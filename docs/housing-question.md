# Sınırlı soru → plan → konut analizi çekirdeği

Takip: #42. Bu teslimat bir Python servisidir; soru kabul eden HTTP endpoint'i,
genel amaçlı agent, ek ekonomik analiz ve serbest LLM yorumlama henüz yoktur.

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

`HousingDataCoverage` sınırları sunucunun doğrulanmış veri/manifest bilgisinden
oluşturulmalıdır. Kullanıcı veya model bu nesnenin kaynağı olmamalıdır.
Bu sınıf iki sınırı doğrular; fiziksel dosya varlığı, hash, tüm ara aylar veya
kaynak zincirini doğrulamaz. Eksik/mükerrer ay ve sayısal kalite kontrolleri
mevcut Gold servisinde kalır. Gerçek dosya/manifest entegrasyonu #39/#40 ve
#42'nin sonraki HTTP entegrasyon teslimatında tamamlanacaktır.

Mevcut servisin ilk ay davranışı korunur: seçilen aralığın ilk ayı için önceki
aya ait değişim ve koşul sonucu bulunmaz. Planlama servisi geçmiş ay ekleyerek
bu davranışı değiştirmez.

`run_housing_question()` karar ve analiz içeren `HousingQuestionRun` döndürür.
Açıklama isteği/unsupported kararda `analysis=None` olur. Çalıştırılan analiz
veya narrator hata verirse mevcut hata yükseltilir; yarım sonuç başarı diye
sunulmaz. Henüz HTTP durum kodu veya API cevap şeması eklenmemiştir.

## Doğrulamanın sınırı

Şema ve izin kontrolleri, modelin kullanıcının niyetini doğru anladığını
kanıtlamaz. Şemaya uyan yanlış bir dönem/niyet modeli de ayrıca gerçek sorularla
değerlendirilmelidir. İstemdeki talimatlar tek başına prompt injection koruması
veya anlamsal doğruluk garantisi değildir; çalıştırma sınırı kodla uygulanır.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_housing_question.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Yeni testler socket erişimini engeller; sahte model yanıtıyla gerçek analiz
servisine kadar gider. Doğrudan servisle sayısal/grafik eşitliği, dönem aktarımı,
araç çağrısının yapılmaması gereken durumlar, bozuk planlar, eksik veri ve
narrator hatası kontrol edilir. Bunlar canlı model başarı oranı ölçmez.
`evals/golden_cases.json` içindeki geniş taslak vakalar bu teslimatta çalıştırılmış
sayılmaz. Canlı soru planlama, API, dosya tabanlı entegrasyon ve anlamsal eval
runner bu görevin açık kalan parçalarıdır.
