# Sınırlı konut–TÜFE soru çekirdeği

Takip: [#59](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/59).
`app/services/economic_question.py`, Türkçe bir soruyu tek model çağrısında
doğrulanmış plana dönüştürür ve en fazla bir mevcut Python analizini çalıştırır.
Ortak HTTP yüzeyi `POST /analysis/economic/question` ve 28 vakalık offline HTTP
değerlendirme seti mevcuttur. Mevcut `/analysis/housing/question` yalnızca konut
analizini desteklemeye devam eder.

İzinli `analysis_id` değerleri:

- `housing_rate_down_real_credit_not_up`: faiz düşerken reel konut kredisi
  stokunun artmadığı aylar; mevcut `run_housing_analysis()` servisi.
- `cpi_inflation_summary`: genel TÜFE endeksinin aylık, aynı ayın önceki yılına
  göre yıllık ve seçilen ilk-son ay değişimleri; mevcut
  `build_inflation_evidence()` servisi.

Çağıran, normalize edilmiş `HousingQuestionData` ve/veya
`InflationQuestionData` sağlar. Servis konut kapsamını ortak, kesintisiz
BDDK/EVDS aylarından; TÜFE kapsamını sayısal değerleri ve tüm geçmişi
doğrulanmış CPI satırlarından türetir. Kaynak referansları ve tablolar modele
gönderilmez. Bu satırlar henüz fiziksel dosya/manifest ile doğrulanmış veri
sayılmaz.

Plan yalnızca `status`, izinli `analysis_id`, `start_period`, `end_period`
alanlarını taşıyabilir. `ready` için dönem açık olmalıdır. Belirsiz dönem/metrik
veya analiz `clarification_required`; tahmin, nedensellik, başka analiz ve iki
analizi birlikte isteme `unsupported` kararıdır. İstenen dönem veriye sığmazsa
kırpılmaz, `outside_coverage` açıklaması döner. Seçilen veri yoksa
`data_unavailable` döner. Bu kararlarda analiz çalışmaz. Bozuk veya ek alanlı
model JSON'u `EconomicPlanValidationError`, model çağrısı hatası ham sağlayıcı
metni olmadan `EconomicPlanningError` üretir.

Konut sonucunun ilk seçilen ayında önceki ay değişimi mevcut servis sözleşmesi
gereği `null` kalır. TÜFE sonucu, sağlanan seçim öncesi geçmişi kullanır;
karşılaştırma ayı yoksa ilgili oran `null` olur. İlk-son endeks değişimi aylık
oranların toplamı değildir. İki formül de yönlendirme servisinde tekrarlanmaz.

Bu sınırlama kodda şema, dönem ve servis seçimi için uygulanır. Modelin sorudaki
anlamı doğru seçtiği offline stub testleriyle kanıtlanmaz; prompt injection
metninin geçerli fakat yanlış bir plan ürettirmesi ancak ayrıca gerçek model
değerlendirmesinde ölçülebilir. Canlı model veya resmî veri kabulü bu parçanın
parçası değildir.

## Soru API'si

İstek, zorunlu `question` ve isteğe bağlı iki veri grubu alır:

- `housing`: normalize `bddk_monthly`, `evds_monthly`, `bddk_source_ref`,
  `evds_source_refs` alanları; mevcut Housing satırları yeni endpoint'te katı
  sayı tipleriyle doğrulanır.
- `inflation`: `cpi_monthly` (`period`, pozitif/sonlu `cpi_index`) ve `source_ref`.
  Sağlanan seçim öncesi geçmiş de bu grupta gönderilir.

İki grup birlikte bulunabilir; soru başına tek analiz seçilir. Veri grupları
verilmezse model çağrısı yapılmadan `data_unavailable` döner. Gruplar içindeki
boş listeler, eksik/mükerrer aylar ve geçersiz sayılar 422 hatasıdır. Konut
satırları ortak dönem taşımıyorsa o analiz için kapsam yoktur. Sunucu her
analizin kapsamını bağımsız türetir; TÜFE geçmişi konut kapsamına kırpılmaz.

Model, anahtar, dosya yolu, SQL, `analysis_id`, `start_period`, `end_period` veya
coverage üst alanları istek parametresi değildir. Satırlardaki `period` veri
dönemidir; analiz dönemi planlayıcıdan gelir ve çekirdekte doğrulanır.
Kaynak etiketleri fiziksel dosya doğrulaması yerine geçmez; bu HTTP yüzeyi
çağıranın sağladığı normalize satırları işler.

| HTTP / durum | Yanıt |
| --- | --- |
| 200 / `ok` | `decision`, `available_periods`, tipli `analysis` |
| 200 / `clarification_required` | Sabit uygulama mesajı ve `analysis=null` |
| 200 / `unsupported` | Desteklenen kapsam mesajı ve `analysis=null` |
| 200 / `data_unavailable` | Seçilen veri grubu/kapsam yok; `analysis=null` |
| 422 / `invalid_economic_input` | Geçersiz JSON/istek/sayısal veri; ham girdi dönmez |
| 502 / `question_planning_failed` | Model çağrısı başarısız; retry veya diğer analize geçiş yok |
| 502 / `invalid_question_plan` | Bozuk veya izin dışı plan; analiz çalışmaz |

`available_periods` içinde `housing` ve `inflation` dönemleri veya `null` vardır.
`analysis.analysis_id`, `analysis.evidence` tipini belirler. Konut sonucunda
ayrıca mevcut altı trace'li `analysis.chart` bulunur; TÜFE sonucu evidence
taşır. Endpoint anlatım çağrısı yapmaz ve sohbet geçmişi tutmaz.

### Sentetik istek örnekleri

[İki veri gruplu Housing örneği](economic-question-api-example.json) 3 ay ve
2021-02 eşleşmesi bekler. [Geçmişli TÜFE örneği](economic-question-cpi-example.json)
2020-01–2021-03 girdisinden 2021-01–2021-03 seçer: Ocak aylık oranı yaklaşık %4,
yıllık oranı %30 olur. Bunlar gerçek ekonomik bulgu değildir.

Aşağıdaki HTTP kullanımı canlı planlama çağrısı yapar; yalnızca ayrıca yetki
verilmiş model erişiminde çalıştırılmalıdır. Offline doğrulama komutu sonraki
bölümdedir.

```powershell
$body = Get-Content .\docs\economic-question-cpi-example.json -Raw -Encoding UTF8
$result = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analysis/economic/question -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result.analysis.evidence
```

## Yalnızca soru alan doğrulanmış dosya API'si

Takip: [#69](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/69).
`POST /analysis/economic/question/files` yalnızca `{"question":"..."}` alır;
`housing`, `inflation`, yol, dönem, model veya anahtar üst alanları reddedilir.
Eski normalize-satır endpoint'lerinin istek/yanıt davranışı korunur.

Sunucu `ANALYTICS_DATA_ROOT` değişkeninden (process environment veya yerel `.env`)
`data/` klasörünü içeren kökü seçer; boşsa depo kökü kullanılır. Göreli yollar:

- `data/silver/bddk/housing_loans.parquet`
- `data/bronze/bddk/aylik/raw/` ve `data/bronze/bddk/aylik/receipts/`
- `data/silver/evds/monthly/manifest.json`; CSV ve EVDS raw/makbuz yolları manifestten.

Mevcut [fiziksel yükleyici](housing-question-files.md) tam paketi her istekte
modelden önce doğrular. Bu ilk sürümde iki analiz için de tam BDDK+EVDS paketi
gerekir; bir dosya bozuksa diğer analize sessiz geçiş veya eski veri cache'i yoktur.
BDDK Bronze→Silver eşitliği, EVDS fiziksel hash/kaynak/metadata ve sürekli kapsam
kontrolleri gevşetilmedi. Doğrulanmış bellek kopyası plan sonrasında tekrar okunmaz.

`run_verified_economic_question()` iki mevcut hesabı aynı `run_economic_question()`
çekirdeğine verir. Konut kapsamı ortak aylardır; TÜFE tüm doğrulanmış EVDS geçmişini
kullanır, konut kapsamına kırpılmaz. Soru başına en fazla bir plan ve bir hesap
çağrısı vardır; netleştirme/unsupported/kapsam dışı planda hesap çalışmaz.
Yanıt aynı `status/decision/available_periods/analysis` yapısındadır. Konutta mevcut
evidence/grafik ve weekly coverage notu korunur. TÜFE'de hesaplar aynı kalırken
`input_origin=verified_files`, yalnız TÜFE makbuz referansları ve fiziksel doğrulama
notu döner; eski satır API'sinde `caller_supplied` varsayılanı değişmez.

| HTTP / kod | Davranış |
| --- | --- |
| 503 / `economic_data_unavailable` | Paket yüklenemiyor/doğrulanamıyor; bu durumda model/analiz çağrısı 0. Plan sonrası hesap doğrulanamazsa da güvenli 503 döner, başka analize geçilmez |
| 422 / `invalid_economic_input` | Boş/uzun soru, ek istek alanı veya bozuk JSON; ham girdi dönmez |
| 502 / `question_planning_failed` | Tek model denemesi başarısız; sağlayıcı gövdesi/anahtarı/yolu dönmez |
| 502 / `invalid_question_plan` | Şema/izin/dönem sırası hatası; hesap çalışmaz |

Kullanım/başlatma komutu [README'dedir](../README.md#question-only-api-with-verified-server-files).
Bu endpoint anlatım modeli çağırmaz. Ekran #70, sınırlı canlı kabul #71'dir;
canlı Gemini çağrısı öncesinde vaka listesi ve azami çağrı sayısı ayrıca onaylanır.
Offline stub sonuçları modelin Türkçe anlama başarısı değildir.

## Offline değerlendirme

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_economic_questions
```

`evals/economic_question_cases.json` içindeki 28 vaka gerçek HTTP doğrulaması ve
Python analizleriyle, sabit model yanıtları kullanılarak çalışır. Housing/TÜFE
sonuçları aynı girdili doğrudan hesap endpoint'leriyle karşılaştırılır;
soru başına plan/analiz çağrıları sayılır. Referans hesap istekleri soru
yürütme sayacına dahil değildir. Rapor `out/economic-question-eval-offline.json`
altındadır; `--output` yalnızca `out/` içinde başka bir rapor seçebilir.

İlk 12 vakanın soru/beklenti/stub yanıtları korunmuştur. Ek 16 vaka; farklı Türkçe
ifadeler ve tarih biçimleri, eksik yıl/bitiş, göreli dönem, nominal/reel belirsizliği,
genel analiz isteği, kapsam dışı dönem, ters faiz koşulu, dönem karşılaştırması ve
alakasız isteği kapsar. Beklentiler model çıktısı görülmeden yazıldı; yeni vakaların
`rationale` alanı gerekçeyi açıklar. Anlamlı fakat desteklenmeyen ekonomik sorular
anlamsız olarak etiketlenmez. Dağılım: 9 ready, 10 netleştirme, 7 unsupported,
2 veri yokluğu. Tahmin/nedensellik/şema değiştirme talepleri eski sette de vardır.

Rapor **`offline_stub / harness_behavior_only`** olarak etiketlenir; 28/28 gibi
bir stub sonucu modelin Türkçe anlama başarısı veya injection dayanıklılığı değildir.
Hazırlıkta gerçek model/EVDS çağrısı yapılmadı. 20 Ekim'deki ayrı onaylı canlı
koşunun sonucu aşağıda kaydedildi; #71'in dört gerçek vaka kaydı ayrı kanıttır
ve tüketilen bütçesi bu değerlendirmeye yetki vermez.

### Seçilmiş canlı planlama yolu — ayrı onay gerekir

Varsayılan hâlâ offline'dır. `--live` **açık `--case` seçimi ve pozitif
`--max-model-calls`** olmadan çalışmaz; seçim sırası korunur, bilinmeyen/tekrarlı
kimlik reddedilir. Canlı yol mevcut LLM istemcisini, ekonomik çekirdeği ve aynı
HTTP endpoint'ini kullanır. Sentetik girdiler/coverage ve doğrudan Python referans
hesapları modelden önce doğrulanır; gerçek veri paketi veya EVDS indirmesi gerekmez.
Modele yalnız soru ve veri kapsamı gider, beklenen karar/stub yanıtı gitmez.

- Soru başına en fazla 1 planlama çağrısı, toplamda kesin bütçe. Başarısız istek
  de bütçeyi tüketir; SDK retry 0, ek anlatım/model hakemi/sağlayıcı geçişi yok.
- İlk sağlayıcı, geçersiz plan, yanlış karar/analiz/dönem veya hesap hatasında durur;
  sonraki vakalar `not_run_after_failure` olur. Bütçe yetmezse kalanlar
  `budget_exhausted` olarak atlanır ve komut başarısız döner; sınır artırılmaz.
- Hem modelin ham planının **doğrulanmış alanları** hem çekirdeğin son kararı
  önceden sabitlenen beklentiyle karşılaştırılır. Şemaya uyan yanlış analiz/dönem
  başarısızdır. Kapsam dışı vakalarda tam istenen ready planın çekirdekte
  reddedilmesi veya doğrudan güvenli `outside_coverage` netleştirmesi önceden
  kabul edilmiştir (`accepted_model_decisions`); başka tarih uydurmak kabul edilmez.
- Varsayılan raporlar ayrı: `out/economic-question-eval-offline.json` ve
  `out/economic-question-eval-live.json`. Canlı raporun üzerine yazılmaz;
  sonraki onaylı koşuda yeni `--output` gerekir. Offline yol da canlı raporu ezmez.
  Raporlarda vaka kimliği/sorusu, beklenen/gerçek model ve son karar, deneme sayısı,
  başarısızlık/atlama nedeni, seçilen kimlikler, kaynak commit/dirty bilgisi,
  evaluator/vaka/fixture hash'leri bulunur. Anahtar/ham sağlayıcı hata gövdesi yoktur.
- Sahte sağlayıcıyla test edilen live kontrol akışı gerçek model ölçümü değildir.
  Gerçek koşu `live_model / selected_live_cases` etiketi taşır; seçilmiş birkaç
  vakanın sonucu genel başarı oranı olarak sunulmaz.

20 Ekim'de ayrıca onaylanan ilk alt küme: **EQ-013, EQ-016, EQ-020, EQ-022, EQ-024, EQ-025,
EQ-026, EQ-010**. İki farklı analiz ifadesi, eksik yıl, belirsiz metrik, kapsam
dışı dönem, ters koşul, karşılaştırma ve şema değiştirme talepleri. **Azami 8 toplam
çağrı, retry 0, timeout 60 saniye, ilk hatada durma** sınırı kullanıldı.
Mevcut yerel model `gemini-3.5-flash-lite`; sağlayıcı/model değiştirilmez.
Sorular ve dönem/karar beklentileri JSON setinde sabit kaldı. Aşağıdaki komut
`dd149d9c4d94cea64bec76e2975a510b5900f920` PR head'inde bir kez çalıştırıldı;
**yeniden çalıştırma yetkisi yoktur**:

```powershell
.\out\clean312\Scripts\python.exe -m scripts.evaluate_economic_questions --live `
  --case EQ-013 --case EQ-016 --case EQ-020 --case EQ-022 `
  --case EQ-024 --case EQ-025 --case EQ-026 --case EQ-010 `
  --max-model-calls 8 --output out/economic-question-eval-77-live.json
```

Sonuç: **3 çağrı denemesi; 2 geçen, 1 başarısız, 5 çalıştırılmayan vaka**.
EQ-013 konut ve EQ-016 TÜFE için 2021-01–2021-03 planları ve hesaplar mevcut
doğrudan Python referansına eşitti. EQ-020, “Ocak-Mart TÜFE aylık ve yıllık
oranlarını göster.” sorusunda beklenen `clarification_required / period_required`
yerine `ready / cpi_inflation_summary / 2021-01–2021-03` döndürdü. Yıl sorulmadan
bir TÜFE analizi çalıştı; kullanıcı istemediği yılın sonucunu alabilirdi.
Evaluator `status_mismatch` kaydedip diğer beş vakayı `not_run_after_failure`
olarak atladı. Retry/ek çağrı yok; kullanılmayan beş deneme yeni yetki değildir.

Özgün rapor `out/economic-question-eval-77-live.json` Git dışında korunur;
SHA-256: `208728435b2a72290cc9066927cc0219662779d48c110a46373147cb678084e4`.
Rapor kaynak head'i/temiz ağaç bilgisini, sabit beklenti ve fixture hash'lerini taşır.
Vaka beklentileri veya girdiler sonuç görüldükten sonra değiştirilmedi. Bu küçük
ve ilk hatada kesilmiş koşu genel model başarı oranı değildir; UI kabulü de değildir.

Offline düzeltme: prompt, eksik yıl/başlangıç/bitiş bilgisinin kullanıcı sorusundan
gelmesi ve `available_periods` veya bugünden tamamlanmaması kuralını genelleştirdi.
Gözlenen hatalı plan ağsız sahte sağlayıcı regresyonunda hâlâ başarısız sayılır ve
sonraki vaka durur; oracle gevşetilmedi. Bu test evaluator davranışını doğrular,
prompt'un gerçek modelde hatayı giderdiğini kanıtlamaz. Düzeltmenin canlı etkisi
**henüz doğrulanmadı**. Yeni koşu ayrıca onay ve farklı `--output` gerektirir;
gerçek sağlayıcı/plan hatası otomatik tekrar denenmez.

Mustafa'nın mevcut Python 3.12.15 ortamında offline komut için de `.venv` yerine
`out/clean312/Scripts/python.exe` kullanılabilir; eski `.venv` yolu onarılmadı,
yeni kurulum/dependency yok. Python hesapları ve HTTP sözleşmeleri değişmedi;
yukarıdaki prompt düzeltmesi yalnız offline hazırlanmıştır.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_economic_question.py tests/test_housing_question.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_economic_question_api.py tests/test_economic_question_evals.py -q
.\.venv\Scripts\python.exe -m pytest -q
```
