# İlk Uçtan Uca Demo Senaryosu

**Durum:** Taslak
**Sorumlu:** Mustafa Ekinci
**İlgili issue:** #1

## 1. Amaç

Bu senaryo, Quad-Qore platformunun ilk uçtan uca çalışan örneğini tanımlar.

Amaç; BDDK ve TCMB EVDS verilerini güvenilir biçimde bir araya getirmek, belirli ekonomik koşulları Python ile hesaplamak ve doğrulanmış sonuçları Kloudeks MIA modeli yardımıyla kullanıcıya anlaşılır biçimde açıklamaktır.

Bu senaryo aynı zamanda veri bağlantıları, lakehouse katmanları, analitik araçlar, agent orchestration, çıktı doğrulama ve kaynak izlenebilirliği bileşenlerinin birlikte çalıştığını gösterecektir.

## 2. Ana kullanıcı sorusu

> 2021–2025 döneminde konut kredisi faizlerinin düştüğü hâlde toplam konut kredisi tutarının artmadığı ayları bul ve olası nedenleri kaynaklarıyla açıkla.

## 3. İlk sürümün kapsamı

İlk sürüm şu dönemi kapsayacaktır:

* Başlangıç: Ocak 2021
* Bitiş: Aralık 2025
* Hedef frekans: Aylık
* Beklenen gözlem sayısı: 60 ay

İlk sürümde yalnızca Türkiye geneli toplam konut kredisi verisi kullanılacaktır. İl bazlı FinTürk verileri ve farklı kredi türleri sonraki sürümlerde ele alınabilir.

## 4. Önemli veri anlamı

BDDK konut kredisi verisi ile EVDS konut kredisi faiz verisi aynı tür ölçüm değildir.

* BDDK tarafındaki toplam konut kredisi tutarının bir **stok** büyüklüğü olması beklenmektedir.
* EVDS `TP.KTF12` serisi yeni kullandırılan konut kredilerine ilişkin ağırlıklı ortalama **akım faiz oranıdır**.

Bu nedenle iki seri doğrudan aynı ekonomik büyüklüğü ölçmez. Analizde faiz oranı değişimleriyle kredi stoku değişimleri birlikte incelenecek ancak aralarında otomatik olarak nedensellik kurulduğu iddia edilmeyecektir.

## 5. Veri kaynakları

| Veri                        | Kaynak    | Seri veya tablo                      | Ham frekans  | Durum      |
| --------------------------- | --------- | ------------------------------------ | ------------ | ---------- |
| Toplam konut kredisi tutarı | BDDK      | Osman’ın araştırmasıyla kesinleşecek | Kesinleşecek | Bekleniyor |
| Konut kredisi faiz oranı    | TCMB EVDS | `TP.KTF12`                           | Haftalık     | Doğrulandı |
| Tüketici fiyat endeksi      | TCMB EVDS | Afra’nın araştırmasıyla kesinleşecek | Kesinleşecek | Bekleniyor |
| Konut Fiyat Endeksi         | TCMB EVDS | Afra’nın araştırmasıyla kesinleşecek | Kesinleşecek | Bekleniyor |

Her veri kaydıyla birlikte şu metadata alanları korunmalıdır:

* Kaynak kurum
* Kaynak adresi
* Seri kodu veya tablo adı
* Açıklama
* Birim
* Ham frekans
* Kullanılan tarih aralığı
* İndirme zamanı
* Uygulanan dönüşümler

## 6. Harness-first görev ayrımı

### Python ve araçların sorumlulukları

Aşağıdaki işlemler deterministik kodla yapılacaktır:

* Kaynak dosyalarını indirmek veya okumak
* Excel, CSV veya API yanıtlarını ayrıştırmak
* Tarihleri standart biçime dönüştürmek
* Sayısal değerleri temizlemek
* Birimleri kontrol etmek
* Haftalık veriyi aylık frekansa dönüştürmek
* Serileri ay bazında birleştirmek
* Aylık değişimleri hesaplamak
* Koşula uyan ayları belirlemek
* Eksik verileri tespit etmek
* Çıktı şemasını doğrulamak
* Kaynak ve dönüşüm bilgilerini saklamak

