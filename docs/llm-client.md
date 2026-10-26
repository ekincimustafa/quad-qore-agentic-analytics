# Yapılandırılabilir LLM istemcisi

API narrator'ı `app/connectors/llm_client.py` içindeki `ask_llm` fonksiyonunu
kullanır. Economic soru planlayıcısı aynı istemciyi `ask_economic_plan` üzerinden
şemalı JSON çıktısıyla çağırır. Tek protokol OpenAI uyumlu Chat Completions'tır; başka protokollere
adapter veya sağlayıcı seçme framework'ü eklenmedi. Hesaplar Python'da kalır.

## Yapılandırma

Repo kökündeki yerel `.env` dosyasına veya process environment'a erişebildiğiniz
sağlayıcının değerlerini girin:

```dotenv
LLM_API_KEY=
LLM_BASE_URL=
LLM_CHAT_MODEL=
LLM_TIMEOUT_SECONDS=30
LLM_REASONING_EFFORT=
```

Anahtar, tam API base URL ve model zorunludur; otomatik sağlayıcı/model varsayılanı
ve `MIA_*` fallback'i yoktur. URL HTTPS olmalı; user-info, query ve fragment
içeremez. `.env` yalnızca model çağrısı gerektiğinde okunur; process environment
değerleri `.env` tarafından değiştirilmez. Anahtarı Git'e eklemeyin.

Timeout sonlu, 0'dan büyük ve en fazla 120 saniyedir. Bu SDK/HTTP timeout'udur;
tüm uçtan uca analiz için kesin toplam süre garantisi değildir. SDK retry sayısı
sıfırdır: bir istek için yalnızca bir deneme yapılır. 429/5xx otomatik denenmez.
Her çağrı sonunda istemci kapanır. Connection pooling ileride ölçüm gerektirirse
ayrı değerlendirilir; şu an uygulama çapında istemci yaşam döngüsü eklenmedi.

`LLM_REASONING_EFFORT` isteğe bağlıdır: boşsa istekten tamamen çıkarılır ve
sağlayıcının mevcut varsayılanı korunur; yalnız `low`, `medium`, `high` kabul
edilir. Doluysa seçilen sağlayıcı/model bu parametreyi desteklemelidir.
Google'ın [OpenAI uyumluluk belgesi](https://ai.google.dev/gemini-api/docs/openai)
`gemini-3.8-flash` için `reasoning_effort="low"` örneği verir. Bu modelde
`minimal` desteklenmediğinden düşük gecikme denemesi için `low` kullanılır.
Bu seçenek daha kısa yanıt süresini garanti etmez ve önceki timeout'ların
nedeninin düşünme seviyesi olduğunu kanıtlamaz. Otomatik model/sağlayıcı geçişi yoktur.

## Hata ve anlatım sınırı

