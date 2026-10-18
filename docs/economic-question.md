# Sınırlı konut–TÜFE soru çekirdeği

Takip: [#59](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/59).
`app/services/economic_question.py`, Türkçe bir soruyu tek model çağrısında
doğrulanmış plana dönüştürür ve en fazla bir mevcut Python analizini çalıştırır.
Ortak HTTP yüzeyi `POST /analysis/economic/question` ve 12 vakalık offline HTTP
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

## Offline değerlendirme

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_economic_questions
```

`evals/economic_question_cases.json` içindeki 12 vaka gerçek HTTP doğrulaması ve
Python analizleriyle, sabit model yanıtları kullanılarak çalışır. Housing/TÜFE
sonuçları aynı girdili doğrudan hesap endpoint'leriyle karşılaştırılır;
soru başına plan/analiz çağrıları sayılır. Referans hesap istekleri soru
yürütme sayacına dahil değildir. Rapor `out/economic-question-eval-offline.json`
altındadır; `--output` yalnızca `out/` içinde başka bir rapor seçebilir.

Set; iki analiz, geçmişli/tek aylık TÜFE, belirsizlik, kapsam dışı dönem,
tahmin/nedensellik, iki analizi birlikte isteme, injection talebi ve veri
yokluğunu kapsar. Bozuk model JSON'u, model hatası ve geçersiz HTTP sayıları
ayrıca davranış testlerindedir. Offline komutta canlı mod yoktur. Rapor
`harness_behavior_only` olarak etiketlenir; vaka geçişleri modelin Türkçe
anlama başarısı veya injection dayanıklılığı ölçümü değildir.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_economic_question.py tests/test_housing_question.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_economic_question_api.py tests/test_economic_question_evals.py -q
.\.venv\Scripts\python.exe -m pytest -q
```
