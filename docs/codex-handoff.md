# Codex devir notu — 27 Ekim 2026

Bu not, Mustafa'nın yerel VS Code/Codex oturumuna proje bağlamını taşır.
Kurulum adımları ve hesap arayüzü zamanla değişebilir; bu dosya ürün kurulumu
için bir sürüm garantisi değildir. Bu dalın main tabanı `8e38593` (PR #119
sonrası); aşağıdaki ilk bölüm bugünkü değişikliği ve sonraki adımı belirtir.
Aşağıdaki eski kayıtlar tarihli kaynak kanıtıdır; en üstteki oturum güncellemesi
güncel durumu belirtir. Tarihli bölümlerdeki dal/CI/onay bekleme ifadeleri yalnız
o tarihin kanıtıdır ve güncel engel değildir.
Yeni bir oturum güncel HEAD'i, çalışma ağacını ve ilgili issue'yu yeniden kontrol
etmelidir. Mustafa Hacettepe Bilgisayar Mühendisliği üçüncü sınıf öğrencisidir;
ekip Mustafa, Osman ve Afra'dan oluşur. Gerçek verili yerel prototip mevcut;
şimdiki hedef mevcut soru planlama gecikmesini doğrulukla birlikte ölçmektir.

## İsteğe bağlı minimal planlama ve süre kaydı — 27 Ekim 2026

- PR #119 bağımsız incelemeden sonra `8e38593` olarak merge edildi; exact main
  CI completed/success. Portföy belgeleri tamamlandı. Bu dal
  `perf/planner-minimal-effort`, taban `8e38593`.
- İstemci ve kısa probe artık açık `minimal` seçimini de kabul eder. Google'ın
  resmî rehberi mevcut `gemini-3.5-flash-lite` için minimal desteği/varsayılanını
  doğrular; `gemini-3.8-flash` için desteklenmez. Bağlantılar llm-client.md'de.
  Model, sağlayıcı veya boş reasoning ayarının varsayılanı değiştirilmedi.
- Mevcut Economic evaluator'a yalnız `--live` ile geçici reasoning/timeout
  seçenekleri ve vaka başına model/HTTP süreleri eklendi. Başarısız denemenin
  süresi tutulur; atlanan vakalar null. Süreler saf model üretim süresi değildir.
  Şema/prompt, guard, hesaplar, HTTP/UI, fiziksel hash ve eval girdileri değişmedi.
- Önce 10 yeni davranış başarısız oldu; uygulama sonrası odaklı 179 passed.
  Son kodda tek scripts.verify_project: 4/4, Linux 1428 passed/1 skipped,
  Housing 9/9, Economic 45/45, canlı 0, diff-check temiz. Günlük
  out/verification/20261027T121253Z-2-dbac3ff7. Yedi yerel belge hedefi çözüldü;
  PowerShell parser/Windows kontrolü yapılmadı. Sonrasında yalnız bu kayıt eklendi.
- Hız veya canlı model doğruluğu artışı kanıtlanmadı. Sonraki adım bağımsız PR
  incelemesi; ardından aynı commit/model/fixture/timeout ve seçilmiş sorularda
  ayrıca onaylı low/minimal karşılaştırması. Örnek komut yeni çağrı yetkisi değildir.
  Canlı LLM/EVDS çağrısı, gerçek veri indirmesi, merge veya release yapılmadı.


## Portföy kapsamı ve güncel kullanım kanıtı — 27 Ekim 2026

- Dal `docs/portfolio-ready-scope`, taban `main` `7d2f294`. Yalnız README,
  bu not ve mevcut kabul kaydı güncelleniyor; runtime/fixture/CI kodu değişmiyor.
- README dört analiz türünü, tek soru/tek analiz sözleşmesini ve üç başlangıç
  yolunu ayırıyor: anahtarsız sentetik HTML, doğrulanmış paketle sabit preview,
  aynı paket+model ayarıyla normal soru ekranı. Clone gerçek paketi içermez.
- PR #118 bağımsız incelenip `7d2f294` olarak merge edildi; main CI success.
  Önceki bölümlerdeki inceleme beklentileri tarihli kayıttır. 26 Ekim kullanıcının
  üç ekranında beklenen karşılaştırma/ters sıra/TÜFE özeti görüldü; görünen özetler
  önceki değerlerle uyumlu. Tam tablolar/grafik etkileşimleri/hash'ler yeniden
  doğrulanmadı. Ayrıntı ve kaynak sınırı mevcut release-acceptance.md kaydında.
- Süreler toplam 36.728/29.257/24.982 sn; plan istemcisi
  36.422/28.959/24.211 sn. Genel model doğruluk veya hız kazancı iddiası yok.
  Bu belge işi yeni canlı LLM/EVDS çağrısı veya yeni veri kabulü değildir.
- #46 closed/not_planned; video çekilmeyecek ve kabul kapısı değildir.
  Eski rc.1 etiketi `abea431` offline Housing sürümünde kalır; güncel soru
  ekranıyla karıştırılmaz. Yeni tag/release yayımlanmıyor.
- Afra'nın #115 karşılaştırma grafik/raporu, Osman'ın #113 yerel başlatıcısı
  seçilmiş katkı kanıtlarına eklendi. Ekip katkıları Mustafa'ya topluca yazılmaz.
- Yeni public clone/venv (Linux, Python 3.12.14, `7d2f294`), requirements kurulumu
  ve pip check başarılı. Üç sentetik HTML oluştu; görünür uyarılar ve dış
  script/stylesheet bulunmadığı içerikten kontrol edildi. Gerçek TCP'de health,
  kök ekran, docs, UI asset'leri ve iki deterministik API örneği 200; eksik paket
  dosya API'si 503 ve başlatıcı check-only exit 1 ile güvenli durdu. İlk ayrı
  araç oturumunun TCP bağlantısı reddedildi; başarılı koşu aynı üst süreçteydi.
  Sunucular kapatıldı; tarayıcı render/Windows/gerçek veri kabulü yapılmadı.
- 74 yerel link/fragment ve 10 bash bloğu geçti; PowerShell bu ortamda yok.
  Runtime değişmediği için tam yerel test paketi tekrarlanmadı; CI ayrıca izlenir.
- Sonraki adım bağımsız belge PR incelemesi. Sonraki ürün önceliği mevcut plan
  gecikmesi/niyet güvenilirliğini ölçmek; yeni özellik veya canlı koşu bu PR'a
  eklenmez. Güncel kullanıcı makinesinde yeni Windows kurulum kontrolü yapılmış
  sayılmamalı; yalnız gerçekten yapılan kontroller kaydedilecek.

## Economic plan prompt'unu sadeleştirme — 26 Ekim 2026

- PR #117 bağımsız incelemeden sonra `a25ffef` olarak main'e alındı; main CI
  success. Önceki bölümdeki inceleme beklentisi tarihli kayıttır. Bu dal
  `fix/compact-economic-planner`, taban `a25ffef`.
- Son kullanıcı ekran/header kanıtı: 2023 TÜFE ready/cpi_inflation_summary,
  12 ay ve ilk-son %54,5003; total 21732.182 ms, plan 20942.280 ms.
  İki tam yılın aylık+yıllık TÜFE karşılaştırması yanlış
  clarification_required/question_ambiguous; total 25675.635 ms,
  plan 25367.104 ms. Kullanıcı sorusu açıktır; bu model kararı kabul başarısı
  değildir. Plan, tüm istemci çağrısı süresidir; saf model üretim süresi değildir.
- Yalnız build_economic_question_prompt metni sadeleştirildi. Aynı katı sekiz
  alanlı şema response_format'ta kalır; metindeki JSON şeması kaldırıldı.
  Hesaplar, parser, dönem/metrik/koşul guard'ları, HTTP, teşhis başlıkları,
  hash denetimleri, model/timeout/retry ayarları ve 45+9 vaka korunur.
- Aynı karşılaştırma sorusu ve 2021-01–2026-06 kapsamıyla prompt 7148'den
  3668 karaktere indi (%48,68). Token/maliyet/hız veya doğruluk kazancı değildir.
- Sahte SDK ile uzun ve ters sıralı iki yıl soruları mevcut bağımsız hesapla
  karşılaştırılıyor. Gözlenen yanlış model netleştirmesi hâlâ başarısızdır;
  analiz 0 ve ilk hatada durma korunur. Canlı çağrı yapılmadı.
- Odaklı 385 passed; evaluator 89 passed. Son kodda tek scripts.verify_project:
  4/4, pytest 1415 passed, 1 skipped; Housing 9/9, Economic 45/45, canlı 0;
  diff-check temiz. Günlük out/verification/20261026T170424Z-2-17f81904.
  Prompt dışındaki runtime AST ve evals girdileri tabanla aynı; beş ilgili
  yerel belge bağlantısı çözüldü. Son testten sonra yalnız bu sonuç kaydı eklendi.
- Sonraki adım: bağımsız PR incelemesi, ardından ayrıca onaylı en çok üç canlı
  UI denemesiyle karar ve süre kontrolü. Uygulayan oturum merge/release yapmaz.

## Normal ekran denemesinden TÜFE düzeltmesi — 26 Ekim 2026

- PR #116 bağımsız incelemeden sonra `e33f89d` olarak main'e alındı;
  önceki bölümdeki inceleme beklentisi tarihli kayıttır. Bu dal
  `fix/cpi-question-periods`, taban `e33f89d`.
- Mustafa'nın normal model modu ekranları: konut 60 ay/22 eşleşme; açık
  `2023 yılı için` sorusunda gereksiz period_required; iki tam yılın aylık ve
  yıllık TÜFE karşılaştırmasında unsupported; nominal/reel belirtilmeyen
  konut sorusunda beklenen metric_ambiguous. Kullanıcı ayrıca yavaşlık bildirdi;
  ekran görüntüleri süre veya ham model planı kanıtı değildir.
- Tarih hatası doğru ready planıyla yeniden üretildi. `yılı` / `yılı için`
  bağlamı tam yıl veya açık dar dönem olarak denetleniyor; eksik/çelişkili/açık
  uçlu tarihler tamamlanmıyor. Aynı TÜFE analizinin aylık+yıllık çıktılarının
  birlikte istenebildiği prompt'ta netleştirildi. İki yıl sorusu doğru planla
  eski Python karşılaştırmasına eşit; canlı model düzeltmesi kanıtlanmadı.
- İki Economic HTTP yolunda Server-Timing toplam/plan istemci sürelerini,
  X-Analytics-Model-Decision yalnız izinli model karar başlığını gösteriyor.
  JSON sözleşmesi, model/uygulama ayrımı, hesaplar, hash denetimleri, tek çağrı
  ve retry 0 korunuyor; ham yanıt/soru/anahtar/yol başlıklara eklenmiyor.
- Odaklı testler 508 passed. Son kodda tek `scripts.verify_project`: 4/4,
  pytest 1413 passed, 1 skipped; Housing 9/9, Economic 45/45, canlı 0;
  diff-check temiz. Günlük out/verification/20261026T153938Z-2-5aaf8bbd.
- Sonraki adım: bağımsız PR incelemesi. Gerçek ekran reddinin kaynağı ve
  yavaşlığın aşaması başlıklarla görülebilir; yeni canlı deneme yapılmadı.
  Bu kayıt canlı başarı veya hız artışı iddiası değildir.

## LLM şemalı planlama ve güvenli teşhis — 26 Ekim 2026

- Dal `fix/llm-thinking-and-probe`, başlangıç `main` `a57c65a`.
- İstemci `LLM_REASONING_EFFORT` boşken eski isteği korur; low/medium/high açıkça
  seçilebilir. `ask_llm` geçici frozen ayarları da kabul eder; retry hâlâ 0.
- `python -m scripts.smoke_test_llm --probe --reasoning-effort low --timeout-seconds 60`
  yalnız tek kısa üretim isteğidir. Analiz çalışmaz; timeout aşaması yalnız izinli
  türlerden aktarılır. Anahtar/URL/ham hata/yanıt yazdırılmaz; ortam geri yüklenir.
- Economic canlı raporu timeout/reasoning/retry ve response_format ayarlarını
  kaydeder. Hesaplar, guard, vaka beklentileri ve HTTP sözleşmeleri korunur.
- İlk SDK/CLI/evaluator: **143 passed**. İlk offline `scripts.verify_project`:
  **1364 passed, 1 skipped**, Housing **9/9**, Economic **45/45**, canlı **0**;
  günlük `out/verification/20261025T170455Z-2-e2644db7` (Git dışında).
- Gemini anahtarı bu ortamda yok; önceki 3.8 / 60–120 sn timeout'larının
  kök nedeni çözülmüş sayılmıyor.
- Aynı dalda ek teşhis: kullanıcının 3.5 Flash-Lite / low EQ-038 denemesi
  `invalid_plan` döndürdü; filtre çağrısı 0. Önceki evaluator geçersiz yanıtın
  biçim/alan hatasını saklamadığından o yanıt sonradan geri alınamıyor.
  `invalid_plan_diagnostics` yalnız kapalı biçim/hata türlerini ve bilinen şema
  alanlarını kaydeder; metin/değer/bilinmeyen alan adı yazılmaz. Yanıt onarılmaz.
  Ek odaklı evaluator 81 passed; o sürümde offline doğrulama 1370 passed,
  1 skipped, Housing 9/9, Economic 45/45, canlı 0
  (`out/verification/20261025T185657Z-2-5c5798db`).
- Önceki yerel kullanıcı teşhisi: EQ-038 / 3.5 Flash-Lite / low, tek deneme,
  `invalid_plan_diagnostics.format=code_fence_prefix`, filtre 0. Model yanıtı
  gelmiş, Markdown öneki yüzünden katı JSON doğrulamasında reddedilmiş; içerideki
  planın doğruluğu bu kayıttan bilinmiyor. Eski 3.8 timeout/5xx ayrı hata türüdür.
- Önceki PR #116 kodu b08ba30: `ask_economic_plan`, mevcut Pydantic karar şemasını
  nesne kökü + anyOf/$defs ile `response_format=json_schema`, strict=true gönderdi.
  Doğrudan servis, iki HTTP yolu ve canlı evaluator CLI bu tek fonksiyonu kullanır.
  Evaluator CLI başlangıçta okunan frozen ayarları isteğe de geçirir. Normal
  `ask_llm`, Housing/anlatım ve kısa probe şemasız eski sözleşmeyi korur.
- Kod bloğu soyma, alan/koşul onarma, metin modu fallback'i, otomatik retry veya
  model değişimi yok. Şema reddinde tek güvenli hata; planlar ayrıca mevcut
  Python kontrollerinden geçer. Odaklı istemci/servis/iki API/evaluator 423 passed.
- b08ba30 kodunda tek `scripts.verify_project`: **4/4**, pytest **1383 passed,
  1 skipped**, Housing **9/9**, Economic **45/45**, canlı **0**; diff-check temiz.
  Kayıt `out/verification/20261025T193553Z-2-44d7c934` (Git dışında).
- Mustafa'nın b08ba30 üzerindeki tek 3.5/low/60 sn denemesi yine invalid_plan:
  json_object, missing + extra_forbidden, filtre 0; yerel rapor
  out/economic-question-eq038-schema-20261025-225915-487.json.
  Bu kayıt hangi alanın eksik/fazla olduğunu ve başlığı ayırmıyor; ham yanıt
  saklanmadığından seçilen dal veya sağlayıcının uyumsuzluk nedeni kanıtlanmış değil.
- Aynı dalda sağlayıcı şeması artık EconomicModelResponse: kökte union içermeyen
  sekiz zorunlu alan, kullanılmayanlar açık null. Prompt aynı taşıma biçimini ister.
  Ortak parser taşıma tipini, sonra yalnız bilinen null alanları çıkararak mevcut
  karar tipini doğrular. Dolu ilgisiz alan atılmaz; eksik alan/koşul tamamlanmaz.
  Eski yalın kararlar, Python guard'ları ve HTTP yanıtları korunur. Evaluator
  actual_model_decision alanı aynı parser'ın kararını gösterir; guard sonucu ile
  değiştirilmez. Teşhis missing_fields/extra_fields ve izinli karar başlığını ayırır.
- Son odaklı paket 432 passed: gerçek SDK/sahte HTTP ile dört analiz türü,
  netleştirme/unsupported; düz ve dosya HTTP yolları; eksik/null/karışık alan,
  bool/metin eşik, yanlış koşul ve güvenli hata regresyonları. Gerçek çağrı 0.
- Son kodda tek `scripts.verify_project`: **4/4**, pytest **1392 passed,
  1 skipped**, Housing **9/9**, Economic **45/45**, canlı **0**, diff-check temiz.
  Kayıt `out/verification/20261025T201631Z-2-033595aa` (Git dışında).
  Son prompt kontrolünde karşılaştırmanın diğer alanları da açık null yazması
  netleştirildi; taşıma şeması ile eski "yalnız iki alan" ifadesi ayrıştırıldı.
- 26 Ekim yerel canlı kanıtı (uygulama kaynağı 51a736a): 3.5 Flash-Lite, low,
  timeout 60 sn, retry 0. Önce EQ-038 tek denemede passed, filtre 1; rapor
  out/economic-question-eq038-flat-20261026-091820-323.json. Sonra toplam 3
  denemede EQ-040 passed (yalnız 2021-06), EQ-041 passed (2021-02 ve 2021-06),
  EQ-043 failed/model_decision_mismatch; rapor
  out/economic-question-filter-final-20261026-100033-771.json, exit 1.
