## 1. Amaç

Bu belge, Quad-Qore sisteminde Agent Orchestrator tarafından kullanılacak araçların (tools) sorumluluklarını, giriş ve çıkış sözleşmelerini, kaynak/kanıt taşıma biçimlerini ve hata yönetimini tanımlar.

Bu sözleşmelerin amacı:

* Araçların görev sınırlarını birbirinden ayırmak.
* LLM'nin yalnızca izin verilen araçları kullanmasını sağlamak.
* Sayısal hesaplamaları deterministik kodda tutmak.
* Araç girdilerini ve çıktılarını yapılandırılmış hâle getirmek.
* Kaynak, seri, tarih aralığı ve birim bilgilerinin korunmasını sağlamak.
* Hata ve veri kalitesi durumlarını standartlaştırmak.
* İleride Pydantic modelleri, FastAPI ve orchestration katmanına temel oluşturmak.

---

## 2. Temel Tasarım İlkeleri

1. **Harness-first:** Veri erişimi, filtreleme ve hesaplama işlemleri mümkün olduğunca deterministik Python/DuckDB kodu ile yapılır.

2. **LLM hesaplama yapmaz:** LLM, araçlardan gelen sayısal sonuçları kendisi yeniden hesaplayan veya değiştiren bir otorite değildir.

3. **Tek ve açık sorumluluk:** Her tool belirli bir görevi yerine getirir. Bir tool başka bir tool'un analiz sorumluluğunu tekrar etmemelidir.

4. **Yapılandırılmış I/O:** Tool girdileri ve çıktıları JSON uyumlu, doğrulanabilir şemalara sahip olmalıdır.

5. **Kaynak izlenebilirliği:** Önemli sonuçlar kullanılan veri kaynağı, seri/veri seti, tarih aralığı, birim ve yöntem bilgisiyle birlikte taşınmalıdır.

6. **Korelasyon ≠ nedensellik:** İstatistiksel ilişki, tek başına ekonomik nedensellik kanıtı olarak sunulamaz.

7. **Kontrollü hata:** Geçersiz parametreler ve desteklenmeyen işlemler açık, makinece okunabilir hata kodlarıyla reddedilmelidir.

8. **Sağlayıcı bağımsızlığı:** Tool sözleşmeleri mümkün olduğunca MIA veya belirli bir agent framework'üne bağımlı tasarlanmamalıdır.

9. **Güvenlik:** API anahtarları tool çıktılarında, loglarda, kaynak paketlerinde veya kullanıcıya dönen yanıtlarda yer almamalıdır.

---

## 3. Sistem İçindeki Konum

Tool'lar, Agent Orchestrator tarafından çağrılır. Tool'lar arası yönlendirme ve sonuçların birleştirilmesi orchestrator'ın sorumluluğundadır.

```text
User Question
      |
      v
Agent Orchestrator
      |
      +--> lakehouse_query      [planned]
      |
      +--> web_search           [planned]
      |
      +--> web_url_reader       [planned]
      |
      +--> detect_anomalies     [planned]
      |
      +--> analyze_causality    [disabled]
      |
      +--> detect_changes       [planned]
      |
      v
Tool Responses
      |
      v
Evidence Package
      |
      v
LLM Explanation
```

### 3.1 Tool'lar arası temel kural

* Tool'lar varsayılan olarak birbirini doğrudan çağırmaz.
* Tool çağrılarının yönetimi orchestrator üzerinden yapılır.
* Bir tool'un çıktısı başka bir tool'un girdisi olabilir.
* Orchestrator, bir tool'un çıktısını doğrulamadan sonraki analize aktarmamalıdır.

Örnek:

```text
lakehouse_query
      |
      v
Validated Time Series
      |
      +--> detect_anomalies
      |
      +--> detect_changes
      |
      +--> analyze_causality
```


### 3.2 MVP Durum Tablosu

Orchestrator yalnızca `enabled` durumundaki tool'ları çağrılabilir araç listesine eklemelidir. `planned` araçlar sözleşme/roadmap düzeyindedir ve ilk demo akışında çağrılmamalıdır. `disabled` araçlar ise adı bilinse dahi çalıştırılmamalı; dispatch edilmeye çalışıldığında kontrollü olarak `UNSUPPORTED_OPERATION` dönmelidir.

| Tool | MVP durumu | İlk demo davranışı |
| --- | --- | --- |
| `lakehouse_query` | `planned` | Generic tool implementasyonu henüz mevcut MVP kodunda yoktur. İlk tool adaptörü olarak eklendiğinde mevcut Housing Analysis servis/evidence akışını ince bir adapter ile çağırmalı; Gold formüllerini yeniden uygulamamalıdır. |
| `web_search` | `planned` | İlk demo için zorunlu değildir; güvenilir dış kaynak keşfi sonraki orchestrator iterasyonunda etkinleştirilebilir. |
| `web_url_reader` | `planned` | Güvenlik sözleşmesi uygulanıp çevrimdışı testlerle doğrulanmadan tool registry'ye eklenmez. |
| `detect_anomalies` | `planned` | Genel amaçlı anomali analizi gelecek kapsamdadır ve ilk demo akışında çağrılmaz. |
| `analyze_causality` | `disabled` | Kesin yöntem, minimum gözlem sayısı ve varsayımlar tanımlanana kadar çağrılamaz; çağrılırsa `UNSUPPORTED_OPERATION` döner. |
| `detect_changes` | `planned` | İlk demo sırasında Gold katmanında zaten hesaplanan değişimleri yeniden hesaplamaz. Genel amaçlı değişim aracı gelecek kapsamdadır. |

> Güncel repository'de bu tabloda adı geçen generic tool'ların runtime implementasyonları henüz bulunmamaktadır. Mevcut ilk demo, servis tabanlı ve dosya destekli deterministik orchestration akışıyla çalışır. Bu nedenle `enabled` statüsü ancak ilgili tool adapter'ı kodlanıp test edildikten sonra verilmelidir.

### 3.3 Mevcut MVP ile Eşleme

İlk demo için amaç yeni bir hesaplama doğruluk kaynağı oluşturmak değil, mevcut ve doğrulanmış Housing Analysis akışını ileride orchestrator'a güvenli bir tool yüzeyi olarak bağlamaktır. Güncel kodda çalışan akış aşağıdaki bileşenlerden oluşur:

| Mevcut MVP kodu | Gerçek sorumluluk | Tool sözleşmesiyle ilişki |
| --- | --- | --- |
| `app/lakehouse/gold.py` — `build_housing_gold_table` | BDDK ve EVDS Silver verilerini doğrular, birleştirir ve reel kredi/değişim/ana koşul metriklerini deterministik olarak hesaplar. | Sayısal doğruluk kaynağıdır. `detect_changes` bu metrikleri ilk demo için yeniden hesaplamamalıdır. |
| `app/tools/housing_evidence.py` — `HousingAnalysisEvidence`, `build_housing_analysis_evidence` | Gold tablosunu tekrar doğrular ve LLM'ye verilebilecek JSON-safe kanıt payload'ını üretir. | Gelecekteki tool adapter'ının ortak response/evidence zarfına saracağı mevcut kanıt kaynağıdır. |
| `app/services/housing_analysis.py` — `run_housing_analysis` | Gold tabloyu, evidence payload'ını ve doğrulanmış grafiği tek servis çağrısında üretir; narration isteğe bağlıdır. | İlk generic tool adapter'ı yeni business logic yazmak yerine bu servisi veya onun ürettiği evidence'ı kullanmalıdır. |
| `app/services/housing_demo.py` — `run_file_backed_housing_demo` | Sunucu kontrollü BDDK/EVDS Silver dosyalarını yükler ve mevcut `run_housing_analysis` servisini çağırır. | Güncel ilk-demo orchestrator akışıdır; generic tool registry'nin yerini şimdilik bu servis akışı alır. |
| `app/tools/housing_narrator.py` — `narrate_housing_evidence_with_mia`, `validate_housing_narration` | Yalnızca doğrulanmış evidence üzerinden MIA anlatımı üretir; kanıtta bulunmayan sayı/kaynak iddialarını reddeder. | Evidence Package sonrasındaki açıklama katmanıdır; hesaplama tool'u değildir. |
| `app/tools/housing_chart.py` — `build_housing_chart` | Gold tablodan doğrulanmış Plotly chart specification üretir. | Görselleştirme katmanıdır; ikinci bir sayısal doğruluk kaynağı değildir. |
| `app/api/housing.py` — `/analysis/housing`, `/analysis/housing/demo` | Doğrulanmış Housing Analysis servisini FastAPI üzerinden sunar ve domain hatalarını kontrollü HTTP hatalarına çevirir. | Tool değildir; mevcut servis sonucunun HTTP yüzeyidir. |
| `app/api/main.py` — `create_app` | Housing router'ını uygulamaya bağlar ve API uygulamasını oluşturur. | Orchestrator/tool sözleşmesinin hesaplama katmanı değildir. |

Güncel ilk-demo akışı şu şekildedir:

```text
BDDK Silver + EVDS Silver
          |
          v
run_file_backed_housing_demo
app/services/housing_demo.py
          |
          v
run_housing_analysis
app/services/housing_analysis.py
          |
          +--> build_housing_gold_table
          |    app/lakehouse/gold.py
          |
          +--> build_housing_analysis_evidence
          |    app/tools/housing_evidence.py
          |
          +--> build_housing_chart
          |    app/tools/housing_chart.py
          |
          +--> optional guarded narrator
               app/tools/housing_narrator.py
          |
          v
FastAPI /analysis/housing/demo
app/api/housing.py
```

**İlk orchestrator/tool entegrasyon kuralı:** Bu belgede tanımlanan generic tool katmanı kodlanırken ilk köprü olarak `lakehouse_query` kullanılacaksa, tool mevcut `run_file_backed_housing_demo(..., narrator=None)` / `run_housing_analysis(..., narrator=None)` sonucunu adapte etmelidir. Gold hesap formüllerini, ana koşulu veya evidence doğrulamasını kendi içinde yeniden uygulamamalıdır. Adapter implementasyonu ve testleri repository'ye eklenene kadar `lakehouse_query` statüsü `planned` kalır.

İlk demo akışında `detect_changes` çağrılmaz. Çünkü `app/lakehouse/gold.py` zaten `nominal_housing_loan_change_pct`, `real_housing_loan_change_pct`, `interest_rate_change_pp` ve `rate_down_real_credit_not_up` alanlarını deterministik olarak üretmektedir. `detect_changes` bu değerleri yeniden hesaplayıp ikinci bir doğruluk kaynağı oluşturmamalıdır. Araç ancak Gold tarafından sağlanmayan genel amaçlı bir değişim analizi ihtiyacı için, ayrı testlerle etkinleştirilebilir.

Aynı şekilde `detect_anomalies`, `web_search` ve `web_url_reader` ilk demo runtime akışında kullanılmaz; `analyze_causality` ise açıkça `disabled` durumundadır.

---

## 4. Araç Sorumluluk Sınırları

### 4.1 Sorumluluk Matrisi

| Tool                | MVP durumu | Temel görevi                                                         | Yapmaması gereken                                                     |
| ------------------- | ---------- | -------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `lakehouse_query`   | `planned`  | İlk adapter implementasyonunda mevcut Housing Analysis service/evidence sonucunu ortak tool response yapısına taşımak | Gold formüllerini veya evidence doğrulamasını yeniden uygulamak; serbest yorum üretmek |
| `web_search`        | `planned`  | Dış kaynakları aramak ve sonuç metadata'sı döndürmek                 | Kaynak içeriğinin nihai finansal yorumunu üretmek                     |
| `web_url_reader`    | `planned`  | Belirli URL içeriğini okunabilir yapılandırılmış içeriğe dönüştürmek | İçeriğin doğruluğunu tek başına onaylamak veya ekonomik analiz yapmak |
| `detect_anomalies`  | `planned`  | Zaman serisindeki olağandışı gözlemleri belirlemek                   | Anomalinin ekonomik nedenini açıklamak                                |
| `analyze_causality` | `disabled` | Gelecekte desteklenen yöntemlerle olası nedensel ilişkileri değerlendirmek | Korelasyonu kesin nedensellik olarak sunmak                           |
| `detect_changes`    | `planned`  | Genel amaçlı dönemsel değişimleri ve desteklenen değişim noktalarını hesaplamak | MVP'de Gold/evidence değişimlerini yeniden hesaplayarak ikinci doğruluk kaynağı oluşturmak |

---

### 4.2 `lakehouse_query`

**MVP durumu: `planned`**

Generic `lakehouse_query` tool'u güncel repository'de henüz uygulanmış değildir. İlk adapter implementasyonunda mevcut doğrulanmış Housing Analysis akışı yeniden kullanılmalıdır.

**İlk adapter'ın yapması gerekenler:**

* Sunucu kontrollü ilk-demo akışında `run_file_backed_housing_demo(..., narrator=None)` veya aynı domain servisi olan `run_housing_analysis(..., narrator=None)` sonucunu kullanmak.
* `HousingAnalysisEvidence` içindeki dönem, metodoloji, sınırlama, BDDK kaynak referansı ve EVDS seri referanslarını ortak tool response yapısına taşımak.
* Orchestrator tarafından atanmış evidence kimliğini response'a eklemek ve sonraki analiz tool'ları için provenance zincirini korumak.
* İleride generic catalog sorgusu eklendiğinde yalnızca izin verilen dataset/seri/alan/filtre sözleşmelerini kullanmak.

**Yapmaz:**