### LLM’in sorumlulukları

Kloudeks MIA modeli şu görevlerle sınırlandırılacaktır:

* Kullanıcının doğal dildeki amacını anlamak
* Tanımlı araçlar arasından uygun olanları seçmek
* Araçların ürettiği doğrulanmış sonuçları yorumlamak
* Sonraki araştırma adımını önermek
* Sonucu anlaşılır bir dille açıklamak
* Analizin sınırlamalarını belirtmek

LLM:

* Ham veriden kendi başına sayısal sonuç üretmemelidir.
* Kaynakta bulunmayan değer uydurmamalıdır.
* Python tarafından hesaplanan değerleri değiştirmemelidir.
* Korelasyonu nedensellik olarak sunmamalıdır.
* Tanımlanmamış bir aracı çağırmamalıdır.

## 7. Veri katmanları

### Bronze

Kaynaklardan alınan ham veriler mümkün olduğunca değiştirilmeden saklanır.

Örnek içerik:

* Ham BDDK Excel dosyası
* Ham EVDS yanıtı
* Kaynak adresi
* İndirme zamanı
* Dosya özeti veya hash değeri

### Silver

Veriler temizlenir ve standartlaştırılır.

Beklenen işlemler:

* Tarih normalizasyonu
* Sayısal değer dönüşümü
* Birim kontrolü
* Frekans dönüşümü
* Seri ve sütun adlarının standartlaştırılması
* Eksik ve hatalı gözlemlerin işaretlenmesi

### Gold

Demo sorusuna doğrudan cevap verecek birleştirilmiş aylık tablo oluşturulur.

Gold tablosu Ocak 2021–Aralık 2025 dönemini kapsayan 60 satır içermelidir.

## 8. Gold tablo sözleşmesi

| Alan                             | Açıklama                                   |
| -------------------------------- | ------------------------------------------ |
| `period`                         | Ay bilgisi, `YYYY-MM` biçiminde            |
| `housing_loan_amount`            | Toplam konut kredisi tutarı                |
| `housing_loan_unit`              | BDDK verisinin birimi                      |
| `housing_loan_change_pct`        | Bir önceki aya göre kredi tutarı değişimi  |
| `housing_loan_interest_rate_pct` | Aylıklaştırılmış konut kredisi faiz oranı  |
| `interest_rate_change_pp`        | Faiz oranındaki aylık yüzde puan değişimi  |
| `rate_down_credit_not_up`        | Ana koşulun gerçekleşip gerçekleşmediği    |
| `bddk_source_ref`                | BDDK kaynak referansı                      |
| `evds_series_code`               | Kullanılan EVDS seri kodu                  |
| `evds_source_ref`                | EVDS kaynak referansı                      |
| `data_quality_note`              | Eksik veya şüpheli veriye ilişkin açıklama |

## 9. İlk hesaplama kuralları

### Faiz oranının aylıklaştırılması

EVDS `TP.KTF12` haftalık bir akım faiz serisidir.

İlk teknik varsayım olarak bir ay içindeki haftalık faiz gözlemlerinin aritmetik ortalaması kullanılacaktır:

```text
monthly_interest_rate = mean(weekly_interest_rates_in_month)
```

Bu karar geçicidir. Ortalama ile ay sonu değerinin hangisinin kullanılacağı ekip ve mentor görüşmesiyle kesinleştirilecektir.

### Kredi tutarındaki aylık değişim

```text
housing_loan_change_pct =
    ((current_amount - previous_amount) / previous_amount) * 100
```

### Faiz oranındaki değişim

Faiz değişimi yüzde değişim olarak değil, yüzde puan olarak hesaplanacaktır:

```text
interest_rate_change_pp =
    current_interest_rate - previous_interest_rate
```

### Ana koşul

