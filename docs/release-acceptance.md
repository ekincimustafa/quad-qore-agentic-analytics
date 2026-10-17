# İlk sürüm kabul kaydı — ara durum

İlk kayıt: 12 Ekim 2026. Güncelleme: 13 Ekim 2026. Takip: [#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46).
Durum: Sentetik demo ve temel analiz doğrulandı; gerçek veri kabulü ve ilk sürüm teslimi açık.

İlk kontrollerin kod temeli: `f9d02099b2fc97a7a8588a022e4c0c04ce07b652` (PR #48 sonrası main).
13 Ekim temiz Windows kontrolü: `8943608b807f791ea6af92436724d9db4dcc7115`
(PR #49 sonrası main). Aşağıdaki yeni Windows satırları bu commit'e aittir.
`housing-api-example.json`, PR #49 ile eklenmiştir.
Bu kayıt bir tag/release duyurusu değildir. Sonraki kod/veri değişiklikleri için
commit ve sonuçlar yeni bir doğrulama kaydında güncellenmelidir.

## Gerçekleştirilen doğrulamalar

| Kontrol | Ortam / kanıt | Sonuç |
| --- | --- | --- |
| Bağımlılık kurulumu | Yeni Linux venv, Python 3.12.14, mevcut requirements.txt | Başarılı |
| Tam test paketi | Yeni Linux venv; MIA_API_KEY ve EVDS_API_KEY boş | 306 passed, 1 warning |
| Tam test paketi | Kullanıcının mevcut Windows venv ortamı, `ee8c416` | 305 passed, 1 skipped, 2 warnings |
| Temiz Windows kurulumu | 13 Ekim; yeni git clone ve yeni venv, Python 3.12.10, `8943608`, requirements.txt | Başarılı |
| Tam test paketi | 13 Ekim; temiz Windows venv, `8943608` | 305 passed, 1 skipped, 1 warning; 51.86 s |
| Windows sentetik HTML | 13 Ekim; `scripts.render_housing_sample` ve `Start-Process`, kullanıcı ekran görüntüsü | Dosya üretildi ve açıldı; 2021-01–2025-12, 60 ay, 55 eşleşme; ilk grafik paneli görüldü |
| Main CI | [PR #48 merge sonrası çalışma](https://github.com/ekincimustafa/quad-qore-agentic-analytics/actions/runs/38284032614) | 306 passed, 1 warning |
| Sentetik HTML komutu | `python -m scripts.render_housing_sample`, anahtarsız | Dosya üretildi; 60 ay, 55 eşleşme, ilk eşleşme 2021-02 |
| Health endpoint | Gerçek yerel HTTP isteği | HTTP 200, status ok |
| Sentetik API örneği | README curl komutu ve housing-api-example.json | HTTP 200; 3 ay, 1 eşleşme: 2021-02; 6 trace; narration null |
| Windows API örneği | Kullanıcının mevcut venv ortamı, README PowerShell komutları | Health ve analiz HTTP 200; 3 ay, 1 eşleşme: 2021-02 |
| Eksik Silver dosyaları | `/analysis/housing/demo`, anlatım kapalı | HTTP 503, demo_data_unavailable |
| API dokümantasyonu | `/docs` HTTP yanıtı | HTTP 200; tarayıcı görünümü ayrıca denenmedi |
| İlk ay kuralı | JSON örneğinden mevcut Gold fonksiyonu | Üç değişim alanı ve koşul bayrağı null |
| Veri hazırlama CLI'ları | BDDK/EVDS download ve Silver komutlarının --help çıktıları | Argümanlar doğrulandı; canlı veri indirilmedi |

Linux kurulum kontrolü, belirtilen kod temelini kullanan çalışma kopyasında
yeni venv ile yapıldı. Git clone adımı bu Linux ortamında çalıştırılmadı.
13 Ekim Windows kontrolünde ise ayrı geçici dizine git clone yapıldı; commit
kaydedildi, yeni venv oluşturuldu ve bağımlılıklar requirements.txt ile kuruldu.
Terminal kaydı rapor üretimini ve tam test sonucunu doğrular. Bu yeni Windows
koşusunda ayrıca API başlatma/HTTP denemesi yapılmadı; tablodaki Windows API
sonucu önceki mevcut venv kontrolüne aittir. `pytest -q` çıktısı atlanan testin
nedenini göstermediği için skip nedeni burada doğrulanmış sayılmaz.

55 eşleşme yalnızca sentetik fixture'ın sonucudur; gerçek ekonomik bulgu veya
model başarı metriği değildir. Gerçek BDDK/EVDS dosyaları bu doğrulamada kullanılmadı.
13 Ekim kullanıcı ekran görüntüsünde sentetik uyarı, dönem, 60 ay/55 eşleşme
sayaçları ve ilk grafik paneli kontrol edildi. Görüntü raporun alt bölümlerini,
mobil görünümü veya etkileşimlerini kapsamıyor; ağ kapatılarak tarayıcı kontrolü
yapıldığına dair kayıt yok. Offline üretim, kaynak metni escape ve
grafik/evidence uyumu testlerle kontrol edildi.

HTTP 422 sabitine ilişkin deprecation uyarısı sürüyor. Önceki Windows koşusunda
AnyIO portal alias uyarısı da vardı; 13 Ekim temiz Windows çıktısında yalnızca
HTTP 422 uyarısı bulunuyor. Uyarılar kabul tablosunda gizlenmedi.

## Kod ve sentetik kabul güncellemesi — 17 Ekim 2026

Bu bölümün kod temeli `d0fecc8e2684a36e40de94dec22432b16330bafa`
(PR #58 sonrası main). Yukarıdaki 12–13 Ekim ortam/uyarı kayıtları tarihsel
koşularına aittir; güncel sürümün aynı ortamda tekrar kontrolü sayılmaz.

- PR #43: fiziksel EVDS manifest tüketimi, kaynak/çıktı koruması,
  evidence/chart/run summary ve `--html` CLI ana dalda.
- PR #58: manifest üretimi, metadata kontrolü, normal CLI'da
  Bronze–Silver türetim karşılaştırması ve göreli yol düzeltmeleri ana dalda.
- Son zorunlu PR CI: **708 passed in 17.10s** (job 117348171632).
  Bağımsız yerel birleşik koşu: **708 passed**, uyarılar hata kabul edildi.
- `core.autocrlf=true` ayrı checkout'ta fixture hash'i ve fiziksel
  consumer/gerçek HTML CLI: **3 passed**. Bu Windows işletim sisteminde yeni
  kurulum yapıldığı anlamına gelmez; Git satır sonu dönüşümü kontrolüdür.
- Kaynak takvimi doğrulanmadığı için haftalık kapsam `unverified` olarak
  manifest, summary ve kalite notlarında taşınır; tam kapsam iddia edilmez.
- PR #51/#52/#54/#55 ile LLM istemcisi, sınırlı Housing soru API'si ve
  dokuz vakalık offline değerlendirme mevcut. Kullanıcının önceki üç canlı
  sentetik vaka kaydı [eval belgesindedir](housing-question-evals.md);
  genel model başarı oranı değildir. Buradaki güncellemede canlı çağrı yapılmadı.
- PR #57: deterministik TÜFE endpoint'i mevcut; doğal dil yönlendirmesi
  henüz yalnızca Housing analizine izin veriyor.

**Gerçek veri kabulü açık:** #39 dosya/komut/hash teslimi, #40 gerçek 66→60 ay
ve üç örnek ay karşılaştırması, ardından gerçek veri kullanılan demo/sürüm
notu #46'da tamamlanmalı. Bu güncelleme tag/release veya deployment değildir.
Aşağıdaki gerçek veri kutuları yalnızca bu kayıt nedeniyle işaretlenmez.

## Açık kabul kapıları

- [x] Windows'ta yeni Python 3.12 ortamında README sentetik hızlı başlangıcını doğrula (13 Ekim: clone, kurulum, rapor ve testler).
- [ ] BDDK/EVDS gerçek girdilerinin yollarını, boyutlarını ve SHA-256 özetlerini kaydet.
- [ ] EVDS seri kodu, frekans, baz yıl ve haftalık kapsam notlarını doğrula (#39, #45).
- [ ] 66 aylık gerçek Silver girdisinden tam 60 aylık analiz kapsamını doğrula.
- [ ] 2021-01, 2023-06 ve 2025-12 aylarını ham kaynak/Silver çıktısıyla karşılaştır.
- [ ] BDDK satır referansları ve EVDS manifestini Gold/evidence akışında koru (#40).
- [ ] Gerçek dosya tabanlı demo sonucunu HTML raporuna bağla; run summary ve kaynak zincirini göster (#46).
- [ ] Araç sözleşmesini güncel anlatım ve enabled/planned/disabled kapsamla uyumlu teslim et (#6).
- [ ] Gerçek veri kullanılan 60–90 saniyelik demo akışını çalıştır ve katkı/sürüm notunu tamamla.

Opsiyonel MIA'nın Housing JSON sözleşmesine canlı uyumu henüz doğrulanmadı.
`scripts.smoke_test_mia` yalnızca temel bağlantıyı sınar. İlk offline sürümün
teslimi MIA çağrısı gerektirmez; sonraki istemci/ajan işleri #41 ve #42'dedir.

Gerçek veri kabulünde doldurulacak kayıt:

| Alan | Durum |
| --- | --- |
| Kullanılan kod commit'i | Gerçek veri koşusunda kaydedilecek |
| BDDK Silver yolu / boyutu / SHA-256 | Bekleniyor |
| EVDS Silver yolu / boyutu / SHA-256 | Bekleniyor |
| EVDS manifesti / Bronze receipt referansları | Bekleniyor |
| 66→60 ay ve üç örnek ay karşılaştırması | Bekleniyor |
| Evidence/chart/run summary/HTML dosyaları | Gerçek veri koşusunda kaydedilecek |

## Katkı kanıtları ve aktif iş paylaşımı

Bu tablo seçilmiş PR örneklerini ve mevcut görev sahiplerini gösterir.
Kişisel katkılar ilgili PR'ların kod farklarıyla değerlendirilir.

| PR sahibi | Birleşmiş katkı örnekleri | Açık teslimat |
| --- | --- | --- |
| Mustafa / ekincimustafa | [#27 Gold](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/27), [#30 API](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/30), [#47 anlatım doğrulaması](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/47), [#48 HTML raporu](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/48) | #46 kurulum, kabul kaydı ve sürüm teslimi |
| Osman / OsmanerdemDutar | [#36 BDDK Silver](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/36) | #40 / PR #43 kaynak zinciri ve offline demo |
| Afra / afratopcu | [#23 EVDS Silver](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/23), [#35 EVDS ingestion](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/35) | #39 veri/manifest, #45 zaman/kapsam, #6 / PR #38 sözleşme |

Açık görevler tamamlanmış katkı olarak raporlanmaz. Tag/release yayınlama,
bu kabul kapıları tamamlandıktan sonraki ayrı teslim adımıdır.