- EQ-043 model kararı yanlış ready/housing_rate_down_real_credit_not_up /
  2021-01–2021-06; uygulama doğru clarification_required/metric_ambiguous,
  filter_calls 0. Kodun guard akışı bu kararı analizden önce döndürür. Model
  başarısı olarak işaretlenmez: dört seçili vakada model 3 doğru/1 hatalı;
  uygulama kararları beklentiye uydu, katı dört-model-kararı kabulü tamamlanmadı.
  Genel başarı oranı değildir. Mevcut EQ-022 regresyonu aynı nominal/reel
  varsayımı hata türünü kapsar; test veya prompt değişikliği yapılmadı.
- Kanıt kullanıcının terminal çıktısıdır; yerel JSON/hash burada bağımsız
  açılmadı/doğrulanmadı. Eski raporlar ve vaka beklentileri korunur. Bu oturumda
  canlı çağrı 0; yalnız bu devir kaydı güncellendi, tam test paketi tekrarlanmadı.
- Önerilen sonraki adım: bu bilinen model sınırlamasıyla bağımsız PR incelemesi;
  uygulama davranışı ve ham model doğruluğu ayrı değerlendirilmeli. Yeni model
  çağrısı veya dört-model-kararı kabulünün tamamlandığı iddiası yok. Uygulayan
  oturum kendi PR'ını merge etmez; release yapılmadı.

## #110 TÜFE karşılaştırma grafik ve offline HTML — 25 Ekim 2026

- Branch: feat/inflation-comparison-report; başlangıç main b82b653.
- Üç panelli, altı trace içeren grafik ve internetsiz HTML raporu hazırlandı.
- Hesaplamalar mevcut InflationComparison evidence üzerinden alınıyor.
- Sentetik 2023-2024 HTML raporu out/inflation-comparison/sample.html altında üretildi.
- Odaklı testler: 40 passed. Tarayıcıda görsel kontrol henüz yapılmadı.
- API/UI/evaluator değiştirilmedi; canlı LLM/EVDS çağrısı yapılmadı.
- Sonraki adım: tam offline doğrulama, commit, push ve Issue #110 için tek PR. Merge/release yok.

## #111 ön kontrollü tek komut yerel uygulama başlatıcısı — 24 Ekim 2026

- Sorumlu: Osman (@OsmanerdemDutar). Dal `feat/local-app-launcher`; güncel `origin/main`
  `e67df98` üzerinden açıldı.
- `scripts/run_local_app.py` eklendi (`python -m scripts.run_local_app [--mode preview|model] [--data-root <yol>] [--port 1..65535] [--check-only]`):
  - Üst düzeyde yalnız Python standart kütüphanesi ve stdlib-only `scripts.check_local_setup`
    kullanılır; `uvicorn`, `scripts.preview_question_ui` ve `app.api.main` ancak ön
    kontroller başarılı olduğunda ve `--check-only` verilmediğinde tembel (lazy) import edilir.
  - `run_diagnostics`, `resolve_data_root` ve `format_human_report` yeniden yazılamadan
    doğrudan kullanılır; `--data-root > süreç ANALYTICS_DATA_ROOT > yerel .env > repo kökü`
    önceliği korunur.
  - Varsayılan `--mode preview` anahtarsız çalışır (`create_preview_app`, yalnız 3 sabit
    örnek); `--mode model` (`create_app`) yerel LLM ayarları eksik veya geçersizse
    sunucuyu başlatmadan `exit 1` ile durur. Geçersiz `--mode`/`--port` veya bilinmeyen
    argümanlar `exit 2` döndürür.
  - `--check-only` ön kontrolleri ve seçilen modun hazırlık özetini yazdırır; sunucu,
    socket bind, tarayıcı veya sağlayıcı çağrısı başlatmadan (`0` çağrı) uygun çıkış
    koduyla (`0` veya `1`) sonlanır.
  - Sunucu yalnız `127.0.0.1` üzerinde çalışır; seçilen veri kökü sunucu ömrü boyunca
    süreç `ANALYTICS_DATA_ROOT` değişkenine uygulanır ve kapanışta, `Ctrl+C`'de veya
    hatada eski değer/eksiklik durumuna geri yüklenir (`.env` ve `LLM_*` değiştirilmez).
    Dolu portta başka süreç öldürülmez veya başka porta geçilmez (`exit 1`).
- `tests/test_run_local_app.py`: **18 passed** (hatalı argümanlarda `exit 2`, `--check-only`
  sıfır socket/sunucu/model, `preview` ve `model` fabrika/dependency ayrımı, 4 kademeli
  veri kökü önceliği ve sunucuya taşınması, dolu port ve `Ctrl+C` ortam geri yükleme,
  bozuk veri/uyumsuz ortam ve boş `--without-pip` venv subprocess testi, ayrıca `127.0.0.1`
  yerel loopback üzerinde `GET /health` ve `GET /` HTTP 200 subprocess smoke testi;
  harici ağ/LLM/EVDS çağrısı **0**).
- `README.md` Windows/Linux başlatma ve `--check-only` örnekleriyle güncellendi.
- Tam çevrimdışı doğrulama (`scripts.verify_project`): **1297 passed**; Housing
  **9/9**, Economic **45/45** stub değerlendirme, canlı çağrı **0**,
  `git diff --check` temiz (`out/verification/20261024T095622Z-47232-13276454`).

## #107 evaluator sağlayıcı hata kodu — 24 Ekim 2026

- Dal `fix/eval-provider-error-code`; `main` `e67df98` üzerinden açıldı. Eski canlı
  raporlar korundu; canlı LLM/EVDS çağrısı yapılmadı.
- `scripts/evaluate_economic_questions.py` canlı `model_call` sarmalayıcısı
  `LLMRequestError`'ı servisin `EconomicPlanningError` dönüşümünden önce yakalıyor.
  Yalnız izinli kodlar (`timeout`, `authentication_failed`, `access_denied`,
  `rate_limited`, `connection_failed`, `invalid_response`, `provider_unavailable`,
  `request_rejected`, `provider_error`) `provider_error_code` alanına yazılıyor;
  bilinmeyen kod ve diğer istisnalarda değer `null`. İstisna yeniden yükseltiliyor;
  mesaj, ham sağlayıcı gövdesi, anahtar, URL veya traceback rapora girmiyor.
- HTTP sözleşmesi, servis, istemci, prompt, hesaplar, guard'lar, fixture'lar ve
  beklentiler değişmedi. Sahte sağlayıcı testleri farklı güvenli kodları, sır
  sızmamasını, ilk hatada durmayı, başarısız denemenin bütçeye sayılmasını ve sıfır
  analiz çağrısını doğruluyor.
- Odaklı `tests/test_economic_question_evals.py`: **74 passed**. Tek
  `scripts.verify_project`: **1282 passed, 2 skipped**; Housing **9/9**, Economic
  **45/45**, canlı çağrı **0**, diff-check temiz
  (`out/verification/20261024T134723Z-21620-6220df15`).
- Merge/release yapılmadı; sonraki adım bağımsız inceleme ve CI sonucudur.

## #107 EQ-038 canlı planlama düzeltmesi — 24 Ekim 2026

- Dal `fix/housing-filter-planning`; güncel `main` `be81ad7` üzerinden açıldı.
  Canlı rapor `out/economic-question-eval-107-live.json` değiştirilmedi.
- Kök neden: EQ-038 için model doğrudan `unsupported / unsupported_analysis`
  döndürdü; `python_blocked_ready_plan=false` ve filtre/analiz çağrısı 0.
  Ret Python guard'dan değil, ham model planından geldi.
- `build_economic_question_prompt` yalnız netleştirildi: sayısal eşiksiz
  artan/artmayan/azalan/azalmayan yönleri `gt/lte/lt/gte 0.0`; iki metrik
  koşulu tek `housing_condition_filter` planı; "iki analiz" kuralının bu
  koşulları kapsamadığı belirtildi. Hesaplar, guard, fixture ve beklentiler değişmedi.
- Odaklı Economic/API/evaluator/filtre paketi **310 passed**. Tek
  `scripts.verify_project`: **1277 passed, 2 skipped**; Housing **9/9**,
  Economic **45/45**, canlı çağrı **0**, diff-check temiz
  (`out/verification/20261023T213613Z-20180-07d7c6cc`).
- Gerçek modelle yeniden canlı koşu yapılmadı; EQ-038 düzeltmesinin model
  davranışına etkisi doğrulanmadı. Sahte model testleri bunun kanıtı değildir.

## #107 konut filtresi kabul vakaları — 22–23 Ekim 2026