```text
rate_down_credit_not_up =
    interest_rate_change_pp < 0
    AND housing_loan_change_pct <= 0
```

İlk ay için önceki ay değeri bulunmadığından değişim alanları ve koşul sonucu `null` olacaktır.

## 10. Eksik veri politikası

İlk sürümde eksik gözlemler sessizce doldurulmayacaktır.

* Eksik ay varsa sonuç tablosunda işaretlenecektir.
* `data_quality_note` alanına açıklama yazılacaktır.
* Eksik değere sahip dönem ana koşul değerlendirmesine alınmayacaktır.
* İnterpolasyon ancak açık bir yöntem ve gerekçe belirlendikten sonra uygulanacaktır.

## 11. Beklenen çalışma akışı

1. Kullanıcı doğal dilde sorusunu gönderir.
2. Agent controller soruyu analiz eder.
3. Agent yalnızca izinli veri ve analiz araçlarını seçer.
4. BDDK ve EVDS araçları gerekli verileri lakehouse üzerinden getirir.
5. Python araçları serileri aylık frekansta birleştirir.
6. Değişimler ve ana koşul deterministik olarak hesaplanır.
7. Çıktı doğrulayıcı tablo şemasını, tarihleri ve kaynakları kontrol eder.
8. MIA modeli doğrulanmış sonuçları yorumlar.
9. Son cevap tablo, açıklama, kaynaklar ve sınırlamalarla kullanıcıya sunulur.

## 12. Beklenen kullanıcı çıktısı

Kullanıcıya en az şu bilgiler gösterilmelidir:

* Koşula uyan ayların listesi
* İlgili aylardaki kredi tutarı ve değişimi
* İlgili aylardaki faiz oranı ve değişimi
* Kullanılan BDDK ve EVDS kaynakları
* Uygulanan aylıklaştırma yöntemi
* Eksik veya şüpheli veri notları
* Korelasyon ve nedensellik sınırlaması
* Enflasyon veya Konut Fiyat Endeksiyle analizi genişletme önerisi

## 13. İlk değerlendirme ölçütleri

Senaryo başarılı kabul edilmek için:

* 60 aylık hedef dönem açıkça oluşturulmalıdır.
* BDDK ve EVDS verileri aynı ay anahtarıyla birleştirilmelidir.
* Sayısal hesaplar yalnızca Python tarafından yapılmalıdır.
* Koşula uyan aylar deterministik kuralla belirlenmelidir.
* Her sonuç kullanılan kaynaklara bağlanmalıdır.
* Eksik veriler gizlenmemelidir.
* LLM hesaplanmamış sayısal değer üretmemelidir.
* Sonuç açıklaması korelasyonu nedensellik olarak sunmamalıdır.
* Aynı veri ve parametrelerle çalıştırılan araçlar aynı sonucu üretmelidir.

## 14. Açık kararlar

Aşağıdaki konular takım araştırmaları tamamlandıktan sonra güncellenecektir:

* [ ] BDDK veri setinin kesin adı
* [ ] BDDK tablo veya sütun adı
* [ ] BDDK verisinin birimi
* [ ] BDDK ham veri frekansı
* [ ] EVDS haftalık faiz verisinin aylıklaştırma yöntemi
* [ ] Enflasyon serisinin kesin kodu ve baz yılı
* [ ] Konut Fiyat Endeksi serisinin kesin kodu ve baz yılı
* [ ] Eksik değerler için son politika
* [ ] Kullanılacak analiz ve değişim araçlarının kesin adları

## 15. İlk sürüm dışında kalanlar

Aşağıdaki özellikler ilk uçtan uca sürümün dışında tutulacaktır:

* İl bazlı FinTürk karşılaştırmaları
* Tahmin modeli geliştirme
* Otomatik ekonomik nedensellik iddiası
* Çok sayıda kredi türünün aynı anda analizi
* Kullanıcıya sınırsız araç çalıştırma yetkisi
* Modelin doğrudan ham veriyi değiştirmesi
