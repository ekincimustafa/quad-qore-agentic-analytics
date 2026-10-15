# Yapılandırılabilir LLM istemcisi

API narrator'ı `app/connectors/llm_client.py` içindeki `ask_llm` fonksiyonunu
kullanır. Tek protokol OpenAI uyumlu Chat Completions'tır; başka protokollere
adapter veya sağlayıcı seçme framework'ü eklenmedi. Hesaplar Python'da kalır.

## Yapılandırma

Repo kökündeki yerel `.env` dosyasına veya process environment'a erişebildiğiniz
sağlayıcının değerlerini girin:

```dotenv
LLM_API_KEY=
LLM_BASE_URL=
LLM_CHAT_MODEL=
LLM_TIMEOUT_SECONDS=30
```

Anahtar, tam API base URL ve model zorunludur; otomatik sağlayıcı/model varsayılanı
ve `MIA_*` fallback'i yoktur. URL HTTPS olmalı; user-info, query ve fragment
içeremez. `.env` yalnızca anlatım istendiğinde okunur; process environment
değerleri `.env` tarafından değiştirilmez. Anahtarı Git'e eklemeyin.

Timeout sonlu, 0'dan büyük ve en fazla 120 saniyedir. Bu SDK/HTTP timeout'udur;
tüm uçtan uca analiz için kesin toplam süre garantisi değildir. SDK retry sayısı
sıfırdır: bir istek için yalnızca bir deneme yapılır. 429/5xx otomatik denenmez.
Her çağrı sonunda istemci kapanır. Connection pooling ileride ölçüm gerektirirse
ayrı değerlendirilir; şu an uygulama çapında istemci yaşam döngüsü eklenmedi.

## Hata ve anlatım sınırı

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