Economic soru yolu (`run_economic_question` varsayılanı, iki Economic HTTP
endpoint'i ve canlı evaluator CLI) aynı `ask_economic_plan` fonksiyonunu kullanır.
Sağlayıcı yanıtı `EconomicModelResponse` ile sabit sekiz alanlı JSON nesnesidir ve
`response_format={"type":"json_schema","json_schema":{"name":"analysis_plan",
"strict":true,"schema":...}}` olarak sağlayıcıya gönderilir. Kök seviyede karar
union'ı yoktur. `status`, `analysis_id`, `reason`, `start_period`, `end_period`,
`first_year`, `second_year`, `conditions` alanlarının hepsi zorunludur; seçilen
karara ait olmayan alanlar açık `null` olmalıdır. Metrik/operatör ve koşul tipi
mevcut `HousingFilterCondition` ile ortaktır; fazladan alan yasaktır.

`parse_economic_model_decision` önce bu taşıma nesnesini katı biçimde doğrular,
yalnız bilinen ve açıkça null alanları çıkarıp aynı `ModelDecision` tipini
doğrular. İlgisiz bir alan doluysa atılmaz, mevcut karar tipi tarafından
reddedilir; eksik zorunlu alan veya koşul tamamlanmaz. Önceki yalın karar
JSON'ları da desteklenir; HTTP yanıtları ve offline `model_call` sözleşmesi
değişmez. Evaluator'ın `actual_model_decision` alanı bu açık dönüşümden sonraki
model kararını gösterir; anlamı veya değerleri Python guard sonucu ile değiştirilmez.
Seçilen sağlayıcı/model bu şemayı desteklemelidir. Google'ın yukarıdaki resmî
belgesi yapılandırılmış çıktıyı gösterir; bu projenin şemasıyla gerçek model
kabulü ayrıca doğrulanmalıdır. Şema isteği reddedilirse güvenli hata verilir;
metin moduna düşme, otomatik tekrar veya başka modele geçiş yapılmaz.

İstemci şemalı istekte de yanıtı onarmaz. Kod bloğu, ek alan veya yanlış plan
Python doğrulamasından geçmez; tarih/metrik/koşul/kapsam kontrolleri hesaplardan
önce uygulanır. Şema uyumu doğru analiz seçildiği anlamına gelmez.
Normal `ask_llm(prompt)` çağrısı, kısa `--probe`, mevcut Housing soru yolu ve
anlatım yolu `response_format` göndermez; mevcut sözleşmeleri korunur.

Eksik/geçersiz ayarlar `LLMConfigurationError`; kimlik/izin, 429, timeout,
bağlantı, 5xx ve beklenmeyen yanıtlar güvenli kodlu `LLMRequestError` üretir.
Uygulama ham sağlayıcı hata gövdesini veya anahtarı hata mesajına/loga yazmaz.
Bu garanti üçüncü taraf SDK/transport için ayrıca açılan debug loglarının
içeriğini kapsamaz; secret-bearing debug çıktıları yayımlanmamalıdır.

Yanıt bir choice, `finish_reason=stop` ve boş olmayan string içerik taşımalıdır.
Kesilmiş yanıtlar reddedilir. Ardından [Housing JSON sözleşmesi](housing-narration.md)
uygulanır: aynı ay/metrik değeri, eksiksiz eşleşen ay kümesi, ek alan yasağı.
Türkçe metni uygulama evidence'den üretir. API response şeması değişmez;
anlatım hataları `502 / narration_failed` olarak kalır.

`include_narration=false` yolunda ayar okunmaz, LLM istemcisi oluşturulmaz.
Eski `mia_client.py`, `narrate_housing_evidence_with_mia` ve `smoke_test_mia`
ayrı legacy yardımcılar olarak korunur. `MIA_*` tek başına yeni API narrator'ını
yapılandırmaz; erişiminiz varsa aynı adres/model/anahtarı `LLM_*` ile açıkça seçin.

## Kontrol komutları

### Tek kısa üretim isteği

Anahtarınız yerel `.env` içindeyken, ayrı onaylı canlı teşhis için:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test_llm --probe --reasoning-effort low --timeout-seconds 60
```

Komut mevcut model/endpoint ile yalnız `Reply with exactly OK.` mesajını gönderir;
konut/TÜFE servisi, veri dosyası, evaluator veya anlatım sözleşmesini çalıştırmaz.
Toplam bir istemci çağrı denemesi vardır; SDK retry 0, hata sonrası ikinci istek yoktur.
Geçici seçenekler bellekteki frozen ayarlara uygulanır; `.env` yazılmaz ve süreç
ortamı başarı/hata sonunda eski haline getirilir. Seçenekler yalnız `--probe` ile
kullanılabilir. Seçenekler verilmezse mevcut yerel ayarlar kullanılır.

Çıktı başarıyı veya izinli güvenli hata kodunu, istemci çağrı sayısını ve istemci
süresini gösterir; bu süre saf model çıkarım süresi değildir. Timeout varsa SDK'nın
türlü istisna zincirinden `connect`, `read`, `write`, `pool` veya `unknown` aktarılır.
Ham hata, yanıt, anahtar, URL veya traceback yazdırılmaz. `read` tek başına
sağlayıcının düşündüğünü ya da proxy'nin hatalı olduğunu kanıtlamaz.
`OK` başarısı ekonomik sorunun doğru planlandığı, ücretsiz kota garantisi veya
EQ-038 kabulünün geçtiği anlamına gelmez. Canlı komutu otomatik testler çalıştırmaz.

### Mevcut anlatım kontrolü

Anahtarsız/offline kontroller:

```bash
python -m pytest tests/test_llm_client.py tests/test_housing_llm_api.py tests/test_housing_narrator.py -q
python -m pytest -q
```

Kendi anahtarınızı yerel ortamda yapılandırdıktan sonra isteğe bağlı canlı kontrol:

```bash
python -m scripts.smoke_test_llm
```

Bu komut üç aylık sentetik fixture'dan deterministik evidence üretir; canlı modele
tek istek gönderir ve gerçek narrator doğrulamasını çalıştırır. Beklenen sonuç
üç ay ve yalnızca 2021-02 eşleşmesidir. Çıktı ham model metni değil, evidence'den
üretilen Türkçe anlatımdır. Offline mock testler canlı sağlayıcı/model uyumunu
ölçmez.

Economic evaluator'ın yeni canlı raporlarında `llm_request_settings`, koşu
başlangıcında okunan timeout, isteğe bağlı reasoning effort, retry 0 ve
`response_format=json_schema` bilgisini
tutar; anahtar veya URL içermez. Önceki raporlar değiştirilmez. Offline raporlar
LLM ayarı okumaz. Mevcut vaka beklentileri, çağrı bütçesi ve ilk hatada durma kuralı korunur.

`invalid_plan` satırlarında `invalid_plan_diagnostics`, kod bloğu öneki
(`code_fence_prefix`), geçersiz JSON (`invalid_json`), nesne olmayan JSON
(`json_non_object`), aşırı uzun yanıt veya şema hatasını ayırır. Şema hatasında
yalnız izinli hata türleri ve sözleşmenin bilinen alan adları kaydedilir;
`missing_fields` ve `extra_fields` ayrı verilir. `decision_header` yalnız izinli
status/analysis_id değerlerini, diğer değerler için `unknown` bilgisini taşır;
model metni, hatalı değerler ve bilinmeyen alan adları saklanmaz. Çalışan servisin
aynı ayrıştırıcısı kullanılarak diğer union dallarının ilgisiz hataları ayıklanır. Bu işlem
yanıtı düzeltmez, kod bloğunu soyup kabul etmez ve analizi çalıştırmaz.
Önceki raporlara kaydedilmeyen yanıtlar sonradan geri getirilemez.

## Canlı kabul kaydı — 15 Ekim 2026

Kullanıcının Windows PowerShell / mevcut venv ortamında Gemini API ve
`gemini-3.5-flash-lite` ile `python -m scripts.smoke_test_llm` başarılı oldu.
Son bildirilen çalışma tabanı `72836a9` idi. Üç sentetik ay incelendi;
tek eşleşme `2021-02`, çıkış kodu `0`. Gerçek anahtar paylaşılmadı.

Önceki `gemini-3.8-flash` isteği kontrollü `provider_unavailable` hatası verdi;
uygulama çıktısı kesin HTTP kodunu göstermiyordu. Flash-Lite başarılı koşusunda
`LLM_CHAT_MODEL` terminalde geçici değiştirildi ve sonra kaldırıldı. Kalıcı seçim
yerel `.env` dosyasında yapılır; uygulamada otomatik model fallback'i eklenmedi.

Bu tek başarılı sözleşme kontrolüdür; sağlayıcı kararlılığı, model başarı oranı,
ekonomik yorum kalitesi veya gerçek veri kabulü ölçülmüş sayılmaz. Türkçe metni
mevcut Python renderer üretir. Gerçek ekonomik veri kabulü #39/#40, soru planlama
ve yorumlama çalışmaları ayrı teslimatlardır. Faturalandırma durumu ve model
kotasının hesabın arayüzünden kontrolü gerekir; kod harcama sınırı uygulamaz.
