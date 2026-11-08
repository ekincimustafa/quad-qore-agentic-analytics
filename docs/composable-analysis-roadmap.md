# Birleştirilebilir ekonomik analiz yol haritası

Hedef, mevcut prototipin doğrulanmış verileri üzerinde kullanıcının seçtiği
göstergeleri ve işlemleri birleştirebilmektir. İlk uçtan uca hedef soru:

> 2022–2024 arasında yıllık TÜFE'nin %50'yi aştığı ve reel konut kredisi stokunun
> bir önceki aya göre azaldığı ayları bul. Sonra aynısını 2025 için yap.

Mevcut dört analiz yolu çalışma örneği ve geriye dönük kontrol olarak kalır.
Hesap, dönem kontrolü ve kaynak kanıtı Python'dadır. Planlayıcı yalnız katalogda
bulunan serileri ve izinli işlemleri seçer. Her çalışma oturumu, tamamlanabilir
tek bir kabul ölçütüyle biter; sonraki oturuma devir notundan başlanır.

| Sıra | Oturum | Teslim ve kabul ölçütü |
| --- | --- | --- |
| 1 | 1 oturum | **Çekirdek:** aylık/yıllık TÜFE ve reel kredi değişimi kataloğu, aylık hizalama, koşullar ve kaynak kanıtı. Aynı çekirdek iki farklı metrik/eşik bileşimini bağımsız beklenen sonuçlarla doğrular. Bu dalda hazır. |
| 2 | 1–2 oturum | **Doğrulanmış paket ve planlayıcı:** mevcut dosya doğrulayıcısını çekirdeğe bağla. Modele kısa katalog ve plan şeması ver. Dönem, ölçü veya analiz niyeti belirsizse kontrollü yanıt üret. Sahte sağlayıcıyla soru → plan → doğru aylar akışını doğrula; eski uç noktaları koru. |
| 3 | 1–2 oturum | **Kullanılabilir demo:** deneysel yolu ekranda seçilebilir yap. Sonuçla birlikte seçilen seri, birim, dönem, kaynak ve değerlendirilemeyen ayları göster. “Aynısını 2025 için yap” son geçerli planın yalnız dönemini değiştirip kapsamı yeniden doğrulasın. Yeni soru ve farklı oturum eski bağlamı yanlışlıkla kullanmasın. |
| 4 | 1 oturum | **Ölçüm:** iki örnek dışındaki doğal dil sorularında seri, dönem, dönüşüm, eşik ve sonuçları ayrı ayrı kontrol et. Yanlış/belirsiz plan, eksik geçmiş ve desteklenmeyen isteği ekle. Çevrimdışı akış doğruluğu ile ayrıca onaylanmış canlı model doğruluğunu ayrı raporla. |
| 5 | Sonraki tur | **Akışı genişlet:** aynı araçlara dönemsel özet/karşılaştırma ekle; farklı adımlar gerektiren ikinci bir akış çalıştır. Koşullu dallanma veya durum yönetimi karmaşıklaşınca LangGraph'ı mevcut yürütücünün yerine ölçümlü bir denemeyle değerlendir. |

Oturum sayıları iş bölümü için tahmindir. Önce 60–90 dakikalık bir blok ayırıp
tablodaki sıradaki satırın ilk kabul örneğini bitirmek yeterlidir. Web arama,
anomali ve nedensellik ayrı özelliklerdir; bu ilk demo için gerekli değildir.

## İlk dilimin davranışı

[Aylık metrik kataloğu](../app/catalog/monthly_metrics.py) seri adlarını, Türkçe
karşılıkları, birim, frekans ve gerekli geçmişi tanımlar.
[Çekirdek](../app/services/composable_analysis.py) 1–3 koşul ve en çok 120 aylık
kapalı bir dönem alır. Koşullarda adı geçen metriklerden hangi hesap ailesinin
çalışacağını çıkarır; koşullar AND ile birleşir. Yalnız TÜFE seçilirse BDDK
gerekmez. Reel kredi seçilirse mevcut Gold fonksiyonunun gerektirdiği aylık
BDDK ve EVDS kolonları sağlanır.

- TÜFE için mevcut hesap önceki ayı veya 12 ay öncesini kullanır. Reel kredi
  için her iki tabloda varsa önceki ay hesaplamaya katılır; sonuç dönemi
  kullanıcının istediği ilk ayda başlar.
- Eşleştirme ay anahtarıyla yapılır. İstenen aralıkta eksik veya mükerrer veri
  kontrollü hatadır. Hesap için gerekli geçmiş yoksa gözlem gösterilir ama
  koşul sonucu `null` olur; sıfır ya da eşleşmiyor olarak yazılmaz.
- Çıktı planı, gözlemleri, eşleşen ayları, değerlendirilebilen ay sayısını ve
  metriklerin kaynak referanslarını taşır. İlk ayın hesabında kullanılan
  önceki BDDK gözleminin kaynağı da korunur.
- Bu aşamada tablolar bellekte çağıran tarafından verilir; kaynak referansı
  dosya doğrulaması anlamına gelmez. Dosya doğrulayıcısı ve doğal dil yolu
  2. aşamanın teslimidir.

Sentetik [kabul testleri](../tests/test_composable_analysis.py) aynı çekirdeği
iki farklı soruya karşılık gelen planla çalıştırır:

| Soru | Beklenen eşleşme (sentetik) |
| --- | --- |
| 2022 Ocak–Nisan'da yıllık TÜFE %50'nin üzerindeyken reel kredi stoku hangi aylarda azaldı? | Ocak ve Mart |
| Aynı dönemde aylık TÜFE artmazken reel kredi stoku hangi ayda arttı? | Şubat |

Depo kökünden Python 3.12 ortamıyla odaklı komut:
`python -m pytest -q tests/test_composable_analysis.py`.
