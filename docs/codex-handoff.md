# Codex devir notu — 18 Ekim 2026

Bu not, Mustafa'nın yerel VS Code/Codex oturumuna proje bağlamını taşır.
Kurulum adımları ve hesap arayüzü zamanla değişebilir; bu dosya ürün kurulumu
için bir sürüm garantisi değildir. Güncel main: `6abcfb8` (PR #62 sonrası).
Bu belge dalı PR #62 sonrası main ile güncellendi; kendi diff'i runtime değişikliği içermez.
Yeni bir oturum güncel HEAD'i, çalışma ağacını ve ilgili issue'yu yeniden kontrol
etmelidir. Mustafa Hacettepe Bilgisayar Mühendisliği üçüncü sınıf öğrencisidir;
ekip Mustafa, Osman ve Afra'dan oluşur. İlk hedef çalıştırılabilir bir CV demosudur.

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
| TÜFE hesabı | `app/services/inflation_analysis.py`, `app/api/inflation.py` | Aylık/yıllık değişimler ve ilk-son endeks değişimi; henüz soru yönlendirmesinde değil |

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
| [#59](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/59) | Mustafa | Çekirdek PR #62 main'de; ortak HTTP/örnekler/eval PR #66'da açık |
| [#42](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/42) | Mustafa | Doğrulanmış dosya wrapper'ı PR #64'te açık; gerçek veri kabulü bekler |
| [#39](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39) | Afra | Gerçek CSV/coverage/manifest/raw/makbuz paketine ekip erişimi ve üç gerçek örnek ay karşılaştırması |
| [#40](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40) | Osman | Gerçek BDDK+EVDS ile 66→60 ay ve üç örnek ayın birleşik demo kabulü |
| [#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46) | Mustafa | Gerçek rapor, güncel kurulum/kabul kaydı, kısa demo ve katkı/sürüm notu |

#6, #41, #44, #45 ve #56 tamamlandı. PR #43 ve #58 merge edildi; yeni bir
üretici/tüketici düzeltme PR'ı beklenmiyor. Gerçek veri dosyaları bu oturumda
erişilebilir ve bağımsız doğrulanmış sayılmaz; ilgili yazarların yerel kabul
beyanları ile bağımsız kabul birbirinden ayrılır.

## #59'un ilk parçası: servis çekirdeği (PR #62 ile merge edildi)

Aşağıdaki ilk parça PR #62'de (`01018ae`) tamamlandı ve kullanıcı onayıyla
`6abcfb8` olarak main'e merge edildi. Ortak API/eval PR #66'da; bağımsız #42
dosya wrapper'ı PR #64'tedir. İkisi de kendi review/merge adımını bekler.

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

## Oturum kaydı — 18 Ekim 2026

- Aktif dal `docs/autonomous-workflow`; kullanıcının devam/teslim ve onay
  sınırları `AGENTS.md` içine kaydedildi. Değişiklik belge kapsamındadır.
- PR #62 merge'i `6abcfb8` ile tamamlandı. Kullanıcı #63–#66 PR'larının sırayla
  merge edilmesini de onayladı; her biri güncel tabanında gerekli CI'den geçer.
  Yeni API/eval işi PR #66'dadır; diğer merge/release işlemleri ayrıca onay ister.
- PR #62'nin önceki Windows kaydı 731 passed, 1 skipped ve Housing stub 9/9'dur;
  bu belge dalında aynı testler yeniden çalıştırılmış sayılmaz.
- Yerel `.venv` kayıp Python yoluna işaret eder. Test ortamı Git'in yok saydığı
  `out/python312` altında Python 3.12.15'tir.
- Altı yerel bağlantı ve `git diff --check` doğrulanır; zorunlu PR CI'si izlenir.
  #39/#40 gerçek dosya/kanıt teslimi #42/#46'nın kabulü için hâlâ gereklidir.

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
