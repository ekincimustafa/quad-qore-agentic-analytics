# Sınırlı konut–TÜFE soru çekirdeği

Takip: [#59](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/59).
`app/services/economic_question.py`, Türkçe bir soruyu tek model çağrısında
doğrulanmış plana dönüştürür ve en fazla bir mevcut Python analizini çalıştırır.
Ortak HTTP yüzeyi `POST /analysis/economic/question` ve 45 vakalık offline HTTP
değerlendirme seti mevcuttur. Mevcut `/analysis/housing/question` yalnızca konut
analizini desteklemeye devam eder.

Normal model yolunda `ask_economic_plan`, `EconomicModelResponse` sabit alanlı
nesne şemasını OpenAI uyumlu API'ye `response_format=json_schema` ile gönderir.
Sekiz alan da zorunlu; seçilen kararda kullanılmayanlar açık null'dır. Taşıma
nesnesi doğrulandıktan sonra yalnız bilinen null alanlar çıkarılır ve aşağıdaki
mevcut karar tipi aynen doğrulanır. Dolu ilgisiz alanlar atılmaz; eksik alanlar
tamamlanmaz. Eski yalın karar JSON'ları ve HTTP yanıtları korunur. Servis, normal
HTTP, doğrulanmış dosya HTTP ve canlı evaluator CLI aynı planlayıcıyı kullanır.
Sağlayıcı/modelin şema desteği gerekir; reddedilen istekte otomatik tekrar veya
metin moduna geçiş yoktur. Dönen metin ayrıca mevcut katı Pydantic doğrulaması
ve Python guard'lardan geçer; Markdown kod bloğu soyulmaz, eksik alan veya
koşul uydurulmaz. Offline sabit planlar ve enjekte edilen `model_call` arayüzü
değişmedi. Ayrıntı: [LLM istemcisi](llm-client.md#hata-ve-anlatım-sınırı).

İzinli `analysis_id` değerleri:

- `housing_rate_down_real_credit_not_up`: faiz düşerken reel konut kredisi
  stokunun artmadığı aylar; mevcut `run_housing_analysis()` servisi. Bu kimlik
  yalnız sabit kuralın aynen istendiği sorular içindir.
- `housing_condition_filter`: dönemdeki ayları 1–3 tipli metrik/operatör/eşik
  koşuluyla (AND) filtreler; mevcut `run_housing_filter()` çekirdeği.
- `cpi_inflation_summary`: genel TÜFE endeksinin aylık, aynı ayın önceki yılına
  göre yıllık ve seçilen ilk-son ay değişimleri; mevcut
  `build_inflation_evidence()` servisi ve üç panelli `build_inflation_chart()`
  çıktısı.
- `cpi_two_year_comparison`: iki tam takvim yılının Ocak–Aralık TÜFE
  değişimleri ve Aralık yıllık oran farkı; mevcut
  `compare_inflation_years()` çekirdeği. Plan yalnız `first_year` ve
  `second_year` taşır; yıl sırası kullanıcının söylediği sıradır.

### Parametreli konut koşulu filtreleme çekirdeği

`app/services/housing_filter.py` içindeki `run_housing_filter()`, normalize
BDDK/EVDS satırlarında 1–3 tipli koşulu AND ile uygular. İzinli metrikler
`interest_rate_change_pp` (yüzde puan), `real_housing_loan_change_pct`,
`nominal_housing_loan_change_pct` ve `housing_loan_interest_rate_pct`
(yüzde); operatörler `lt`, `lte`, `gt`, `gte`. Eşik sonlu bir sayı olmalıdır;
bool/metin/NaN/Infinity, bilinmeyen metrik veya operatör ve fazladan alan
reddedilir. Koşullar Gold hesaplayıcısı çalışmadan önce doğrulanır.

Servis `build_housing_gold_table()` çağrısını bir kez yapar ve hesapları
tekrar etmez; eski `rate_down_real_credit_not_up` bayrağını ön filtre olarak
kullanmaz. Null bir koşul değeri olan ay değerlendirilemez ve eşleşmez; ilk ay
değişim koşullarında dışarıda kalır, yalnız faiz seviyesi koşuluyla
eşleşebilir. Boş eşleşme başarılı boş sonuçtur. Evidence açık dönemi,
koşulları ve birimlerini, `observed_month_count`, `evaluable_month_count`,
`matched_month_count`, kronolojik `matched_periods`, eşleşen ayların Gold
değerleri/kaynakları/kalite notlarını taşır. Girdiler değiştirilmez; JSON'da
NaN/Infinity bulunmaz. Servis fiziksel dosya veya hash doğrulaması yapmaz.

Eski kuralın parametre karşılığı
`interest_rate_change_pp lt 0` + `real_housing_loan_change_pct lte 0`
mevcut `find_rate_down_real_credit_not_up()` ile aynı ayları verir. Soru/HTTP
katmanında bu analiz `{"status":"ready","analysis_id":"housing_condition_filter",
"start_period":"...","end_period":"...","conditions":[...]}` planıyla seçilir.
Python, sorudaki açık metrik/yön/eşik/birim ifadelerini
`app/services/housing_filter_question.py` ile sınırlı biçimde çıkarır. Her
karşılaştırma kendi sayısına eşlenir; açık negasyon tersine çevrilir,
azalış/düşüş eşikleri işaretli değişime dönüştürülür ve aynı metrikteki iki
sınır birlikte korunur. Eski `housing_rate_down_real_credit_not_up` planı yalnız
`interest_rate_change_pp lt 0` + `real_housing_loan_change_pct lte 0` koşulları
soruda açıkça istendiğinde kabul edilir; kredi değişim yönü belirtilmemişse plan
reddedilir ve netleştirme istenir. Plan koşullarıyla birebir karşılaştırılır. Eksik/fazla/uydurulmuş koşul, açıkça
belirtilmemiş nominal/reel kredi, yüzde ile yüzde puan karışıklığı, OR, sıralama/top-N,
ortalama/yıllık/toplam, tahmin/nedensellik ve kapsam dışı analizlerde analiz **0** kez
çalışır; uygun `metric_ambiguous`, `question_ambiguous` veya `unsupported` kararı döner.
Yalnız faiz sorusunda nominal/reel netleştirmesi istenmez; nominal ve reel
kredi koşulları birlikte açıkça istenirse iki koşul da korunur. Doğal dil guard'ı
genel bir Türkçe ayrıştırıcısı değildir ve modelin niyeti doğru anladığını
kanıtlamaz.

Çağıran, normalize edilmiş `HousingQuestionData` ve/veya
`InflationQuestionData` sağlar. Servis konut kapsamını ortak, kesintisiz
BDDK/EVDS aylarından; TÜFE kapsamını sayısal değerleri ve tüm geçmişi
doğrulanmış CPI satırlarından türetir. Kaynak referansları ve tablolar modele
gönderilmez. Bu satırlar henüz fiziksel dosya/manifest ile doğrulanmış veri
sayılmaz.

Konut/TÜFE planı yalnızca `status`, izinli `analysis_id`, `start_period`,
`end_period`; filtre planı ayrıca 1–3 `conditions`; karşılaştırma planı yalnızca
`status`, `analysis_id`, `first_year`, `second_year` alanlarını taşıyabilir.
`ready` için dönem veya iki yıl açık olmalıdır. Belirsiz dönem/metrik
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

Şema, kapsam ve aşağıdaki açık dönem/metrik kontrolü Python'da uygulanır.
Modelin soruyu doğru anladığı offline stub testleriyle kanıtlanmaz; Python'ın
yanlış bir `ready` planı engellemesi model başarısı değildir.

### `ready` planı için analiz öncesi kontrol

Sorudaki döneme yalnız şu açık biçimlerde karşılık aranır:

- tam yıl: `2023 yılında`, `2023 yılı boyunca`, `2023 yılının tamamında`
  (2023-01–2023-12). `2023 yılında` tek başına tam yıl isteğidir; aynı cümlede
  daha dar bir aynı yıl aralığı varsa yalnız bağlam sayılır. `yılının tamamı`,
  `yılı boyunca`, `yılı içinde` ve `yılı genelinde` açık tam yıl isteğidir;
- çeyrek: `2023'ün ikinci çeyreği`, `2023 yılının 2. çeyreği`,
  `2023'ün ilk üç ayı`; `ilk/ikinci/üçüncü/dördüncü` ve `1./2./3./4.` eşdeğerdir;
- yarıyıl: `2023'ün ilk/son altı ayı`, `2023 yılının ilk/son yarısı` (sayı `6` da
  kabul edilir);
- kapalı ay aralığı: `2023 Ocak-Mart`, `Ocak-Mart 2023`,
  `2020 Aralık-2021 Mart`, `2023 Ocak ile Mart arasında`,
  `2023 Ocak ve Mart arasında`, `2023 Ocak'tan Mart'a kadar`;
- noktalar: `2021-02`, `01/2021 ile 03/2021`, `2021 Ocak` gibi tek ay, tam gün
  sınırlı `1 Ocak 2021–31 Mart 2021` ve tam yıl aralığı `2021-2025`.

`2023 yılında Ocak-Mart` ifadesindeki yıl, daha belirli ay aralığının bağlamıdır;
ayrı bir tam yıl isteği sayılmaz ve sonuç 2023-01-2023-03 olur. Farklı yıllar
(`2023 yılında ve 2024 Ocak-Mart`) veya açık tam yıl ile dar dönem
(`2023 yılının tamamında ve 2023 Ocak-Mart`) çelişki sayılır. Kesintili ay
listesi `2023 Ocak ve Mart`, `2023 Ocak ve 2023 Mart`, `Ocak 2023 ve Mart 2023`
ve bunların tab/çoklu boşluk varyantları aralık değildir; Şubat'ı kapsamadığı
için `period_required` döndürür. Aralık bildiren `Ocak ve Mart arasında` kabul
edilir. ISO veya sayısal gün sınırları (`2023-02-15`, `15.02.2023`) desteklenmez
ve karşılaştırma yolunda da tam yıla dönüşmez; tam gün aralığı yalnız
`1 Ocak 2023-31 Mart 2023` gibi adlandırılmış aylarla kabul edilir. Ters yıl
aralığı (`2025-2023`) reddedilir.

Tek ayın ardından `itibaren`, `sonra/sonraki`, `sonrası` veya `başlayarak`
gelirse bitiş eksik sayılır; tanınan ay kapalı tek aya çevrilmez. Planın iki ucu
sorudaki kapalı ifadeyle aynı olmalıdır; eksik yıl veya bitiş, başka/çelişkili
tarih, kısmi günlük sınır veya tanınmayan biçim `period_required` döndürür.
`Ocak-Mart` (yıl yok), `2023 Ocak'tan itibaren` (bitiş yok), `son altı ay` veya
`geçen yıl` (referans politikası yok) gibi ifadelerde yıl/bitiş bugünden veya veri
kapsamından tamamlanmaz. Dönem parçaları `app/services/question_periods.py`
içinde birleştirilip çelişki denetlenir; birden çok farklı tarihten ilki
seçilmez. Yeni bir dönem biçimi yeni bir analiz türü eklemez. Bu sınırlı kontrol
genel bir Türkçe tarih ayrıştırıcısı değildir.

Konut `ready` kararı için kredi metriği açıkça `reel`, `enflasyondan
arındırılmış` veya eşdeğer TÜFE ile arındırılmış kredi/stok/bakiye/tutar olmalıdır.
`Reel faiz` tek başına kredi metriği sayılmaz; olumsuz veya çelişkili metrik
ifadeleri güvenli biçimde netleştirilir. Yalnız nominal kredi isteği
`unsupported_analysis` olur. Bu kontroller mevcut tek model çağrısından sonra,
her iki soru API'sinin ortak çekirdeğinde ve analizden önce uygulanır; reddedilen
planda analiz **0** kez çalışır. Bunlar sınırlı açık ifade kontrolleridir;
modelin tüm ekonomik niyeti doğru seçtiğini garanti etmez.

### İki tam yıl TÜFE karşılaştırması

“2023 ve 2024 TÜFE değişimlerini karşılaştır.” ve “2024 ile 2023 Aralık yıllık
TÜFE enflasyonunu karşılaştır.” iki tam yıl için çalışır; yıl sırası korunur.
Yanıt iki yılın 12'şer aylık evidence tablosunu, ayrı Ocak–Aralık endeks
değişimlerini, Aralık yıllık oranlarını ve `ikinci yıl - birinci yıl` farkını
yüzde puan olarak taşır. Ekran iki `first_to_last_index_change_pct` değerini
kendi yıl başlığı altında yüzde birimiyle, Aralık yıllık oranı ve yüzde puan
farkından ayrı gösterir. Hesaplama mevcut `compare_inflation_years()` içinde bir
kez yapılır; formüller yönlendirme/API/ekran katmanında tekrarlanmaz.

Python planı analizden önce soruyla karşılaştırır. İki yıl açık değilse, yıllar
eksik/uyuşmuyor veya ters verilmişse, model tek dönem özeti seçmişse ya da soru
aynı yılı iki kez/tek yıl belirtiyorsa `period_required` döner. Ortalama, kısmi
dönem, açık TÜFE dışı metrik, tahmin ve nedensellik istekleri `unsupported`;
tam yıl veri kapsamı dışındaysa `outside_coverage` olur. Kısmi dönem niyeti
cümledeki konumdan bağımsız denetlenir: `2023 ve 2024 için ikinci çeyrek`,
`2023 ile 2024 ... ilk altı ay`, `2023 ve 2024 için Ocak ayı` ve ISO/sayısal gün
sınırları (`2023-02-15 ile 2024-03-15`, `15.02.2023 ile 15.03.2024`) gibi
ifadeler de `unsupported` döndürür. Yalnız açık `yıllık`/`12 aylık` ifadesiyle
istenen Aralık karşılaştırmaları bu kontrolden geçer. Bu durumlarda analiz 0 kez çalışır. Eksik
önceki Aralık nedeniyle yıllık oran veya fark `null` kalabilir; sıfır/tahmin
üretilmez. “2023-2024 TÜFE değişimlerini özetle.” aralık özeti karşılaştırma
sayılmaz. Yeni bir HTTP endpoint'i, genel tarih ayrıştırıcısı, grafik katmanı
veya model çağrısı eklenmedi.

```json
{"status":"ready","analysis_id":"cpi_two_year_comparison","first_year":2023,"second_year":2024}
```

Yerel soru ekranı iki yılın evidence tablolarını ve yüzde puan farkını mevcut
sayfada gösterir; `null` değerler `—` olarak açıklanır. Sayfa açılışında istek
yoktur ve yeni CDN/bağımlılık eklenmemiştir.

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
ayrıca mevcut altı trace'li `analysis.chart` bulunur. `housing_condition_filter`
sonucu yalnız tipli evidence taşır: koşullar/birimler, gözlem/değerlendirilebilir/
eşleşen ay sayıları, kronolojik eşleşen aylar ve kaynak/kalite/sınırlama
notları. Yeni grafik üretilmez ve eski sabit konut grafiği yeni sonuç gibi
kullanılmaz; ekran önceki grafiği temizler ve koşul özeti ile eşleşen ay
tablosunu gösterir. Tek dönem TÜFE özetinde aynı evidence'dan üretilen mevcut
üç panelli `analysis.chart` yer alır; grafik için ek model, veri veya hesap
çağrısı yapılmaz. İki yıl karşılaştırması yalnız evidence taşır. Karşılaştırmada
iki nested evidence'ın kaynak referansı ve `input_origin` bilgisi korunur.
Endpoint anlatım çağrısı yapmaz ve sohbet geçmişi tutmaz.

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

`run_verified_economic_question()` iki mevcut hesabı ve parametreli filtre
çekirdeğini aynı `run_economic_question()` çekirdeğine verir. Konut kapsamı ortak
aylardır; TÜFE tüm doğrulanmış EVDS geçmişini kullanır, konut kapsamına kırpılmaz.
Soru başına en fazla bir plan ve bir hesap çağrısı vardır; netleştirme/unsupported/
kapsam dışı planda hesap çalışmaz. Yanıt aynı `status/decision/available_periods/
analysis` yapısındadır. Konutta mevcut evidence/grafik ve weekly coverage notu
korunur. `housing_condition_filter` evidence'ında hesaplar aynı kalır; fiziksel
doğrulama sınırlaması doğrulanmış dosya ifadesiyle değiştirilir ve weekly coverage
notu kalite notlarına eklenir. TÜFE özetinde hesaplar aynı kalır; üç panelli grafik
doğrulanmış evidence'dan ek çağrı yapılmadan üretilir ve
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

`evals/economic_question_cases.json` içindeki 45 vaka gerçek HTTP doğrulaması ve
Python analizleriyle, sabit model yanıtları kullanılarak çalışır. Housing/TÜFE
sonuçları aynı girdili doğrudan hesap endpoint'leriyle, filtre sonucu doğrudan
`run_housing_filter()` çekirdeğiyle, karşılaştırma sonucu ise mevcut
`compare_inflation_years` çekirdeğiyle karşılaştırılır; soru başına plan/analiz
çağrıları sayılır. Referans hesap istekleri soru yürütme sayacına dahil değildir.
Rapor `out/economic-question-eval-offline.json` altındadır; `--output` yalnızca
`out/` içinde başka bir rapor seçebilir.

İlk 28 vakanın soru/beklenti/stub yanıtları korunmuştur. Son 9 vaka iki tam yıl
karşılaştırmasını, ters yıl sırasını, önceki Aralık eksikliğinde null davranışını,
aynı yıl, kapsam dışı yıl, belirsiz dönem ve desteklenmeyen ay/ortalama/
yıllıklandırma isteklerini kapsar. Aralık yıllık oranları ve farkı elle hesaplanan
sentetik sabitlerle ayrıca sınanır. Beklentiler model çıktısı görülmeden yazıldı;
`rationale` alanı gerekçeyi açıklar. Yeni filtre yeteneği yalnız gerçekten
desteklenen EQ-025'i değiştirdi: faiz değişimi `gt 0` ve reel kredi değişimi
`gt 0` koşulları korunuyor; sentetik dönemde eşleşen ay yok. Diğer eski
`unsupported`/netleştirme beklentileri (kapsam dışı, tahmin/nedensellik, OR,
ortalama, açıkça belirtilmemiş nominal/reel kredi) değişmedi. 22 Ekim'de #107
kapsamında EQ-038–045 eklendi: yalnız konut içeren yeni sentetik fixture üzerinde
dört olumlu filtre planı, üç netleştirme ve bir desteklenmeyen OR isteği. Eşleşen
aylar uygulamadan kopyalanmayan sabit oracle olarak tutulur. Dağılım: 17 ready,
16 netleştirme, 10 unsupported, 2 veri yokluğu. Tahmin/nedensellik/şema
değiştirme talepleri eski sette de vardır.

Rapor **`offline_stub / harness_behavior_only`** olarak etiketlenir; 45/45 gibi
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
- Rapor `actual_model_decision` ve `actual_decision` yanında model ve uygulama
  beklenti eşitliğini ayrı alanlarda gösterir. `python_blocked_ready_plan=true`
  ve doğru son netleştirme olsa bile yanlış ham model planının vaka sonucu
  **başarısız** kalır; analiz çağrısı ayrıca sayılır.
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

İlk offline düzeltmede prompt, eksik yıl/başlangıç/bitiş bilgisinin kullanıcı sorusundan
gelmesi ve `available_periods` veya bugünden tamamlanmaması kuralını genelleştirdi.
Gözlenen hatalı plan ağsız sahte sağlayıcı regresyonunda hâlâ başarısız sayılır ve
sonraki vaka durur; oracle gevşetilmedi. Bu test evaluator davranışını doğrular,
prompt'un gerçek modelde hatayı giderdiğini kanıtlamaz. Sonraki ayrı onaylı
canlı gözlem aşağıdadır; gerçek sağlayıcı/plan hatası otomatik tekrar denenmez.

### Düzeltmenin canlı kontrolü — 20 Ekim 2026

Mustafa'nın yeni onayıyla **`204de1ebfe0225f2c0badee01c65f1bbcd75d387`**
PR head'i ve [başarılı Tests #133 CI'si](https://github.com/ekincimustafa/quad-qore-agentic-analytics/actions/runs/39432710748)
doğrulandı. Temiz ağaçta tek koşu, sırasıyla **EQ-020, EQ-013, EQ-016, EQ-022,
EQ-024, EQ-025, EQ-026, EQ-010**. Aynı Gemini modeli; azami 8 toplam deneme,
retry 0, timeout 60 saniye, ilk hatada durma. Beklentiler/fixture'lar değişmedi.

| Vaka | Modelin kararı ve gözlem | Deneme |
| --- | --- | --- |
| EQ-020 | `clarification_required/period_required`; yıl varsaymadı. Analiz 0; geçti. | 1 |
| EQ-013 | Konut `ready`, 2021-01–2021-03; evidence/grafik doğrudan Python referansına eşit. | 1 |
| EQ-016 | TÜFE `ready`, 2021-01–2021-03; evidence doğrudan Python referansına eşit. | 1 |
| EQ-022 | Beklenen `metric_ambiguous` yerine konut `ready`, 2021-01–2021-03; `status_mismatch`. | 1 |
| EQ-024/025/026/010 | İlk hatadan sonra `not_run_after_failure`; çalıştırılmadı. | 0 |

**Toplam 4 deneme; 3 geçen, 1 başarısız, 4 atlanan; ek çağrı yok.** EQ-020'de
netleştirmeyi **model kendisi üretti**; Python yanlış dönemi engellemedi. Bu tek
gözlem genel güvenilirlik kanıtı değildir. Yıl varsayımı tekrarlanmadığından
koşullu Python dönem kontrolü eklenmedi.

EQ-022'nin “2021 Ocak-Mart'ta konut kredisi faizi düşerken kredi bakiyesinin
artmadığı ayları göster.” sorusu nominal/reel ayrımını belirtmiyordu. Model reel
analizi seçti; mevcut Python şema/kapsam kontrolü bunu engellemedi ve **1 konut
analizi çalıştı**. Kullanıcıdan ayrım istenmeliydi. Bu bir anlam/plan hatasıdır;
EQ-022 hesap eşitliği başarısı olarak kaydedilmedi. Sentetik HTTP koşusudur,
gerçek dosyalı UI kabulü veya genel model başarı oranı değildir.

Yeni rapor `out/economic-question-eval-77-live-recheck.json` Git dışında:
SHA-256 `acdffd6645d3e813fa58ed7ddfa2fabcb45061791449468b387b8e5ecfbd29f0`.
Önceki rapor/hash korundu; iki rapor ayrı kaynak commit'lerini kaydeder.

Yalnız offline hazırlanan sonraki düzeltme: konut planında nominal/reel ayrımı
belirsizse `metric_ambiguous` istenmesi genel prompt kuralında açıklaştırıldı.
Gözlenen EQ-022 yanıtı da sahte sağlayıcı regresyonunda başarısız sayılır ve
kalanları durdurur. Bu test prompt'un modele etkisini kanıtlamaz; runtime'da
semantik metrik engeli eklenmedi. Düzeltmenin canlı etkisi **doğrulanmadı**.
Kullanılmayan dört deneme yeni yetki değildir; yeni koşu açık onay ve yeni rapor
yolu gerektirir. Merge/release yapılmadı.

Mustafa'nın mevcut Python 3.12.15 ortamında offline komut için de `.venv` yerine
`out/clean312/Scripts/python.exe` kullanılabilir; eski `.venv` yolu onarılmadı,
yeni kurulum/dependency yok. Python hesapları ve HTTP sözleşmeleri değişmedi;
son metrik prompt düzeltmesi yalnız offline hazırlanmıştır.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_economic_question.py tests/test_housing_question.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_economic_question_api.py tests/test_economic_question_evals.py -q
.\.venv\Scripts\python.exe -m pytest -q
```