- Dal `test/housing-filter-acceptance`; `origin/main` `8119e1d` (PR #106 merge)
  üzerinden açıldı, inceleme sonrası güncel `origin/main` `d5fd045` normal merge
  ile alındı. Çakışan handoff kaydında Afra #99/#102 ve Osman #100 bölümleri
  birlikte korundu; force-push yok. Runtime/prompt/API/UI değişmedi.
- `evals/fixtures/economic-housing-filter.json` eklendi: yalnız sentetik konut
  girdisi, 2021-01–06 altı ay, `synthetic://` kaynakları. Mevcut dört fixture
  değişmedi.
- Mevcut evaluator genişletildi: fixture seçimi/`_payload`/`FIXTURES`/hash zinciri
  yeni fixture'ı biliyor; `EconomicSuite` üst sınırı 45. Eski 37 vakanın
  soru/plan/beklenti/gerekçesi değişmedi. EQ-038–045 eklendi: dört olumlu
  `housing_condition_filter` planı, üç netleştirme ve bir unsupported OR isteği.
  Eşleşen aylar uygulamadan kopyalanmayan sabit oracle olarak tutuldu.
- Odaklı servis/API/dosya/filtre/evaluator paketi **391 passed**. Odaklı
  regresyonlar altı gözlem ve tek filtre çağrısını, negatiflerde sıfır analizi,
  yanlış yön/eşik/eksik sınır ve eksik kredi yönlü legacy ready planlarının
  başarısız kalmasını, sahte sağlayıcıda iki denemede ilk hatada durmayı kontrol
  eder. Canlı LLM/EVDS/ağ çağrısı yapılmadı.
- PR #109 inceleme bulgusu düzeltildi: yalnız `housing_condition_filter`
  karşılaştırmasında AND koşullarının sırası önemsiz. Normalizasyon koşul
  listesini yalnız karşılaştırma için sıralar; koşul çokluğu, metrik/operator/
  eşik (evidence'da birim) ve diğer alanlar katı karşılaştırılır. Ham
  model/application/evidence değerleri raporda değiştirilmez, eşik yuvarlanmaz.
- Sahte sağlayıcı regresyonları EQ-038/EQ-040/EQ-041 için yalnız ters koşul
  sırasının geçtiğini ve sonraki vakanın çalıştığını; yanlış yön/eşik/metrik,
  eksik/fazla/tekrarlı koşulların sıfır analizle başarısız kaldığını; çağrı
  bütçesinin vaka başına tek çağrıda durduğunu doğrular. Odaklı evaluator
  paketi **69 passed**. Canlı LLM/EVDS/ağ çağrısı yapılmadı.
- Tek `scripts.verify_project`: **1276 passed, 2 skipped**; Housing **9/9**,
  Economic **45/45**, canlı çağrı **0**, `git diff --check` temiz
  (`out/verification/20261023T182752Z-5108-8352359a`). Bunlar
  `harness_behavior_only` stub sonuçlarıdır; model anlama/kabul metriği değildir.
- Canlı koşu komutu yalnız PR açıklamasında öneri olarak hazırlanır; çalıştırma
  yoktur. PR [#109](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/109)
  bağımsız incelemeye açık kalır; bu oturum merge yapmaz.

## #99 bağımsız ekonomik kullanıcı kabul seti — 22 Ekim 2026

- Sorumlu: Afra (@afratopcu).
- Dal: `test/economic-user-acceptance-99`; başlangıç main commit'i:
  `f3a15a8051fae6784b44ef15c62a9c382ccd3647`.
- `evals/economic_user_acceptance_cases.json` ve
  `docs/economic-user-acceptance.md` hazırlandı.
- Toplam 48 bağımsız vaka: 8 konut, 8 TÜFE, 8 iki tam yıl
  karşılaştırması, 8 netleştirme, 8 kapsam dışı,
  4 parametreli konut filtresi ve 4 çok turlu devam sorusu.
- Yerel kontrol: 48/48 vaka, benzersiz kimlikler, kategori dağılımı,
  analysis_id, dönem ve yıl sırası doğrulandı; `git diff --check` temiz.
- Mevcut 37 Economic ve 9 Housing vakası, evaluator, runtime,
  API, UI ve CI değiştirilmedi. Canlı LLM/EVDS çağrısı yapılmadı.
- Kabul setinin `planned` etiketleri başlangıç commit'i `f3a15a8`
  için geçerlidir; güncel `main` özellik envanteri değildir.
  #104/#106 sonrasında konut filtreleme uygulamaya eklendi.
  EUA-041–044 için canlı model başarısı iddia edilmez; çok turlu
  devam soruları hâlâ geleceğe yönelik kabul beklentisidir.
- PR #102 ilk teslim commit'i `6f3ce9c` ile açıldı; ilk head'in
  zorunlu Python 3.12 CI kontrolü başarılıydı.
- Bağımsız incelemede istenen güncel `main` birleştirmesi
  `d87103e` merge commit'iyle tamamlandı. #99 ve #105
  handoff kayıtları birlikte korundu.
- Sonraki adım: belge düzeltmelerini doğrulayıp aynı PR #102'ye
  commit/push etmek ve yeni head'in CI sonucunu kontrol etmek.
  Canlı LLM/EVDS çağrısı, release veya uygulayan tarafından
  PR merge işlemi yapılmayacak.

## #100 çevrimdışı yerel kurulum ve veri paketi teşhis komutu — 22 Ekim 2026

- Dal `feat/check-local-setup`; güncel `origin/main` `dcd5814` üzerinden açıldı,
  sonrasında `8119e1d` (PR #106 merge) normal merge ile birleştirilerek tüm
  benzersiz README/handoff kayıtları korundu.
- `scripts/check_local_setup.py` eklendi (`python -m scripts.check_local_setup [--data-root <yol>] [--json]`):
  - Giriş, `argparse`, Python 3.12 ve `requirements.txt` paket/sürüm kontrolleri
    yalnız standart kütüphane ile çalışır; üçüncü parti (`dotenv`, `pandas`,
    `pydantic` vb.) ve `app.*` modülleri ancak ortam uygun (`python` ve
    `dependencies` `ok`) olduğunda tembel (lazy) import edilir. Uygun olmayan
    ortamda veri/model kontrolleri `status: skipped`, `code: not_run` olarak
    raporlanır (`preview_ready: false`, `exit 1`, traceback yok).
  - `_check_dependencies`, paket pinlerini doğrudan `requirements.txt` kaynağından
    okur ve kurulu sürümleri hem ana sürüm (`major_version_mismatch`, örn.
    Pydantic `1.10.0` vs `2.13.5`) hem de tam pin (`pin_mismatch`) düzeyinde
    karşılaştırır (`incompatible_dependencies`); kurulum veya ortam değişikliği
    yapmaz.
  - Veri kökü seçiminde `--data-root > süreç ANALYTICS_DATA_ROOT > yerel .env > repo kökü`
    önceliğini uygular; süreç ortamını `.env` ile ezmez ve boşluklu Windows yollarını
    destekler.
  - Gerçek dosya doğrulamasını yeniden yazmadan `VerifiedHousingQuestionPaths`,
    `load_verified_question_inputs` ve `derive_economic_coverage` ile tam
    Bronze/makbuz/hash/Silver zincirini denetler; BDDK, TÜFE ve konut kapsamı için
    satır/dönem sayılarını doğrulanmış snapshot'tan dinamik üretir.
  - LLM ayarını yalnız yerel `read_llm_settings()` ile denetler; sağlayıcıya ağ
    isteği göndermez, `Ayar mevcut; sağlayıcı erişimi denenmedi` ile canlı erişim
    arasındaki farkı korur (`live_model_access_verified: false`), anahtar veya ham
    `.env`/hata gövdesi sızdırmaz.
  - Veri ve çalışma zamanı uygunsa LLM anahtarı olmasa da `preview_ready: true` ve
    çıkış kodu `0` döner (`llm_not_configured` / `llm_config_invalid` yalnız uyarıdır);
    eksik/bozuk veri veya zorunlu ortam hatasında çıkış kodu `1` döner.
- `tests/test_check_local_setup.py`: **26 passed** (geçerli sentetik paket, boşluklu
  yol, dinamik dönem/satır üretimi, 4 kademeli veri kökü önceliği, 14 eksik/bozuk
  veri ve Bronze hash senaryosu, `python -S` ve boş `--without-pip` sanal ortam
  subprocess testleri, `requirements.txt` ana sürüm ve pin uyuşmazlığı testleri,
  LLM ayar varyasyonları, gizli değer sızdırmama ve sıfır ağ/model/analiz çağrısı).
- Yerelde mevcut gerçek teslim paketi (`out/issue-076 setup/delivery/inputs`,
  boşluklu yol) üzerinde tek çevrimdışı teşhis koşusu doğrulandı: `exit 0`,
  `preview_ready: true`, BDDK/TÜFE/konut kapsamı 66 ay (`2021-01`–`2026-06`).
- `README.md` kullanım ve bilinen teşhis kodları tablosuyla güncellendi. Uygulama
  HTTP sözleşmesi, UI, ekonomik planlama/hesaplar ve bağımlılıklar değişmedi.
- Tam çevrimdışı doğrulama (`scripts.verify_project`): **1245 passed**; Housing
  **9/9**, Economic **37/37** stub değerlendirme, canlı çağrı **0**,
  `git diff --check` temiz (`out/verification/20261022T201838Z-42824-f5b4b164`).

## #105 parametreli konut filtresini soru/API/ekran akışına bağlama — 22 Ekim 2026

- Dal `feat/housing-filter-question`; güncel `origin/main` `dcd5814` (PR #104
  merge) üzerinden açıldı. #103 çekirdeği yeniden kullanıldı; hesaplar
  kopyalanmadı. Afra #99 ve Osman #100 kapsamına dokunulmadı.
- Yeni `housing_condition_filter` planı `EconomicHousingFilterReadyPlan` olarak
  eklendi: açık dönem + 1–3 AND koşulu. Mevcut dört metrik ve `lt/lte/gt/gte`
  operatörleri strict/frozen Pydantic ile korunuyor. Eski
  `housing_rate_down_real_credit_not_up` sözleşmesi değişmedi.
- `app/services/housing_filter_question.py`, modelin şema-geçerli ama
  niyet-dışı planını analizden önce durduran dar bir guard ekliyor. Yüzde puan
  ile `%` ayrımı, faiz seviyesi/değişimi, reel/nominal belirsizliği, OR,
  sıralama/top-N, ortalama/yıllık/toplam, tahmin/nedensellik ve kapsam dışı
  metrikler reddediliyor; açık “reel ve nominal” iki koşul olarak korunuyor.
  Eksik/uyuşmayan dönem `period_required`, kapsam dışı dönem
  `outside_coverage`; bu durumlarda analiz 0 kez çalışıyor.
- Normal `/analysis/economic/question` ve `/files` yolları yeni evidence tipini
  döndürüyor; `/files` doğrulanmış kaynak/sınırlama notlarını koruyor. Ekran
  koşul özeti ve eşleşen ay tablosu gösteriyor, yeni grafik üretmiyor; eski
  `.chart` temizleniyor. `docs/economic-question.md` ve README plan/guard/HTTP/UI
  kapsamıyla güncellendi.
- Offline evaluator filtre referansını, `filter_calls` sayacını ve beklenen
  çağrı sayılarını biliyor. 37 vaka tek tek incelendi; yalnız gerçekten yeni
  yetenekle desteklenen `EQ-025` filtre ready vakasına çevrildi. Diğer
  `unsupported`/netleştirme beklentileri değişmedi. Dağılım: 13 ready,
  13 clarification, 9 unsupported, 2 data_unavailable. Yanlış filtre eşiği
  regresyonu ham model kararını başarı saymıyor ve filtre çağrısının 0 olduğunu
  doğruluyor.
- Odaklı: `test_housing_filter_question.py` **28 passed**; ekonomik
  servis/API **187 passed**; dosya API **70 passed**; UI **5 passed**; evaluator
  kontrol testleri **36 passed**. Tek `scripts.verify_project`:
  **1185 passed, 2 skipped**; Housing **9/9**, Economic **37/37**, canlı çağrı
  **0**, `git diff --check` temiz
  (`out/verification/20261022T163736Z-18468-172992c8`). Bu sonuçlar
  `harness_behavior_only` stub kapsamıdır; canlı model/EVDS kabulü değildir.
- PR [#106](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/106)
  açıldı; ilk kod commit'i `127d488`. Bağımsız incelemede duruldu. Merge, release ve
  canlı LLM/EVDS çağrısı yapılmadı.
- Bağımsız incelemedeki dört P1 bulgu aynı dalda düzeltildi (`e839935`):
  `altında olmayan` gibi negasyonlar ters operatöre çevriliyor; aynı metrikteki
  iki sınır birlikte korunuyor; `azalışı %2'yi aşan` gibi ifadeler `lt -2`
  işaretli değişime dönüşüyor. Takip incelemesinde legacy varsayımsal
  `implicit_credit_not_up` fallback'i kaldırıldı (`b2082f6`): eski
  `housing_rate_down_real_credit_not_up` planı yalnız iki koşul açıkça
  istendiğinde kabul ediliyor; kredi değişim yönü belirtilmemişse
  `question_ambiguous` dönüyor ve servis, normal HTTP, verified `/files`
  yollarında analiz **0** kez çalışıyor. Eski testlerdeki eksik koşullu başarı
  beklentileri netleştirme/negatif regresyonlara ayrıldı; dispatch soruları açık
  iki koşulla yazıldı; `faiz düşerken reel stok artmayan` örnekleri çalışmaya
  devam ediyor.
- Son inceleme düzeltmeleri odaklı paketi **358 passed**. Tek
  `scripts.verify_project`: **1217 passed, 2 skipped**; Housing **9/9**,
  Economic **37/37**, canlı çağrı **0**, `git diff --check` temiz
  (`out/verification/20261022T192936Z-18144-b40895b5`). Önceki `e839935`
  koşusu **1211 passed, 2 skipped** idi
  (`out/verification/20261022T172113Z-3196-c8f3f507`). Bunlar
  `harness_behavior_only` stub kapsamıdır; canlı model/EVDS kabulü değildir.
  Review thread'leri bağımsız incelemeye bırakılır; merge/release yok.

## #103 parametreli konut koşulu filtreleme çekirdeği — 22 Ekim 2026

- Dal `feat/housing-condition-filter`; güncel `origin/main` `4aecee0`
  (PR #101 merge) üzerinden açıldı. Afra #99 ve Osman #100 kapsamına dokunulmadı.
- `app/services/housing_filter.py` eklendi. `run_housing_filter()` normalize
  BDDK/EVDS satırlarını mevcut `build_housing_gold_table()` ile tam bir kez
  işler; reel kredi, değişim ve birleştirme formülleri tekrarlanmaz. Yalnız
  dört metrik ve `lt/lte/gt/gte` operatörleri, 1–3 AND koşulu izinlidir.
  Koşullar strict/frozen Pydantic ile Gold hesaplayıcısından önce doğrulanır;
  bool/metin/NaN/Infinity, bilinmeyen metrik/operatör ve fazladan alan reddedilir.
- Filtre tüm Gold aylarını kendi koşullarıyla değerlendirir; eski
  `rate_down_real_credit_not_up` bayrağı ön filtre değildir. Null değerli ay
  değerlendirilemez/eşleşmez, ilk ay yalnız faiz seviyesi koşuluyla eşleşebilir.
  Sonuç açık dönemi, koşul/birimleri, gözlem/değerlendirilebilir/eşleşme
  sayılarını, kronolojik dönemleri, eşleşen Gold değerleri/kaynak/kalite
  notlarını taşır; NaN/Infinity yoktur. Boş eşleşme başarılı sonuçtur.
- `tests/test_housing_filter.py`: **28 passed**. Dört operatör, eşik eşitliği,
  pozitif/negatif/kesirli eşik, 1–3 AND, tek ay, sıfır eşleşme, null/ilk ay,
  eski fonksiyon eşdeğerliği, geçersiz koşulda builder'ın 0 kez çalışması,
  geçerli koşulda tam 1 kez çalışması, girdi/kaynak değişmezliği, kronoloji ve
  JSON güvenliği sınanır.
- Odaklı komşu paket **69 passed**. Tek `scripts.verify_project`:
  **1152 passed, 2 skipped**; Housing **9/9**, Economic **37/37**, canlı çağrı
  **0**, `git diff --check` temiz
  (`out/verification/20261022T143352Z-2952-ff70a813`). Mevcut analiz/API
  beklentileri değişmedi.
- Kapsam yalnız deterministik çekirdektir: LLM planlama/`analysis_id` dispatch,
  HTTP/ekran/grafik, OR/sıralama/top-N ve yeni bağımlılık yok. PR
  [#104](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/104)
  bağımsız incelemeye bırakıldı; merge/release ve canlı LLM/EVDS çağrısı
  yapılmadı.

## Issue #98 doğal dönem çözümleme — 22 Ekim 2026 (PR #101)

- Etkin dal `feat/natural-question-periods`; `main` `f3a15a8` üzerinden açıldı.
- `app/services/question_periods.py` eklendi: tam yıl, çeyrek, yarıyıl, kapalı
  adlandırılmış aralık, ay noktası ve tam gün aralığı çözümlemesi; artık/çelişkili
  tarih denetimi. `app/services/economic_question.py` ortak ayrıştırıcıya bağlandı,
  model istemi güncellendi. Eksik veya varsayılabilecek dönem yine
  `period_required` döndürüyor.
- Ayrıştırıcı, servis, normal API ve doğrulanmış dosya API regresyon testleri
  eklendi; kabul edilen biçimler `docs/economic-question.md` içinde belgelendi.
  Mevcut değerlendirme vakaları değiştirilmedi.
- Bağımsız inceleme bulguları düzeltildi: kısmi karşılaştırma niyeti cümle
  konumundan bağımsız `unsupported`; ISO/sayısal gün sınırları ve ters yıl
  aralığı reddediliyor; `2023 yılında Ocak-Mart` yıl bağlamıyla 2023-01–03
  çözülüyor; çıplak `Ocak ve Mart` listesi aralığa dönüşmüyor, `Ocak ve Mart
  arasında` aralık kalıyor. Yanlış planlarda servis ve iki HTTP yolunda analiz
  0 kez çalışıyor.
- Son inceleme düzeltmeleri: gün sınırı denetimi karşılaştırma yoluna da
  uygulanıyor; ay listesi/aralık ayrımı iki month-point fallback dahil tekrar
  eden yıllar ve tab/çoklu boşluklarda korunuyor; `2023 yılında` bağlamı açık
  `yılının tamamı`/`yılı boyunca` isteğinden ayrılıyor. Açık tam yıl ile dar
  dönem aynı yıl olsa bile `period_required`; analiz 0 kez çalışıyor.
- Odaklı çalışma: 308 test geçti. Tam çevrimdışı doğrulama başarılı:
  1124 geçti, 2 atlandı; Economic 37/37 ve Housing 9/9 stub değerlendirme;
  `git diff --check` temiz (`out/verification/20261022T133059Z-832-e660d4e0`).
  PR: https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/101.
  Aynı dala commit/push yapıldı; yeni head bağımsız incelemeye bırakıldı, bu dal
  birleştirilmedi ve canlı EVDS/model çağrısı yapılmadı.

## Portföy README düzenlemesi — 21 Ekim 2026

- Dal `docs/portfolio-readme`; başlangıç güncel `main` `56ffc46` (PR #96 merge).
- README girişi doğal dilde soru, sınırlı LLM planlama, Python hesapları, FastAPI
  ekranı, konut analizi, TÜFE özeti ve iki tam yıl TÜFE karşılaştırmasını anlatıyor.
  Normal model modu ile yalnız üç sabit örneği çalıştıran offline preview ayrımı
  kısa ve görünür. Gerçek veri paketinin Git'te olmadığı ve anahtarsız sentetik
  HTML örneğinin bulunduğu belirtildi. Kısa ekip katkıları bölümü Git geçmişiyle
  uyumlu; tarihli gerçek veri kabul kanıtları korundu ve tamamlanmış kontrolleri
  güncel engel gibi gösteren cümleler düzeltildi.
- Doğrulama: README'de 50 yerel bağlantı/başlık çözüldü, `git diff --check`
  temiz. Uygulama/test/CI kodu değişmedi; canlı çağrı, tarayıcı veya release yok.
- PR [#97](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/97)
  açık; bağımsız inceleme bekliyor. Bu oturum merge etmedi.

## #95 TÜFE grafiğini soru ekranına bağlama — 21 Ekim 2026

- Dal `feat/inflation-question-chart`; başlangıç güncel `origin/main` `98cbb9c`
  (PR #94 merge). Hesaplar ve `build_inflation_chart()` yeniden yazılmadı.
- `InflationQuestionAnalysis` yanıtına aynı evidence'dan üretilen mevcut üç
  panelli `chart` eklendi; bu yol hem normalize satırlı hem doğrulanmış dosya
  API'sinde ortak. Konut grafiği/alanları ve iki yıl karşılaştırması değişmedi.
- Soru ekranı TÜFE özetinde grafiği tablodan önce gösteriyor; yerel Plotly
  kullanılıyor. Analiz değişimi, netleştirme ve hatada tüm `.chart` düğümleri
  `Plotly.purge` ile temizleniyor. Grafik için ek model/veri çağrısı yok.
- Odaklı API/dosya/grafik testleri **109 passed**, UI **5 passed**. Tek
  `python -m scripts.verify_project`: **986 passed, 2 skipped**; Housing **9/9**,
  Economic **37/37**, canlı çağrı **0**, `git diff --check` temiz.
  Günlük: `out/verification/20261021T173151Z-25272-f1d27e4f/`.
- Gerçek paket `out/housing-acceptance-20261018/inputs` ile offline preview:
  Konut **60 ay/22 eşleşme**, TÜFE 2023 **12 satır + üç panel**, karşılaştırma
  **12+12 satır**, fark **-20,3941 yüzde puan**. Masaüstü ve gerçek 390 px CDP
  görünümünde panel/tablo eşleşmesi, hover/zoom/pan/reset, eski grafiğin
  temizlenmesi ve yatay taşma kontrol edildi. Görseller/rapor
  `out/issue-095-check/` altında, Git dışında.
- PR [#96](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/96)
  açık; kod head `e3a0167`. Merge bağımsız incelemeye bırakıldı. Canlı LLM/EVDS,
  yeni veri indirme, merge/release/tag değişimi yok. Kullanım notları README ve
  `docs/economic-question.md` içinde.

- Bağımsız inceleme düzeltmesi: grafik üreten yanıt dönüşümü iki endpoint'te de
  try bloğuna alındı; InflationChartError artık normalize istekte güvenli 422,
  dosya isteğinde güvenli 503 verir. İki HTTP regresyonu önce hatayı yeniden
  üretti; düzeltme sonrasında tek planlama denemesi ve ham ayrıntı gizliliği
  kontrol edilir. İnceleme ortamında odaklı API/dosya/grafik/UI paketi
  **115 passed, 1 skipped** (Chrome yok); yerel tam paket tekrarlanmadı.
  Yukarıdaki 986/2 ilk teslimindir; son head'in CI'si ayrıca doğrulanır.


## #81 TÜFE HTML raporu ikinci aşama — 21 Ekim 2026

- Dal `feat/inflation-html-report`; başlangıç güncel `origin/main` `efa22a7`
  (PR #93 merge). Grafik ve hesaplar yeniden yazılmadı.
- `app/tools/inflation_report.py` üç panelli mevcut grafiği, 12 aylık tabloyu,
  dönem/ilk-son özetini ve kaynak/yöntem metnini aynı evidence'dan üretir.
  Plotly.js gömülüdür; dinamik metinler escape edilir. Aylık, yıllık ve ilk-son
  oranları ayrı etiketlenir; null `—` ve açıklamayla gösterilir.
- `scripts/render_inflation_report.py` varsayılan sentetik üretim ve
  `--manifest/--root` ile doğrulanmış EVDS modu sunar. CSV, manifest
  doğrulamasından sonra okunan baytların hash'iyle bağlanır; BDDK gerekmez.
  Girdilerle çakışan çıktı reddedilir, yazma atomiktir.
- Kullanım: `docs/inflation-report.md`. Odaklı testler:
  `tests/test_inflation_report.py` + mevcut `tests/test_inflation_chart.py`.
- Gerçek yerel paket `out/housing-acceptance-20261018/inputs` ile 2023 raporu
  üretildi: 12 ay, ilk-son **%54,5003**, Aralık yıllık **%64,7729**. Headless
  Chrome'da masaüstü ve 390 px genişlikte üç panel, tablo, hover, zoom/pan/reset,
  kaynak/etiket görünürlüğü, harici kaynak yokluğu ve null `—` açıklamaları
  otomatik kontrol edildi; ekran görüntüleri görsel olarak da incelendi.
  Raporlar `out/` altında, Git dışında.
- Son doğrulama `scripts.verify_project` ile geçti: 986 test geçti, 2 atlandı;
  housing 9/9, economic 37/37, diff-check temiz. Soru ekranı/API entegrasyonu,
  canlı LLM/EVDS ve yeni bağımlılık yok. PR #94 açık; inceleme/merge bağımsız
  oturumda, `Closes #81`.

## #81 TÜFE grafiği ilk aşama — 21 Ekim 2026

- Dal `feat/inflation-chart`; başlangıç `origin/main` `f20bf4a`. Yalnız
  `app/tools/inflation_chart.py` ve `tests/test_inflation_chart.py` eklendi;
  HTML/CLI ve soru ekranı bu PR'ın kapsamı dışında bırakıldı.
- `build_inflation_chart(InflationEvidence)` üç panelli Plotly spec üretir:
  TÜFE endeksi (2025=100), aylık değişim (%) ve yıllık değişim (%). Değerler
  evidence sırasıyla ve tam hassasiyetle aktarılır; null'lar boşluk kalır;
  hover en çok dört ondalık gösterir. Tek ay ve tümüyle eksik yıllık geçmiş
  açıklanır; tutarsız dönem/satır/özet reddedilir. Hesaplama, sıralama veya
  doldurma yapılmaz.
- Odaklı `tests/test_inflation_chart.py`: **11 passed**. Tek
  `python -m scripts.verify_project`: **972 passed, 2 skipped**; Housing
  **9/9**, Economic **37/37**, canlı çağrı **0**, `git diff --check` temiz.
  Günlük: `out/verification/20261021T154724Z-19648-a71563e0/`.
- Sıradaki adım: PR'ın bağımsız incelenmesi. İkinci aşama (HTML/CLI ve gerçek
  EVDS kontrolü) ilk PR main'e alındıktan sonra ayrı dal/PR olarak ele alınır.
  Canlı LLM/EVDS, yeni bağımlılık veya veri indirme yok.

## PR #79 kalan belge birleştirmesi — 21 Ekim 2026

- Başlangıç dalı `docs/issue-76-local-setup`; uzak head `15515fa` yeniden
  doğrulandı. Güncel main `2b58e3c` (PR #92 merge) normal merge ile bu dala
  alındı; force-push veya toplu ours/theirs yok.
- README çakışmasında Osman'ın mevcut Python 3.12/.venv, ayrı çıkarma, `inputs`
  kökü ve boşluklu yol yönergeleri korundu; main'in üçüncü offline örneği
  (2023/2024 TÜFE karşılaştırması), 37 ekonomik vaka, #71/#87 kabulleri ve
  rc.1 sürüm kayıtları birlikte tutuldu.
- Devir notunda #91, #89 ve #88 kayıtları ile Osman'ın 20 Ekim tarihli kurulum
  kanıtı korundu. Görsel/runtime kanıtı `5bc12a7` üzerinde alınmış tarihli kayıt
  olarak kalır; bu head'de yeniden üretilmiş gibi sunulmaz.
- Doğrulama: yerel bağlantılar, PowerShell bloklarının sözdizimi ve
  `git diff --check`; belge değişikliği olduğu için tam yerel test tekrarı yok.
  Zorunlu PR CI'si bu commit/push sonrası son head üzerinden kontrol edilir.
- Uygulama/test/CI kodu değişmedi; yeni canlı LLM/EVDS çağrısı, veri indirme,
  merge veya release yok. Sıradaki adım güncel PR #79 head'inin bağımsız
  incelenmesi.

## #91 üç analizli offline ekran demosu — 21 Ekim 2026

- Dal `feat/three-analysis-offline-demo`; başlangıç güncel `origin/main` `244c44c`.
  `question.html` üçüncü örnek düğmesini (`TÜFE karşılaştırması · 2023 / 2024`) ve
  tam soruyu içeriyor; düğmeler yalnız alanı dolduruyor, istek/model çağrısı yok.
- `scripts/preview_question_ui.py::fixed_plan` bu tam soruya
  `cpi_two_year_comparison / first_year=2023 / second_year=2024` veriyor. Diğer
  sorular güvenli netleştirmede kalıyor. Offline etiket yalnız üç sabit örneğin
  desteklendiğini, serbest soruların normal yapılandırılmış model modu gerektirdiğini
  ve doğal dil anlama başarısı iddia etmediğini söylüyor. Renderer/hesap çekirdeği
  ve normal sunucu dependency override'ı değişmedi.
- Odaklı `tests/test_question_ui.py` **5 passed** (üç plan, üç düğme/otomatik
  gönderim yok, normal/offline metni, tarayıcı akışı). Tek
  `python -m scripts.verify_project`: **961 passed, 2 skipped**; Economic stub
  **37/37**, Housing stub **9/9**, canlı çağrı **0**, `git diff --check` temiz.
  Günlük: `out/verification/20261021T144946Z-10136-536a0231/`.
- Gerçek paket `out/housing-acceptance-20261018/inputs` ile Chrome'da üç örnek
  birer kez denendi: Konut 60 ay/22 eşleşme, TÜFE 2023 12 satır, karşılaştırma
  2023→2024 sırası ve 12+12 satır, fark **-20,3941 yüzde puan**. Ekran görüntüleri
  `out/three-analysis-check/example-{1,2,3}.png`, DOM/JSON log aynı dizinde.
  Bu çıktılar Git dışındadır; canlı LLM/EVDS çağrısı yapılmadı.
- Sonraki adım: [#92](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/92)
  PR'ının bağımsız incelenmesi ve birleştirme kararı. Bu oturum merge/release yapmadı.

## #89 iki yıl TÜFE karşılaştırmasını offline değerlendirmeye ekleme — 21 Ekim 2026

- Dal `feat/inflation-comparison-evals`; başlangıç `origin/main` `31b1711`. Evaluator
  artık `EconomicComparisonReadyPlan` için `compare_inflation_years` referansını, her
  yılın 12 gözlemini ve elle hesaplanan Aralık oranı/fark sabitlerini doğruluyor.
  Konut/TÜFE/karşılaştırma üst düzey çağrıları ayrı sayılıyor; reddedilen istekte üçü de sıfır.
- `evals/economic_question_cases.json` eski 28 vakayı koruyarak 37'ye çıktı; iki küçük
  sentetik karşılaştırma fixture'ı eklendi. Önceki Aralık yokluğu null, seçilen yıl
  içindeki eksik ay red olarak ayrı sınanıyor. EQ-026 unsupported kaldı.
- Tek `python -m scripts.verify_project`: **956 passed, 2 skipped**; Economic stub
  **37/37**, Housing stub **9/9**, canlı çağrı **0**, `git diff --check` temiz.
  Rapor: `out/verification/20261021T122540Z-20544-d8628610/`.
- Sonraki adım: bağımsız inceleme ve PR birleştirme kararı. Bu oturum merge/release yapmadı.

- Bağımsız inceleme düzeltmesi: EQ-032 (aynı yıl) ve EQ-034 (yıl yok) artık hatalı
  ready planı kabul edilen model yanıtı saymıyor; offline stub netleştirme istiyor.
  İki sahte sağlayıcı regresyonu Python engelini model başarısından ayırıp ilk hatada
  durmayı kontrol ediyor. Yukarıdaki 956/2 sonucu ilk teslimindir; düzeltme sonrası
  zorunlu CI sonucu güncel PR head'i üzerinden ayrıca kontrol edilmelidir.

## #88 eski yayın ve canlı kabul belgelerini PR #74'te uzlaştırma — 21 Ekim 2026

- Bu bölüm güncel durumdur; altındaki tarihli kayıtlar kaynak kanıtıdır.
  Başlangıç `origin/main` `34918f8`. `docs/live-acceptance-plan` dalına güncel
  main ve `docs/rc1-publication` `b6fc985` normal merge ile alındı; çakışmalar
  içerik değerlendirilerek çözüldü. Force push/reset veya toplu ours/theirs yok;
  eski dalların benzersiz kanıtı ve katkı geçmişi korundu.
- [#82](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/82),
  [#84](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/84)
  ve [#86](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/86)
  merge edildi; [#80](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/80),
  [#83](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/83),
  [#85](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/85)
  ve [#87](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/87)
  tamamlandı. #87'de yerel uygulayıcı API/çekirdek alan eşitliğini, fiziksel
  manifest zincirini ve 145 girdinin değişmezliğini doğruladı; ayrı inceleme
  yalnız yayımlanan beş endeksle Aralık yıllık oranlarını, Ocak–Aralık endeks
  değişimlerini ve yüzde puan farkını Decimal ile yeniden hesapladı. İnceleme
  yerel `report.json`/veri dosyalarını açmadı ve fiziksel kontrolleri yeniden
  çalıştırmış sayılmaz. İkisi de yeni canlı model/EVDS çağrısı veya genel model
  başarı metriği değildir.
- `v0.1.0-rc.1` hedefi `abea43137eed8a6ceb20cd9bbd22cd0afeb58f1b`, yayın
  18 Ekim 2026 18:36:49 UTC, prerelease, ek 0. Tag/release değiştirilmedi; bu
  sürüm sonraki soru ekranı/TÜFE karşılaştırma kodunu içeriyor gibi sunulmaz.
- README: rc.1 yayımlandı; #71 offline ve sınırlı canlı kabulü tamamlandı;
  video isteğe bağlı. Normal ekran üç analizi (konut, TÜFE özeti, iki yıl
  karşılaştırması) destekler; offline preview yalnız iki sabit örnek verir.
  İki yıl karşılaştırması için canlı model başarısı iddia edilmez. #71'in dört
  canlı çağrısı yalnız o koşuya aittir; #77'nin ayrı tarihli çağrılarıyla genel
  toplam yapılmaz.
- #68'in README/handoff/real-demo-delivery/release-acceptance kayıtları bu
  PR'da birleştirildi; #68 kapatılmadı. #81 (Afra) ve #76/#79 (Osman) ayrı
  işlerdir; dosyaları değiştirilmedi.
- PR #74 yalnız belgeleri değiştirir; uygulama/test/CI/AGENTS değişmedi.
  README/docs genelinde 84 yerel bağlantı çözüldü; değişen dört belgede 15
  PowerShell bloğu parser'dan geçti ve `git diff --check` temiz. Tam yerel test
  paketi tekrarlanmadı. `c25050b` head'i için `Pytest - Python 3.12` başarılı;
  bu handoff commit'i sonrası güncel head CI'si PR'dan izlenir.
- Durum: PR #74 başlık/açıklaması birleşik kapsam ve gerçek kontrollerle
  güncellendi; #68 açıklaması içeriğin #74'te birleştiğini belirtir ve açık
  kaldı. Sıradaki adım güncel PR #74 head/CI'siyle bağımsız inceleme. Merge,
  release/yayın, canlı uygulama LLM/EVDS çağrısı yok; gerçek veri/rapor/anahtar
  Git'e eklenmedi.

## PR #79 inceleme düzeltmesi — 21 Ekim 2026

- Önce `main` fast-forward pull edildi: `34918f87cdc6325791c3104c9abd683bcbfdfa87`.
  Güncel main, `docs/issue-76-local-setup` dalına `f8bb7b9` merge commit'iyle
  alındı; force-push yok. Devir notu çakışmasında main'in #77/#78 dönem/metrik
  kayıtları ve sonraki kayıtlar ile aşağıdaki 20 Ekim kurulum kanıtı korundu.
  Uygulama/test/eval/CI dosyaları güncel main ile aynı; PR diff'i yalnız belgedir.
- #75'in kalan görsel maddeleri, 20 Ekim'de `5bc12a7` üzerinde gerçek in-app
  tarayıcıda alınan `out/issue-076 setup/cpi-full.jpg` ve `cpi-dom.json` ile
  teyit edildi: 2023-01–2023-12 **12 satır**; **TÜFE (2025=100)** endeksi;
  **Aylık değişim (%)** ve **Yıllık değişim (%)** ayrı sütunlar. Üstteki
  **İlk aydan son aya TÜFE endeksi değişimi %54,5003** ifadesi, tablodaki
  Aralık yıllık **%64,7729** oranından ayrı ve okunur. Tablonun altındaki
  **—: Karşılaştırma için geçmiş ay yok** açıklaması ve yıllık oranın geçen
  yılın aynı ayına göre olduğu, 12 aylık ortalama olmadığı bilgisi okunur.
  2023 satırlarında eksik geçmiş olmadığı için hücrelerde — üretildiği iddia edilmez.
- Yeni birleşik sürümde sunucu başladı; ancak in-app sekmesi webview bağlantı
  zaman aşımı nedeniyle açılamadı. Bu nedenle yukarıdaki görsel kanıtın kaynağı
  açıkça eski commit'tir; yeni head'de görsel tekrar veya 46 testin yeniden
  geçtiği iddia edilmez. Bu oturum yalnız mevcut ekran kaydının kapsamını
  tamamlar; hesap/veri yeniden üretilmedi, yeni canlı LLM/EVDS çağrısı 0.
- Yeni birleşik belge için yerel bağlantı, PowerShell sözdizimi, çatışma işareti,
  main koduyla eşitlik ve diff kontrolleri yapıldı. Tam yerel test tekrarı yok;
  son gönderilen PR head'inin zorunlu CI sonucu GitHub'da ayrıca doğrulanacak.
  Mevcut 145 kaynak korundu, bu oturumun preview sunucusu durduruldu.
- Sonuç yorumu kullanıcı tarafından #76'ya bir kez gönderilecek ve #75'e
  bağlanacak; asistan issue/PR yorumu göndermez, PR'ı merge etmez.

## Osman #76 — yerel kurulum ve ekran kabulü, 20 Ekim 2026

- Kullanıcı planı inceledikten sonra uygulama ve kontrolleri onayladı. Temiz
  `feat/housing-demo-e2e` dalından `main` dalına geçilip fast-forward pull yapıldı.
  Kabulün runtime kaynağı `5bc12a7213cd4f3a47d691803c443e1ad463b445`;
  çalışma dalı `docs/issue-76-local-setup`. #72/#73 birleşmiş, #68/#74 açık.
- Windows 11 (10.0.26200), mevcut `.venv` Python 3.12.4 kullanıldı. Temiz checkout
  veya yeni venv kurulumu iddiası yok. `pip check` ve gerekli importlar geçti.
- Önceki `Housing_tam_teslim_20261018.zip` (SHA-256
  `956e47c3a7d922b4da7b755635379ccc357423aeceed2bcdef817a1098ca312f`)
  bir kez ayrı, boşluklu `out/issue-076 setup/delivery/` altına açıldı. Arşiv
  envanteri ve 145 kaynak doğrulandı; `ANALYTICS_DATA_ROOT` buradaki `inputs/`.
- Repo kökünde çalışan PowerShell akışı:

  ```powershell
  $env:ANALYTICS_DATA_ROOT = (Resolve-Path -LiteralPath '.\out\issue-076 setup\delivery\inputs').Path
  .\.venv\Scripts\python.exe -m scripts.preview_question_ui
  ```

- Gerçek in-app tarayıcıda iki örnek yalnız soru alanını doldurdu; Analiz et
  sonrası konut **60 ay/22 eşleşme**, 22 tablo satırı ve Plotly grafiği; TÜFE
  **2023-01–2023-12 için 12 satır** gösterildi. TÜFE sonucunda eski konut grafiği
  temizlendi. BDDK kaynak bölümü açıldı; Pan modu ve Reset axes düğmeleri denendi.
  Grafik sürükleme/hover için bu oturumda ayrı bir kabul iddiası yapılmıyor.
- Ayrı preview oturumunda bulunmayan veri kökü güvenli UI hatası ve HTTP 503
  `economic_data_unavailable` verdi. Sonuç gizli, düğme tekrar kullanılabilir;
  ekranda ham hata, anahtar veya yerel dosya yolu görünmedi. Geçerli veri bozulmadı.
- Aynı veri köküyle normal `.\.venv\Scripts\python.exe -m uvicorn app.api.main:app
  --host 127.0.0.1 --port 8000` oturumunda yalnız GET `/`, `/health`, `/docs`
  kontrol edildi: üçü de 200. Normal sunucudan soru gönderilmedi. Kendi açtığımız
  dört sunucu süreci kapatıldı; 145 kaynak ve özgün ZIP hash'i değişmedi.
- README'deki makineye özel `out/clean312` ve veri yolu örnekleri yerine mevcut
  `.venv`, bir kez ayrı çıkarma, `inputs` kökü, boşluklu yol yazımı ve sunucular
  arasında Ctrl+C ile geçiş anlatıldı. Runtime/hesap kodu değişmedi.
- Ek offline kontroller: `tests/test_question_ui.py` ve
  `tests/test_economic_question_files_api.py` **46 passed in 15.14s**. İlk kısıtlı
  çalıştırma Windows `socketpair` oluştururken takıldı; aynı testler gerekli
  sandbox izniyle geçti. Tam pytest paketi bu belge değişikliğinde tekrar koşulmadı.
- 56 yerel belge bağlantısı, PowerShell bloklarının sözdizimi ve
  `git diff --check` geçti. Kayıtlar/görüntüler `out/issue-076 setup/` altında,
  Git dışında. Canlı LLM/EVDS **0**; yeni veri indirme veya `.env` değişikliği yok.
- Kullanıcı son inceleme sonrası `docs/issue-76-local-setup` dalının push edilmesini
  onayladı; PR'ı ve #76 yorumunu kendisi açacak. Bu kayıt push öncesinde yazıldı;
  zorunlu PR CI'si gönderilen son başlıkta ayrıca kontrol edilecek.

## #85 iki yıl TÜFE karşılaştırmasını soru akışına bağlama — 21 Ekim 2026

- `feat/inflation-comparison-question` dalı güncel `origin/main` `4f779b1`
  (PR #84 merge) üzerinden temiz ağaçta açıldı; eski yerel dallar main sayılmadı.
- `compare_inflation_years` mevcut ekonomik soru çekirdeğine bağlandı. Yeni
  strict `cpi_two_year_comparison` ready planı yalnız `first_year`/`second_year`
  taşıyor; Python iki yılı, sırayı, karşılaştırma niyetini ve tam yıl kapsamını
  analizden önce denetliyor. Eksik/uyuşmayan/ters yıl, tek/aynı yıl, ortalama,
  kısmi dönem, tahmin/nedensellik ve yanlış analiz türünde analiz 0 çalışıyor.
- İki API yolu (`/analysis/economic/question`, `/files`) tipli karşılaştırma
  yanıtı döndürüyor; `/files` iki nested evidence'a doğrulanmış kaynak/limitations
  aktarıyor. Mevcut Konut/TÜFE davranışları ve 28/9 offline vaka beklentileri
  değişmedi. Ekran iki yıllık tabloları, Aralık oranlarını ve yüzde puan farkını
  göstermeye hazır; yeni CDN/grafik/model çağrısı yok.
- Bağımsız inceleme P1/P2 düzeltmeleri: `_comparison_out_of_scope` tek ay/ISO ay
  ve açık TÜFE dışı metrikleri (kredi/stok/bakiye/tutar/faiz) analizden önce
  `unsupported` ile durduruyor; yalnız açık `yıllık` ifadeli Aralık
  karşılaştırmaları geçiyor. Ekran her yılın `first_to_last_index_change_pct`
  değerini kendi başlığı altında yüzde olarak Aralık yıllık oranı ve yüzde puan
  farkından ayrı gösteriyor. Servis/API regresyonları yanlış ready planlarda
  analizin 0 kez çalıştığını doğruluyor; eval beklentileri değişmedi.
- Doğrulama: odaklı servis/API/dosya **166 passed**, UI **2 passed**. Tek komut
  `out/verification/20261021T110727Z-11200-007b8c5e`: **948 passed, 2 skipped**;
  Economic **28/28**, Housing **9/9**, canlı çağrı 0; `git diff --check` temiz.
- Durum: düzeltmeler aynı `feat/inflation-comparison-question` dalında commit/
  push edilip PR #86 güncellenecek; merge, canlı LLM/EVDS çağrısı, veri indirme
  ve release yok.

## #83 tek komutla offline doğrulama — 21 Ekim 2026

- Başlangıç güncel `origin/main` `190093d`: PR #82 merge edildi ve #80 kapalı.
  `chore/offline-verification` dalı bu main üzerinden açıldı; #81 ve #76 kapsamına
  girilmedi.
- `scripts/verify_project.py` tek komutta sırasıyla `pytest -q tests`, iki offline
  stub değerlendirmesi ve `git diff --check` çalıştırır. İlk hatada durur, ayrıntılı
  günlükleri koşuya özel `out/verification/` altında tutar. `tests/test_verify_project.py`
  başarı, ilk hata, komut başlatma hatası ve repo kökü/yorumlayıcı sınırlarını sahte
  alt süreçle sınar. CI aynı girişi kullanır; README ve AGENTS.md güncellendi.
- Doğrulama: odaklı **4 passed**; ilgili evaluator testleriyle birlikte **53
  passed**. Tek komut `out/verification/20261021T092436Z-24428-e8da83d9`:
  **919 passed, 2 skipped**; Housing **9/9**, Economic **28/28**, canlı çağrı 0;
  `git diff --check` temiz.
- Durum: PR [#84](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/84)
  açıldı ve bağımsız incelemeye bırakıldı; merge/release yapılmadı.

## #80 iki yıl TÜFE karşılaştırması — 21 Ekim 2026

- `feat/inflation-two-year-comparison` dalı güncel `origin/main` (`4a1a327`)
  üzerinden açıldı. Başlangıçta çalışma ağacı temizdi ve #80 için önceki yerel
  uygulama yoktu.
- `app/services/inflation_comparison.py` eklendi: iki tam takvim yılı mevcut
  `build_inflation_evidence` ile hesaplanıyor; yıl sırası korunuyor, önceki
  Aralık hesap geçmişi kesilmiyor. Aralık yıllık oran farkı yüzde puan olarak
  dönüyor; aynı/geçersiz yıl reddediliyor, eksik önceki Aralıkta oran ve fark
  `null` kalıyor.
- `tests/test_inflation_comparison.py` bağımsız beklenen değerlerle eklendi;
  `docs/inflation-analysis.md` kısa kullanımı belgeliyor. API, planlayıcı ve
  ekran değişmedi.
- Doğrulama (kod/test bu haliyle): odaklı **56 passed**; tam paket
  `out/clean312` ile **915 passed, 2 skipped in 95.17s**; offline Housing
  **9/9**; `git diff --check` temiz. Canlı LLM/EVDS çağrısı yapılmadı. Yalnızca
  belge değişikliğinden sonra tam paket yeniden çalıştırılmadı.
- Durum: yerel uygulama tamamlandı; commit/push/PR teslimi bu oturumda
  yürütülecek. Merge ve release yapılmayacak.

## #77 ekonomik soru değerlendirmesi — 20 Ekim 2026

Bu bölüm 20 Ekim tarihli kayıttır; dal/CI/onay ifadeleri o tarihe aittir.

### Güncel oturum: analiz öncesi Python kontrolü, yalnız offline

- Başlangıç temiz `feat/economic-question-evaluation` dalı, PR #78 head
  `babd3690bb8f4ca0863d7d559b913d34a900a177`; #77/PR açık. Mustafa canlı
  denemeleri durdurdu. Önceki iki gerçek rapor ve SHA-256 değerleri aşağıda
  korunur; vaka beklentileri/fixture'lar değiştirilmez.
- Ortak ekonomik soru çekirdeği, modelin `ready` yanıtındaki açık dönem ve konut
  kredi metriğini analizden önce soruyla karşılaştırır. Yılı veya sınırı
  varsayılmış/uyuşmayan dönem `period_required`; belirtilmemiş ya da çelişkili
  reel/nominal metrik `metric_ambiguous`; yalnız nominal kredi isteği
  `unsupported_analysis`. Her durumda analiz 0. Açık tarih ve “enflasyondan
  arındırılmış bakiye” gibi geçerli ifadeler çalışır; genel NLU/dependency yok.
- Gözlenen EQ-020/EQ-022 kötü `ready` kararları sahte sağlayıcıyla gerçek
  servis/HTTP yolunda yeniden oynatıldı: Python beklenen netleştirmeyi verir,
  model kararı ise **yanlış** olarak kalır. Evaluator ham ve son kararın beklenti
  eşitliğini ayrı gösterir; güvenli uygulama sonucu model anlama başarısı sayılmaz.
- İncelemede bulunan açık uç boşluğu offline kapatıldı: sahte modelin “2021 Ocak
  ayından itibaren...” ve “2021 Ocak'tan sonraki...” için verdiği `ready /
  2021-01–2021-01` planı artık hem normalize hem doğrulanmış dosya API yolunda
  `period_required` olur ve analiz 0 kez çalışır. `2021 Ocak TÜFE...` gerçek tek ay
  isteği çalışmaya devam eder. Kontrol yalnız tanınmış tek ayın yanındaki sınırlı
  açık uç belirteçlerini ayırır; genel tarih ayrıştırıcısı veya bağımlılık eklenmedi.
  Sahte modelin ham `ready` kararı evaluator'da yine model hatası; Python engeli
  yalnız uygulamanın güvenli davranışıdır.
- Mevcut Python 3.12.15 `out/clean312`: odaklı servis/API/evaluator
  son koşu **166 passed in 22.69s**; tam depo takımı `pytest -q tests` ile
  **897 passed, 2 skipped in 105.78s**
  (Windows symlink izinleri). Economic stub **28/28**, Housing stub **9/9**;
  gerçek çağrı 0. Önceki vaka seti, fixture ve iki canlı rapor SHA-256 değerleri
  değişmedi. Bunlar yeni canlı model başarısı değildir.
- Önceki canlı gözlemler tarihli kanıttır; bu değişikliğin gerçek model veya
  gerçek veriyle yeni kabulü yapılmadı. Düzeltme `f6b2fc00b11d361c78d4b47bda90882168df9a0f`
  olarak aynı PR #78 dalına commit/push edildi; PR ve #77 güncel teslim bölümleri
  değiştirildi. Bu kod head'i için Tests #136 başarılı: **899 passed in 28.06s**.
  Sıradaki adım PR incelemesidir; canlı çağrı, merge ve release durdurulmuştur.

### Önceki oturum: ikinci onaylı canlı koşu ve offline metrik düzeltmesi

- Aktif dal **`feat/economic-question-evaluation`**, PR #78 açık ve merge edilmedi.
  Başlangıç temizdi. PR head **`204de1ebfe0225f2c0badee01c65f1bbcd75d387`** ve
  başarılı Tests #133 CI (**865 passed**) doğrulanarak tek koşu çalıştırıldı.
- Mustafa'nın onayladığı sıra EQ-020,013,016,022,024,025,026,010; aynı
  `gemini-3.5-flash-lite`, azami 8 deneme, retry 0, timeout 60 saniye.
  **4 gerçek deneme: 3 geçen, 1 başarısız, 4 atlanan**. İlk hata sonrası duruldu.
- EQ-020'de **model kendisi** `period_required` üretti; analiz 0. Python'ın yanlış
  planı engellediği bir sonuç değildir. EQ-013/016 doğru analiz/dönemle
  2021-01–2021-03 için doğrudan Python evidence/grafik referanslarıyla eşleşti.
- EQ-022'de nominal/reel ayrımı eksik “kredi bakiyesi” için beklenen
  `metric_ambiguous` yerine konut `ready/2021-01–2021-03` geldi; Python bunu
  engellemedi, konut analizi 1 kez çalıştı. Kullanıcıya yanlış metrik sunulabilirdi.
  Hesap eşitliği başarısı sayılmadı. EQ-024/025/026/010 çağrılmadı.
- Yeni rapor `out/economic-question-eval-77-live-recheck.json`, SHA-256
  `acdffd6645d3e813fa58ed7ddfa2fabcb45061791449468b387b8e5ecfbd29f0`.
  Önceki `out/economic-question-eval-77-live.json` ve hash'i korundu. Beklentiler,
  case set/fixture hash'leri değişmedi; raporlar Git dışında. Sentetik HTTP
  değerlendirmesi, gerçek paketli UI kabulü veya genel model başarı ölçümü değildir.
- EQ-020 tekrarlanmadığından koşullu Python dönem kontrolü eklenmedi. EQ-022 için
  genel nominal/reel netleştirme prompt kuralı ve gözlenen kötü planın sahte sağlayıcı
  regresyonu yalnız **offline** hazırlandı; gerçek modele etkisi henüz doğrulanmadı.
  Python'a semantik metrik engeli eklenmedi; oracle gevşetilmedi.
- Mevcut Python 3.12.15 `out/clean312`: odaklı **133 passed in 21.30s**;
  tam offline **864 passed, 2 skipped in 102.61s** (Windows symlink izinleri).
  Ekonomik stub **28/28**, Housing stub **9/9**, canlı çağrı 0; bunlar yalnız
  harness davranışı. **61 yerel belge bağlantısı**, **11 PowerShell bloğu** ve
  diff kontrolü başarılı. O metrik düzeltmesi `4aae841` olarak PR'a gönderildi;
  tam head'in Tests #134 CI'si **866 passed**.
- Sıradaki adım bu offline düzeltmenin PR incelemesi; tekrar canlı çalışma için
  yeni açık onay gerekir. Kullanılmayan 4 deneme yeni koşuya yetki vermez.
  Merge/release/tag değişimi, EVDS indirmesi, yeni özellik yok; #75/#76 korunur.

### Önceki hazırlık ve ilk canlı koşu (tarihli kanıt)

- Başlangıç ağacı temizdi; güncel main **`5bc12a7`** üzerinden ayrı aktif dal
  **`feat/economic-question-evaluation`** açıldı. #74'ün merge edilmemiş belge
  değişiklikleri main'de var sayılmadı veya bu dala taşınmadı. #71 tamamlandı;
  önceki dört canlı çağrı bu görev için yeni yetki değildir. #75/#76'ya dokunulmadı.
- Mevcut ekonomik evaluator genişletildi, ikinci sistem kurulmadı. İlk 12 vakanın
  soru/beklenti/stub alanları korunarak **28 vaka** yapıldı: 9 ready, 10 netleştirme,
  7 unsupported, 2 veri yokluğu. Yeni beklenti ve gerekçeler model çıktısı görülmeden
  yazıldı. Türkçe ifadeler/tarihler, eksik veya göreli dönem, nominal/reel belirsizliği,
  kapsam dışı dönem, ters koşul, karşılaştırma ve alakasız istek kapsanır.
- Varsayılan offline. Live CLI açık vaka seçimi + pozitif toplam bütçe ister;
  soru başına en fazla 1 çağrı, başarısız istek de bütçede, retry 0. İlk sağlayıcı,
  plan veya hesap hatasında durur; bütçe bitince kalan vakaları atlar. Şemaya uyan
  yanlış analiz/dönem de başarısızdır; kapsam kontrolü sonrası kararın yanında
  modelin doğrulanmış plan alanları da karşılaştırılır. Python hesapları ve
  HTTP sözleşmeleri değişmedi; karşılaştırma özelliği eklenmedi.
- Raporlar `out/` altında offline/live ayrı adlarla; canlı raporun üzerine yazılmaz.
  Beklenen/gerçek kararlar, vaka kimlikleri, denemeler, hata nedenleri, kaynak
  commit/dirty bilgisi ve evaluator/vaka/fixture hash'leri kaydedilir. Gerçek veri,
  `.env`, anahtar veya ham sağlayıcı hatası Git'e eklenmez.
- Hazırlıkta gerçek SDK + sahte HTTP sağlayıcıyla ağsız testler yapıldı; bunlar
  model anlama ölçümü değildir. **20 Ekim'de ayrı açık onayla** PR head
  **`dd149d9c4d94cea64bec76e2975a510b5900f920`**, temiz ağaçta sekiz vaka sırasıyla
  seçildi: EQ-013,016,020,022,024,025,026,010. Mevcut Gemini
  `gemini-3.5-flash-lite`, timeout 60 saniye, azami 8 deneme, retry 0.
- **Canlı sonuç: 3 deneme, 2 geçen, 1 hata, 5 çalıştırılmayan vaka.** EQ-013/016
  2021-01–2021-03 için doğru analiz ve doğrudan Python hesabıyla eşleşti.
  EQ-020'de yıl eksik soruya beklenen `clarification_required/period_required`
  yerine `ready/cpi_inflation_summary/2021-01–2021-03` geldi. Yıl varsayıldı,
  TÜFE analizi 1 kez çalıştı; kullanıcı yanlış yılın sonucunu görebilirdi.
  Evaluator `status_mismatch` kaydetti ve ilk hatada kalan 5 vakayı atladı.
  Retry/ek çağrı/EVDS yok; kullanılmayan 5 deneme otomatik devam yetkisi değildir.
- Özgün rapor `out/economic-question-eval-77-live.json` Git dışında; SHA-256
  `208728435b2a72290cc9066927cc0219662779d48c110a46373147cb678084e4`.
  Beklentiler/fixture'lar değişmedi; case set hash'i hâlâ
  `e2c0db23e3ad02febc466a653afa51e8ff31c8b746591df5644c3d8fe8d76d2f`.
  Bu gerçek sonuç offline kanıttan ayrıdır; küçük/erken kesilmiş seçimi genel
  başarı metriği olarak sunma. Bu değerlendirme **sentetik fixture** kapsamını
  kullanır; gerçek dosyalı #71 kabulünü tekrar etmez. Kullanım/sorular
  [mevcut rehberdedir](economic-question.md#seçilmiş-canlı-planlama-yolu--ayrı-onay-gerekir).
- Offline düzeltme: prompt'ta yıl/başlangıç/bitişin sorudan gelmesi, eksik bilginin
  kapsamdan veya bugünden tamamlanmaması genel kuralı belirginleştirildi. EQ-020'nin
  gözlenen kötü planı sahte sağlayıcı regresyonuna eklendi; oracle hâlâ reddeder ve
  kalanları durdurur. O aşamada prompt düzeltmesinin canlı etkisi bilinmiyordu;
  sonraki ayrı onaylı koşu ve yeni kalan eksik üstte kaydedilmiştir.
- Python 3.12.15 için mevcut `out/clean312` kullanıldı; bozuk `.venv` korunur,
  yeni kurulum/dependency yok. Başlangıç odaklı **65 passed**; son odaklı
  **107 passed in 18.35s**. Tam offline **862 passed, 2 skipped in 115.30s**
  (Windows symlink izinleri). Housing stub **9/9**, ekonomik stub **28/28**;
  ikisi `harness_behavior_only`, Türkçe anlama başarısı değildir. Raporlar
  `out/*-question-eval-77-offline.json` altında Git dışında.
- İlk teslimde son rapor etiketi kontrolünden sonra evaluator **26 passed in 14.28s**;
  **61 yerel belge bağlantısı**, **11 PowerShell bloğu** ve `git diff --check`
  geçti. PR CI'si kendi tam head'i için ayrıca izlenir; yerel sonuç CI yerine
  sayılmaz. İlk hazırlıkta canlı kontrol yolu yalnız sahte sağlayıcıyla sınandı.
- Canlı gözlemden sonraki offline düzeltmede odaklı servis/API/evaluator paketi
  **132 passed in 21.84s**; tam offline **863 passed, 2 skipped in 104.18s**
  (Windows symlink izinleri). Ekonomik stub **28/28**, Housing stub **9/9**;
  bunlar prompt'un gerçek modelde sorunu giderdiği kanıtı değildir. Belge kontrolleri
  yine **61 bağlantı/11 PowerShell bloğu**, diff temiz. Özgün canlı rapor,
  beklentiler ve fixture hash'leri sabit kaldı; yeni canlı çağrı yapılmadı.
- Teslim: **PR #78 açık**, dal commit/push edildi; main'e merge edilmedi.
  Bu ilk teslimin ardından ayrı onayla yapılan kontrol üsttedir. Yeni özellik,
  merge, release veya tag değişimi bu görevin dışında.



## Sınırlı canlı kabul sonucu — 19–20 Ekim 2026

Bu bölüm 19–20 Ekim tarihli kabul kanıtıdır; dal/CI/onay ifadeleri o tarihe aittir.

- Başlangıç ağacı temiz, aktif dal **`docs/live-acceptance-plan`**; açık
  **PR #74** güncellenir, merge edilmedi. Ürün kodu main `5bc12a7` ile aynı;
  mevcut kullanıcı değişiklikleri/veri/anahtar korunur. #70 ve #71 kapalı.
- Mustafa #71'deki dört sabit vaka için mevcut Gemini yapılandırmasında
  **azami 4 toplam çağrı, retry 0, ilk sağlayıcı/plan/hesap hatasında durma**
  onayı verdi. Normal `create_app()` ve `/analysis/economic/question/files`
  kullanıldı; **stub veya dependency override yok**. CUA tarayıcısı/native
  pipe kullanılamadı; kurulu Chrome ayrı başsız profille gerçek formu gönderdi.
  Gözlem katmanı yalnız sayım/karşılaştırma yaptı, plan veya yanıt üretmedi.
- 19 Ekim **23:34 TRT**: **4 orijinal model çağrısı, retry 0**, model
  `gemini-3.5-flash-lite`, timeout 60 saniye; her soru yalnız bir gönderim.
  Aynı yanıtla plan/hesap ve ekran kontrol edildi. API'den sonra ekran için
  ikinci istek yok. Hata/uyuşmazlık görülmedi; bütçe tamamen tüketildi.
- Vaka 1: konut `ready`, **2021-01–2025-12**. Evidence **ve grafik JSON'u**
  önceki doğrudan CLI ile birebir aynı, **60 ay/22 eşleşme**. Ekranın 22 satırı,
  altı trace'in x/y/adları ve özet aynı yanıtla eşleşti; ilk ay eşleşme dışında.
- Vaka 2: TÜFE `ready`, **2023-01–2023-12**, **12 ay**. Hesap alanları ve
  aylık/yıllık oranlar aynı doğrulanmış geçmişten doğrudan mevcut Python
  servisiyle eşit; verified_files kökeni/sınırlamaları ayrıca kontrol edildi.
  Ekranda 12 satır ve ilk-son endeks değişimi **%54,5003**; bu Aralık/Aralık
  yıllık oranı değildir.
- Vaka 3: `clarification_required / period_required`; dönem varsayılmadı.
  Vaka 4: `unsupported / unsupported_analysis`; döviz tahmini reddedildi.
  Bu iki vakada analiz çağrısı 0, evidence/grafik yok; ekran doğru mesajları
  gösterdi ve önceki sonucu temizledi. Dört HTTP yanıtı 200; toplam iki analiz.
- Aynı yanıtlarla kaydedilen DOM ek çağrı olmadan incelendi: konut 22 satır/
  **132 hücre**, TÜFE 12 satır/**48 hücre**; dönemler ve sayılar dört ondalık
  gösterim hassasiyetinde API evidence ile uyumlu. Hesap eşitliği ayrıca tam
  JSON/değer eşitliğiyle kontrol edildi; gösterim yuvarlamasıyla karıştırılmadı.
- Modelden önce mevcut fiziksel doğrulayıcı: BDDK/EVDS **66 ay**, kapsam
  2021-01–2026-06. **145 girdi SHA-256'sı aynı**. EVDS/yeniden indirme, ek
  anlatım, ücretli plana/model/sağlayıcıya geçiş, yeni özellik/merge/release yok.
- Gerçek yanıtlar, özgün/annotasyonlu audit ve ekranlar
  `out/live-acceptance-20261019/` altında, **Git dışında**. Agent dört
  `case-1.png` … `case-4.png` görselini inceledi. Çağrı sayımı orijinal
  `ask_llm` sınırında 4 ve SDK retry 0 üzerinden; opsiyonel httpx sayacı SDK'nin
  httpx2 transport'unu görmedi, bu sınırlama audit'te açıklanmıştır. Sayacı
  düzeltmek için yeni çağrı yapılmadı; sağlayıcı logları sorgulanmadı.
- **20 Ekim: Mustafa case-1–case-4 statik ekran görüntülerini teyit etti.**
  Konutta dönem/60 ay/22 eşleşme doğru, grafik/tablo okunur; TÜFE'de dönem ve
  aylık/yıllık ayrımı anlaşılır. Dönemsiz soruda dönem, döviz tahmininde kapsam
  dışı mesajı var; ikisinde önceki sonuç görünmüyor. Görüntülerde belirgin
  taşma/çakışma görülmedi. **Bu yalnız statik görsel teyittir; yeni etkileşim
  testi veya model çağrısı yapılmadı.** Önceki offline teyit ayrı kanıttır.
  #71'in son kabul maddesi işaretlenip issue **closed/completed** kapatıldı.
  Dört vaka genel model başarı oranı değildir; toplam canlı çağrı hâlâ 4/retry 0.
  Ek canlı gönderim için yeni açık onay gerekir.
- Python 3.12.15 için mevcut `out/clean312` kullanıldı; eski `.venv` Python
  yolu hâlâ eksik, değiştirilmedi. Ürün kodu değişmedi; tam yerel test tekrarı
  yok. **56 yerel belge bağlantısı**, **7 PowerShell bloğu** ve diff kontrolü
  geçti; README/devir değişikliği mevcut PR #74'e commit/push edilir.
  Önceki head `cd2df9e` CI'si **842 passed in 39.42s**; bu statik teyit
  güncellemesinin CI'si kendi yeni head'i için PR'dan izlenir. 20 Ekim'de
  yerelde tam test paketi veya UI/model koşusu tekrarlanmadı; değişiklik yalnız
  belgedir, zorunlu PR CI'si mevcut offline kontrolleri ayrıca çalıştırır.
  rc.1 `abea431` aynı, #46 videosu isteğe bağlı/çekilmedi, PR #68 korunur.
- Sonraki adım: mevcut PR #74'ün dokümantasyon merge'i için ayrı onay bekle.
  Bu teyit merge/release veya yeni canlı çağrı yetkisi vermez; yeni kapsam açma.

## Ekran merge ve canlı kabul hazırlığı tarihli kaydı — 19 Ekim 2026

Bu bölüm canlı koşu öncesinin kaydıdır; eski onay bekleme/canlı0 ifadeleri
güncel durum değildir. Güncel sonuç ve kalan kullanıcı teyidi üsttedir.

- Başlangıç ağacı temizdi. PR #73'ün son head'i
  `440ad0d0a78ec9c652db660f1f82453bdfe96f87`, 10 dosyalık diff'i,
  başarılı PR CI'si (**842 passed**), boş review/thread listeleri ve temiz
  merge durumu yeniden kontrol edildi. Mustafa'nın açık onayıyla
  **`5bc12a7213cd4f3a47d691803c443e1ad463b445`** olarak main'e merge edildi;
  #70 **closed/completed** doğrulandı. #70 ve PR açıklamaları güncellendi.
- Mustafa offline önizlemede iki örneği denediğini; konut grafiği/eşleşme
  tablosu, TÜFE tablosu, kaynaklar/sınırlamalar ve grafik etkileşimlerini uygun
  bulduğunu teyit etti. Bu kullanıcı teyididir; canlı model kabulü değildir.
- [#71](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/71)
  içinde dört soru ve beklenen analiz/dönem/karar **çalıştırılmadan önce**
  yazıldı: konut 2021-01–2025-12, TÜFE 2023-01–2023-12, dönem eksikliği ve
  kapsam dışı tahmin. Aynı vaka listesi yeni bir takip belgesine kopyalanmadı.
- Yerel yapılandırmadan yalnız model/zaman aşımı ağsız okundu:
  **`gemini-3.5-flash-lite`, 60 saniye**. Öneri: **azami 4 toplam çağrı**,
  vaka başına 1 planlama, **yeniden deneme 0** (`max_retries=0`). Hatalı
  deneme bütçeye dahildir; ilk sağlayıcı/plan/doğruluk hatasında durulur.
  Ek anlatım, ücretli plana/sağlayıcıya otomatik geçiş veya EVDS çağrısı yok.
  **Canlı çağrı 0; vaka/bütçe onayı bekleniyor. #71 açık.**
- Aktif dal **`docs/live-acceptance-plan`**, merge edilmiş güncel main'den
  açıldı. Bu dal yalnız README/devir kaydıdır; ürün kodu/veri/anahtar/audit
  değiştirilmedi. PR #68 kendi dalında korunur. rc.1 tag'i `abea431`;
  yeni release yok. Bu dokümantasyon dalı ayrıca onay olmadan merge edilmez.
- Test durumu: merge edilen ekran head'inin CI'si **842 passed**; önceki
  yerel tam paket **840 passed, 2 skipped**, odaklı UI/API **46 passed**,
  Housing stub **9/9**. Dokümantasyon değişikliği için tam yerel test tekrarı
  yapılmadı. Bu oturumda **56 yerel belge bağlantısı**, **7 PowerShell bloğu**
  ve `git diff --check` geçti. Bu dokümantasyon dalı commit/push edilip ayrı
  PR olarak teslim edilir; CI'nin güncel sonucu PR'dan izlenir, merge bekler.
- Sonraki adım: Mustafa dört vaka/model/azami çağrı bütçesini açıkça onaylarsa,
  mevcut doğrulanmış yerel dosyalarla normal endpoint'te bu sırayla çalıştır;
  gerçek sonuçları offline kanıttan ayrı kaydet, genel başarı oranı çıkarma.
  Onaya kadar normal ekrandan soru gönderme veya canlı smoke testi çalıştırma.
  #46 videosu isteğe bağlıdır, çekilmedi ve ürün kabulünü bekletmez.



## Yerel soru ekranı: Aşama 2 tarihli kaydı — 19 Ekim 2026

Bu bölüm eski kaynak/test kanıtıdır; güncel dal/teslim durumu üsttedir. #73 main'e
alınmıştır, #70/#71 kapanmıştır; aşağıdaki eski bekleyen ifadeler güncel engel değildir.


- Başlangıç ağacı temizdi. Mustafa'nın açık onayıyla PR #72'nin tam başlığı
  `545a285`, diff, başarılı Tests #122 (**840 passed**) ve boş review/thread
  listesi yeniden kontrol edildi; **`23a820ba525b4d829a65698d2d13b80b9bc64cae`**
  olarak main'e merge edildi. #69 `closed/completed` olarak doğrulandı.
- Aktif dal **`feat/local-question-screen`**, doğrudan bu güncel main'den açıldı.
  PR #68 kendi dalında korunur ve merge edilmedi. `v0.1.0-rc.1` hâlâ `abea431`;
  tag/release değiştirilmedi. Bu ekranın PR'si onay olmadan merge edilmez.
- #70: FastAPI `GET /`, yerel CSS/JS ve kurulu Plotly paketinden sunulan JS.
  Tarayıcı yalnız `/analysis/economic/question/files` adresine `question` yollar.
  Örnekler yalnız alanı doldurur; gönderme kullanıcı eylemidir. Konutun mevcut
  grafiği/eşleşme tablosu, TÜFE tablosu, evidence'dan kısa Türkçe özet, kaynak,
  kapsam, birim ve sınırlamalar gösterilir. Sayısal hesap veya ek model yok.
- Bekleme/tek istek, başarı, netleştirme, unsupported, veri/sağlayıcı/ağ hataları
  ayrı gösterilir; eski sonuç yeni istekte temizlenir. Kullanıcı/kaynak metni
  `textContent` ile yazılır; ham sağlayıcı gövdesi gösterilmez. CSP aynı origin
  script/connect kuralını uygular; GET/asset yükleme LLM ayarını okumaz.
- `python -m scripts.preview_question_ui` iki örneğe açık sabit plan verir;
  diğer sorulara netleştirme döner. Offline etiketi görünür. Mevcut
  `out/clean312` Python 3.12.15 kullanılır; kurulum/dependency tekrarı yok.
  Gerçek paket kökü ve 8000 adresi için [README](../README.md#local-question-screen--offline-preview).
- CUA'da tarayıcı yüzeyi yok (`browsers: []`, iab kullanılamıyor). İstenen
  yazılım UI testi/görüntüsü kurulu Chrome'un ayrı geçici profilli başsız
  oturumunda, yalnız 127.0.0.1 test sunucusuna karşı yapıldı. Sandbox ilk Chrome
  GPU sürecini engelledi; gerekli izinle aynı test geçti. Kontroller gerçek DOM,
  gerçek Plotly, HTTP/dosya yükleme ve açık stub planları kullanır; canlı **0**.
- Gerçek paketli offline ekran görüntüleri `out/question-ui-housing.png` ve
  `out/question-ui-cpi.png`; incelendi. Konut **60 ay/22**, TÜFE **2023 için 12 ay**.
  Görülen lejant/başlık çakışması yalnız sunum layout'unda düzeltildi; trace/veri
  değişmedi. **145 kaynak dosyasının hash'i aynı**; görseller/veri/audit Git dışında.
- #71 **açık**: gerçek model kabulü yapılmadı; vaka/bütçe onayı ve Mustafa'nın son
  ekran/etkileşim kontrolü eksik. #46 videosu isteğe bağlıdır, çekilmedi. Bu
  ekran PR'si main'e alınmış veya canlı kabul tamamlanmış sayılmaz.
- Kontroller: odaklı UI/API paketi **46 passed in 10.21s**; tam yerel offline
  paket **840 passed, 2 skipped in 82.78s** (mevcut Windows symlink izinleri).
  Housing stub **9/9**, canlı **0**. Tarayıcı testi açılış/örnek, bekleme/tek istek,
  grafik/tablolar, netleştirme/unsupported, veri/sağlayıcı/ağ hatası ve XSS metin
  sınırlarını gerçek DOM'da kontrol eder. Chrome geçici profili LLM/EVDS/GitHub
  anahtar ortam değişkenlerini devralmaz. 56 yerel bağlantı, 7 PowerShell bloğu
  ve `git diff --check` geçti; son commit'in CI'si ayrıca izlenir.

## Yeni yerel soru ürünü: Aşama 1 kaydı — 19 Ekim 2026

Bu bölüm PR #72 öncesinin tarihli kaynak/test kanıtıdır; güncel merge/dal ve
sonraki adım üstteki Aşama 2 bölümündedir.

- Mustafa önceki “yeni özellik açma” sınırını bu ürün için açıkça kaldırdı.
  Hedef yalnız Türkçe soru girilen yerel web ekranı; mevcut Python hesapları,
  fiziksel veri kontrolleri ve izinli iki analiz korunur. Canlı/merge/release
  öncesinde ayrı onay gerekir. #46 videosu **isteğe bağlı portföy işi**, çekilmedi;
  ürün geliştirmesini veya kabulünü bekleten zorunlu kapı değildir.
- Başlangıç ağacı temizdi. PR #68 (`docs/rc1-publication`) açık ve önceki CI'si
  başarılıydı; yayın kayıtları korunup video isteğe bağlı olarak güncellendi.
  PR #68'in son başlığı `b6fc985` için Tests #121 başarılı; bu belge dalı main
  değildir. **`v0.1.0-rc.1` değiştirilmedi**, hedefi `abea431`;
  prerelease yayımlıdır. Yeni kod dalı **`feat/verified-economic-question-api`**,
  doğrudan güncel main `abea431` tabanından açıldı; #68'e bağımlı değildir.
- İşler: [#69 backend](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/69),
  [#70 ekran](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/70),
  [#71 uçtan uca kabul](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/71).
  Tamamlanmış #42/#59 yeniden açılmadı; yeni iş onların çekirdeklerini kullanır.
- #69: `POST /analysis/economic/question/files` yalnız `question` alır.
  `ANALYTICS_DATA_ROOT` sunucu yapılandırmasıdır; tam BDDK/EVDS paketi mevcut
  fiziksel yükleyiciyle modelden önce doğrulanır. Konut/TÜFE aynı ekonomik soru
  çekirdeğine bağlandı; hesap tekrarı veya ek anlatım modeli yok. Netleştirme,
  desteklenmeyen soru ve dönem doğrulaması korunur. Eski endpoint'ler değişmez.
  Eksik/bozuk pakette güvenli 503; model/analiz çağrısı 0. Kullanım README ve
  mevcut [soru belgesindedir](economic-question.md).
- Mevcut `.venv` kayıp kurulum yoluna bağlı; korunur. Yeni kurulum yapılmadı,
  Python **3.12.15 `out/clean312`** kullanıldı. Temiz başlangıç main testleri
  **794 passed, 2 skipped in 97.71s** (Windows symlink izinleri). İlk bağlantı
  regresyonu **97 passed, 1 skipped**, yeni HTTP/dosya odaklı paket
  **103 passed, 1 skipped in 14.84s**. Son tam offline paket **838 passed,
  2 skipped in 81.37s**; atlamalar aynı Windows symlink izinleri. Housing
  stub **9/9**, Economic HTTP stub **12/12**, canlı çağrı **0**. 60 yerel belge
  bağlantısı, 9 PowerShell bloğu ve `git diff --check` geçti. Son commit'in
  zorunlu PR CI'si ayrıca izlenir; bu dalın değişiklikleri henüz main'de değildir.
- Gerçek teslim üzerinde TestClient + **2 açık sabit plan**: konut HTTP evidence/
  grafiği önceki gerçek CLI çıktısıyla tam eşit (**60 ay/22**), TÜFE 60 ayın
  hesapları doğrudan `build_inflation_evidence` ile tam eşit. Bu gerçek dosya
  kabulüdür; stub model anlama testi değildir. **145 girdi dosyasının hash'i
  değişmedi**, canlı LLM/EVDS **0**. Yerel kontrol script'i ve veriler Git dışında.
- Sonraki adım #69 PR'sinin review/merge onayı; backend merge edilmeden #70'i
  güncel main'de varmış gibi başlatma. Sonra #71'de küçük vaka/bütçe listesini
  canlı Gemini çağrısından önce Mustafa'ya göster. Bu oturumda ekran, canlı
  kabul veya yeni release tamamlandı sayılmaz.

## v0.1.0-rc.1 yayımlandı; ekran kaydı açık — 18 Ekim 2026

19 Ekim ürün kararı: #46 videosu **isteğe bağlı portföy işi**, kaydedilmedi;
ürün geliştirmesinin zorunlu kabul kapısı değildir. Yalnızca soruyla çalışan
yerel ürün artık açıkça yetkili: backend #69, ekran #70, uçtan uca kabul #71.
Önceki “yeni özellik açma” sınırı bu kapsam için geçersizdir. PR #68 açık,
başarılı CI'li belge teslimidir; main'de varmış gibi kullanılmaz. rc.1 değişmez.

- Başlangıç çalışma ağacı temizdi; kullanıcının değişikliği yoktu. Aktif dal
  **`docs/rc1-publication`**, güncel main `abea431` tabanlıdır. PR #67 main'e
  merge edilmiştir; runtime `7ee7225` ile aynı, yalnızca kabul belgeleri değişti.
- Mustafa bu oturumda yalnızca **`v0.1.0-rc.1` sürüm adayının yayımlanmasına**
  açık onay verdi. Güncel main tam SHA
  `abea43137eed8a6ceb20cd9bbd22cd0afeb58f1b` yeniden kontrol edildi;
  bu commit'in [main CI'si](https://github.com/ekincimustafa/quad-qore-agentic-analytics/actions/runs/39153169544)
  **796 passed in 20.89s**. Gereksiz yerel tam pytest tekrarı yapılmadı.
- Annotated `v0.1.0-rc.1` tag'i tam bu commit'e oluşturulup gönderildi;
  [GitHub prerelease](https://github.com/ekincimustafa/quad-qore-agentic-analytics/releases/tag/v0.1.0-rc.1)
  **18 Ekim 2026 18:36:49 UTC** yayımlandı. `prerelease=true`, `draft=false`,
  release kimliği `416628413`, yüklenen ek sayısı **0**. Tag hedefi ve yayımlanan
  notlar bağımsız GET ile kontrol edildi. Gerçek veri, HTML, yerel audit veya
  operasyon script'i eklenmedi; kaynak arşivleri yalnızca Git'teki dosyalardır.
- #39/#40/#42 tamamdır. #46'da prerelease/onay maddeleri işaretlendi;
  **60–90 saniyelik ekran kaydı alınmadı**, isteğe bağlı portföy işi olarak açık.
  Kullanıcının önceki gerçek HTML görsel kabulü kayıt yapıldığı anlamına gelmez.
- Bu dal yalnızca mevcut README/kabul/teslim/devir kaydını günceller; sürüm
  tag'i bu yayın sonrası belge commit'lerine taşınmaz. Belge commit/push/PR
  rutini uygulanır; yeni PR'nin merge'i veya kararlı release için onay yoktur.
  Bu belgelerde **63 yerel bağlantı**, **12 PowerShell bloğu** ve
  `git diff --check` geçti; zorunlu belge PR CI'si son commit için izlenir.
  Bu yayın kaydının tarihli sonraki adımı videoydu; 19 Ekim ürün kararıyla artık
  geliştirmeyi bekletmez. Yeni geliştirme #69 ile başlar; canlı EVDS/LLM yok.
## PR #67 gerçek demo kabul teslimi — 18 Ekim 2026

Bu bölüm yayın öncesi tarihli kabul kaydıdır; güncel yayın ve aktif dal durumu
üstteki `v0.1.0-rc.1` bölümündedir. Önceki onay sınırları bu tarihe aittir.

- Aktif dal `docs/real-demo-readiness`; başlangıç çalışma ağacı temizdi,
  mevcut kullanıcı değişikliği yoktu. Runtime `7ee7225`, Python 3.12.15
  `out/clean312`; uygulama kodu değiştirilmedi. Yeni özellik veya takip belgesi
  açılmaz. #39/#40/#42/#46 açıklamaları ve mevcut PR #67 güncellenir;
  yeni yorum/paket talebi gönderilmez. Bu kayıt PR #67'nin son kabul teslimidir;
  Mustafa uygun güncel diff/CI/review sonrası merge'e bu oturumda onay verdi.
  Gerçek merge sonucu [PR #67 kaydından](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/67)
  kontrol edilir; tag/release/yayınlama onayı verilmedi.
- Afra'nın [OneDrive teslimi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251399411)
  Mustafa tarafından İndirilenler'e alınmış. `OneDrive_1_18.10.2026.zip` bir
  taşıma arşivi; içindeki **20.344 baytlık** `EVDS_gercek_veri_teslim.zip` hash'i
  `1c9255194c3222dccc33e056ba195c46a8d0912cdb9ccccd178e8e4b2731ebc1` ile eşleşti.
  Paket `out/evds-acceptance-20261018/inputs/` altında dizin yapısı korunarak
  açıldı. Repo `data/` dizini ve 12 teslim dosyasının ilk/son hash'leri değişmedi.
- Teslim belgesi okundu; **12/12 boyut ve SHA-256** eşleşti. Mevcut tüketicide
  iki fiziksel manifest/raw/makbuz/CSV zinciri geçti. Mevcut üreticinin manifest
  yapıları birebir aynı; aynı Bronze'dan ayrı `rebuilt/` alanında üretilen
  **66 ve 60 aylık CSV'ler bayt düzeyinde**, coverage raporları JSON olarak aynı.
  Üç örnek ayın ham ortalama/sayı/TÜFE/KFE değerleri belgeyle ayrıca eşleşti.
  03-07-2026 faiz gözlemi kapsam dışında; weekly coverage hâlâ `unverified`.
- Sonuç [#39 yorumuna](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251815563)
  kullanıcının açık yetkisiyle kaydedildi. Yeni paket talebi veya #40'a mesaj
  gönderilmedi. Ayrıntı ve CSV hash'leri [kabul kaydında](release-acceptance.md).
  Yerel `audit-report.json` ve `audit_evds.py` aynı ignored kabul dizinindedir;
  gerçek paket, teslim belgesi, ham gözlemler ve yerel audit çıktıları Git'e eklenmez.
- Ağ erişimi kapatılmış yerel audit'te **0 ağ girişimi**; canlı EVDS/LLM veya
  yeniden veri indirme yok. Önceki tam kod testleri gereksiz tekrar edilmedi;
  bu oturumun kanıtı gerçek EVDS paket doğrulamasıdır, sentetik test sayısı değildir.
- **İki veri erişim engeli de kalktı.** Osman [EVDS alıcı teyidini](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6252994701)
  ve [birleşik Housing teslimini](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6252930443)
  paylaştı. #39 teslim/alıcı kapsamı tamamlandı ve kapandı.
- `Housing_tam_teslim_20261018.zip`: 1.587.106 bayt; SHA-256
  `956e47c3a7d922b4da7b755635379ccc357423aeceed2bcdef817a1098ca312f` eşleşti.
  Ayrı `out/housing-acceptance-20261018/` klasöründe açıldı. **156/156 envanter**,
  145 girdi, **66 BDDK raw + 66 makbuz + 66 aylık Silver** doğrulandı; mevcut
  üreticiyle yeniden kurulan tablo tam eşit. Üç BDDK örneği 276785 / 438466 /
  678970 Milyon TL. EVDS'nin 12 dosyası eski kanıt kopyasıyla bayt eşit;
  iki fiziksel manifest geçti.
- Teslim README/kabul/audit dosyaları **yazar kanıtı** olarak okundu. Eski
  `housing-demo/...` bağlantıları korunmuş teslim `outputs/...` dosyalarıdır.
  Osman'ın iki koşusu/görsel incelemesi Mustafa'nın yaptığı kontrol sayılmaz.
- Mustafa CLI girişini **bir kez** socket kapalı çalıştırdı: exit 0,
  **60 ay / 22 hesaplanan eşleşme**, ilk ay null değişimleri/koşulu, 6 trace ve
  bütün Gold/grafik değerleri, 60 BDDK / 3 EVDS kaynak referansı doğrulandı.
  Aynı girdilerle açık sabit planlı wrapper **1 stub çağrısı** yaptı;
  evidence/grafik CLI ile tam eşit. #42 teknik dosya kabulü tamamlandı ve kapandı.
- Yeni dört dosya `out/housing-acceptance-20261018/reproduced/` altında;
  hepsi teslim `outputs/` ile **bayt eşit**. Açılacak gerçek HTML:
  `out/housing-acceptance-20261018/reproduced/report.html`.
  HTML SHA-256 `81a7eef0e09880e109b41bd9c75fc26ce0f7f45525446af28f18f5c52ca6c09f`.
- Ocak faizi Decimal `18.38800000`, CSV metni `18.387999999999998`; fark
  **−2E−15 yüzde puan**. Pandas okuması `18.388`; tam Decimal eşitliği yok.
  Kaynak/hash değiştirilmedi, toleransla saklanmadı; hesap/çıktı uyuşmazlığı yok.
- Yerel `independent-audit.json` hash'i
  `6267c389bb90634fb57bea4e8028cdb718435ae32d93922d6c89cd837fb7ac5b`.
  Özgün ZIP, inputs/outputs ve önceki EVDS kopyası değişmedi; ağ girişimi ve
  canlı model çağrısı **0**. Yerel veri/audit dosyaları ignored; Git'e eklenmez.
  Kod değişmediği için gereksiz tam test tekrarı yapılmadı; belge CI'si izlenir.
- **Görsel kabul tamamlandı:** Mustafa gerçek `reproduced/report.html` dosyasını
  tarayıcıda inceledi; 60 ay/22, hover–zoom–pan–sıfırlama, seçtiği ayın tablo/grafik
  uyumu, Ocak 2021'in eşleşmemesi, kaynak/birim/baz yılı ve sınırlamaların
  okunmasını açıkça teyit etti. Bu kullanıcı beyanıdır; Codex tarayıcı testi
  değildir. HTML hash'i yeniden aynı bulundu. #40 tamamlandı; #46 görsel maddesi
  işaretlendi, sürüm teslimi açık bırakıldı.
- Sürüm notu, önerilen **`v0.1.0-rc.1`** tag'i ve 60–90 saniyelik demo anlatımı
  [mevcut kabul kaydında](release-acceptance.md) incelemeye hazır. Sunum/kayıt
  yapılmış sayılmaz. Sonraki adım Mustafa'nın bu önerileri incelemesi ve ayrı
  tag/release/yayınlama kararıdır; bu sınırda durulur, yeni kapsam açılmaz.
- Bu son belge değişikliğinde uygulama/test kodu aynı; gereksiz yerel tam test
  tekrarı yapılmadı. **62 yerel bağlantı, 12 PowerShell bloğu** ve `git diff --check`
  geçti; merge yalnızca son kaynak başlığının zorunlu CI'si başarılı ve
  review durumu uygunsa yapılır. Önceki Windows **794 passed, 2 skipped** kaydı
  tarihli runtime kanıtıdır, bu belge değişikliğinin yeniden koşusu değildir.

## Önceki gerçek demo hazırlığı — 18 Ekim 2026

Bu bölüm EVDS tesliminden önceki tarihli kurulum kanıtıdır. O tarihteki erişim
engeli artık kapalıdır; güncel eksik ve iş sırası yalnızca üst bölümde yer alır.

- Aktif dal `docs/real-demo-readiness`, güncel main `7ee7225` tabanlı. Kullanıcı
  yeni özellik istemiyor; mevcut demoyu gerçek veriyle doğrulama öncelikli.
  PR #63–#66 başarılı CI ile merge edildi; #59 kapandı. Önceki onay yeni
  belge PR'ının merge'ini veya release/yayınlamayı kapsamaz.
- [Teslim rehberi](real-demo-delivery.md) hazır paketi yeniden istemeden kalan
  dosya/dizin/komut/hash kanıtlarını ve Afra/Osman için ayrı mesaj taslaklarını
  içerir. Mustafa paylaşım taleplerini [#39 yorumunda](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6250879475)
  ve [#40 yorumunda](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6250883464)
  yayımladı. ZIP eki veya ekip erişimli OneDrive/Google Drive bağlantısı kabul
  ediliyor. Kullanıcı talimatı: **tekrar mesaj gönderme**; mevcut taleplerin
  iki teslim de artık alındı; güncel durum üst bölümde kayıtlıdır.
- Yeni `out/clean312` venv'i (Python 3.12.15, sistem paketlerine kapalı) ve
  `git archive main` ile `out/clean-demo` kaynak kopyası kuruldu. Eski bozuk
  `.venv` korunur. `requirements.txt` kurulumu ve `pip check` başarılı;
  yeni ortamda tam paket **794 passed, 2 skipped in 103.97s**. Atlamalar Windows
  symlink izinleridir. Yeni clone/Python kurulumu yapılmış sayılmaz.
- Sentetik HTML **60 ay, 55 eşleşme, ilk 2021-02, 6 trace**; hash önceki kayıtla
  aynı. Gerçek yerel Uvicorn TCP'de Health/Housing/TÜFE ve `/docs` **200**;
  anlatım null. Sunucu durduruldu. CLI help/PowerShell komut kontrolleri yapıldı;
  ayrıntı [kabul kaydında](release-acceptance.md). Önceki 12/12 ve 9/9 stub CLI
  sonuçları gereksiz tekrar çalıştırılmadı; yeni tam paket evaluator testlerini içerir.
- Tarayıcı yüzeyi bulunmadığından güncel HTML'nin görsel/hover/zoom kontrolü
  yapılmadı. Kullanıcı HTML'yi açıp bunu kontrol edebilir. Canlı LLM/EVDS çağrısı, veri
  indirme, veri silme, force push, merge, release veya yayınlama yapılmadı.

## Önceki teslim ve sonraki adım — 18 Ekim 2026

Aşağıdaki geliştirme kronolojisi önceki kaynak/test kanıtlarını korur. Teslim,
merge ve erişim durumları için üstteki güncel bölüm ve açık iş tablosu esas alınır.

- Aktif dal `feat/economic-question-api`; çalışma ağacı teslim commit'i sonrası
  temiz bırakılır. PR #63 çalışma düzeni (`a987a88`), #64 dosya wrapper'ı
  (`96031e2`) ve #65 tarihli kabul kaydı (`909f8c7`) başarılı güncel CI ile
  kullanıcı onayı kapsamında main'e merge edildi.
- PR #66 teslimi: ortak `POST /analysis/economic/question`, iki sentetik istek,
  12 vakalı offline HTTP evaluator ve davranış testleri tamamlandı. Sınırlı
  plan mevcut Housing/TÜFE servislerinden en fazla birini yürütür; mevcut
  endpoint'ler korunur. #59'un çekirdek ve API/eval kapsamı tamamlanmıştır.
- Birleşik runtime test kaynağı `624d176a37e8f7e1714cd395700270932fbe582e`
  (PR #62–#65 main + #66), Python 3.12.15 `out/python312`: tam offline paket
  **794 passed, 2 skipped in 92.08s**. İki atlama BDDK ve dosya soru testlerinin
  Windows symlink iznidir. Önceki birleşik odaklı paket **87 passed, 1 skipped**.
- Aynı kaynakta Economic offline stub **12/12**, Housing offline stub **9/9**;
  canlı çağrı **0**. İki HTTP örneği, 12 vaka şeması ve 51 yerel bağlantı
  doğrulandı; `git diff --check` temiz. Son belge commit'inin zorunlu PR CI'si
  ayrıca geçmelidir; merge son başlık SHA'sı kontrol edilerek yapılır.
- Kullanıcı #63–#66 merge sırasını onayladı. Canlı model/EVDS çağrısı, gerçek
  veri indirme, veri silme, force push, tag/release veya yayınlama yapılmadı.
- Güncel açık issue'lar kontrol edildi: Mustafa'nın kalan #42/#46 gerçek kabulü,
  Afra #39 ve Osman #40'ın erişilebilir gerçek CSV/coverage/manifest/raw/makbuz,
  BDDK Silver ve üç örnek ay karşılaştırma paketine bağlıdır. Yerel `data/`
  yalnızca `.gitkeep` içerir. Bağımsız yeni özellik uydurulmaz; bu paket
  erişilebilir olunca önce sabit planla offline doğrulama ve rapor incelemesi
  yapılır. Diğer ekip üyelerinin görevleri/dalları devralınmaz.

## #42 dosya wrapper'ı geliştirme kaydı — 18 Ekim 2026

Bu bölüm geliştirme sırasındaki kanıtı korur. Dal `45c8dcf` tabanından açıldı;
PR #62/#63 sonrası main (`a987a88`) ile merge öncesinde güncellendi.
Ortak API/eval PR #66'da açıktır. #63–#66 merge sırası kullanıcı tarafından onaylıdır.

- Aktif dal `feat/verified-housing-question`, doğrudan `45c8dcf` tabanından açıldı.
  #42'nin sunucu kontrollü yerel dosya wrapper'ı, fiziksel paket kontrolleri ve
  [kısa belgesi](housing-question-files.md) bu dalda tamamlandı.
- BDDK Silver mevcut üreticiyle doğrulanmış Bronze'dan yeniden türetilen tabloyla
  karşılaştırılır; EVDS mevcut manifest tüketicisiyle doğrulanır. Ortak kapsam
  türetildikten sonra mevcut soru/hesap servisi kullanılır. Yeni HTTP endpoint'i
  ve anlatım çağrısı eklenmedi; gerçek veri kabulü tamamlanmış sayılmaz.
- `1191654` runtime kaynağı, Python 3.12.15 (`out/python312`): odaklı paket **63 passed, 1 skipped**;
  tam paket **729 passed, 2 skipped**. Atlamalar Windows symlink izinlerindendir.
  Housing offline stub değerlendirmesi **9/9** geçti; canlı çağrı yapılmadı.
  46 yerel belge bağlantısı ve bir Python örneğinin sözdizimi kontrol edildi.
- Yerel `.venv` kayıp Python kurulumuna işaret eder. `out/python312` ve çıktılar
  Git tarafından yok sayılır. Yerel `data/` yalnızca `.gitkeep` dosyaları içerir.
- #46 sentetik kabul kaydı PR #65'te, #59 API/eval PR #66'da review bekler.
  #42/#46 gerçek kabulü #39/#40'ın erişilebilir gerçek dosya/kanıt paketini bekler.
  Bu belge düzeltmesi runtime kodunu değiştirmez; birleşik PR CI'si izlenir.
- Güncel main ile birleşik kaynakta odaklı dosya/iki analiz/Housing soru paketi
  **87 passed, 1 skipped** (Windows symlink); 49 yerel bağlantı ve diff kontrolü
  başarılıdır. Tam paket zorunlu PR CI'sinde ve son birleşik teslimde doğrulanır.

## Temel karar

Hesaplanabilen işler Python ile yapılır. LLM soru → sınırlı plan dönüşümü ve
mevcut strict JSON anlatım rolündedir. Hesaplar, veri doğrulaması, izinli analiz
seçimi ve çıktı sözleşmeleri kodun kontrolünde kalır. Serbest ekonomik yorum,
genel tool registry, web/anomali/nedensellik araçları henüz uygulanmış değildir.

## Çalışan parçalar

| Parça | Kod / belge | Durum |
| --- | --- | --- |
| BDDK ve EVDS veri katmanları | `app/lakehouse/`, ingestion belgeleri | Bronze/Silver, makbuz/hash ve dönem kontrolleri mevcut |
| Konut hesabı | `app/lakehouse/gold.py`, `app/services/housing_analysis.py` | Reel kredi ve aylık değişimler; faiz farkı < 0 ve reel kredi değişimi <= 0 koşulu |
| Konut evidence/grafik/anlatım | `app/tools/housing_evidence.py`, `housing_chart.py`, `housing_narrator.py` | Altı trace; model sayıları evidence ile kontrol edilir, Türkçe metni Python üretir |
| Dosya demosu | `scripts/run_housing_demo.py`, `app/services/evds_manifest.py` | Fiziksel EVDS zinciri, kaynak/çıktı koruması, JSON paketleri ve `--html` |
| Manifest üretimi | `scripts/build_evds_manifest.py`, `app/lakehouse/evds_manifest_producer.py` | Normal CLI mevcut 66 aylık Silver/coverage'ı seçilen Bronze'dan yeniden hesaplanan sonuçla karşılaştırır; `--demo` 60 ay üretir |
| LLM istemcisi | `app/connectors/llm_client.py` | Yapılandırılabilir OpenAI-compatible Chat Completions; kontrollü hatalar ve SDK retry=0 |
| Housing sorusu | `app/services/housing_question.py`, `app/api/housing_question.py` | Normalize satırlarda tek izinli analiz ve üç karar: ready, clarification_required, unsupported |
| Housing değerlendirmesi | `scripts/evaluate_housing_questions.py`, `evals/housing_question_cases.json` | Dokuz vakalı offline stub; ayrı, açık bütçeli canlı mod |
| TÜFE hesabı | `app/services/inflation_analysis.py`, `app/api/inflation.py` | Aylık/yıllık değişimler ve ilk-son endeks değişimi; iki analizli soru çekirdeğine PR #62 ile bağlı |
| İki analizli soru API/eval | `app/api/economic_question.py`, `scripts/evaluate_economic_questions.py` | PR #66 teslimi: ortak HTTP yüzeyi ve 12 offline vaka |
| Doğrulanmış dosya sorusu | `app/services/housing_question_files.py` | PR #64 main'de; sunucu kontrollü fiziksel paket doğrulanır, mevcut Housing servisi kullanılır |

İlgili belgeler: [Housing question](housing-question.md),
[eval](housing-question-evals.md), [inflation](inflation-analysis.md),
[file demo](housing-demo.md), [tool contracts](tool-contracts.md),
[release acceptance](release-acceptance.md).

## Değiştirilmemesi gereken anlamlar

- Varsayılan konut demo aralığı 2021-01–2025-12: 60 ay.
  Tam Silver teslim aralığı 2021-01–2026-06: 66 ay.
- Reel kredi = nominal tutar × 100 / TÜFE; TÜFE 2025=100, KFE 2023=100.
- Housing seçiminin ilk ayı için önceki ay değişimleri ve koşul null kalır.
- TÜFE servisi seçimden önce **sağlanmış** geçmişi kullanır. Aylık oran
  `(CPI[t]/CPI[t-1]-1)*100`, yıllık oran `(CPI[t]/CPI[t-12]-1)*100`.
  Geçmiş yoksa null; ilk-son değişim aylık oranların toplamı değildir.
- Weekly coverage, doğrulanmış yayın takvimi olmadan unverified/not_available;
  expected_count null. Tam aylık seri, tam haftalık yayın takvimi kanıtı değildir.
- Fiziksel manifest doğrulaması şu an CLI'da mevcuttur. Mevcut normalize-satır
  soru API'si veya genel dosya yükleme servisi aynı kontrolü otomatik yapmaz.

## Açık işler ve sahipleri

Bu tablo 18 Ekim tarihli durumdur; GitHub erişimin varsa güncel body/yorumları oku.

| Issue | Sorumlu | Kalan sonuç |
| --- | --- | --- |
| [#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46) | Mustafa | Gerçek teknik/görsel kabul tamam; kısa sunum ve ayrı onaylı tag/release teslimi açık |

#6, #39, #40, #41, #42, #44, #45, #56 ve #59 tamamlandı. PR #43 ve #58 merge edildi; yeni bir
üretici/tüketici düzeltme PR'ı beklenmiyor. Gerçek EVDS dosyaları erişilebilir ve
Mustafa'da bağımsız doğrulandı. BDDK teslimi ve birleşik teknik kabul de tamam;
Mustafa'nın HTML etkileşim kabulü de kendi tarayıcı teyidiyle alındı.

## #59'un ilk parçası: servis çekirdeği (PR #62 ile merge edildi)

Aşağıdaki ilk parça PR #62'de (`01018ae`) tamamlandı ve kullanıcı onayıyla
`6abcfb8` olarak main'e merge edildi. Ortak API/eval PR #66 teslimidir;
bağımsız #42 dosya wrapper'ı PR #64 ile main'dedir.

1. Çalışma ağacını/branch'i kontrol et, bu notu ve #59'u oku. Yerel değişiklikleri
   koru. Python 3.12 `.venv` ve offline başlangıç testini doğrula.
2. `feat/economic-question-routing` gibi ayrı bir dalda yalnızca çekirdeği ele al.
   Bu isim zaten varsa dalın içeriğini kontrol et; mevcut işi ezme.
3. Tek model planlama çağrısında iki izinli analysis_id'yi destekle:
   `housing_rate_down_real_credit_not_up` ve `cpi_inflation_summary`.
   Model, hesap sonucu/SQL/kod/dosya yolu/anahtar üretmesin.
4. Planı ve analize ait kullanılabilir veri kapsamını doğrula. Belirsiz soru
   açıklama isteği, desteklenmeyen tahmin/nedensellik unsupported olsun.
   Veri yokluğu ve geçersiz model yanıtı kontrollü sonuç/hata versin.
5. Doğru mevcut servisi en fazla bir kez çağır. Housing hesabını veya TÜFE
   formüllerini dispatcher içinde yeniden yazma. İlk çekirdekte narrator,
   yeni HTTP endpoint'i, UI veya serbest ekonomik yorum ekleme.
6. Stub modelle iki geçerli analiz, eksik/belirsiz dönem, kapsam dışı istek,
   bozuk/izin dışı plan, prompt injection ve model hatasını test et.
   Çalışmaması gereken kararda sıfır analiz çağrısını; doğru planda doğrudan
   servisle sayısal eşitliği doğrula. Mevcut Housing davranışları korunsun.
7. Kısa çekirdek belgesi, odaklı testler ve tam paketle review edilebilir ilk
   değişikliği teslim et. Issue #59'u yalnızca bu ilk parça ile kapatma;
   ortak API ve değerlendirme seti sonraki küçük PR'dır.

Bu görev gerçek veri teslimini beklemeden sentetik girdilerle yapılabilir.
GitHub erişimi yoksa bu yerel kapsamla ilerle, erişilemeyen issue/PR bilgisini
doğrulanmış gibi sunma. Commit/push/PR/merge adımlarında oturumdaki kullanıcı
yetkisini izle; bir yetki veya araç eksikse yerel diff/test sonucunu teslim et.

## PR #63 çalışma düzeni kaydı — 18 Ekim 2026

- Kullanıcının devam/teslim ve onay sınırları `AGENTS.md` içine eklendi.
  PR #63, güncel tabanında başarılı CI sonrası `a987a88` ile merge edildi.
- Kullanıcı #63–#66 PR'larının sırayla merge edilmesini onayladı. Diğer
  merge/release, canlı çağrı ve yayınlama işlemleri ayrıca onay gerektirir.
- Önceki PR #62 test kaydı 731 passed, 1 skipped ve Housing stub 9/9'dur;
  tarihli kaynak kanıtıdır. Yerel `.venv` kayıp Python yoluna işaret eder;
  kullanılan `out/python312` Python 3.12.15 ortamı Git tarafından yok sayılır.

## PR #65 kabul kaydı güncellemesi — 18 Ekim 2026

- Aktif dal `docs/current-demo-acceptance`; ilk taban `45c8dcf`, güncel birleşik
  taban `96031e2` (PR #62/#63/#64 main'de). Kendi diff'i yalnızca belgelerdir.
- PR #64, başarılı güncel CI sonrasında `96031e2` ile merge edildi. Birleşik
  odaklı soru/dosya testleri 87 passed, 1 skipped; gerçek kabul hâlâ açık.
- #59 ortak API/eval PR #66'dadır. `a672bf3` runtime kaynağının önceki sonucu
  96 odaklı, 772 passed/1 skipped tam paket; Economic stub 12/12, Housing 9/9.
  Son birleşik teslim bunları yeniden doğrulayacaktır.
- `45c8dcf` main arşivinde Python 3.12.15 ile 707 passed, 1 skipped; 60 aylık
  sentetik HTML ve süreç içi Health/Housing/TÜFE HTTP kontrolleri başarılıydı.
  Ayrıntı ve çıktı hash'i [kabul kaydında](release-acceptance.md); bu sonuç
  güncel birleşik main testi veya yeni clone/ortam kurulumu değildir.
- Belge bağlantıları ve diff kontrol edilir; zorunlu Tests CI bu PR'ın güncel
  başlığında izlenir. Yerel `data/` yalnızca `.gitkeep` içerir.
- #39/#40'ta erişilebilir yeni gerçek paket/kanıt teslimi görünmedi. Afra ve
  Osman'ın görevleri devralınmadı; canlı çağrı, veri indirme veya release yok.
- Sıradaki adım onaylı #65/#66 merge sırasını tamamlamak; ardından #42/#46
  gerçek kabulü için #39/#40 dosya/kanıt paketine erişmektir.

## Yerel Windows başlangıcı

Repo zaten klonluysa VS Code ile **repo kök klasörünü** açmak yerel dosya
çalışması için yeterlidir. ChatGPT oturumu açmak, GitHub'a push veya issue/PR
erişimi için ayrıca yetki verildiği anlamına gelmez. Mevcut Git kimlik doğrulaması
korunur; GitHub CLI/entegrasyonu gerekiyorsa erişimi ayrıca doğrula.

PowerShell'de mevcut venv ile:

```powershell
git status
git branch --show-current
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest -q
```

Temiz çalışma ağacında güncelleme gerektiğinde:

```powershell
git switch main
git pull --ff-only
```

Bu sohbette son runtime Linux/PR CI kanıtı 708 geçen testtir. Kullanıcının
Windows/venv sürümleri farklı olabilir; yeni sonuç aynen raporlanmalı. Başlangıç
için canlı modele ihtiyaç yoktur. Gemini Free Tier anahtarı uygulamanın isteğe
bağlı canlı çağrıları içindir; Codex'e ChatGPT hesabıyla girişten ayrıdır.

## Devamlılık

Her teslim sonunda testleri, diff kapsamını ve kalan parçayı kısaca kaydet.
Bu nottaki planlı işi yapılmış gibi işaretleme. Gerçek 60 aylık kabul yapılmadan
release tamamlandı veya ekonomik analiz/model doğruluğu ölçüldü deme. Aynı
görev üzerinde bu sohbet ve yerel Codex oturumu eşzamanlı farklı kod üretmesin.

## #59 servis çekirdeği ilerlemesi — 17 Ekim 2026

`feat/economic-question-routing` dalında iki izinli analiz için tipli soru planı,
veriden türetilen dönem kapsamı ve mevcut Housing/TÜFE servislerine tek yürütmeli
yönlendirme eklendi. Sınırlar ve kapsam dışı kararlar
[çekirdek belgesinde](economic-question.md). Mevcut Housing soru endpoint'i
değişmedi. #59 açık kalır; ortak HTTP yüzeyi, örnekler ve sınırlı değerlendirme
seti sonraki küçük PR kapsamıdır.

Bu yerel Windows kopyasında mevcut `.venv` kayıp bir Python 3.12 yoluna işaret
ettiği için testlerde Git tarafından yok sayılan `out/python312` ortamında Python
3.12.15 kullanıldı. Temiz `HEAD` başlangıç paketi **707 passed, 1 skipped**;
çekirdek sonrası tam paket **731 passed, 1 skipped**. Housing offline stub
değerlendirmesi **9/9** geçti. Bunlar canlı model başarı ölçümü veya gerçek veri
kabulü değildir.

## #59 ortak HTTP ilk geliştirme kaydı — 18 Ekim 2026

Bu bölüm `a672bf3` kaynağının tarihçesidir; son entegrasyon kaydı aşağıdadır.

- Kullanıcı onayıyla PR #62, `6abcfb8` commit'iyle main'e merge edildi. Öncesinde
  aynı `01018ae` başlığı, temiz diff, başarılı CI ve boş review/yorum durumu
  kontrol edildi. Diğer PR'lar için merge onayı verilmiş sayılmaz.
- Aktif dal `feat/economic-question-api`, güncel main `6abcfb8` tabanlıdır.
  `POST /analysis/economic/question`, iki sentetik JSON örneği ve 12 vakalık
  offline HTTP değerlendirmesi PR #66'dadır; henüz main'de değildir.
- `a672bf3` API/eval runtime kaynağı, Python 3.12.15 (`out/python312`): odaklı paket **96 passed**;
  tam paket **772 passed, 1 skipped**. Tek atlama mevcut BDDK Windows symlink
  kontrolüdür. Economic offline stub **12/12**, mevcut Housing offline stub
  **9/9** geçti; canlı model/EVDS çağrısı yapılmadı.
- İki HTTP JSON örneği ve vaka şeması doğrulandı; 48 yerel belge bağlantısı ile
  üç PowerShell bloğunun sözdizimi kontrol edildi. HTTP örnekleri canlı modele
  gönderilmedi. Stub geçişleri model anlama başarısı değildir.
- PR #63 çalışma düzeni, #64 doğrulanmış dosya sorusu ve #65 kabul kaydı ayrı
  PR'lardır. #59 API kodu bunlara bağımlı değildir. #42/#46 gerçek kabulü hâlâ
  Afra/Osman'ın #39/#40 dosya ve kanıt teslimini bekler.
- #62 sonrası #63 devir kaydı (`846f0f8`) ve #64 README/devir kaydı (`013a23e`)
  çakışmaları kendi dallarında belge commit'leriyle giderildi. #65 (`fc1662a`)
  kabul/devir kaydı da yeni main durumuyla düzeltildi. Runtime kodu, fixture
  hash'leri ve paylaşılan geçmiş değiştirilmedi; force push veya başka merge yok.
- PR #66'nın `a672bf3` CI'si başarılı; #59 ilerlemesi bu test kaynağı belirtilerek
  güncellendi ve issue review/merge için açık bırakıldı. Sıradaki adım açık
  #63–#66 PR'ları için kullanıcı merge onayı ve gerçek kabul için #39/#40
  dosya/kanıt paketine erişimdir. Bu belge takibi API runtime'ını değiştirmez.
