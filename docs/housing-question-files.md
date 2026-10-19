# Doğrulanmış yerel dosyalarda Housing sorusu

Takip: [#42](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/42).
`app/services/housing_question_files.py::run_verified_housing_question()` sunucunun
seçtiği yerel dosya paketini model çağrısından önce doğrular ve mevcut tek analizli
Housing soru servisini kullanır.

`VerifiedHousingQuestionPaths` yalnızca güvenilen sunucu yapılandırmasıdır:

| Alan | Varsayılan / anlam |
| --- | --- |
| `project_root` | Sunucunun verdiği veri/proje kökü |
| `bddk_silver` | `data/silver/bddk/housing_loans.parquet` |
| `bddk_bronze` | `data/bronze/bddk`; altındaki `aylik/raw` ve `aylik/receipts` |
| `evds_manifest` | `data/silver/evds/monthly/manifest.json`; CSV yolu manifestten gelir |

Artefakt yolları köke göreli olmalı ve fiziksel olarak kökün içinde kalmalıdır.
Soru veya model JSON'u dosya yolu, kaynak, model veya anahtar seçemez.
Bu tek konut wrapper'ının sözleşmesi korunur. Ortak fiziksel yükleyiciyi kullanan
iki analizli `POST /analysis/economic/question/files` [#69 kapsamında](economic-question.md#yalnızca-soru-alan-doğrulanmış-dosya-apisi)
eklenmiştir; mevcut normalize-satır endpoint'leri değişmez.

## Doğrulama ve yürütme sırası

1. BDDK Silver'ın tüm dönemi, birimi, değerleri ve kaynak/kalite alanları mevcut
   Silver doğrulayıcısıyla kontrol edilir. Mevcut BDDK üreticisi makbuz ve raw
   boyut/hash/başlık dönemi/birim kontrollerini yapıp tabloyu bellekte yeniden
   oluşturur; saklanan Silver'ın sözleşme kolonları bununla birebir eşleşmelidir.
2. Mevcut EVDS tüketicisi manifest, seri metadata'sı, raw/makbuz zinciri ve CSV
   boyut/hash/dönem kapsamını doğrular. CSV tekrar okunurken aynı hash'e bağlı
   baytlar belleğe alınır; tüm EVDS sayısal satırları da mevcut Silver
   doğrulayıcısından geçer. Kaynak referansları manifest makbuzlarından gelir.
3. Ortak BDDK/EVDS kapsamı Python'da türetilir. Veri doğrulama hatası veya ortak
   dönem yokluğu `VerifiedHousingQuestionDataError` üretir; model ve analiz
   çağrılmaz. Bu hata ham dosya içeriği/yolu taşımaz.
4. Mevcut `run_housing_question()` tek plan çağrısı yapar. `ready` planında mevcut
   hesap servisi en fazla bir kez çalışır. Diğer kararlarda `analysis=None` olur;
   kapsam dışı dönem kırpılmaz. Model/plan hataları mevcut hata türlerini korur.

Sonuç `available_period`, `decision` ve `analysis` içerir. Planlama sonrasında
dosyalar tekrar yüklenmez; analiz doğrulanmış bellek kopyasını kullanır. Sonuçtaki
BDDK kaynak/kalite notları ve EVDS makbuz referansları korunur. CLI ile ortak
haftalık kapsam notu `unverified/not_available` olarak evidence'a eklenir.
Bu wrapper anlatım çağrısı yapmaz.

## Offline kullanım

Aşağıdaki örnek, sunucuda erişilebilir **tam bir dosya paketi** gerektirir.
Depo gerçek BDDK/EVDS verisini içermez. Stub model yalnızca harness davranışını
sınar; gerçek model anlama başarısını ölçmez.

```python
import json
from pathlib import Path
from app.services.housing_question_files import (
    VerifiedHousingQuestionPaths, run_verified_housing_question,
)

result = run_verified_housing_question(
    "2021 Ocak-Mart faiz düşerken reel konut kredisinin artmadığı ayları bul.",
    VerifiedHousingQuestionPaths(project_root=Path(".")),
    model_call=lambda _: json.dumps({
        "status": "ready", "analysis_id": "housing_rate_down_real_credit_not_up",
        "start_period": "2021-01", "end_period": "2021-03",
    }),
)
```

`model_call` verilmezse mevcut yapılandırılmış LLM istemcisi kullanılır; bu canlı
çağrı için ayrıca kullanıcı yetkisi gerekir. Gerçek veri kabulü #39/#40 paketine
erişim ve gerçek örnek ay karşılaştırmalarıyla ayrıca kaydedilmelidir. Sentetik
fiziksel fixture başarısı #42'yi tek başına kapatmaz.