* `build_housing_gold_table` içindeki reel kredi, aylık değişim, faiz değişimi veya ana koşul hesaplarını yeniden uygulamaz.
* `build_housing_analysis_evidence` doğrulamalarını paralel bir implementasyonla kopyalamaz.
* Serbest ekonomik yorum üretmez.
* Nedensellik analizi yapmaz.
* Anomali veya değişim noktası tespit etmez.
* LLM adına sonuçları yorumlamaz.
* Catalog'da bulunmayan veri setlerini uydurmaz.

> Adapter implementasyonu ve çevrimdışı testleri eklenmeden bu tool `enabled` olarak işaretlenmemelidir.


---

### 4.3 `web_search`

**Yapar:**

* Kullanıcı sorusu veya analiz planıyla ilişkili dış kaynakları arar.
* Kaynak başlığı, URL, kısa özet/alıntı ve yayın tarihi gibi bilgileri döndürür.
* Kaynak türünü ve mümkünse sağlayıcı bilgisini taşır.

**Yapmaz:**

* Kaynakların nihai finansal analizini üretmez.
* Bir haber veya raporu tek başına nedensellik kanıtı kabul etmez.
* Kaynakta bulunmayan sayısal bilgileri uydurmaz.
* `web_url_reader` sorumluluğundaki tam içerik ayrıştırma işini üstlenmez.

**Kaynak güvenilirliği:**

Arama sonucu bulunması, kaynağın otomatik olarak güvenilir olduğu anlamına gelmez. Resmî kurumlar, akademik yayınlar ve güvenilir kurumsal kaynaklar tercih edilmelidir.

---

### 4.4 `web_url_reader`

**Yapar:**

* Belirli bir URL'deki desteklenen web sayfası veya doküman içeriğini alır.
* Metin ve desteklenen tablo içeriklerini yapılandırılmış biçime dönüştürür.
* Kullanılan içerik türünü ve çıkarma yöntemini belirtir.
* Erişilemeyen veya desteklenmeyen içerikleri kontrollü hata olarak döndürür.

**Yapmaz:**

* İçeriğin finansal doğruluğunu tek başına doğrulamaz.
* İçerikten ekonomik nedensellik sonucu çıkarmaz.
* Okunan metni doğrulanmış veri serisi olarak otomatik kabul etmez.
* Desteklenmeyen dosya formatlarını varmış gibi garanti etmez.

#### 4.4.1 Güvenlik Sözleşmesi

`web_url_reader` kullanıcı kontrollü URL kabul ettiği için SSRF ve veri sızıntısı risklerine karşı aşağıdaki kurallar zorunludur:

* Yalnızca `http` ve `https` şemaları kabul edilir.
* `file://`, `ftp://`, `data:`, `javascript:` ve diğer desteklenmeyen şemalar `UNSAFE_URL` veya `UNSUPPORTED_FORMAT` ile reddedilir.
* URL içinde `user:password@host` biçiminde credential/user-info bulunması reddedilir.
* DNS çözümlemesi sonrasında loopback/localhost, private IP, link-local, unspecified ve bilinen metadata adreslerine erişim engellenir. Bu kontrol IPv4 ve IPv6 için uygulanır.
* `169.254.169.254` gibi cloud metadata adresleri ve bunlara çözümlenen hostname'ler engellenir.
* Her HTTP yönlendirmesinden sonra yeni hedef URL ve çözümlenen IP adresi baştan doğrulanır. İlk URL'nin güvenli olması sonraki redirect hedefini otomatik olarak güvenli yapmaz.
* Maksimum redirect sayısı MVP için `5` olarak sınırlandırılır.
* Bağlantı timeout'u MVP için en fazla `5 saniye`, okuma timeout'u en fazla `15 saniye` olmalıdır.
* Decompress edilmiş response body için maksimum boyut MVP'de `10 MiB` olarak sınırlandırılır. Limit aşılırsa işlem `RESPONSE_TOO_LARGE` ile fail-closed sonlandırılır.
* İzin verilen MIME türleri MVP'de `text/html`, `text/plain` ve `application/pdf` ile sınırlıdır. Destek listesi genişletilecekse kod ve testlerle açıkça güncellenmelidir.
* Content-Type eksik veya izin verilen listeyle uyumsuzsa içerik güvenli biçimde reddedilir; uzantıya bakılarak MIME varsayımı yapılmaz.
* URL query parametrelerinde credential/API key/token taşıyan değerler loglara, `metadata.sources[].url` alanına veya tool response'una ham biçimde yazılmaz. Hassas parametreler redakte edilir.
* Beklenmeyen network/parser exception'ları ortak hata sözleşmesine göre normalize edilir; raw exception ve stack trace kullanıcıya dönmez.

Bu güvenlik kontrolleri uygulanıp çevrimdışı testlerle doğrulanmadan `web_url_reader` MVP'de `enabled` durumuna getirilemez.


---

### 4.5 `detect_anomalies`

**Yapar:**

* Verilen zaman serisindeki olağandışı gözlemleri veya dönemleri tespit eder.
* Önceden tanımlanmış istatistiksel/algoritmik yöntemleri uygular.
* Kullanılan yöntem, parametreler, skorlar ve tespit edilen tarih/değer bilgilerini döndürür.
* Yeterli veri bulunmadığında kontrollü hata veya uyarı döndürür.

**Yapmaz:**

* Anomalinin ekonomik veya politik nedenini açıklamaz.
* Anomaliyi otomatik olarak nedensellik kanıtı kabul etmez.
* Kullanıcı adına serbest yorum üretmez.
* Kullanılan yöntem belirtilmeden "anomali" sonucu üretmemelidir.


---

### 4.6 `analyze_causality`

**MVP durumu: `disabled`**

Kesin yöntem, minimum gözlem sayısı, varsayımlar ve sonuç yorumlama modeli tanımlanmadığı için bu tool ilk sürümde aktif değildir. Orchestrator bu aracı çağrılabilir tool registry'ye eklememelidir. Adı üzerinden çağrı denenirse `UNSUPPORTED_OPERATION` döndürülmelidir.

**Planlanan davranış:**

* İki veya daha fazla zaman serisi arasındaki olası nedensel ilişkiyi değerlendirmek için açıkça desteklenen istatistiksel yöntemleri uygulamak.
* Kullanılan yöntemi, varsayımları ve test sonuçlarını döndürmek.
* Veri uzunluğu, frekans uyumu ve gerekli ön koşullar gibi sınırlamaları belirtmek.
* Korelasyon gibi yardımcı istatistikleri, nedensellik sonucundan ayrı olarak raporlamak.

**Yapmaz:**

* Korelasyonu tek başına nedensellik olarak sunmaz.
* Kesin ekonomik nedensellik iddiası üretmez.
* Gözlemsel veriden otomatik olarak politika sonucu çıkarmaz.
* Yöntem ve varsayımlar belirtilmeden nedensellik sonucu döndürmez.

