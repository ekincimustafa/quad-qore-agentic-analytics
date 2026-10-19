# Codex devir notu — 19 Ekim 2026

Bu not, Mustafa'nın yerel VS Code/Codex oturumuna proje bağlamını taşır.
Kurulum adımları ve hesap arayüzü zamanla değişebilir; bu dosya ürün kurulumu
için bir sürüm garantisi değildir. Kod temeli `7ee7225` (PR #66 sonrası main).
Aşağıdaki eski kayıtlar tarihli kaynak kanıtıdır; en üstteki oturum güncellemesi
güncel durumu belirtir.
Yeni bir oturum güncel HEAD'i, çalışma ağacını ve ilgili issue'yu yeniden kontrol
etmelidir. Mustafa Hacettepe Bilgisayar Mühendisliği üçüncü sınıf öğrencisidir;
ekip Mustafa, Osman ve Afra'dan oluşur. İlk hedef çalıştırılabilir bir CV demosudur.

## Yerel soru ekranı: Aşama 2 — 19 Ekim 2026

- Başlangıç ağacı temizdi. Mustafa'nın açık onayıyla PR #72'nin tam başlığı
  `545a285`, diff, başarılı Tests #122 (**840 passed**) ve boş review/thread
  listesi yeniden kontrol edildi; **`23a820ba525b4d829a65698d2d13b80b9bc64cae`**
  olarak main'e merge edildi. #69 `closed/completed` olarak doğrulandı.
- Aktif dal **`feat/local-question-screen`**, doğrudan bu güncel main'den açıldı.
  PR #68 kendi dalında korunur ve merge edilmedi. `v0.1.0-rc.1` hâlâ `abea431`;
  tag/release değiştirilmedi. Bu ekranın PR'si onay olmadan merge edilmez.
- #70: FastAPI `GET /`, yerel CSS/JS ve kurulu Plotly paketinden sunulan JS.
  Tarayıcı yalnız `/analysis/economic/question/files` adresine `question` yollar.
  Örnekler yalnız alanı doldurur; gönderme kullanıcı eylemidir. Konutun mevcut
  grafiği/eşleşme tablosu, TÜFE tablosu, evidence'dan kısa Türkçe özet, kaynak,
  kapsam, birim ve sınırlamalar gösterilir. Sayısal hesap veya ek model yok.
- Bekleme/tek istek, başarı, netleştirme, unsupported, veri/sağlayıcı/ağ hataları
  ayrı gösterilir; eski sonuç yeni istekte temizlenir. Kullanıcı/kaynak metni
  `textContent` ile yazılır; ham sağlayıcı gövdesi gösterilmez. CSP aynı origin
  script/connect kuralını uygular; GET/asset yükleme LLM ayarını okumaz.
- `python -m scripts.preview_question_ui` iki örneğe açık sabit plan verir;
  diğer sorulara netleştirme döner. Offline etiketi görünür. Mevcut
  `out/clean312` Python 3.12.15 kullanılır; kurulum/dependency tekrarı yok.
  Gerçek paket kökü ve 8000 adresi için [README](../README.md#local-question-screen--offline-preview).
- CUA'da tarayıcı yüzeyi yok (`browsers: []`, iab kullanılamıyor). İstenen
  yazılım UI testi/görüntüsü kurulu Chrome'un ayrı geçici profilli başsız
  oturumunda, yalnız 127.0.0.1 test sunucusuna karşı yapıldı. Sandbox ilk Chrome
  GPU sürecini engelledi; gerekli izinle aynı test geçti. Kontroller gerçek DOM,
  gerçek Plotly, HTTP/dosya yükleme ve açık stub planları kullanır; canlı **0**.
- Gerçek paketli offline ekran görüntüleri `out/question-ui-housing.png` ve
  `out/question-ui-cpi.png`; incelendi. Konut **60 ay/22**, TÜFE **2023 için 12 ay**.
  Görülen lejant/başlık çakışması yalnız sunum layout'unda düzeltildi; trace/veri
  değişmedi. **145 kaynak dosyasının hash'i aynı**; görseller/veri/audit Git dışında.
- #71 **açık**: gerçek model kabulü yapılmadı; vaka/bütçe onayı ve Mustafa'nın son
  ekran/etkileşim kontrolü eksik. #46 videosu isteğe bağlıdır, çekilmedi. Bu
  ekran PR'si main'e alınmış veya canlı kabul tamamlanmış sayılmaz.
- Kontroller: odaklı UI/API paketi **46 passed in 10.21s**; tam yerel offline
  paket **840 passed, 2 skipped in 82.78s** (mevcut Windows symlink izinleri).
  Housing stub **9/9**, canlı **0**. Tarayıcı testi açılış/örnek, bekleme/tek istek,
  grafik/tablolar, netleştirme/unsupported, veri/sağlayıcı/ağ hatası ve XSS metin
  sınırlarını gerçek DOM'da kontrol eder. Chrome geçici profili LLM/EVDS/GitHub
  anahtar ortam değişkenlerini devralmaz. 56 yerel bağlantı, 7 PowerShell bloğu
  ve `git diff --check` geçti; son commit'in CI'si ayrıca izlenir.

## Yeni yerel soru ürünü: Aşama 1 kaydı — 19 Ekim 2026

Bu bölüm PR #72 öncesinin tarihli kaynak/test kanıtıdır; güncel merge/dal ve
sonraki adım üstteki Aşama 2 bölümündedir.

- Mustafa önceki “yeni özellik açma” sınırını bu ürün için açıkça kaldırdı.
  Hedef yalnız Türkçe soru girilen yerel web ekranı; mevcut Python hesapları,
  fiziksel veri kontrolleri ve izinli iki analiz korunur. Canlı/merge/release
  öncesinde ayrı onay gerekir. #46 videosu **isteğe bağlı portföy işi**, çekilmedi;
  ürün geliştirmesini veya kabulünü bekleten zorunlu kapı değildir.
- Başlangıç ağacı temizdi. PR #68 (`docs/rc1-publication`) açık ve önceki CI'si
  başarılıydı; yayın kayıtları korunup video isteğe bağlı olarak güncellendi.
  PR #68'in son başlığı `b6fc985` için Tests #121 başarılı; bu belge dalı main
  değildir. **`v0.1.0-rc.1` değiştirilmedi**, hedefi `abea431`;
  prerelease yayımlıdır. Yeni kod dalı **`feat/verified-economic-question-api`**,
  doğrudan güncel main `abea431` tabanından açıldı; #68'e bağımlı değildir.
- İşler: [#69 backend](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/69),
  [#70 ekran](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/70),
  [#71 uçtan uca kabul](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/71).
  Tamamlanmış #42/#59 yeniden açılmadı; yeni iş onların çekirdeklerini kullanır.
- #69: `POST /analysis/economic/question/files` yalnız `question` alır.
  `ANALYTICS_DATA_ROOT` sunucu yapılandırmasıdır; tam BDDK/EVDS paketi mevcut
  fiziksel yükleyiciyle modelden önce doğrulanır. Konut/TÜFE aynı ekonomik soru
  çekirdeğine bağlandı; hesap tekrarı veya ek anlatım modeli yok. Netleştirme,
  desteklenmeyen soru ve dönem doğrulaması korunur. Eski endpoint'ler değişmez.
  Eksik/bozuk pakette güvenli 503; model/analiz çağrısı 0. Kullanım README ve
  mevcut [soru belgesindedir](economic-question.md).
- Mevcut `.venv` kayıp kurulum yoluna bağlı; korunur. Yeni kurulum yapılmadı,
  Python **3.12.15 `out/clean312`** kullanıldı. Temiz başlangıç main testleri
  **794 passed, 2 skipped in 97.71s** (Windows symlink izinleri). İlk bağlantı
  regresyonu **97 passed, 1 skipped**, yeni HTTP/dosya odaklı paket
  **103 passed, 1 skipped in 14.84s**. Son tam offline paket **838 passed,
  2 skipped in 81.37s**; atlamalar aynı Windows symlink izinleri. Housing
  stub **9/9**, Economic HTTP stub **12/12**, canlı çağrı **0**. 60 yerel belge
  bağlantısı, 9 PowerShell bloğu ve `git diff --check` geçti. Son commit'in
  zorunlu PR CI'si ayrıca izlenir; bu dalın değişiklikleri henüz main'de değildir.
- Gerçek teslim üzerinde TestClient + **2 açık sabit plan**: konut HTTP evidence/
  grafiği önceki gerçek CLI çıktısıyla tam eşit (**60 ay/22**), TÜFE 60 ayın
  hesapları doğrudan `build_inflation_evidence` ile tam eşit. Bu gerçek dosya
  kabulüdür; stub model anlama testi değildir. **145 girdi dosyasının hash'i
  değişmedi**, canlı LLM/EVDS **0**. Yerel kontrol script'i ve veriler Git dışında.
- Sonraki adım #69 PR'sinin review/merge onayı; backend merge edilmeden #70'i
  güncel main'de varmış gibi başlatma. Sonra #71'de küçük vaka/bütçe listesini
  canlı Gemini çağrısından önce Mustafa'ya göster. Bu oturumda ekran, canlı
  kabul veya yeni release tamamlandı sayılmaz.

## PR #67 ilk gerçek demo kabul kaydı — 18 Ekim 2026

Bu ve aşağıdaki bölümler tarihli kanıttır; ürün kapsamı/onay/dal ve sonraki iş
için üstteki 19 Ekim güncellemesi geçerlidir.

- Aktif dal `docs/real-demo-readiness`; başlangıç çalışma ağacı temizdi,
  mevcut kullanıcı değişikliği yoktu. Runtime `7ee7225`, Python 3.12.15
  `out/clean312`; uygulama kodu değiştirilmedi. Yeni özellik veya takip belgesi
  açılmaz. #39/#40/#42/#46 açıklamaları ve mevcut PR #67 güncellenir;
  yeni yorum/paket talebi gönderilmez. Bu kayıt PR #67'nin son kabul teslimidir;
  Mustafa uygun güncel diff/CI/review sonrası merge'e bu oturumda onay verdi.
  Gerçek merge sonucu [PR #67 kaydından](https://github.com/ekincimustafa/quad-qore-agentic-analytics/pull/67)
  kontrol edilir; tag/release/yayınlama onayı verilmedi.
- Afra'nın [OneDrive teslimi](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251399411)
  Mustafa tarafından İndirilenler'e alınmış. `OneDrive_1_18.10.2026.zip` bir
  taşıma arşivi; içindeki **20.344 baytlık** `EVDS_gercek_veri_teslim.zip` hash'i
  `1c9255194c3222dccc33e056ba195c46a8d0912cdb9ccccd178e8e4b2731ebc1` ile eşleşti.
  Paket `out/evds-acceptance-20261018/inputs/` altında dizin yapısı korunarak
  açıldı. Repo `data/` dizini ve 12 teslim dosyasının ilk/son hash'leri değişmedi.
- Teslim belgesi okundu; **12/12 boyut ve SHA-256** eşleşti. Mevcut tüketicide
  iki fiziksel manifest/raw/makbuz/CSV zinciri geçti. Mevcut üreticinin manifest
  yapıları birebir aynı; aynı Bronze'dan ayrı `rebuilt/` alanında üretilen
  **66 ve 60 aylık CSV'ler bayt düzeyinde**, coverage raporları JSON olarak aynı.
  Üç örnek ayın ham ortalama/sayı/TÜFE/KFE değerleri belgeyle ayrıca eşleşti.
  03-07-2026 faiz gözlemi kapsam dışında; weekly coverage hâlâ `unverified`.
- Sonuç [#39 yorumuna](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251815563)
  kullanıcının açık yetkisiyle kaydedildi. Yeni paket talebi veya #40'a mesaj
  gönderilmedi. Ayrıntı ve CSV hash'leri [kabul kaydında](release-acceptance.md).
  Yerel `audit-report.json` ve `audit_evds.py` aynı ignored kabul dizinindedir;
  gerçek paket, teslim belgesi, ham gözlemler ve yerel audit çıktıları Git'e eklenmez.
- Ağ erişimi kapatılmış yerel audit'te **0 ağ girişimi**; canlı EVDS/LLM veya
  yeniden veri indirme yok. Önceki tam kod testleri gereksiz tekrar edilmedi;
  bu oturumun kanıtı gerçek EVDS paket doğrulamasıdır, sentetik test sayısı değildir.
- **İki veri erişim engeli de kalktı.** Osman [EVDS alıcı teyidini](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6252994701)
  ve [birleşik Housing teslimini](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6252930443)
  paylaştı. #39 teslim/alıcı kapsamı tamamlandı ve kapandı.
- `Housing_tam_teslim_20261018.zip`: 1.587.106 bayt; SHA-256
  `956e47c3a7d922b4da7b755635379ccc357423aeceed2bcdef817a1098ca312f` eşleşti.
  Ayrı `out/housing-acceptance-20261018/` klasöründe açıldı. **156/156 envanter**,
  145 girdi, **66 BDDK raw + 66 makbuz + 66 aylık Silver** doğrulandı; mevcut
  üreticiyle yeniden kurulan tablo tam eşit. Üç BDDK örneği 276785 / 438466 /
  678970 Milyon TL. EVDS'nin 12 dosyası eski kanıt kopyasıyla bayt eşit;
  iki fiziksel manifest geçti.
- Teslim README/kabul/audit dosyaları **yazar kanıtı** olarak okundu. Eski
  `housing-demo/...` bağlantıları korunmuş teslim `outputs/...` dosyalarıdır.
  Osman'ın iki koşusu/görsel incelemesi Mustafa'nın yaptığı kontrol sayılmaz.
- Mustafa CLI girişini **bir kez** socket kapalı çalıştırdı: exit 0,
  **60 ay / 22 hesaplanan eşleşme**, ilk ay null değişimleri/koşulu, 6 trace ve
  bütün Gold/grafik değerleri, 60 BDDK / 3 EVDS kaynak referansı doğrulandı.
  Aynı girdilerle açık sabit planlı wrapper **1 stub çağrısı** yaptı;
  evidence/grafik CLI ile tam eşit. #42 teknik dosya kabulü tamamlandı ve kapandı.
- Yeni dört dosya `out/housing-acceptance-20261018/reproduced/` altında;
  hepsi teslim `outputs/` ile **bayt eşit**. Açılacak gerçek HTML:
  `out/housing-acceptance-20261018/reproduced/report.html`.
  HTML SHA-256 `81a7eef0e09880e109b41bd9c75fc26ce0f7f45525446af28f18f5c52ca6c09f`.
- Ocak faizi Decimal `18.38800000`, CSV metni `18.387999999999998`; fark
  **−2E−15 yüzde puan**. Pandas okuması `18.388`; tam Decimal eşitliği yok.
  Kaynak/hash değiştirilmedi, toleransla saklanmadı; hesap/çıktı uyuşmazlığı yok.
- Yerel `independent-audit.json` hash'i
  `6267c389bb90634fb57bea4e8028cdb718435ae32d93922d6c89cd837fb7ac5b`.
  Özgün ZIP, inputs/outputs ve önceki EVDS kopyası değişmedi; ağ girişimi ve
  canlı model çağrısı **0**. Yerel veri/audit dosyaları ignored; Git'e eklenmez.
  Kod değişmediği için gereksiz tam test tekrarı yapılmadı; belge CI'si izlenir.
- **Görsel kabul tamamlandı:** Mustafa gerçek `reproduced/report.html` dosyasını
  tarayıcıda inceledi; 60 ay/22, hover–zoom–pan–sıfırlama, seçtiği ayın tablo/grafik
  uyumu, Ocak 2021'in eşleşmemesi, kaynak/birim/baz yılı ve sınırlamaların
  okunmasını açıkça teyit etti. Bu kullanıcı beyanıdır; Codex tarayıcı testi
  değildir. HTML hash'i yeniden aynı bulundu. #40 tamamlandı; #46 görsel maddesi
  işaretlendi, sürüm teslimi açık bırakıldı.
- Sürüm notu, önerilen **`v0.1.0-rc.1`** tag'i ve 60–90 saniyelik demo anlatımı
  [mevcut kabul kaydında](release-acceptance.md) incelemeye hazır. Sunum/kayıt
  yapılmış sayılmaz. Sonraki adım Mustafa'nın bu önerileri incelemesi ve ayrı
  tag/release/yayınlama kararıdır; bu sınırda durulur, yeni kapsam açılmaz.
- Bu son belge değişikliğinde uygulama/test kodu aynı; gereksiz yerel tam test
  tekrarı yapılmadı. **62 yerel bağlantı, 12 PowerShell bloğu** ve `git diff --check`
  geçti; merge yalnızca son kaynak başlığının zorunlu CI'si başarılı ve
  review durumu uygunsa yapılır. Önceki Windows **794 passed, 2 skipped** kaydı
  tarihli runtime kanıtıdır, bu belge değişikliğinin yeniden koşusu değildir.

## Önceki gerçek demo hazırlığı — 18 Ekim 2026

Bu bölüm EVDS tesliminden önceki tarihli kurulum kanıtıdır. O tarihteki erişim
engeli artık kapalıdır; güncel eksik ve iş sırası yalnızca üst bölümde yer alır.

- Aktif dal `docs/real-demo-readiness`, güncel main `7ee7225` tabanlı. Kullanıcı
  yeni özellik istemiyor; mevcut demoyu gerçek veriyle doğrulama öncelikli.
  PR #63–#66 başarılı CI ile merge edildi; #59 kapandı. Önceki onay yeni
  belge PR'ının merge'ini veya release/yayınlamayı kapsamaz.
- [Teslim rehberi](real-demo-delivery.md) hazır paketi yeniden istemeden kalan
  dosya/dizin/komut/hash kanıtlarını ve Afra/Osman için ayrı mesaj taslaklarını
  içerir. Mustafa paylaşım taleplerini [#39 yorumunda](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6250879475)
  ve [#40 yorumunda](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6250883464)
  yayımladı. ZIP eki veya ekip erişimli OneDrive/Google Drive bağlantısı kabul
  ediliyor. Kullanıcı talimatı: **tekrar mesaj gönderme**; mevcut taleplerin
  iki teslim de artık alındı; güncel durum üst bölümde kayıtlıdır.
- Yeni `out/clean312` venv'i (Python 3.12.15, sistem paketlerine kapalı) ve
  `git archive main` ile `out/clean-demo` kaynak kopyası kuruldu. Eski bozuk
  `.venv` korunur. `requirements.txt` kurulumu ve `pip check` başarılı;
  yeni ortamda tam paket **794 passed, 2 skipped in 103.97s**. Atlamalar Windows
  symlink izinleridir. Yeni clone/Python kurulumu yapılmış sayılmaz.
- Sentetik HTML **60 ay, 55 eşleşme, ilk 2021-02, 6 trace**; hash önceki kayıtla
  aynı. Gerçek yerel Uvicorn TCP'de Health/Housing/TÜFE ve `/docs` **200**;
  anlatım null. Sunucu durduruldu. CLI help/PowerShell komut kontrolleri yapıldı;
  ayrıntı [kabul kaydında](release-acceptance.md). Önceki 12/12 ve 9/9 stub CLI
  sonuçları gereksiz tekrar çalıştırılmadı; yeni tam paket evaluator testlerini içerir.
- Tarayıcı yüzeyi bulunmadığından güncel HTML'nin görsel/hover/zoom kontrolü
  yapılmadı. Kullanıcı HTML'yi açıp bunu kontrol edebilir. Canlı LLM/EVDS çağrısı, veri
  indirme, veri silme, force push, merge, release veya yayınlama yapılmadı.

## Önceki teslim ve sonraki adım — 18 Ekim 2026

Aşağıdaki geliştirme kronolojisi önceki kaynak/test kanıtlarını korur. Teslim,
merge ve erişim durumları için üstteki güncel bölüm ve açık iş tablosu esas alınır.

- Aktif dal `feat/economic-question-api`; çalışma ağacı teslim commit'i sonrası
  temiz bırakılır. PR #63 çalışma düzeni (`a987a88`), #64 dosya wrapper'ı
  (`96031e2`) ve #65 tarihli kabul kaydı (`909f8c7`) başarılı güncel CI ile
  kullanıcı onayı kapsamında main'e merge edildi.
- PR #66 teslimi: ortak `POST /analysis/economic/question`, iki sentetik istek,
  12 vakalı offline HTTP evaluator ve davranış testleri tamamlandı. Sınırlı
  plan mevcut Housing/TÜFE servislerinden en fazla birini yürütür; mevcut
  endpoint'ler korunur. #59'un çekirdek ve API/eval kapsamı tamamlanmıştır.
- Birleşik runtime test kaynağı `624d176a37e8f7e1714cd395700270932fbe582e`
  (PR #62–#65 main + #66), Python 3.12.15 `out/python312`: tam offline paket
  **794 passed, 2 skipped in 92.08s**. İki atlama BDDK ve dosya soru testlerinin
  Windows symlink iznidir. Önceki birleşik odaklı paket **87 passed, 1 skipped**.
- Aynı kaynakta Economic offline stub **12/12**, Housing offline stub **9/9**;
  canlı çağrı **0**. İki HTTP örneği, 12 vaka şeması ve 51 yerel bağlantı
  doğrulandı; `git diff --check` temiz. Son belge commit'inin zorunlu PR CI'si
  ayrıca geçmelidir; merge son başlık SHA'sı kontrol edilerek yapılır.
- Kullanıcı #63–#66 merge sırasını onayladı. Canlı model/EVDS çağrısı, gerçek
  veri indirme, veri silme, force push, tag/release veya yayınlama yapılmadı.
- Güncel açık issue'lar kontrol edildi: Mustafa'nın kalan #42/#46 gerçek kabulü,
  Afra #39 ve Osman #40'ın erişilebilir gerçek CSV/coverage/manifest/raw/makbuz,
  BDDK Silver ve üç örnek ay karşılaştırma paketine bağlıdır. Yerel `data/`
  yalnızca `.gitkeep` içerir. Bağımsız yeni özellik uydurulmaz; bu paket
  erişilebilir olunca önce sabit planla offline doğrulama ve rapor incelemesi
  yapılır. Diğer ekip üyelerinin görevleri/dalları devralınmaz.

## #42 dosya wrapper'ı geliştirme kaydı — 18 Ekim 2026

Bu bölüm geliştirme sırasındaki kanıtı korur. Dal `45c8dcf` tabanından açıldı;
PR #62/#63 sonrası main (`a987a88`) ile merge öncesinde güncellendi.
Ortak API/eval PR #66'da açıktır. #63–#66 merge sırası kullanıcı tarafından onaylıdır.

- Aktif dal `feat/verified-housing-question`, doğrudan `45c8dcf` tabanından açıldı.
  #42'nin sunucu kontrollü yerel dosya wrapper'ı, fiziksel paket kontrolleri ve
  [kısa belgesi](housing-question-files.md) bu dalda tamamlandı.
- BDDK Silver mevcut üreticiyle doğrulanmış Bronze'dan yeniden türetilen tabloyla
  karşılaştırılır; EVDS mevcut manifest tüketicisiyle doğrulanır. Ortak kapsam
  türetildikten sonra mevcut soru/hesap servisi kullanılır. Yeni HTTP endpoint'i
  ve anlatım çağrısı eklenmedi; gerçek veri kabulü tamamlanmış sayılmaz.
- `1191654` runtime kaynağı, Python 3.12.15 (`out/python312`): odaklı paket **63 passed, 1 skipped**;
  tam paket **729 passed, 2 skipped**. Atlamalar Windows symlink izinlerindendir.
  Housing offline stub değerlendirmesi **9/9** geçti; canlı çağrı yapılmadı.
  46 yerel belge bağlantısı ve bir Python örneğinin sözdizimi kontrol edildi.
- Yerel `.venv` kayıp Python kurulumuna işaret eder. `out/python312` ve çıktılar
  Git tarafından yok sayılır. Yerel `data/` yalnızca `.gitkeep` dosyaları içerir.
- #46 sentetik kabul kaydı PR #65'te, #59 API/eval PR #66'da review bekler.
  #42/#46 gerçek kabulü #39/#40'ın erişilebilir gerçek dosya/kanıt paketini bekler.
  Bu belge düzeltmesi runtime kodunu değiştirmez; birleşik PR CI'si izlenir.
- Güncel main ile birleşik kaynakta odaklı dosya/iki analiz/Housing soru paketi
  **87 passed, 1 skipped** (Windows symlink); 49 yerel bağlantı ve diff kontrolü
  başarılıdır. Tam paket zorunlu PR CI'sinde ve son birleşik teslimde doğrulanır.

## Temel karar

Hesaplanabilen işler Python ile yapılır. LLM soru → sınırlı plan dönüşümü ve
mevcut strict JSON anlatım rolündedir. Hesaplar, veri doğrulaması, izinli analiz
seçimi ve çıktı sözleşmeleri kodun kontrolünde kalır. Serbest ekonomik yorum,
genel tool registry, web/anomali/nedensellik araçları henüz uygulanmış değildir.

## Çalışan parçalar

| Parça | Kod / belge | Durum |
| --- | --- | --- |
| BDDK ve EVDS veri katmanları | `app/lakehouse/`, ingestion belgeleri | Bronze/Silver, makbuz/hash ve dönem kontrolleri mevcut |
| Konut hesabı | `app/lakehouse/gold.py`, `app/services/housing_analysis.py` | Reel kredi ve aylık değişimler; faiz farkı < 0 ve reel kredi değişimi <= 0 koşulu |
| Konut evidence/grafik/anlatım | `app/tools/housing_evidence.py`, `housing_chart.py`, `housing_narrator.py` | Altı trace; model sayıları evidence ile kontrol edilir, Türkçe metni Python üretir |
| Dosya demosu | `scripts/run_housing_demo.py`, `app/services/evds_manifest.py` | Fiziksel EVDS zinciri, kaynak/çıktı koruması, JSON paketleri ve `--html` |
| Manifest üretimi | `scripts/build_evds_manifest.py`, `app/lakehouse/evds_manifest_producer.py` | Normal CLI mevcut 66 aylık Silver/coverage'ı seçilen Bronze'dan yeniden hesaplanan sonuçla karşılaştırır; `--demo` 60 ay üretir |
| LLM istemcisi | `app/connectors/llm_client.py` | Yapılandırılabilir OpenAI-compatible Chat Completions; kontrollü hatalar ve SDK retry=0 |
| Housing sorusu | `app/services/housing_question.py`, `app/api/housing_question.py` | Normalize satırlarda tek izinli analiz ve üç karar: ready, clarification_required, unsupported |
| Housing değerlendirmesi | `scripts/evaluate_housing_questions.py`, `evals/housing_question_cases.json` | Dokuz vakalı offline stub; ayrı, açık bütçeli canlı mod |
| TÜFE hesabı | `app/services/inflation_analysis.py`, `app/api/inflation.py` | Aylık/yıllık değişimler ve ilk-son endeks değişimi; iki analizli soru çekirdeğine PR #62 ile bağlı |
| İki analizli soru API/eval | `app/api/economic_question.py`, `scripts/evaluate_economic_questions.py` | PR #66 teslimi: ortak HTTP yüzeyi ve 12 offline vaka |
| Doğrulanmış dosya sorusu | `app/services/housing_question_files.py` | PR #64 main'de; sunucu kontrollü fiziksel paket doğrulanır, mevcut Housing servisi kullanılır |

İlgili belgeler: [Housing question](housing-question.md),
[eval](housing-question-evals.md), [inflation](inflation-analysis.md),
[file demo](housing-demo.md), [tool contracts](tool-contracts.md),
[release acceptance](release-acceptance.md).

## Değiştirilmemesi gereken anlamlar

- Varsayılan konut demo aralığı 2021-01–2025-12: 60 ay.
  Tam Silver teslim aralığı 2021-01–2026-06: 66 ay.
- Reel kredi = nominal tutar × 100 / TÜFE; TÜFE 2025=100, KFE 2023=100.
- Housing seçiminin ilk ayı için önceki ay değişimleri ve koşul null kalır.
- TÜFE servisi seçimden önce **sağlanmış** geçmişi kullanır. Aylık oran
  `(CPI[t]/CPI[t-1]-1)*100`, yıllık oran `(CPI[t]/CPI[t-12]-1)*100`.
  Geçmiş yoksa null; ilk-son değişim aylık oranların toplamı değildir.
- Weekly coverage, doğrulanmış yayın takvimi olmadan unverified/not_available;
  expected_count null. Tam aylık seri, tam haftalık yayın takvimi kanıtı değildir.
- Fiziksel manifest doğrulaması şu an CLI'da mevcuttur. Mevcut normalize-satır
  soru API'si veya genel dosya yükleme servisi aynı kontrolü otomatik yapmaz.

## Açık işler ve sahipleri

Bu tablo 18 Ekim tarihli durumdur; GitHub erişimin varsa güncel body/yorumları oku.

| Issue | Sorumlu | Kalan sonuç |
| --- | --- | --- |
| [#46](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46) | Mustafa | Gerçek teknik/görsel kabul tamam; kısa sunum ve ayrı onaylı tag/release teslimi açık |

#6, #39, #40, #41, #42, #44, #45, #56 ve #59 tamamlandı. PR #43 ve #58 merge edildi; yeni bir
üretici/tüketici düzeltme PR'ı beklenmiyor. Gerçek EVDS dosyaları erişilebilir ve
Mustafa'da bağımsız doğrulandı. BDDK teslimi ve birleşik teknik kabul de tamam;
Mustafa'nın HTML etkileşim kabulü de kendi tarayıcı teyidiyle alındı.

## #59'un ilk parçası: servis çekirdeği (PR #62 ile merge edildi)

Aşağıdaki ilk parça PR #62'de (`01018ae`) tamamlandı ve kullanıcı onayıyla
`6abcfb8` olarak main'e merge edildi. Ortak API/eval PR #66 teslimidir;
bağımsız #42 dosya wrapper'ı PR #64 ile main'dedir.

1. Çalışma ağacını/branch'i kontrol et, bu notu ve #59'u oku. Yerel değişiklikleri
   koru. Python 3.12 `.venv` ve offline başlangıç testini doğrula.
2. `feat/economic-question-routing` gibi ayrı bir dalda yalnızca çekirdeği ele al.
   Bu isim zaten varsa dalın içeriğini kontrol et; mevcut işi ezme.
3. Tek model planlama çağrısında iki izinli analysis_id'yi destekle:
   `housing_rate_down_real_credit_not_up` ve `cpi_inflation_summary`.
   Model, hesap sonucu/SQL/kod/dosya yolu/anahtar üretmesin.
4. Planı ve analize ait kullanılabilir veri kapsamını doğrula. Belirsiz soru
   açıklama isteği, desteklenmeyen tahmin/nedensellik unsupported olsun.
   Veri yokluğu ve geçersiz model yanıtı kontrollü sonuç/hata versin.
5. Doğru mevcut servisi en fazla bir kez çağır. Housing hesabını veya TÜFE
   formüllerini dispatcher içinde yeniden yazma. İlk çekirdekte narrator,
   yeni HTTP endpoint'i, UI veya serbest ekonomik yorum ekleme.
6. Stub modelle iki geçerli analiz, eksik/belirsiz dönem, kapsam dışı istek,
   bozuk/izin dışı plan, prompt injection ve model hatasını test et.
   Çalışmaması gereken kararda sıfır analiz çağrısını; doğru planda doğrudan
   servisle sayısal eşitliği doğrula. Mevcut Housing davranışları korunsun.
7. Kısa çekirdek belgesi, odaklı testler ve tam paketle review edilebilir ilk
   değişikliği teslim et. Issue #59'u yalnızca bu ilk parça ile kapatma;
   ortak API ve değerlendirme seti sonraki küçük PR'dır.

Bu görev gerçek veri teslimini beklemeden sentetik girdilerle yapılabilir.
GitHub erişimi yoksa bu yerel kapsamla ilerle, erişilemeyen issue/PR bilgisini
doğrulanmış gibi sunma. Commit/push/PR/merge adımlarında oturumdaki kullanıcı
yetkisini izle; bir yetki veya araç eksikse yerel diff/test sonucunu teslim et.

## PR #63 çalışma düzeni kaydı — 18 Ekim 2026

- Kullanıcının devam/teslim ve onay sınırları `AGENTS.md` içine eklendi.
  PR #63, güncel tabanında başarılı CI sonrası `a987a88` ile merge edildi.
- Kullanıcı #63–#66 PR'larının sırayla merge edilmesini onayladı. Diğer
  merge/release, canlı çağrı ve yayınlama işlemleri ayrıca onay gerektirir.
- Önceki PR #62 test kaydı 731 passed, 1 skipped ve Housing stub 9/9'dur;
  tarihli kaynak kanıtıdır. Yerel `.venv` kayıp Python yoluna işaret eder;
  kullanılan `out/python312` Python 3.12.15 ortamı Git tarafından yok sayılır.

## PR #65 kabul kaydı güncellemesi — 18 Ekim 2026

- Aktif dal `docs/current-demo-acceptance`; ilk taban `45c8dcf`, güncel birleşik
  taban `96031e2` (PR #62/#63/#64 main'de). Kendi diff'i yalnızca belgelerdir.
- PR #64, başarılı güncel CI sonrasında `96031e2` ile merge edildi. Birleşik
  odaklı soru/dosya testleri 87 passed, 1 skipped; gerçek kabul hâlâ açık.
- #59 ortak API/eval PR #66'dadır. `a672bf3` runtime kaynağının önceki sonucu
  96 odaklı, 772 passed/1 skipped tam paket; Economic stub 12/12, Housing 9/9.
  Son birleşik teslim bunları yeniden doğrulayacaktır.
- `45c8dcf` main arşivinde Python 3.12.15 ile 707 passed, 1 skipped; 60 aylık
  sentetik HTML ve süreç içi Health/Housing/TÜFE HTTP kontrolleri başarılıydı.
  Ayrıntı ve çıktı hash'i [kabul kaydında](release-acceptance.md); bu sonuç
  güncel birleşik main testi veya yeni clone/ortam kurulumu değildir.
- Belge bağlantıları ve diff kontrol edilir; zorunlu Tests CI bu PR'ın güncel
  başlığında izlenir. Yerel `data/` yalnızca `.gitkeep` içerir.
- #39/#40'ta erişilebilir yeni gerçek paket/kanıt teslimi görünmedi. Afra ve
  Osman'ın görevleri devralınmadı; canlı çağrı, veri indirme veya release yok.
- Sıradaki adım onaylı #65/#66 merge sırasını tamamlamak; ardından #42/#46
  gerçek kabulü için #39/#40 dosya/kanıt paketine erişmektir.

## Yerel Windows başlangıcı

Repo zaten klonluysa VS Code ile **repo kök klasörünü** açmak yerel dosya
çalışması için yeterlidir. ChatGPT oturumu açmak, GitHub'a push veya issue/PR
erişimi için ayrıca yetki verildiği anlamına gelmez. Mevcut Git kimlik doğrulaması
korunur; GitHub CLI/entegrasyonu gerekiyorsa erişimi ayrıca doğrula.

PowerShell'de mevcut venv ile:

```powershell
git status
git branch --show-current
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest -q
```

Temiz çalışma ağacında güncelleme gerektiğinde:

```powershell
git switch main
git pull --ff-only
```

Bu sohbette son runtime Linux/PR CI kanıtı 708 geçen testtir. Kullanıcının
Windows/venv sürümleri farklı olabilir; yeni sonuç aynen raporlanmalı. Başlangıç
için canlı modele ihtiyaç yoktur. Gemini Free Tier anahtarı uygulamanın isteğe
bağlı canlı çağrıları içindir; Codex'e ChatGPT hesabıyla girişten ayrıdır.

## Devamlılık

Her teslim sonunda testleri, diff kapsamını ve kalan parçayı kısaca kaydet.
Bu nottaki planlı işi yapılmış gibi işaretleme. Gerçek 60 aylık kabul yapılmadan
release tamamlandı veya ekonomik analiz/model doğruluğu ölçüldü deme. Aynı
görev üzerinde bu sohbet ve yerel Codex oturumu eşzamanlı farklı kod üretmesin.

## #59 servis çekirdeği ilerlemesi — 17 Ekim 2026

`feat/economic-question-routing` dalında iki izinli analiz için tipli soru planı,
veriden türetilen dönem kapsamı ve mevcut Housing/TÜFE servislerine tek yürütmeli
yönlendirme eklendi. Sınırlar ve kapsam dışı kararlar
[çekirdek belgesinde](economic-question.md). Mevcut Housing soru endpoint'i
değişmedi. #59 açık kalır; ortak HTTP yüzeyi, örnekler ve sınırlı değerlendirme
seti sonraki küçük PR kapsamıdır.

Bu yerel Windows kopyasında mevcut `.venv` kayıp bir Python 3.12 yoluna işaret
ettiği için testlerde Git tarafından yok sayılan `out/python312` ortamında Python
3.12.15 kullanıldı. Temiz `HEAD` başlangıç paketi **707 passed, 1 skipped**;
çekirdek sonrası tam paket **731 passed, 1 skipped**. Housing offline stub
değerlendirmesi **9/9** geçti. Bunlar canlı model başarı ölçümü veya gerçek veri
kabulü değildir.

## #59 ortak HTTP ilk geliştirme kaydı — 18 Ekim 2026

Bu bölüm `a672bf3` kaynağının tarihçesidir; son entegrasyon kaydı aşağıdadır.

- Kullanıcı onayıyla PR #62, `6abcfb8` commit'iyle main'e merge edildi. Öncesinde
  aynı `01018ae` başlığı, temiz diff, başarılı CI ve boş review/yorum durumu
  kontrol edildi. Diğer PR'lar için merge onayı verilmiş sayılmaz.
- Aktif dal `feat/economic-question-api`, güncel main `6abcfb8` tabanlıdır.
  `POST /analysis/economic/question`, iki sentetik JSON örneği ve 12 vakalık
  offline HTTP değerlendirmesi PR #66'dadır; henüz main'de değildir.
- `a672bf3` API/eval runtime kaynağı, Python 3.12.15 (`out/python312`): odaklı paket **96 passed**;
  tam paket **772 passed, 1 skipped**. Tek atlama mevcut BDDK Windows symlink
  kontrolüdür. Economic offline stub **12/12**, mevcut Housing offline stub
  **9/9** geçti; canlı model/EVDS çağrısı yapılmadı.
- İki HTTP JSON örneği ve vaka şeması doğrulandı; 48 yerel belge bağlantısı ile
  üç PowerShell bloğunun sözdizimi kontrol edildi. HTTP örnekleri canlı modele
  gönderilmedi. Stub geçişleri model anlama başarısı değildir.
- PR #63 çalışma düzeni, #64 doğrulanmış dosya sorusu ve #65 kabul kaydı ayrı
  PR'lardır. #59 API kodu bunlara bağımlı değildir. #42/#46 gerçek kabulü hâlâ
  Afra/Osman'ın #39/#40 dosya ve kanıt teslimini bekler.
- #62 sonrası #63 devir kaydı (`846f0f8`) ve #64 README/devir kaydı (`013a23e`)
  çakışmaları kendi dallarında belge commit'leriyle giderildi. #65 (`fc1662a`)
  kabul/devir kaydı da yeni main durumuyla düzeltildi. Runtime kodu, fixture
  hash'leri ve paylaşılan geçmiş değiştirilmedi; force push veya başka merge yok.
- PR #66'nın `a672bf3` CI'si başarılı; #59 ilerlemesi bu test kaynağı belirtilerek
  güncellendi ve issue review/merge için açık bırakıldı. Sıradaki adım açık
  #63–#66 PR'ları için kullanıcı merge onayı ve gerçek kabul için #39/#40
  dosya/kanıt paketine erişimdir. Bu belge takibi API runtime'ını değiştirmez.
