# BDDK bültenlerini yerel Bronze'a alma

İlgili araştırma: issue #2. Bu değişiklik veri toplama altyapısıdır; konut kredisi serisinin ekonomik tanımının doğrulandığı veya tüm arşivin indirildiği anlamına gelmez.

## Saklama kararı

Hackathon geliştirmesi için indirdiğimiz hedef kapsamın ham verisini yerelde saklıyoruz. Bronze, bütün internet verisini veya her dosya biçiminin kopyasını saklamak zorunda değildir. Seçilen dönem, tablo, banka grubu ve para birimine ait orijinal kaynak yanıtını saklaması gerekir. Kaynak JSON ise JSON, HTML tablo ise HTML saklanır. Bunları Excel'e dönüştürmek ham veri oluşturmaz; dönüşüm ayrı katmana aittir.

```text
data/bronze/bddk/
  aylik/
    raw/          # BDDK JSON yanıtları ve keşif sayfaları
    receipts/     # Kaynak URL, istek parametreleri, tarih, hash, doğrulama
  haftalik/
    raw/          # Kaynağın gelişmiş rapor HTML'si; iki hassasiyet tablosu korunur
    receipts/
  gunluk/
    raw/          # Mevcut günlük yayının tam HTML kopyası
    receipts/
  index.json      # Başarılı isteklerin son sürümüne işaret eden yerel indeks
  runs/           # Her çalıştırmanın kapsamı, kataloğu, sonuçları ve eksikleri
```

Bu dosyalar mevcut `.gitignore` sayesinde Git dışında kalır. Kod ve kullanım belgesi repoda tutulur. Yerel disk tek başına ekip yedeği değildir; ortak nesne deposuna geçiş gerektiğinde Mustafa ile kararlaştırılmalıdır. JSON/HTML dosyaları sıkıştırılmadan, kaynak yanıt gövdesi değiştirilmeden saklanır; HTTP taşıma başlıkları/cookie'ler veri dosyasına eklenmez. Kaynak HTML'nin kendi gizli form alanları ham HTML'nin parçası olarak kalabilir; bunlar API anahtarı değildir. İstek metadata'sına oturum token'ı yazılmaz.

## İncelenen uygulamalar ve farklar

2026-09-10 tarihinde kaynak kodları okunarak incelendi; projeye üçüncü taraf kod kopyalanmadı veya paket yüklenmedi.