**Önemli ilke:**

> Faiz oranı ile konut kredisi hacmi arasında negatif korelasyon bulunması, faiz düşüşünün kredi hacmindeki artışa neden olduğunu tek başına kanıtlamaz.


---

### 4.7 `detect_changes`

**Yapar:**

* İki dönem veya birden fazla dönem arasındaki yüzdesel değişimleri hesaplar.
* Mutlak değişim, yüzdesel değişim ve değişim yönünü döndürür.
* Desteklenen bir yöntem mevcutsa yapısal değişim/kırılma noktalarını tespit edebilir.
* Kullanılan hesaplama yöntemini ve karşılaştırılan dönemleri belirtir.

**Yapmaz:**

* Değişimin ekonomik nedenini açıklamaz.
* Değişimi otomatik olarak nedensellik olarak sunmaz.
* Yöntem uygulanmadan "anlamlı kırılma" iddiasında bulunmaz.
* İki gözlemden genel trend veya istatistiksel kırılma sonucu çıkardığını varsaymaz.

**İlk sürüm kapsamı önerisi:**

* Dönemsel yüzdesel değişim
* Mutlak değişim
* Değişim yönü
* Karşılaştırılan dönem bilgisi

**MVP notu:**

İlk demo akışında mevcut Gold/evidence katmanında zaten hesaplanmış değişim metrikleri varsa `detect_changes` yeniden çalıştırılmaz. Bu araç MVP'de `planned` durumundadır ve ikinci bir doğruluk kaynağı oluşturmamalıdır.

**Gelecek kapsam:**

* Change-point detection
* Yapısal kırılma analizi
* Yönteme bağlı anlamlılık değerlendirmesi


---

## 5. Ortak Tool Response Sözleşmesi

Tüm tool'lar aynı tür `data` üretmez. Bu nedenle ortak yapı, tüm sonuçları tek bir veri biçimine zorlamak yerine standart bir response zarfı sağlar.

### 5.1 Genel Response Şeması

```json
{
  "status": "success",
  "data": {},
  "metadata": {
    "sources": [],
    "input_evidence_ids": [],
    "used_series": [],
    "time_window": {
      "start": null,
      "end": null
    },
    "unit": null,
    "frequency": null
  },
  "method": null,
  "warnings": [],
  "limitations": [],
  "error": null
}
```

### 5.2 Ortak Alanlar

| Alan                   | Tip                | Zorunlu | Açıklama                                  |
| ---------------------- | ------------------ | ------- | ----------------------------------------- |
| `status`               | string             | Evet    | `success`, `partial` veya `error`         |
| `data`                 | object/array/null  | Evet    | Tool'un asıl yapılandırılmış sonucu       |
| `metadata`             | object             | Evet    | Kaynak ve veri bağlamı                    |
| `metadata.sources`     | array              | Evet    | Kullanılan kaynakların metadata bilgisi   |
| `metadata.input_evidence_ids` | array[string] | Hayır | Bu sonucu üreten upstream evidence kimlikleri; türetilmiş analizlerde zorunludur |
| `metadata.used_series` | array              | Hayır   | Kullanılan seri veya veri seti kimlikleri |
| `metadata.time_window` | object             | Hayır   | Verinin kapsadığı zaman aralığı           |
| `metadata.unit`        | string/object/null | Hayır   | Sonuç birimi veya metrik bazlı birimler   |
| `metadata.frequency`   | string/null        | Hayır   | Aylık, çeyreklik, yıllık vb.              |
| `method`               | object/string/null | Hayır   | Hesaplama veya analiz yöntemi             |
| `warnings`             | array              | Evet    | Veri kalite veya yorum uyarıları          |
| `limitations`          | array              | Evet    | Sonucun yorum sınırları                   |
| `error`                | object/null        | Evet    | Hata yoksa `null`                         |

### 5.3 Status Değerleri

| Status    | Anlamı                                                    |
| --------- | --------------------------------------------------------- |
| `success` | İşlem başarıyla tamamlandı                                |
| `partial` | İşlem kısmen tamamlandı; uyarılar veya eksik sonuçlar var |
| `error`   | İşlem tamamlanamadı                                       |

### 5.4 Response Zarfı Değişmezleri

Tüm tool implementasyonları aşağıdaki invariant'ları sağlamalıdır:

* `status == "success"` ise `data != null` ve `error == null` olmalıdır.
* `status == "partial"` ise kullanılabilir `data` bulunmalı ve en az bir `warnings` veya `limitations` kaydı bulunmalıdır. `error` varsayılan olarak `null` kalır; kısmi veriyle birlikte fatal hata taşınmaz.
* `status == "error"` ise `data == null` ve `error != null` olmalıdır.
* `metadata`, `warnings` ve `limitations` alanları her response'ta bulunmalıdır; uygun içerik yoksa boş nesne/liste kullanılmalıdır.
* Türetilmiş bir analiz sonucu upstream evidence kullanıyorsa `metadata.input_evidence_ids` boş olmamalıdır.
* Beklenmeyen exception'lar orchestrator/tool boundary'de `TOOL_EXECUTION_ERROR` koduna normalize edilmelidir.
* Raw exception mesajı, stack trace, credential, API key, token, dosya sistemi yolu veya diğer hassas runtime ayrıntıları kullanıcıya dönen response'a eklenmemelidir.
* İç loglama gerekiyorsa loglar secret-redaction uygulanmış ve kullanıcı response'undan ayrılmış olmalıdır.

Bu invariant'lar Pydantic/model validator seviyesinde de enforce edilmelidir; yalnızca dokümantasyon kuralı olarak bırakılmamalıdır.

---

## 6. Kaynak Sözleşmesi

`source_urls` tek başına yeterli bağlam sağlamayabileceği için kaynaklar nesne listesi olarak taşınır.

```json
{
  "sources": [
    {
      "source_type": "evds",
      "source_id": "SERIES_CODE",
      "title": "Temsili seri başlığı",
      "url": "https://example.com/source",
      "provider": "EVDS"
    }
  ]
}
```

### Kaynak alanları

| Alan          | Açıklama                                         |
| ------------- | ------------------------------------------------ |
| `source_type` | `bddk`, `evds`, `web`, `report` vb.              |
| `source_id`   | Seri kodu, veri seti kimliği veya kaynak kimliği |
| `title`       | Kaynak/seri başlığı                              |
| `url`         | Kaynağın orijinal URL'si, mevcutsa               |
| `provider`    | Veriyi sağlayan kurum veya platform              |

> Yukarıdaki URL yalnızca temsili örnektir. Mevcut Housing MVP kodunda BDDK kaynak referansı `bddk_source_ref`, EVDS kaynakları ise `TP.KTF12`, `TP.TUKFIY2025.GENEL` ve `TP.KFE.TR` referanslarıyla evidence içine taşınmaktadır. Generic adapter, yapılandırılmış `metadata.sources` üretirken yalnızca mevcut catalog/provenance bilgisini kullanmalı; bilinmeyen URL veya metadata alanlarını uydurmamalıdır.

