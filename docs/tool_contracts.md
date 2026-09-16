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
      +--> lakehouse_query
      |
      +--> web_search
      |
      +--> web_url_reader
      |
      +--> detect_anomalies
      |
      +--> analyze_causality
      |
      +--> detect_changes
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

---

## 4. Araç Sorumluluk Sınırları

### 4.1 Sorumluluk Matrisi

| Tool                | Temel görevi                                                         | Yapmaması gereken                                                     |
| ------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `lakehouse_query`   | Katalogda tanımlı veri setlerinden yapılandırılmış veri getirmek     | Serbest yorum, nedensellik veya istatistiksel analiz üretmek          |
| `web_search`        | Dış kaynakları aramak ve sonuç metadata'sı döndürmek                 | Kaynak içeriğinin nihai finansal yorumunu üretmek                     |
| `web_url_reader`    | Belirli URL içeriğini okunabilir yapılandırılmış içeriğe dönüştürmek | İçeriğin doğruluğunu tek başına onaylamak veya ekonomik analiz yapmak |
| `detect_anomalies`  | Zaman serisindeki olağandışı gözlemleri belirlemek                   | Anomalinin ekonomik nedenini açıklamak                                |
| `analyze_causality` | Desteklenen yöntemlerle olası nedensel ilişkileri değerlendirmek     | Korelasyonu kesin nedensellik olarak sunmak                           |
| `detect_changes`    | Dönemsel değişimleri ve desteklenen değişim noktalarını hesaplamak   | Değişimin ekonomik nedenini veya nedenselliğini açıklamak             |

---

### 4.2 `lakehouse_query`

**Yapar:**

* Catalog'da tanımlı BDDK ve EVDS veri setlerinden veri getirir.
* Belirtilen tarih aralığına göre filtreleme yapar.
* İzin verilen seri, alan ve filtreleri uygular.
* Gerektiğinde önceden tanımlanmış basit toplulaştırmaları çalıştırabilir.
* Veri kaynağı, seri/veri seti, tarih aralığı ve birim bilgisini döndürür.

**Yapmaz:**

* Serbest ekonomik yorum üretmez.
* Nedensellik analizi yapmaz.
* Anomali veya değişim noktası tespit etmez.
* LLM adına sonuçları yorumlamaz.
* Catalog'da bulunmayan veri setlerini uydurmaz.


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

**Yapar:**

* İki veya daha fazla zaman serisi arasındaki olası nedensel ilişkiyi değerlendirmek için desteklenen istatistiksel yöntemleri uygular.
* Kullanılan yöntemi, varsayımları ve test sonuçlarını döndürür.
* Veri uzunluğu, frekans uyumu ve gerekli ön koşullar gibi sınırlamaları belirtir.
* Korelasyon gibi yardımcı istatistikleri, nedensellik sonucundan ayrı olarak raporlayabilir.

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

> Yukarıdaki seri kodu ve URL yalnızca temsili örnektir. Gerçek BDDK/EVDS kimlikleri veri kataloğu kesinleştiğinde kullanılacaktır.

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
| `TOOL_EXECUTION_ERROR`  | Beklenmeyen tool çalışma hatası     |

Bu kodlar ilk taslak içindir. Uygulama sırasında hata kodları tek bir ortak Python modeli veya enum üzerinden standardize edilmelidir.

### 9.3 Hata Durumunda Response

