# İlk sürüm kabul kaydı — ara durum

İlk kayıt: 12 Ekim 2026. Güncelleme: 18 Ekim 2026. Takip: [#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46).
Durum: Gerçek BDDK+EVDS teknik kabulü ve sabit planlı dosya sorusu doğrulandı;
Mustafa yeniden üretilen HTML'nin görsel kabulünü 18 Ekim'de teyit etti.
#40 tamamlandı; `v0.1.0-rc.1` prerelease yayımlandı. 19 Ekim kararıyla #46 ekran
kaydı isteğe bağlı portföy işidir; kaydedilmedi ve yeni ürünün kabulünü bloke etmez.

İlk kontrollerin kod temeli: `f9d02099b2fc97a7a8588a022e4c0c04ce07b652` (PR #48 sonrası main).
13 Ekim temiz Windows kontrolü: `8943608b807f791ea6af92436724d9db4dcc7115`
(PR #49 sonrası main). Aşağıdaki yeni Windows satırları bu commit'e aittir.
`housing-api-example.json`, PR #49 ile eklenmiştir.
12–13 Ekim tarihli ilk kayıtlar bir tag/release duyurusu değildir; rc.1 yayını
aşağıda ayrı kaydedilmiştir. Sonraki kod/veri değişiklikleri için
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

**İlk kurulum kontrolü sırasındaki engel:** Afra [hazır EVDS ZIP'ini bildirmişti](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6250215723);
o sırada dosya bağlantısı yoktu. Sonraki EVDS teslimi ve alıcı kontrolü aşağıdadır.
#40'taki sonraki birleşik teslim ve bağımsız koşu aşağıda kaydedilmiştir.
Mustafa paylaşım taleplerini [#39'da](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6250879475)
ve [#40'ta](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6250883464)
yayımladı; tekrar mesaj gönderilmez. Yeni durum, kalan teslimler ve önceki taslaklar
[teslim rehberindedir](real-demo-delivery.md). Sentetik sayılar gerçek sonuç
olarak kabul edilmedi; #42/#46 açık kalır. Canlı LLM/EVDS çağrısı yapılmadı.

## Gerçek EVDS paketi: Mustafa alıcı doğrulaması — 18 Ekim 2026

Sentetik kayıtların aksine bu bölüm Afra'nın [OneDrive teslimindeki](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251399411)
mevcut gerçek EVDS dosyalarını kullanır. Canlı kaynaktan yeniden indirme yapılmadı.
Runtime `7ee7225`, Python 3.12.15 (`out/clean312`); uygulama kodu değişmedi.

- Mustafa'nın İndirilenler klasöründeki `OneDrive_1_18.10.2026.zip`, teslim ZIP'i
  ile `KKB_EVDS_Teslim_Belgesi.md` dosyasını içeren taşıma arşividir. Beklenen
  hash içteki **20.344 baytlık** `EVDS_gercek_veri_teslim.zip` içindir ve eşleşti:
  `1c9255194c3222dccc33e056ba195c46a8d0912cdb9ccccd178e8e4b2731ebc1`.
- Paket `out/evds-acceptance-20261018/inputs/` altında güvenli göreli yollarla
  açıldı; repo `data/` dizini korunur. Teslim belgesinin SHA-256'sı
  `2715a66ee17338836193c5f4779107bc488c4597ba65b2cb0995d6c3fabfa25a`.
- Belgedeki **12/12 dosyanın SHA-256 ve boyutu** eşleşti: toplam 158.914 bayt.
  Her iki manifest `load_and_validate_manifest` ile fiziksel CSV/raw/makbuz,
  yol, seri/frekans/birim/baz yıl ve coverage kontrollerinden geçti.
- `build_evds_manifest` ile yeniden kurulan iki manifest teslimle yapısal
  olarak aynı. `build_evds_silver_from_bronze` çıktıları ayrı `rebuilt/` alanına
  yazıldı: CSV'ler teslimle **bayt düzeyinde**, coverage raporları **JSON olarak**
  aynı. Teslim edilen dosyalar üzerine yazılmadı; 12 girdinin ilk/son hash'i aynı.
  60 aylık dosyanın 66 aylık dosyanın ilk 60 satırına sayısal olarak tam eşitliği
  ayrıca `pandas.testing.assert_frame_equal(check_exact=True)` ile doğrulandı.

| Silver kapsamı | Ay | Bayt | Doğrulanan CSV SHA-256 |
| --- | ---: | ---: | --- |
| 2021-01–2026-06 | 66 | 2474 | `ae8dc5f8e69817436278fe19b377ee243d391ff63a8b40014cd1e917479f7c4c` |
| 2021-01–2025-12 | 60 | 2289 | `1a3f90e909a5574533081a4bba19303a7b3754f25706c0582a7d2ff1bd885f3a` |

Üç ayın ham haftalık faiz ortalaması/sayısı ve aylık ham TÜFE/KFE değerleri
ayrıca hesaplanıp teslim belgesiyle tam ondalık eşitlikle karşılaştırıldı.
Silver uyumu yalnızca bu üç satır için değil, tüm CSV'nin yeniden üretimiyle
doğrulandı; yaklaşık eşitlik kullanılıp bir hash kontrolü gevşetilmedi.

| Ay | Ham faiz ortalaması (%) | Gözlem | TÜFE | KFE |
| --- | ---: | ---: | ---: | ---: |
| 2021-01 | 18.388 | 5 | 16.12513498 | 16.49 |
| 2023-06 | 21.294 | 5 | 42.45971400 | 95.66 |
| 2025-12 | 37.290 | 4 | 110.38696292 | 204.36 |

Ham faizdeki `03-07-2026` gözlemi 2026-06 ile biten kapsamdan dışlandı.
TÜFE 2025=100, KFE 2023=100; weekly coverage `unverified/not_available`,
`expected_count=null` kalır. Resmî yayın takvimi doğrulanmış sayılmaz.

Yerel kanıt: `out/evds-acceptance-20261018/audit-report.json`, SHA-256
`01a8160bc5e519fea88c476e0e35f78eb0192cbed73793bd891d61894981c1f4`.
Mevcut doğrulayıcıları çağıran yerel `audit_evds.py` ile socket erişimi kapalı
koşuda **0 ağ girişimi** görüldü. Gerçek paket, teslim belgesi ve yerel audit
dosyaları Git'e eklenmedi. Kod testleri gereksiz tekrar edilmedi; bu kanıt gerçek
dosya doğrulamasıdır. Sonuç [#39'a kaydedildi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251815563).

**Sonraki durum:** Osman [aynı EVDS paketi için alıcı teyidini](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6252994701)
verdi; #39 tamamlandı. BDDK teslimi, birleşik teknik koşu ve #42 kontrolü
aşağıda tamamlandı. Sonraki kullanıcı görsel teyidiyle #40 tamamlandı;
#46'nın kısa sunum ve sürüm teslimi ayrı açıktır.

## Gerçek birleşik Housing: Mustafa'nın bağımsız koşusu — 18 Ekim 2026

[Osman'ın teslimi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6252930443):
`Housing_tam_teslim_20261018.zip`, **1.587.106 bayt**, SHA-256
`956e47c3a7d922b4da7b755635379ccc357423aeceed2bcdef817a1098ca312f` eşleşti.
Paket `out/housing-acceptance-20261018/` altında ayrı açıldı. Özgün ZIP,
teslim `inputs/outputs`, repo data ve önceki EVDS kanıt kopyası korunur.

`README.md`, `acceptance/KABUL_KAYDI.md` ve üç audit JSON'u yazar kanıtı olarak
okundu. Belgedeki eski `housing-demo/...` bağlantıları teslimde `outputs/...`
dosyalarına karşılık gelir; orijinal belge düzeltilmedi. Osman'ın Python 3.12.4
ile iki koşu ve görsel inceleme beyanı, Mustafa'nın kendi koşusu olarak sunulmaz.

### Bu ortamda bağımsız tamamlanan kontroller

- Runtime `7ee7225`, Python **3.12.15**; pandas 3.0.5, pyarrow 25.0.1,
  Plotly 7.0.0, Pydantic 2.13.5. Uygulama/test kodu değişmedi.
- `DELIVERY_INVENTORY.json` **156/156** kaydı ve 145 girdilik ek envanter
  boyut/SHA-256 olarak doğrulandı. EVDS'nin **12/12 dosyası** önceki kabul
  kopyasıyla bayt eşit; iki fiziksel manifest mevcut tüketicide geçti.
- BDDK: **66 raw + 66 makbuz**, 2021-01–2026-06 için 66 tekil/ardışık ay;
  mevcut makbuz doğrulayıcı/üretici hash, boyut, başlık dönemi, zaman, birim ve
  kaynak kontrollerinden geçti. Yeniden oluşturulan tablo saklanan Silver ile
  `assert_frame_equal(check_exact=True)` eşleşti. Parquet **10.792 bayt**,
  SHA-256 `c3cf8929d77de67ae91bbf64f7096f3a3bd926e4d3e81186bf7196037e3ee966`.
- Üç ham BDDK örneği, doğrulanmış başlık/birim/kaynak referansıyla Silver'a eşit:
  **2021-01: 276785; 2023-06: 438466; 2025-12: 678970 Milyon TL**.
- Mevcut `scripts.run_housing_demo.main(args)` girişi socket erişimi kapalı
  **bir kez** çağrıldı; exit **0**. Dönem 2021-01–2025-12, aynı göreli BDDK/EVDS
  yolları, fiziksel manifest ve `--html`; yeni çıktı dizini `reproduced/`.
- Hesap **60 benzersiz ay / 22 eşleşme** verdi. 22 hedef olarak dayatılmadı;
  mevcut Gold seçiminin dönemleri evidence/summary ile karşılaştırıldı. İlk
  ayın nominal/reel/faiz değişimleri ve koşulu gerçekten null kontrol edildi.
- Mevcut grafik doğrulayıcıyla 6 trace'in tüm 60 aylık Gold değerleri ve
  eşleşme marker'ları kontrol edildi. Evidence'daki **60 BDDK / 3 EVDS** kaynak
  referansı girdilerle eşleşti. Weekly coverage `unverified/not_available` kaldı.
- Aynı girdiler ve dönemle `run_verified_housing_question`, açık sabit
  `housing_rate_down_real_credit_not_up` planıyla çalıştı: **1 stub çağrısı**,
  evidence/grafik CLI ile **tam eşit**, anlatım null, canlı çağrı **0**.
  #42'nin gerçek dosya soru teknik kabulü tamamlandı; model anlama metriği değildir.

Hesaplanan eşleşen dönemler: 2021-02, 2021-03, 2021-05, 2021-08, 2021-10,
2021-11, 2022-02, 2022-06, 2022-12, 2023-02, 2023-12, 2024-01, 2024-02,
2024-05, 2024-06, 2024-07, 2024-08, 2024-09, 2025-01, 2025-02, 2025-07, 2025-09.

### Ocak faizi: metin gösterimi ve hesap ayrı

Ham haftalık değerlerin Decimal ortalaması **18.38800000**; değiştirilmemiş CSV
metni **18.387999999999998**. Fark **−2E−15 yüzde puan**; tam Decimal eşitlik
iddiası yok. Bu ortamın `pandas.read_csv` değeri **18.388**. Önceki EVDS audit'i
CSV'nin aynı pipeline ile bayt düzeyinde tekrar üretildiğini doğrulamıştı.
Kaynak/CSV/hash değiştirilmedi, tolerans eklenmedi. Python patch sürümü farklı
olmasına karşın dört çıktı da teslimle bayt eşit; yol/serileştirme/hesap
uyuşmazlığı görülmedi. Bu küçük metin gösterimi farkı hesap hatası sayılmadı.

### Yeniden üretilen dört çıktı

Dizin: `out/housing-acceptance-20261018/reproduced/`. Dördü de korunmuş
`outputs/` teslimiyle bayt eşit; çıktı dizininin adı veya mutlak yolu sonuçları
değiştirmedi.

| Dosya | Bayt | SHA-256 |
| --- | ---: | --- |
| evidence.json | 32089 | `e43bd1f5a78cb6cec2527190e836ba9693af6535e4ab0f6c6f068a17819de3fb` |
| chart.json | 35305 | `60c551bf3d9f8da4a09a36780f32651d3050b167edaaa4919e812407ffde9db3` |
| run_summary.json | 30283 | `9f096787654951b7481c7dc1166fa270f30fe9db690f3d9b4a19581b3f75274d` |
| report.html | 4405838 | `81a7eef0e09880e109b41bd9c75fc26ce0f7f45525446af28f18f5c52ca6c09f` |

Yerel bağımsız rapor `out/housing-acceptance-20261018/independent-audit.json`,
SHA-256 `6267c389bb90634fb57bea4e8028cdb718435ae32d93922d6c89cd837fb7ac5b`.
Kullanılan yerel orchestrator `verify_local.py` mevcut fonksiyonları çağırır;
çalıştırılan komut:

```powershell
.\out\clean312\Scripts\python.exe out/housing-acceptance-20261018/verify_local.py
```

Gerçek paket, yazar belgeleri, yerel script/audit ve çıktılar Git dışında.
Özgün 156 teslim dosyası/envanter, önceki EVDS kopyası ve Downloads ZIP hash'i
koşu sonunda değişmemiştir. Ağ girişimi **0**, canlı model çağrısı **0**.
Yazarın iki tekrar koşusu yeniden yapılmış sayılmaz. Gereksiz tam pytest tekrarı
yapılmadı; kod değişmedi, belge PR'ının zorunlu CI'si ayrıca izlenir.

### Mustafa'nın görsel kabulü — tamamlandı, 18 Ekim 2026

Mustafa gerçek `out/housing-acceptance-20261018/reproduced/report.html` dosyasını
kendi tarayıcısında kontrol edip bu oturumda aşağıdaki sonuçları açıkça teyit etti.
Bu kayıt kullanıcının incelemesidir; Codex'in tarayıcı testi olarak sunulmaz.
Teyit kaydedilirken HTML hash'i yukarıdaki değerle yeniden eşleşti.

- [x] 60 ay ve 22 eşleşme görünüyor; teknik kapsam 2021-01–2025-12.
- [x] Hover, zoom, pan ve sıfırlama çalışıyor.
- [x] Seçilen ayda tablo/grafik uyumlu; 2021-01 eşleşmelerde yok.
- [x] Kaynak, birim ve baz yılı okunuyor.
- [x] Sınırlamalar okunuyor; haftalık kapsamın `unverified` durumu değişmedi.

Osman'ın önceki görsel beyanından ayrı olarak Mustafa'nın alıcı kabulü alındı;
#40 tamamlandı. Kullanıcı teyidi seçtiği ayı kapsar; tüm aylar için yeni bir
tarayıcı karşılaştırması yapıldığı iddia edilmez.

### v0.1.0-rc.1 prerelease ve 60–90 saniyelik demo anlatımı

Mustafa'nın açık onayıyla **`v0.1.0-rc.1`** annotated tag'i
`abea43137eed8a6ceb20cd9bbd22cd0afeb58f1b` main commit'ine bağlandı.
Bu commit'in [main CI'si](https://github.com/ekincimustafa/quad-qore-agentic-analytics/actions/runs/39153169544)
**796 passed in 20.89s**. [GitHub prerelease](https://github.com/ekincimustafa/quad-qore-agentic-analytics/releases/tag/v0.1.0-rc.1)
18 Ekim 2026 18:36:49 UTC yayımlandı: `prerelease=true`, `draft=false`,
kimlik `416628413`. Release'e yüklenen ek **0**; gerçek veri, HTML ve yerel
audit dosyaları eklenmedi. Aşağıdaki notlar yayımlandı; ekran kaydı henüz yok.

**Yayımlanan sürüm notu — İlk gerçek verili offline Housing demosu**

- Teslim edilen gerçek BDDK+EVDS dosyaları hash ve fiziksel kaynak zinciriyle
  doğrulandı. 66 aylık girdiden 2021-01–2025-12 için 60 ay ve 22 eşleşme üretildi.
- Sabit planlı dosya soru wrapper'ı doğrudan CLI ile aynı evidence/grafiği verdi.
  İlk ay değişimleri null; hesaplar mevcut Python servislerinde yapılıyor.
- Kaynak, birim ve sınırlamaları içeren bağımsız HTML, Mustafa'nın hover, zoom,
  pan, sıfırlama ve seçili ay tablo/grafik kontrolünden geçti.
- Canlı EVDS/LLM çağrısı yok; gerçek paketler Git'e eklenmedi. Haftalık yayın
  kapsamı resmî takvim olmadan `unverified`; sonuç nedensellik veya yeni kredi
  akımı iddiası değildir. Sabit plan kontrolü canlı model başarısı ölçmez.
- Katkılar: Afra EVDS/manifest ve ilk araç sözleşmesi; Osman BDDK ve offline CLI;
  Mustafa analiz/soru harness'i, alıcı tekrar koşusu ve kabul/sürüm hazırlığı.

**Demo anlatımı (yaklaşık 75–90 saniye)**

| Süre | Ekran ve anlatım |
| --- | --- |
| 0–20 sn | Üst sayaçları göster: “Bu rapor, gerçek BDDK konut kredisi stoku ve TCMB EVDS verileriyle üretildi. 66 aylık doğrulanmış girdiden Ocak 2021–Aralık 2025 arasındaki 60 ayı inceliyoruz. Faiz düşerken enflasyondan arındırılmış kredi stokunun artmadığı 22 ay var.” |
| 20–40 sn | 2021-02 eşleşmesine hover ve zoom yap, görünümü sıfırla: “İşaretli ayları mevcut Python kuralı belirliyor. Reel stok TÜFE 2025=100 ile hesaplanıyor; KFE bağlam için gösteriliyor. Grafikte aynı ayın faiz ve kredi değerlerini birlikte okuyabiliyoruz.” |
| 40–60 sn | Tabloyu ve Ocak 2021'i göster: “Tablodaki değerler grafikle aynı kanıttan geliyor. Ocak 2021 için pencere içinde önceki ay olmadığından değişimler null ve bu ay eşleşmelere dahil değil. Dosya soru wrapper'ı da aynı girdiler ve açık sabit planla doğrudan CLI sonucunu aynen verdi.” |
| 60–90 sn | Kaynak ve sınırlamaları göster: “Raw, makbuz ve Silver zincirleri hash'lerle kontrol edildi. Bu gösterimde canlı model veya EVDS çağrısı yok. Haftalık yayın kapsamı resmî takvim olmadan doğrulanmış sayılmıyor. Ölçtüğümüz kredi stoku; yeni kredi akımı veya faiz değişiminin neden olduğu bir sonuç iddia etmiyoruz.” |

PR #67 önceden onayla merge edildi. Bu oturumdaki ayrı onay yalnızca
`v0.1.0-rc.1` prerelease yayınını kapsar; kararlı release veya başka tag için
yeni onay gerekir. Yukarıdaki anlatım sunulmuş/kaydedilmiş demo değildir.

## Açık kabul kapıları

- [x] Windows'ta yeni Python 3.12 ortamında README sentetik hızlı başlangıcını doğrula (13 Ekim: clone, kurulum, rapor ve testler).
- [x] BDDK/EVDS gerçek girdilerinin yollarını, boyutlarını ve SHA-256 özetlerini kaydet.
- [x] EVDS seri kodu, frekans, baz yıl ve haftalık kapsam notlarını gerçek paketle doğrula (iki alıcı teyidi tamamlandı).
- [x] 66 aylık gerçek Silver girdisinden tam 60 aylık analiz kapsamını doğrula.
- [x] 2021-01, 2023-06 ve 2025-12 aylarını ham kaynak/Silver çıktısıyla karşılaştır.
- [x] BDDK satır referansları ve EVDS manifestini Gold/evidence akışında koru (#40).
- [x] Gerçek dosya tabanlı demo sonucunu HTML raporuna bağla; run summary ve kaynak zincirini göster (#46 teknik kabul).
- [x] Araç sözleşmesini güncel anlatım ve enabled/planned/disabled kapsamla uyumlu teslim et (#6 tamamlandı; ilk katkı PR #38, güncel kapsam PR #60).
- [x] Mustafa yeniden üretilen gerçek HTML'nin yukarıdaki görsel listesini teyit etti.
- [x] Sürüm notu, önerilen tag ve 60–90 saniyelik demo anlatımını incelemeye hazırla.
- [x] `v0.1.0-rc.1` tag/prerelease için Mustafa'nın ayrı yayın onayını al.
- [x] Başarılı main commit'ini tag'le ve notlarla GitHub prerelease yayımla; veri/audit eki yükleme.
- [ ] İsteğe bağlı portföy: 60–90 saniyelik ekran kaydı; ürün kabul şartı değildir, henüz kaydedilmedi.

Yapılandırılabilir LLM istemcisi #41 ile tamamlandı; önceki sınırlı canlı kontrol
[LLM kabul kaydındadır](llm-client.md). Legacy `scripts.smoke_test_mia` yalnızca
temel bağlantıyı sınar. Güncel sentetik kontrol canlı LLM gerektirmedi.
Dosya destekli sorunun gerçek veri teknik kabulü #42'de tamamlandı. İki analizli
yönlendirme #59, PR #62/#66 ile tamamlandı; gerçek veri kabulünü kapatmaz.

Gerçek veri teknik kabul kaydı:

| Alan | Durum |
| --- | --- |
| Kullanılan kod commit'i | EVDS ve birleşik alıcı kontrolü `7ee7225` |
| BDDK Silver yolu / boyutu / SHA-256 | `inputs/data/silver/bddk/housing_loans.parquet`, 10792 bayt; hash yukarıda |
| EVDS Silver yolu / boyutu / SHA-256 | 66/60 aylık iki dosya yukarıda doğrulandı |
| EVDS manifesti / Bronze receipt referansları | İki manifest ve üç fiziksel raw/makbuz zinciri doğrulandı |
| 66→60 ay ve üç örnek ay karşılaştırması | EVDS, BDDK ve birleşik teknik kontroller geçti |
| Evidence/chart/run summary/HTML dosyaları | `reproduced/` altında dört çıktı; yukarıdaki hash'lerle teslimle bayt eşit |

## Katkı kanıtları ve aktif iş paylaşımı

Bu tablo seçilmiş PR örneklerini ve mevcut görev sahiplerini gösterir.
Kişisel katkılar ilgili PR'ların kod farklarıyla değerlendirilir.

| PR sahibi | Birleşmiş katkı örnekleri | Açık teslimat |
| --- | --- | --- |
| Mustafa / ekincimustafa | [#27 Gold](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/27), [#30 API](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/30), [#47 anlatım doğrulaması](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/47), [#48 HTML raporu](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/48), [#62](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/62)/[#66 soru yönlendirmesi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/66), [#64 dosya wrapper'ı](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/64) | #46 ekran kaydı ve kısa demo teslimi; gerçek HTML kabulü ve rc.1 yayını tamam |
| Osman / OsmanerdemDutar | [#36 BDDK Silver](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/36), [#43 kaynak zinciri ve offline demo CLI](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/43) | #40 teslim, bağımsız teknik tekrar koşu ve Mustafa'nın görsel kabulü tamam |
| Afra / afratopcu | [#23 EVDS Silver](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/23), [#35 EVDS ingestion](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/35), [#38 ilk araç sözleşmesi katkısı](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/38), [#58 manifest üretimi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/58) | #39 teslim ve iki alıcı kabulü tamam; bu kapsamda açık veri teslimi yok |

Açık görevler tamamlanmış katkı olarak raporlanmaz. Sürüm adayı yayını ekran
kaydını tamamlamaz; #46 isteğe bağlı portföy işi olarak açık kalır. 19 Ekim'de
yetkilendirilen yerel soru ürününün backend/ekran/kabul işleri #69/#70/#71'dir.
