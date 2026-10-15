# Housing anlatım sözleşmesi

## Model çıktısı
Model yalnızca bir JSON nesnesi döndürür. Root'ta sadece results bulunur.
Her sonuç period, housing_loan_interest_rate_pct, interest_rate_change_pp
ve real_housing_loan_change_pct alanlarını içerir. Eşleşme yoksa results boştur.

Her eşleşen ay tam bir kez bulunmalıdır. Her değer aynı ayın aynı metriğiyle
karşılaştırılır. Tam değer veya dört ondalığa ROUND_HALF_EVEN ile yuvarlanmış
değer kabul edilir. String/bool sayılar, NaN/Inf, ek alanlar, Markdown,
eksik/mükerrer/kanıtta bulunmayan aylar ve 16000 karakteri aşan yanıt reddedilir.

## Kullanıcıya sunulan metin
Doğrulama sonrası Türkçe metin doğrudan HousingAnalysisEvidence üzerinden
uygulamada üretilir. Modelin ham metni kullanıcıya aktarılmaz. Kaynak
referansları evidence'den alınır; yöntem ve nedensellik sınırlaması uygulama
tarafından eklenir. Metin sayıları en fazla dört ondalıkla gösterir.

Bu sürüm serbest ekonomik yorum üretmez. Evidence'deki kaynak referanslarını
korumak, resmî kaynağın fiziksel bütünlüğünü yeniden doğrulamak anlamına gelmez;
manifest/Bronze zinciri ayrı veri doğrulama akışının sorumluluğundadır.

## API ve test
HTTP yanıtında narration alanı string olarak kalır. include_narration=false
yolunda model çağrılmaz. Geçersiz model JSON'u mevcut narration_failed / 502
hata sınırına taşınır. Model yanıtı üst sınırı, 60 aylık pencerede 59 eşleşmenin
JSON çıktısını da kapsayacak şekilde 16000 karakterdir.

Offline test komutu:
python -m pytest tests/test_housing_narrator.py -q

API, yapılandırılabilir `LLM_*` istemcisini kullanır; eski MIA yardımcı fonksiyonu
ayrı uyumluluk yolu olarak korunur. Seçilen canlı modelin JSON formatına uyumu
için ayrıca anahtar içermeyen bir smoke test sonucu gereklidir; offline mock
testler canlı model uyumunu ölçmez. Kurulum ve `scripts.smoke_test_llm` komutu:
[LLM istemci rehberi](llm-client.md).
