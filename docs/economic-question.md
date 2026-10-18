# Sınırlı konut–TÜFE soru çekirdeği

Takip: [#59](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/59).
`app/services/economic_question.py`, Türkçe bir soruyu tek model çağrısında
doğrulanmış plana dönüştürür ve en fazla bir mevcut Python analizini çalıştırır.
Bu ilk parçada ortak HTTP endpoint'i, yeni narrator veya değerlendirme seti yoktur.
Mevcut `/analysis/housing/question` yalnızca konut analizini desteklemeye devam eder.

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

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_economic_question.py tests/test_housing_question.py -q
.\.venv\Scripts\python.exe -m pytest -q
```