| Kaynak | İncelenen yaklaşım | Bu projedeki seçim |
|---|---|---|
| [urazakgul/bddkdata — data_fetcher.py](https://github.com/urazakgul/bddkdata/blob/464d2cf5790ad7aad763257ea61d6dcef10781a1/bddkdata/data_fetcher.py) | Aylık `BasitRaporGetir` çağrısı; dönem döngüsü; seçili sütunlarla DataFrame; hatalarda None | Aynı resmî istek sözleşmesi, bütün ham yanıt, kaynakla dinamik katalog, görünür hata raporu |
| [incesalim/Carthago — bddk_api_scraper.py](https://github.com/incesalim/Carthago/blob/550233dd5c3c797239475b7b0f5cf48f3562993c/src/scrapers/bddk_api_scraper.py) | Aylık uç, geçici hatalarda tekrar; SQLite ham yanıt ve işlenmiş tablolar; ham kayıtta INSERT OR REPLACE | Hash ile sürümlü dosyalar, eski yanıtı koruma, devam edebilme ve ayrı kontrol kaydı |
| [ozancanozdemir/bddkR README](https://github.com/ozancanozdemir/bddkR/blob/6429940cc5506631e26f6394fb79b0269bd7cf1a/README.md) | Aylık kullanım ve banka kodları dokümantasyonu | README'deki bazı kod açıklamaları canlı BDDK ile uyuşmadığından sabit liste alınmadı; R uygulama kodu incelenmedi |

Özellikle banka kodları frekanslar arasında aynı anlamı taşımıyor: canlı aylık sayfada 10003 Katılım, haftalıkta 10003 Kalkınma ve yatırım. Sayıdan ortak banka anlamı türetilmemeli. Silver aşamasında kaynak etiketlerine dayalı ayrı eşleme gerekir.

## Doğrulanan resmî veri yolları

- [Aylık](https://www.bddk.org.tr/BultenAylik): sayfadaki `TabloListesi` ve `ddlTaraf` okunur. Her tablo için `tr/Home/ParaBirimiGetir` desteklenen para birimlerini verir. `tr/Home/BasitRaporGetir` POST isteği `tabloNo, yil, ay, paraBirimi, taraf` alır. Birden fazla banka grubu aynı istekte gönderilir.
- [Haftalık](https://www.bddk.org.tr/BultenHaftalik/tr/Gelismis): yayınlanmış tarihler, mevcut/sonlandırılmış kalemler ve banka grupları okunur. `tr/Gelismis/GelismisRaporGetir` formu ile ay bazında en fazla 25 kalemlik gruplar alınır. TP/YP/Toplam birlikte, TL ve USD ayrı isteklerle alınır. Oturum/cookie ve sayfanın form token'ı korunur. HTML'deki iki Excel tablosu farklı ondalık hassasiyetleri gösterebildiği için ham yanıtın tamamı saklanır.
- [Günlük](https://www.bddk.gov.tr/BultenGunluk): mevcut sayfa bütünüyle arşivlenir. İncelenen sayfada tarih seçimi yoktu. `tr/Home/KiyaslamaJsonGetir` ile denenen bir seri yalnızca yedi son gözlem döndürdü. Bu, tüm günlük seriler için geçmişin bulunmadığını kanıtlamaz; ancak 2021–2026 günlük arşiv erişimi doğrulanmış değildir. Script geçmiş günlük indirmeyi destekliyormuş gibi davranmaz.

Günlük geçmiş için BDDK'nın arşiv/seri erişim yolunun ayrıca doğrulanması gerekir. Afra ile EVDS'de aynı tanımı taşıyan alternatif seri olup olmadığı araştırılabilir; aynı olduğu doğrulanmadan ikame edilmemeli.

## Kullanım

Repo kökünde Python 3.10+ yeterlidir; indirici standart kütüphane kullanır ve API anahtarı istemez. Aynı çıktı dizininde tek indirici çalıştırın.

Önce kapsam ve istek sayısını görmek için (yalnızca kataloglar indirilir):

```powershell
python -m scripts.download_bddk --start 2021-01-01 --end 2026-07-31 --plan
```

Küçük doğrulama koşusu:

```powershell
python -m scripts.download_bddk --start 2021-01-01 --end 2021-01-31 --limit 2
```

Aylık verilerin bütün tablolarını, canlı katalogdaki bütün banka gruplarını ve desteklenen para birimlerini hedef dönem için indirmek:

```powershell
python -m scripts.download_bddk --frequency aylik --start 2021-01-01 --end 2026-07-31
```

Haftalık verilerin katalogdaki bütün kalemleri ve banka grupları:

```powershell
python -m scripts.download_bddk --frequency haftalik --start 2021-01-01 --end 2026-07-31
```

Üç kaynağı birlikte çalıştırmak için `--frequency` kaldırılır. Günlük geçmiş eksikliği raporlanır; aylık/haftalık indirmeleri engellemez. Canlı katalogda keşfedilmeyen eski/kaldırılmış bir kalemin varlığı yalnızca bu script ile dışlanamaz. “Bütün” ifadesi **keşfedilen katalog ve istenen filtreler** ile sınırlıdır.

İlk demo için daha küçük indirme:

```powershell
python -m scripts.download_bddk --frequency aylik --monthly-tables 4 --groups 10001 --currencies TL --start 2021-01-01 --end 2025-12-31
```

Tablo 4 tüketici kredileridir; doğru konut kredisi satırının seçilmesi, dövize endeksli satırların kapsamı ve stok tanımı ayrı araştırma konusudur.

- `--limit N`: her frekansta ilk N veri isteği; tüm arşiv başarısı ilan edilmez.
- `--refresh`: kaynağı yeniden sorgular; değişmiş içeriği eski dosyayı silmeden yeni hash ile saklar.
- Varsayılan tekrar koşusu: dosya hash'i ve güncel doğrulayıcı geçerse önceki başarılı yanıt kullanılır. Kaynaktaki revizyonu bulmak için refresh gerekir.
- `--output`: alternatif yerel Bronze kökü.
- `--delay`: istekler arasında en az bekleme, varsayılan 0,75 saniye. Geçici hatalarda en fazla üç deneme; 429/5xx için bekleme uygulanır.
- Aylık seçim ay düzeyindedir: bir ayın ortasını seçmek o ayın raporunu alır. Günlük filtreleme gibi yorumlanmamalı.

Çıkış kodu 0: seçilen koşuda teknik hata yok. 1: indirme/doğrulama hatası var. 2: erişilemeyen kapsam var (örneğin günlük geçmiş). `--plan` ve `--limit` koşularında kod 0 bile olsa tüm kapsam tamamlanmış sayılmaz. `runs/*.json` içindeki `complete` alanını, katalogdaki `planned_requests` sayısını ve sonuçları birlikte okuyun. `complete` veri alımını ifade eder; ekonomik anlam ve hücre bazlı insan kontrolü her zaman ayrıdır.

## Kontroller ve öğretici notlar

Silver'a aktarımda belirli bir başarılı koşunun `results` kayıtları kullanılmalı. `index.json` bütün keşif/deneme isteklerinin indeksidir; tek başına analiz veri seti sayılmaz. Geliştirme sırasında saklanan eski deneme yanıtları silinmez, doğrulanan son koşular esas alınır. Başlangıçta indeks makbuzlardan yeniden kurulur; yarım kalan indeks güncellemesi tamamlanmış dosyayı kaybettirmez. Aynı çıktı dizinine eşzamanlı iki CLI çalışması işletim sistemi kilidiyle engellenir.

`Transport` ağ işini yapar; cookie'leri korur, süre aşımı ve geçici hatalarda sınırlı tekrar uygular. `Page` sitedeki seçenekleri ve tabloları okur; banka kodlarının anlamını uydurmaz. `Downloader` istekleri planlar ve yanıtları doğrular. `Archive` ham gövdeyi hash ile saklar; indirilen verinin hangi istekten geldiğini kaydeder. CLI tarihleri/filtreleri alır ve bütün koşunun raporunu üretir. Hesaplama veya aylıklaştırma yapmaz.

Kontroller:

- Aylık: başarılı JSON, dolu veri satırları, sütun/satır yapısı ve banka grubu etiketleri. Dönem başlıkta varsa istekle eşleşmesi zorunlu.
- Aylık tablolar 15/16/17 yanıt başlığında dönem vermiyor. Bunlar `period_confirmation=request_only` olarak işaretlenir; yanıtın içinden bağımsız dönem doğrulaması yapılamaz. Diğer tablolarda eksik/yanlış dönem hata sayılır.
- Haftalık: sayfa seçeneklerindeki tarihler değil, gerçek rapor tablosundaki tarihler kontrol edilir. Her istenen banka grubunda her yayımlanmış dönem bir kez bulunmalı; değer sütunu sayısı seçilen kalem × 3 olmalı; para birimi başlığı eşleşmeli. TP/YP sütunlarının her kalem için ekonomik olarak uygulanabilir olduğu varsayılmaz; boş hücreler korunur.
- Günlük: yayın tarihi ve veri tabloları bulunmalı; istenen tarih aralığı ile mevcut yayın tarihi ayrı kaydedilir.
- Arşiv: dosya hash'i değişmişse cache kullanılmaz; aynı isteğin farklı içerikli sürümleri birlikte kalır.

Testler:

```powershell
python -m unittest tests.test_bddk -v
```

Mevcut pytest ortamında aynı test dosyası `python -m pytest tests/test_bddk.py -q` ile de çalışır.

## İnsan kontrolü ve issue #2

1. Aylık sayfada Ocak 2021, Temmuz 2023 ve Temmuz 2026 için tablo 4, Sektör, TL seçin. Kaynak satırını ham JSON'daki `Json.data.rows[].cell` ve `Json.colModels` ile karşılaştırın; dipnot ve birimi okuyun.
2. Haftalık gelişmiş sayfada aynı aylardan birer yayın tarihi seçin. Aynı banka grubu, kalem, TP/YP/Toplam ve para birimiyle karşılaştırın. Görünen yuvarlatılmış değer ile export hassasiyetini ayırın.
3. Günlük ham kaydın gerçekten mevcut yayın olduğunu, hedef 2021–2026 günlük geçmişi olmadığını raporda kontrol edin.
4. Sonlandırılmış kalemlerde boş hücreler hata veya sıfır diye yeniden etiketlenmemeli. İş anlamı Silver öncesinde incelenmeli.
5. Ekip incelemesinde bu arşiv düzeni, banka grubu eşlemesi, günlük geçmiş sınırı ve ortak yedekleme kararı ele alınmalı.

Issue yorumunda otomasyonun doğrulanan kapsamı, canlı koşu raporlarının dosya adları, test sonucu, günlük geçmiş eksikliği ve insan kontrolü bekleyen alanlar paylaşılmalı. API anahtarı, oturum form token'ı veya büyük ham HTML/JSON issue'ya yapıştırılmamalı.
