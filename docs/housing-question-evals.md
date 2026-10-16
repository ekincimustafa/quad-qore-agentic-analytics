# Housing soru değerlendirmesi

`evals/housing_question_cases.json`, mevcut tek izinli analiz için dokuz küçük
vaka içerir. `scripts.evaluate_housing_questions`, bunları gerçek Python servis
çekirdeğinden geçirir. HTTP katmanı ayrı API testleriyle kapsanır.

Bu set `evals/golden_cases.json` içindeki geniş taslak araç listesinden ayrıdır.
Yeni analiz, web, tahmin veya nedensellik özelliği eklemez. Mevcut kapsamın
doğru seçilmesini ve desteklenmeyen taleplerin çalıştırılmamasını değerlendirir.

| Vaka | Soru türü | Beklenen karar |
| --- | --- | --- |
| HQ-001 | Açık reel kredi koşulu, Ocak–Mart | ready; 3 ay, yalnızca 2021-02 eşleşir |
| HQ-002 | Aynı koşulun farklı ifadesi / ilk çeyrek | ready; aynı sonuç |
| HQ-003 | Dönem yok | clarification_required / period_required |
| HQ-004 | Reel mi nominal mi belirsiz | clarification_required / metric_ambiguous |
| HQ-005 | Veri kapsamı dışında tarih | clarification_required / outside_coverage |
| HQ-006 | Kesin nedensellik talebi | unsupported |
| HQ-007 | Enflasyon özeti; henüz uygulanmamış analiz | unsupported |
| HQ-008 | Şubat–Mart alt aralığı | ready; 2 ay, eşleşme yok |
| HQ-009 | Şemayı atlayıp web aracı seçtirme girişimi | unsupported |

Veri, mevcut `docs/housing-api-example.json` içindeki üç sentetik aydır.
HQ-008'de seçilen ilk ayın değişimi bulunmadığı için Şubat eşleşmez; mevcut
Gold semantiği korunur. Hazır planların evidence/grafiği doğrudan deterministik
servisle karşılaştırılır. Sabit gözlem/eşleşme beklentileri de veriden doğrulanır.

## Anahtarsız kontrol

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_housing_questions
```

Varsayılan mod `offline_stub` / `harness_behavior_only` olur. Repo içindeki
hazır model yanıtları kullanılır; LLM ayarı okunmaz, model çağrısı yapılmaz.
Dokuz vakanın geçmesi **modelin dokuz soruyu doğru anladığı anlamına gelmez**.
Bu, hazır yanıtlar karşısında uygulama akışının kontrolüdür.

Varsayılan rapor: `out/housing-question-eval-offline.json`.

## Açık bütçeli canlı kontrol

Mevcut yerel `LLM_*` ayarları ve kendi ücretsiz projen kullanılmalıdır. Çağrı
bütçesi faturalandırmayı kontrol etmez; Free Tier durumunu hesap arayüzünden
doğrula. Komut ücretli katmana geçmez veya otomatik model fallback'i yapmaz.

Önce üç vaka seçerek en fazla üç çağrı denemesine izin ver:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_housing_questions --live --max-model-calls 3 --case HQ-001 --case HQ-003 --case HQ-006
```

Varsayılan rapor: `out/housing-question-eval-live.json`. Model adı mevcut
yapılandırmadan kaydedilir; API anahtarı rapora eklenmez. Rapor ham model/hata
gövdesini içermez. Üçüncü taraf SDK debug logları ayrıca değerlendirilmelidir.

`--live` tek başına çalışmaz. Seçilen vaka sayısını karşılayan açık bir bütçe
gerekir; yetersiz bütçe, bilinmeyen/tekrarlı vaka veya girdi dosyasını ezecek
rapor yolu canlı çağrıdan önce reddedilir. Her vaka normalde bir plan isteğidir;
narrator kullanılmaz. Model çağrısı başarısız olursa kalan canlı vakalar atlanır.
Bozuk plan, başarısız vaka olarak raporlanır; aynı soruya otomatik retry yapılmaz.

## Raporun okunması

Raporda mod, seçilen/çalıştırılan/geçen/başarısız/atlanan vaka sayıları,
canlı model çağrı denemeleri, vaka başına beklenen/doğrulanan karar ve sabit hata
nedeni bulunur. Atlanan vakalar başarıya dahil edilmez. Model çağrı denemesi,
HTTP isteğinin sağlayıcı tarafından işlendiği veya ücretlendirildiği sayısı değildir.
Vaka seti ve sentetik veri dosyasının SHA-256 özetleri okunan içerikten alınır.

Exit kodları: `0` tüm seçilen vakalar geçti; `1` başarısız/atlanan vaka veya
rapor yazma hatası; `2` argüman, yapılandırma veya değerlendirme girdisi hatası.
`--output` farklı bir rapor dosyası seçer; varsayılan dosya sonraki koşuda yenilenir.

Canlı sonuçlar yalnızca seçilen sorular, veri ve modelle yapılan o koşuya aittir.
Bu küçük, elle hazırlanmış set genel başarı oranı, model kıyaslaması veya
ekonomik yorum doğruluğu ölçümü değildir. Farklı sorular ve tekrar koşuları
ayrı raporlarla değerlendirilmelidir.

## Yerel kabul kaydı — 15 Ekim 2026

Aşağıdaki sonuçlar Mustafa'nın Windows / PowerShell ortamından paylaştığı
konsol çıktısına dayanır; bağımsız bir sağlayıcı ölçümü değildir.

- Tam test paketi: `449 passed, 1 skipped, 2 warnings` (57,36 saniye).
  Atlanan testin gerekçesi paylaşılan çıktıda bulunmuyor.
- Anahtarsız değerlendirme: dokuz vakanın tamamı geçti; sıfır canlı çağrı.
- Canlı değerlendirme: `HQ-001`, `HQ-003` ve `HQ-006` seçildi;
  üçü de `passed (ok)` döndürdü. Üç vaka çalıştırıldı, üç canlı model çağrısı
  denendi; başarısız veya atlanan vaka yoktu. Komut exit kodu `0` oldu.

Bu canlı koşu, desteklenen analiz ve dönem seçimi, eksik dönem için açıklama
isteme ve nedensellik talebini desteklenmeyen analiz olarak reddetme
beklentilerini karşıladı. Diğer altı vakanın canlı sonucu bu kayıt kapsamında
yoktur. Konsol çıktısı model adını veya sağlayıcının model sürümünü göstermedi;
önceki smoke testinden model kimliği varsayılmadı. Yerel JSON raporu bu kayıt
sırasında ayrıca incelenmedi.

Veri üç sentetik aydan oluşur; canlı değerlendirmede narrator çağrılmaz.
Bu kayıt gerçek kaynak verisiyle uçtan uca kabul, ekonomik yorum doğrulaması
veya genellenebilir bir başarı oranı değildir. Ham yerel rapor `out/` altında
kalır ve Git'e eklenmez.