Mevcut `HousingAnalysisEvidence` modelinde bağımsız bir `evidence_id` alanı bulunmaz. Ortak tool sözleşmesindeki `evidence_id` / `input_evidence_ids` ilişkisi orchestrator veya adapter zarfında yönetilebilir; bunun için mevcut domain evidence modelinin hesaplama davranışını değiştirmek zorunlu değildir.

### 6.1 Türetilmiş Kanıtlarda Kaynak Zinciri

`detect_anomalies`, `detect_changes` ve gelecekte etkinleştirilecek diğer analiz tool'ları yeni bir kaynak uydurmaz. Türetilmiş sonuçlar kendilerini üreten upstream evidence kayıtlarına bağlanmalıdır.

Kurallar:

* Analiz tool input'unda `input_evidence_ids` bulunmalıdır.
* Aynı kimlikler output'ta `metadata.input_evidence_ids` altında korunmalıdır.
* Upstream evidence'ın `metadata.sources` bilgisi mümkün olduğunda türetilmiş response'a da taşınmalıdır.
* Evidence Package içinde türetilmiş evidence kaydı, `input_evidence_ids` ile kaynak evidence kaydına makinece izlenebilir biçimde bağlanmalıdır.
* Salt `sources: []` ile üretilmiş hesaplanmış kanıt, upstream evidence mevcutken yeterli provenance kabul edilmez.

Örnek ilişki:

```text
ev-001  lakehouse_query / observed_data
   |
   +--> ev-002  detect_changes / computed_change
        input_evidence_ids = ["ev-001"]
```

---

## 7. Zaman Aralığı ve Birim

### 7.1 Time Window

```json
{
  "time_window": {
    "start": "2021-01",
    "end": "2025-12"
  }
}
```

Tarih biçimi, serinin frekansına uygun ve tutarlı olmalıdır.

Örnekler:

* Aylık: `2021-01`
* Günlük: `2021-01-31`
* Yıllık: `2021`

### 7.2 Unit

Tek birim varsa:

```json
{
  "unit": "TRY million"
}
```

Birden fazla metrik farklı birim taşıyorsa metrik bazlı birim metadata'sı kullanılmalıdır:

```json
{
  "unit": {
    "toplam_hacim": "TRY million",
    "faiz_orani": "%"
  }
}
```

Birimler, kaynaktaki tanımlarla uyumlu olmalıdır. "Milyon TL" ve "TL" gibi farklı ölçekler birbirine karıştırılmamalıdır.

---

## 8. Method, Warnings ve Limitations

### 8.1 Method

Analiz yapan tool'lar, kullanılan yöntemi mümkün olduğunca açıkça belirtmelidir.

```json
{
  "method": {
    "name": "period_over_period_change",
    "parameters": {
      "comparison": "previous_period"
    }
  }
}
```

İstatistiksel analizlerde yöntem ve önemli parametreler, sonucun tekrar üretilebilirliğini destekleyecek biçimde taşınmalıdır.

### 8.2 Warnings

`warnings`, veri veya işlem kalitesiyle ilgili uyarılar içindir.

Örnekler:

* Eksik gözlemler var.
* Gözlem sayısı düşük.
* Seri frekansları eşleştirildi.
* OCR ile çıkarılan içerikte doğrulama gereklidir.

### 8.3 Limitations

`limitations`, sonucun yorum sınırları içindir.

Örnekler:

* Korelasyon nedensellik kanıtı değildir.
* Sonuç yalnızca belirtilen tarih aralığı için geçerlidir.
* Gözlemsel veri, tek başına ekonomik nedensellik göstermez.
* Kullanılan yöntem belirli varsayımlara bağlıdır.

---

## 9. Ortak Hata Sözleşmesi

### 9.1 Hata Yapısı

```json
{
  "code": "INVALID_DATE_RANGE",
  "message": "Başlangıç tarihi bitiş tarihinden büyük olamaz.",
  "details": {
    "start_date": "2025-12",
    "end_date": "2021-01"
  }
}
```

### 9.2 Taslak Hata Kodları

| Kod                     | Açıklama                            |
| ----------------------- | ----------------------------------- |
| `INVALID_INPUT`         | Genel geçersiz girdi                |
| `INVALID_DATE_RANGE`    | Geçersiz tarih aralığı              |
| `DATASET_NOT_FOUND`     | Veri seti bulunamadı                |
| `SERIES_NOT_FOUND`      | Seri bulunamadı                     |
| `UNSUPPORTED_OPERATION` | Desteklenmeyen işlem                |
| `INSUFFICIENT_DATA`     | Analiz için yeterli veri yok        |
| `DATA_QUALITY_ERROR`    | Veri kalite problemi                |
| `SOURCE_UNAVAILABLE`    | Kaynağa erişilemiyor                |
| `UNSUPPORTED_FORMAT`    | Desteklenmeyen içerik/dosya formatı |
| `UNSAFE_URL`            | Güvenlik politikası nedeniyle URL reddedildi |
| `RESPONSE_TOO_LARGE`    | Kaynak response boyutu izin verilen limiti aştı |
| `TOOL_EXECUTION_ERROR`  | Beklenmeyen tool çalışma hatası     |

Bu kodlar ilk taslak içindir. Uygulama sırasında hata kodları tek bir ortak Python modeli veya enum üzerinden standardize edilmelidir.

### 9.3 Hata Durumunda Response

```json
{
  "status": "error",
  "data": null,
  "metadata": {
    "sources": [],
    "input_evidence_ids": [],
    "used_series": [],
    "time_window": {
      "start": null,
      "end": null
    },
    "unit": null,
    "frequency": null
  },
  "method": null,
  "warnings": [],
  "limitations": [],
  "error": {
    "code": "INVALID_DATE_RANGE",
    "message": "Başlangıç tarihi bitiş tarihinden büyük olamaz.",
    "details": {
      "start_date": "2025-12",
      "end_date": "2021-01"
    }
  }
}
```

### 9.4 Partial Response

Kısmi sonuçlarda `status` değeri `partial` olmalıdır.

```json
{
  "status": "partial",
  "data": [],
  "metadata": {
    "sources": [],
    "input_evidence_ids": [],
    "used_series": [],
    "time_window": {
      "start": null,
      "end": null
    },
    "unit": null,
    "frequency": null
  },
  "method": null,
  "warnings": [
    "2022-03 ve 2022-04 dönemlerinde veri bulunamadı."
  ],
  "limitations": [
    "Sonuç eksik gözlemler nedeniyle tüm dönemleri temsil etmeyebilir."
  ],
  "error": null
}
```

Kısmi sonuç davranışı, her tool'un sözleşmesinde gerektiğinde ayrıca belirtilmelidir.