```json
{
  "status": "error",
  "data": null,
  "metadata": {
    "sources": [],
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
  "metadata": {},
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

Bu bölümdeki örnekler sözleşme tasarımını göstermek amacıyla hazırlanmıştır. Gerçek veri seti ve seri kimlikleri katalog kesinleştiğinde güncellenecektir.

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

`lakehouse_query` veri getirir. Yüzdesel değişim, anomali, nedensellik veya trend yorumu üretmek başka tool'ların sorumluluğundadır.

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
    "sources": [],
    "used_series": [],
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

### Amaç

İki veya daha fazla zaman serisi arasındaki olası nedensel ilişkiyi, desteklenen istatistiksel yöntemlerle değerlendirmek.

### Input

```json
{
  "series": [
    {
      "series_id": "housing_loan_volume",
      "name": "Konut kredisi hacmi",
      "unit": "TRY million",
      "observations": [
        {
          "date": "2021-01",
          "value": 250000
        },
        {
          "date": "2021-02",
          "value": 255000
        }
      ]
    },
    {
      "series_id": "housing_loan_rate",
      "name": "Konut kredisi faiz oranı",
      "unit": "%",
      "observations": [
        {
          "date": "2021-01",
          "value": 1.2
        },
        {
          "date": "2021-02",
          "value": 1.15
        }
      ]
    }
  ],
  "method": "TO_BE_DEFINED",
  "parameters": {}
}
```

### Input Alanları

| Alan                    | Tip    | Zorunlu | Açıklama                         |
| ----------------------- | ------ | ------- | -------------------------------- |
| `series`                | array  | Evet    | Karşılaştırılacak zaman serileri |
| `series[].series_id`    | string | Evet    | Seri kimliği                     |
| `series[].name`         | string | Hayır   | Seri adı                         |
| `series[].unit`         | string | Evet    | Seri birimi                      |
| `series[].observations` | array  | Evet    | Tarih-değer gözlemleri           |
| `method`                | string | Evet    | Desteklenen nedensellik yöntemi  |
| `parameters`            | object | Hayır   | Yöntem parametreleri             |

### Başarılı Output İçin Taslak

```json
{
  "status": "success",
  "data": {
    "relationships": [
      {
        "series_a": "housing_loan_rate",
        "series_b": "housing_loan_volume",
        "correlation": {
          "coefficient": -0.62,
          "method": "pearson"
        },
        "causality_test": {
          "method": "TO_BE_DEFINED",
          "result": "TO_BE_DEFINED",
          "p_value": null,
          "lag": null
        }
      }
    ]
  },
  "metadata": {
    "sources": [],
    "used_series": [
      "housing_loan_volume",
      "housing_loan_rate"
    ],
    "time_window": {
      "start": "2021-01",
      "end": "2025-12"
    },
    "unit": {
      "housing_loan_volume": "TRY million",
      "housing_loan_rate": "%"
    },
    "frequency": "monthly"
  },
  "method": {
    "name": "TO_BE_DEFINED",
    "parameters": {}
  },
  "warnings": [
    "Korelasyon katsayısı tek başına nedensellik kanıtı değildir."
  ],
  "limitations": [
    "Nedensellik değerlendirmesi kullanılan yöntemin varsayımlarına ve veri kalitesine bağlıdır.",
    "Gözlemsel verilerden elde edilen sonuçlar kesin ekonomik nedensellik olarak yorumlanmamalıdır."
  ],
  "error": null
}
```

### Önemli Tasarım Notu

Yukarıdaki `correlation` alanı, nedensellik sonucunun yerine geçmez. Korelasyon ve nedensellik testi ayrı alanlarda tutulmuştur.

Desteklenecek kesin yöntem, minimum gözlem sayısı, varsayımlar ve sonuçların nasıl yorumlanacağı kesinleşmeden bu tool üretim kullanımı için tamamlanmış kabul edilmemelidir.

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
  "comparison": "period_over_period",
  "detect_change_points": false
}
```

### Input Alanları

| Alan                   | Tip     | Zorunlu | Açıklama                        |
| ---------------------- | ------- | ------- | ------------------------------- |
| `time_series`          | array   | Evet    | Tarih-değer gözlemleri          |
| `metric_name`          | string  | Evet    | Analiz edilen metrik            |
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
    "sources": [],
    "used_series": [],
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
      "sources": [],
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

---

# 12. Tool'lar Arası Çakışma Kuralları

## Veri erişimi ve analiz

* `lakehouse_query` veri getirir.
* `detect_anomalies` anomali tespit eder.
* `detect_changes` değişim hesaplar.
* `analyze_causality` nedensellik değerlendirmesi yapar.

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
