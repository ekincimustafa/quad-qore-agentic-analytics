# İlk sürüm kabul kaydı — ara durum

İlk kayıt: 12 Ekim 2026. Güncelleme: 18 Ekim 2026. Takip: [#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46).
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

## Windows sentetik kullanım kontrolü — 18 Ekim 2026

Kod temeli `45c8dcf771b6f6b41e2b4a247b94be7607f0d40c` (kontrol sırasında PR #61 sonrası main).
Kontrol sonrası PR #62, kullanıcı onayıyla `6abcfb8` olarak merge edildi;
aşağıdaki test/çıktı kayıtları belirtilen `45c8dcf` kaynağına aittir.
Bu kaynak ağacı `git archive main` ile Git'in yok saydığı `out/acceptance-main`
altına çıkarıldı. Python 3.12.15 ortamı önceki oturumda `requirements.txt` ile
kurulmuş `out/python312` ortamıdır; bugün yeni clone/venv veya bağımlılık kurulumu
yapılmış sayılmaz. PR #62/#64'ün runtime kodu bu tarihli koşuda bulunmaz.

Arşiv kökünde çalıştırılan komutlar:

```powershell
..\python312\python.exe -m pytest tests -q -rs --basetemp "$env:TEMP\qq46main" --tb=short
..\python312\python.exe -m scripts.render_housing_sample
```

- Tam offline paket: **707 passed, 1 skipped in 58.24s**. Atlanan test
  `tests/test_bddk_silver.py::test_symlink_outside_raw_dir_rejected` için Windows
  symlink iznidir.
- Sentetik HTML: **60 ay, 55 eşleşme, ilk eşleşme 2021-02, 6 trace**.
  `SENTETİK DEMO` etiketi ve dış `script src` bulunmadığı dosya içeriğinden
  kontrol edildi. Tarayıcı görünümü/etkileşimi bu oturumda denenmedi.
- Yerel çıktı `out/acceptance-main/out/housing-sample.html`: 4.376.582 bayt;
  SHA-256 `0796af39622e9b3e1cd13fbb3ad188ef923cc838cb29aa73fc122fa5a77952a4`.
- FastAPI TestClient ile süreç içi HTTP: `/health`, README'deki üç aylık Housing
  isteği ve TÜFE örneği **200** döndü. Housing: 3 ay, 2021-02 eşleşmesi;
  TÜFE: 3 ay, ilk-son değişimi yaklaşık %-1. Bu kontrol gerçek TCP sunucusu veya
  tarayıcı denemesi değildir.
- Yerel `data/` yalnızca `.gitkeep` dosyaları içerir. Canlı model/EVDS çağrısı,
  gerçek veri indirme, merge, release veya yayınlama yapılmadı.

Bu kayıt belirtilen `45c8dcf` kaynağının sentetik kullanımını doğrular; gerçek 66→60 ay,
üç örnek ay karşılaştırması ve gerçek veriyle sunum kapıları açık kalır.

## Güncel main: temiz Windows venv ve yerel HTTP — 18 Ekim 2026

Kod temeli `7ee7225a2d70af4c0a58a4b7f7b2a6245ff98b8f` (PR #62–#66 merge sonrası).
Mevcut `.venv`, kayıp Python kurulumuna işaret ettiği için korunup kullanılmadı.
Mevcut Python 3.12.15 ile **yeni**, `include-system-site-packages = false` olan
`out/clean312` venv'i oluşturuldu; bağımlılıklar mevcut `requirements.txt` ile
kuruldu ve `pip check` başarılı oldu. Kod `git archive main` üzerinden
`out/clean-demo` dizinine açıldı. Yeni uzak clone veya yeni Python kurulumu
yapılmadı; önceki ortamın site-packages dizini kopyalanmadı.

Repo kökünde kurulum, ardından arşiv kökünde kontroller:

```powershell
.\out\python312\python.exe -m venv out/clean312
.\out\clean312\Scripts\python.exe -m pip install -r out/clean-demo/requirements.txt
Set-Location out/clean-demo
..\clean312\Scripts\python.exe -m pip check
..\clean312\Scripts\python.exe -m pytest tests -q -rs --basetemp "$env:TEMP\qq46clean" --tb=short
..\clean312\Scripts\python.exe -m scripts.render_housing_sample
..\clean312\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8765
```

- Yeni ortamda tam offline paket **794 passed, 2 skipped in 103.97s**. İki atlama
  `test_bddk_silver.py:813` ve `test_housing_question_files.py:244` Windows
  symlink izinleridir. Önceki ortam testleri yeni kurulum kanıtı yerine kullanılmadı.
- Sentetik HTML **60 ay / 55 eşleşme / ilk 2021-02 / 6 trace**; 4.376.582 bayt,
  SHA-256 `0796af39622e9b3e1cd13fbb3ad188ef923cc838cb29aa73fc122fa5a77952a4`.
  Sentetik etiket ve dış `script src` yokluğu kontrol edildi; önceki kayıtla aynı.
  Dosya `out/clean-demo/out/housing-sample.html` altında korunur.
- Gerçek Uvicorn TCP sunucusunda README'nin PowerShell `Invoke-RestMethod`
  health/Housing örneği (port 8765) ve TÜFE JSON örneği **200** döndü. Housing
  3 ay, 2021-02 eşleşmesi, 6 trace ve null anlatım; TÜFE 3 ay. `/docs` HTTP **200**.
  Kontrol bitince yalnızca bu oturumun sunucusu durduruldu. Bu dış servis çağrısı değildir.
- Dosya demo, BDDK Silver ve EVDS manifest CLI'larının `--help` çıktıları güncel
  bayraklarla uyumlu. Veri indirme veya yeniden gerçek veri üretme komutu çalıştırılmadı.
- Tarayıcı kontrol yüzeyi bulunamadı (`browsers: []`, `iab` erişilemiyor).
  Güncel HTML'nin görsel/etkileşimli tarayıcı kabulü **yapılmadı**; kullanıcı
  açıp grafik hover/zoom, eşleşme tablosu, kaynak ve sınırlamaları kontrol etmeli.

**Gerçek paket erişimi ayrı ve açık:** Afra [hazır EVDS ZIP'ini bildirdi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6250215723);
henüz dosya bağlantısı yok. #40'ta BDDK/gerçek birleşik koşu paketi bağlantısı
veya yorum yok. Yeni durum, kalan teslimler ve gönderilmemiş mesajlar
[teslim rehberindedir](real-demo-delivery.md). Sentetik sayılar gerçek sonuç
olarak kabul edilmedi; #42/#46 açık kalır. Canlı LLM/EVDS çağrısı yapılmadı.

## Açık kabul kapıları

- [x] Windows'ta yeni Python 3.12 ortamında README sentetik hızlı başlangıcını doğrula (13 Ekim: clone, kurulum, rapor ve testler).
- [ ] BDDK/EVDS gerçek girdilerinin yollarını, boyutlarını ve SHA-256 özetlerini kaydet.
- [ ] EVDS seri kodu, frekans, baz yıl ve haftalık kapsam notlarını gerçek paketle doğrula (#39; zaman/kapsam politikası #45'te tamamlandı).
- [ ] 66 aylık gerçek Silver girdisinden tam 60 aylık analiz kapsamını doğrula.
- [ ] 2021-01, 2023-06 ve 2025-12 aylarını ham kaynak/Silver çıktısıyla karşılaştır.
- [ ] BDDK satır referansları ve EVDS manifestini Gold/evidence akışında koru (#40).
- [ ] Gerçek dosya tabanlı demo sonucunu HTML raporuna bağla; run summary ve kaynak zincirini göster (#46).
- [x] Araç sözleşmesini güncel anlatım ve enabled/planned/disabled kapsamla uyumlu teslim et (#6 tamamlandı; ilk katkı PR #38, güncel kapsam PR #60).
- [ ] Gerçek veri kullanılan 60–90 saniyelik demo akışını çalıştır ve katkı/sürüm notunu tamamla.

Yapılandırılabilir LLM istemcisi #41 ile tamamlandı; önceki sınırlı canlı kontrol
[LLM kabul kaydındadır](llm-client.md). Legacy `scripts.smoke_test_mia` yalnızca
temel bağlantıyı sınar. Güncel sentetik kontrol canlı LLM gerektirmedi.
Dosya destekli sorunun gerçek veri kabulü #42'de açık kalır. İki analizli
yönlendirme #59, PR #62/#66 ile tamamlandı; gerçek veri kabulünü kapatmaz.

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
| Mustafa / ekincimustafa | [#27 Gold](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/27), [#30 API](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/30), [#47 anlatım doğrulaması](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/47), [#48 HTML raporu](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/48), [#62](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/62)/[#66 soru yönlendirmesi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/66), [#64 dosya wrapper'ı](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/64) | #42 gerçek dosya destekli soru kabulü, #46 gerçek rapor/kabul/sunum |
| Osman / OsmanerdemDutar | [#36 BDDK Silver](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/36), [#43 kaynak zinciri ve offline demo CLI](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/43) | #40 gerçek BDDK/EVDS birleşik demo kabulü |
| Afra / afratopcu | [#23 EVDS Silver](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/23), [#35 EVDS ingestion](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/35), [#38 ilk araç sözleşmesi katkısı](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/38), [#58 manifest üretimi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/58) | #39 gerçek dosya/komut/hash ve örnek ay teslimi |

Açık görevler tamamlanmış katkı olarak raporlanmaz. Tag/release yayınlama,
bu kabul kapıları tamamlandıktan sonraki ayrı teslim adımıdır.