---

# 10. Tool Input/Output Sözleşmeleri

Bu bölümdeki örnekler sözleşme tasarımını göstermek amacıyla hazırlanmıştır. `planned` veya `disabled` statüsündeki bir tool için burada örnek bulunması, ilgili tool'un güncel runtime'da kullanılabildiği anlamına gelmez. Mevcut Housing MVP ile ilgili gerçek kod eşlemesi için Bölüm 3.3 esas alınmalıdır. Temsili dataset kimlikleri ve URL'ler yalnızca şema örneğidir; production metadata catalog/provenance katmanından gelmelidir.

---

## 10.1 `lakehouse_query`

### Amaç

Katalogda tanımlı veri setlerinden, belirtilen tarih aralığı ve izin verilen filtrelerle yapılandırılmış veri getirmek.

### Input

```json
{
  "dataset_id": "bddk_konut_kredisi_aylik",
  "fields": [
    "date",
    "value"
  ],
  "start_date": "2021-01",
  "end_date": "2025-12",
  "filters": {}
}
```

### Input Alanları

| Alan         | Tip           | Zorunlu | Açıklama                         |
| ------------ | ------------- | ------- | -------------------------------- |
| `dataset_id` | string        | Evet    | Catalog'da tanımlı veri seti     |
| `fields`     | array[string] | Evet    | Getirilecek izin verilen alanlar |
| `start_date` | string        | Evet    | Başlangıç tarihi                 |
| `end_date`   | string        | Evet    | Bitiş tarihi                     |
| `filters`    | object        | Hayır   | İzin verilen filtreler           |

### Başarılı Output

```json
{
  "status": "success",
  "data": [
    {
      "date": "2021-01",
      "value": 250000
    },
    {
      "date": "2021-02",
      "value": 255000
    }
  ],
  "metadata": {
    "sources": [
      {
        "source_type": "bddk",
        "source_id": "bddk_konut_kredisi_aylik",
        "title": "Temsili konut kredisi veri seti",
        "url": "https://example.com/bddk-source",
        "provider": "BDDK"
      }
    ],
    "input_evidence_ids": [],
    "used_series": [
      "bddk_konut_kredisi_aylik"
    ],
    "time_window": {
      "start": "2021-01",
      "end": "2025-12"
    },
    "unit": "TRY million",
    "frequency": "monthly"
  },
  "method": {
    "name": "catalog_query"
  },
  "warnings": [],
  "limitations": [],
  "error": null
}
```

### Sorumluluk Notu

Bu örnek, `lakehouse_query` için planlanan genel amaçlı catalog-query sözleşmesini gösterir. Güncel ilk Housing demo akışında generic `lakehouse_query` implementasyonu yoktur; Bölüm 3.3'teki mevcut servis/evidence akışı kullanılır. İlk adapter bu tool adı altında geliştirilecekse mevcut `HousingAnalysisEvidence` sonucunu sarmalamalı ve Gold değişim metriklerini yeniden hesaplamamalıdır.

---

## 10.2 `web_search`

### Amaç

Analiz için gerekli dış bağlamları ve güvenilir kaynak adaylarını internette aramak.

### Input

```json
{
  "query": "2021 2025 Türkiye konut kredisi faiz oranları BDDK konut piyasası",
  "max_results": 5,
  "domains": [
    "bddk.org.tr",
    "tcmb.gov.tr",
    "tuik.gov.tr"
  ],
  "recency_days": null
}
```

### Input Alanları

| Alan           | Tip           | Zorunlu | Açıklama                           |
| -------------- | ------------- | ------- | ---------------------------------- |
| `query`        | string        | Evet    | Arama sorgusu                      |
| `max_results`  | integer       | Hayır   | Döndürülecek maksimum sonuç sayısı |
| `domains`      | array[string] | Hayır   | Alan adı filtreleri                |
| `recency_days` | integer/null  | Hayır   | Gün bazlı güncellik filtresi       |

### Başarılı Output

```json
{
  "status": "success",
  "data": {
    "results": [
      {
        "title": "Temsili kaynak başlığı",
        "url": "https://example.com/report",
        "snippet": "Kaynak içeriğinden kısa açıklama.",
        "published_at": "2025-12-01",
        "source_type": "official_report"
      }
    ]
  },
  "metadata": {
    "sources": [
      {
        "source_type": "web",
        "source_id": "https://example.com/report",
        "title": "Temsili kaynak başlığı",
        "url": "https://example.com/report",
        "provider": "Example Provider"
      }
    ],
    "input_evidence_ids": [],
    "used_series": [],
    "time_window": {
      "start": null,
      "end": null
    },
    "unit": null,
    "frequency": null
  },
  "method": {
    "name": "web_search"
  },
  "warnings": [],
  "limitations": [
    "Arama sonucu bulunması, kaynağın doğruluğunun otomatik olarak onaylandığı anlamına gelmez."
  ],
  "error": null
}
```

### Sorumluluk Notu

`web_search` kaynak bulur. Belirli bir kaynağın tam içeriğini almak `web_url_reader` sorumluluğundadır.

---

## 10.3 `web_url_reader`

### Amaç

Belirli bir URL'deki desteklenen içeriği okunabilir ve yapılandırılmış metin/tablolar hâline getirmek.

### Input

```json
{
  "url": "https://example.com/report.pdf",
  "content_type": "auto",
  "extract_tables": true,
  "use_ocr": false
}
```

### Input Alanları

| Alan             | Tip     | Zorunlu | Açıklama                                 |
| ---------------- | ------- | ------- | ---------------------------------------- |
| `url`            | string  | Evet    | Okunacak kaynak URL'si                   |
| `content_type`   | string  | Hayır   | `auto`, `html`, `pdf` vb.                |
| `extract_tables` | boolean | Hayır   | Destekleniyorsa tablo çıkarma            |
| `use_ocr`        | boolean | Hayır   | Desteklenen pipeline varsa OCR kullanımı |

### Güvenlik Parametreleri ve Fail-Closed Davranışı

MVP implementasyonu aşağıdaki sabit güvenlik sınırlarını uygulamalıdır:

| Kontrol | MVP kuralı |
| --- | --- |
| Şema | Yalnızca `http` ve `https` |
| Redirect | En fazla `5`; her hop yeniden URL + DNS/IP doğrulamasından geçer |
| Connect timeout | En fazla `5 saniye` |
| Read timeout | En fazla `15 saniye` |
| Maksimum response | Decompress edilmiş body için `10 MiB` |
| İzin verilen MIME | `text/html`, `text/plain`, `application/pdf` |
| Network hedefleri | localhost/loopback, private IP, link-local, metadata ve diğer unsafe adresler yasak |
| Credential içeren URL | Reddedilir veya response/log metadata'sına girmeden redakte edilir |

Bu kurallardan biri ihlal edilirse tool içerik parse etmeye devam etmez; `UNSAFE_URL`, `UNSUPPORTED_FORMAT`, `RESPONSE_TOO_LARGE` veya uygun ortak hata koduyla fail-closed response döndürür.

### Başarılı Output

```json
{
  "status": "success",
  "data": {
    "content_type": "pdf",
    "text": "Çıkarılan metin içeriği.",
    "tables": [
      {
        "title": "Temsili tablo",
        "columns": [
          "date",
          "value"
        ],
        "rows": [
          {
            "date": "2021-01",
            "value": 250000
          }
        ]
      }
    ]
  },
  "metadata": {
    "sources": [
      {
        "source_type": "web",
        "source_id": "https://example.com/report.pdf",
        "title": "Temsili rapor",
        "url": "https://example.com/report.pdf",
        "provider": null
      }
    ],
    "input_evidence_ids": [],
    "used_series": [],
    "time_window": {
      "start": null,
      "end": null
    },
    "unit": null,
    "frequency": null
  },
  "method": {
    "name": "document_text_extraction",
    "parameters": {
      "ocr_used": false,
      "tables_extracted": true
    }
  },
  "warnings": [],
  "limitations": [
    "Çıkarılan içerik, kaynak dokümanın doğruluğunun otomatik olarak onaylandığı anlamına gelmez."
  ],
  "error": null
}
```

### Sorumluluk Notu

Bu tool içeriği çıkarır. Çıkarılan metnin finansal analizde kullanılmaya uygun olup olmadığı orchestrator veya ilgili doğrulama katmanı tarafından değerlendirilmelidir.

---

## 10.4 `detect_anomalies`

### Amaç

Bir zaman serisindeki olağandışı gözlemleri veya dönemleri, belirlenmiş bir yöntemle tespit etmek.

### Input

```json
{
  "time_series": [
    {
      "date": "2021-01",
      "value": 250000
    },
    {
      "date": "2021-02",
      "value": 255000
    },
    {
      "date": "2021-03",
      "value": 420000
    }
  ],
  "metric_name": "toplam_hacim",
  "input_evidence_ids": ["ev-001"],
  "method": "z_score",
  "parameters": {
    "threshold": 3.0
  }
}
```

### Input Alanları

| Alan          | Tip    | Zorunlu | Açıklama                    |
| ------------- | ------ | ------- | --------------------------- |
| `time_series` | array  | Evet    | Tarih-değer gözlemleri      |
| `metric_name` | string | Evet    | Analiz edilen metrik        |
| `input_evidence_ids` | array[string] | Evet | Girdiyi sağlayan upstream evidence kimlikleri |
| `method`      | string | Evet    | Desteklenen anomali yöntemi |
| `parameters`  | object | Hayır   | Yönteme ait parametreler    |

### Başarılı Output

```json
{
  "status": "success",
  "data": {
    "anomalies": [
      {
        "date": "2021-03",
        "value": 420000,
        "score": 3.42,
        "is_anomaly": true
      }
    ],
    "observation_count": 3
  },
  "metadata": {
    "sources": [
      {
        "source_type": "bddk",
        "source_id": "bddk_konut_kredisi_aylik",
        "title": "Temsili konut kredisi veri seti",
        "url": "https://example.com/bddk-source",
        "provider": "BDDK"
      }
    ],
    "input_evidence_ids": ["ev-001"],
    "used_series": [
      "bddk_konut_kredisi_aylik"
    ],
    "time_window": {
      "start": "2021-01",
      "end": "2021-03"
    },
    "unit": "TRY million",
    "frequency": "monthly"
  },
  "method": {
    "name": "z_score",
    "parameters": {
      "threshold": 3.0
    }
  },
  "warnings": [
    "Bu örnekteki gözlem sayısı gerçek istatistiksel analiz için yetersiz olabilir."
  ],
  "limitations": [
    "Anomali tespiti, gözlemin ekonomik nedenini açıklamaz."
  ],
  "error": null
}
```

> Bu örnek yalnızca sözleşme gösterimidir. Gerçek anomali skoru, yöntem çalıştırılmadan sabit bir sonuç olarak kabul edilmemelidir.

---

## 10.5 `analyze_causality`

### MVP Durumu

`disabled`

Bu tool için kesin yöntem, minimum gözlem sayısı, frekans uyumu, durağanlık/lag gibi varsayımlar ve sonuç yorumlama modeli henüz kararlaştırılmamıştır. Bu nedenle ilk sürümde başarılı analiz response'u üretilmez ve tool orchestrator registry'ye çağrılabilir araç olarak eklenmez.

### MVP Çağrı Davranışı

Herhangi bir `analyze_causality` dispatch denemesi kontrollü olarak aşağıdaki yapıda reddedilir:

```json
{
  "status": "error",
  "data": null,
  "metadata": {
    "sources": [],
    "input_evidence_ids": [],
    "used_series": [],
    "time_window": {
      "start": null,
      "end": null
    },
    "unit": null,
    "frequency": null
  },
  "method": null,
  "warnings": [],
  "limitations": [
    "Nedensellik analizi MVP kapsamında etkin değildir."
  ],
  "error": {
    "code": "UNSUPPORTED_OPERATION",
    "message": "analyze_causality is not enabled in the MVP.",
    "details": {
      "tool": "analyze_causality",
      "status": "disabled"
    }
  }
}
```

### Gelecek Sözleşme Taslağı

Tool etkinleştirilmeden önce en az aşağıdakiler kararlaştırılmalı ve testlerle sabitlenmelidir:

* Desteklenen nedensellik yöntemi veya yöntemleri
* Minimum gözlem sayısı
* Frekans eşleme davranışı
* Durağanlık ve lag seçimi gereksinimleri
* Varsayım ihlallerinde `partial`/`error` davranışı
* Sonuç modelinde test istatistiği, p-value ve lag alanlarının anlamı
* `input_evidence_ids` ile upstream kaynak zincirinin korunması
* Korelasyon yardımcı metriğinin nedensellik sonucundan ayrı tutulması

> Başarılı response örneği yöntem kesinleşene kadar özellikle verilmemektedir. Belirsiz placeholder alanlar üretim sözleşmesi olarak kabul edilmez.

### Önemli Tasarım Notu

Korelasyon, nedensellik sonucu değildir. Gözlemsel veriden elde edilen istatistiksel ilişki kesin ekonomik veya politik nedensellik olarak sunulamaz.

---

## 10.6 `detect_changes`

### Amaç

Zaman serisindeki dönemsel değişimleri ve desteklenen yöntemlerle değişim noktalarını hesaplamak.

### Input

```json
{
  "time_series": [
    {
      "date": "2021-01",
      "value": 250000
    },
    {
      "date": "2021-02",
      "value": 255000
    },
    {
      "date": "2021-03",
      "value": 260000
    }
  ],
  "metric_name": "toplam_hacim",
  "input_evidence_ids": ["ev-001"],
  "comparison": "period_over_period",
  "detect_change_points": false
}
```

### Input Alanları

| Alan                   | Tip     | Zorunlu | Açıklama                        |
| ---------------------- | ------- | ------- | ------------------------------- |
| `time_series`          | array   | Evet    | Tarih-değer gözlemleri          |
| `metric_name`          | string  | Evet    | Analiz edilen metrik            |
| `input_evidence_ids`   | array[string] | Evet | Girdiyi sağlayan upstream evidence kimlikleri |
| `comparison`           | string  | Evet    | Karşılaştırma yöntemi           |
| `detect_change_points` | boolean | Hayır   | Destekleniyorsa kırılma analizi |

### Başarılı Output

```json
{
  "status": "success",
  "data": {
    "period_changes": [
      {
        "from_date": "2021-01",
        "to_date": "2021-02",
        "from_value": 250000,
        "to_value": 255000,
        "absolute_change": 5000,
        "percentage_change": 2.0,
        "direction": "increase"
      },
      {
        "from_date": "2021-02",
        "to_date": "2021-03",
        "from_value": 255000,
        "to_value": 260000,
        "absolute_change": 5000,
        "percentage_change": 1.9608,
        "direction": "increase"
      }
    ],
    "change_points": []
  },
  "metadata": {
    "sources": [
      {
        "source_type": "bddk",
        "source_id": "bddk_konut_kredisi_aylik",
        "title": "Temsili konut kredisi veri seti",
        "url": "https://example.com/bddk-source",
        "provider": "BDDK"
      }
    ],
    "input_evidence_ids": ["ev-001"],
    "used_series": [
      "bddk_konut_kredisi_aylik"
    ],
    "time_window": {
      "start": "2021-01",
      "end": "2021-03"
    },
    "unit": "TRY million",
    "frequency": "monthly"
  },
  "method": {
    "name": "period_over_period_change",
    "parameters": {
      "detect_change_points": false
    }
  },
  "warnings": [],
  "limitations": [
    "Yüzdesel değişim, değişimin ekonomik nedenini veya nedenselliğini göstermez."
  ],
  "error": null
}
```

### Hesaplama Tanımı

Sıfır olmayan bir önceki değer için:

```text
absolute_change = current_value - previous_value

percentage_change =
    ((current_value - previous_value) / previous_value) * 100
```

Özel durumlar:

* Önceki değer `0` ise yüzdesel değişim doğrudan hesaplanmamalıdır.
* Eksik gözlemler varsa sonuçta uyarı taşınmalıdır.
* Kırılma noktası tespiti yapılmıyorsa `change_points` boş liste olabilir.
* "Genel trend" sonucu, yeterli gözlem ve tanımlı yöntem olmadan üretilmemelidir.

---

# 11. Evidence Package ile İlişki

Tool response'ları, orchestrator tarafından birleştirilerek Evidence Package oluşturulmasına uygun olmalıdır.

## 11.1 Evidence Package'ın Amacı

Evidence Package, LLM'nin yanıt üretirken kullanabileceği doğrulanmış ara sonuçları ve bunların bağlamını taşır.

En az şu bilgileri içermelidir:

* Kullanılan veri kaynağı
* Veri seti veya seri kimliği
* Seri açıklaması
* Başlangıç ve bitiş tarihi
* Kullanılan hesaplama yöntemi
* Hesaplanan sayısal değerler
* Eksik veri veya kalite uyarıları
* Kullanılan tool isimleri

## 11.2 Örnek Evidence Package Taslağı

```json
{
  "question": "2021-2025 arasında konut kredisi hacmi ve faiz oranı nasıl değişti?",
  "evidence": [
    {
      "evidence_id": "ev-001",
      "tool_name": "lakehouse_query",
      "claim_type": "observed_data",
      "sources": [
        {
          "source_type": "bddk",
          "source_id": "bddk_konut_kredisi_aylik",
          "title": "Temsili konut kredisi veri seti",
          "url": "https://example.com/bddk-source",
          "provider": "BDDK"
        }
      ],
      "input_evidence_ids": [],
      "used_series": [
        "bddk_konut_kredisi_aylik"
      ],
      "time_window": {
        "start": "2021-01",
        "end": "2025-12"
      },
      "method": {
        "name": "catalog_query"
      },
      "data": []
    },
    {
      "evidence_id": "ev-002",
      "tool_name": "detect_changes",
      "claim_type": "computed_change",
      "sources": [
        {
          "source_type": "bddk",
          "source_id": "bddk_konut_kredisi_aylik",
          "title": "Temsili konut kredisi veri seti",
          "url": "https://example.com/bddk-source",
          "provider": "BDDK"
        }
      ],
      "input_evidence_ids": [
        "ev-001"
      ],
      "used_series": [
        "bddk_konut_kredisi_aylik"
      ],
      "time_window": {
        "start": "2021-01",
        "end": "2025-12"
      },
      "method": {
        "name": "period_over_period_change"
      },
      "data": {
        "period_changes": []
      }
    }
  ],
  "warnings": [],
  "limitations": [
    "Korelasyon nedensellik kanıtı değildir."
  ]
}
```

> Bu Evidence Package yalnızca taslak yapıyı gösterir. Nihai Pydantic modeli, tool response modelleri ve orchestrator veri akışı netleştirildikten sonra ayrı bir belge veya kod modeli olarak tanımlanabilir.

Türetilmiş `ev-002` kaydı `input_evidence_ids: ["ev-001"]` ile kaynak veri kanıtına bağlanır ve aynı BDDK source metadata'sını korur. Böylece hesaplanmış kanıtın hangi gözlemlerden türetildiği makinece izlenebilir.

---

# 12. Tool'lar Arası Çakışma Kuralları

## Veri erişimi ve analiz

* `lakehouse_query` MVP'de mevcut doğrulanmış Gold/evidence yüzeyinden veri getirir.
* `detect_anomalies` `planned` durumundadır.
* `detect_changes` `planned` durumundadır; ilk demo için Gold/evidence değişimlerini yeniden hesaplamaz.
* `analyze_causality` `disabled` durumundadır ve çağrı girişimi `UNSUPPORTED_OPERATION` ile reddedilir.

## Web erişimi ve içerik okuma

* `web_search` kaynak arar.
* `web_url_reader` belirli bir kaynağın içeriğini okur.
* `web_search`, tam doküman ayrıştırma işini üstlenmez.
* `web_url_reader`, arama motoru gibi kaynak keşfi yapmaz.

## Yorum ve karar desteği

* Tool'lar serbest ekonomik yorum üretmez.
* Orchestrator, araç sonuçlarını birleştirir ve doğrular.
* LLM, doğrulanmış kanıt paketini anlaşılır biçimde açıklar.
* LLM, araç çıktılarında bulunmayan sayısal sonuçları uydurmamalıdır.

---