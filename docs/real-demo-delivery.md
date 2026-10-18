# Gerçek demo teslimi ve gösterim

18 Ekim 2026; kod temeli `7ee7225` (PR #66 sonrası main). Bu belge teslim ve
EVDS/BDDK alıcı ve birleşik teknik doğrulamayı izler; Mustafa'nın görsel kabulü tamamdır.
İlgili işler: [#39][39], [#40][40], [#42][42], [#46][46].

## Kontrol edilen teslimler

- Afra [OneDrive teslim bağlantısını][delivery39] paylaştı. Mustafa'nın indirdiği
  ZIP ve teslim belgesi ayrı kabul klasöründe açıldı. 66/60 aylık CSV, coverage,
  manifest ve üç serinin raw/makbuzları için **12/12 dosya boyutu ve hash'i**,
  fiziksel tüketici zinciri, üretici eşitliği ve üç örnek ay doğrulandı.
  ZIP SHA-256: `1c9255194c3222dccc33e056ba195c46a8d0912cdb9ccccd178e8e4b2731ebc1`.
  ZIP hash'i bağımsız eşleşti; [alıcı sonucu][acceptance39] #39'a kaydedildi.
  Ayrıntılar [kabul kaydındadır](release-acceptance.md).
- Osman [birleşik gerçek paketi][delivery40] ve [ayrı EVDS teyidini][receiver39]
  paylaştı. Housing ZIP hash'i `956e47c3a7d922b4da7b755635379ccc357423aeceed2bcdef817a1098ca312f`
  eşleşti; **156/156 envanter kaydı**, BDDK raw/makbuz/Silver ve üç örnek ay
  Mustafa'da doğrulandı. EVDS'nin 12 dosyası eski kabul kopyasıyla bayt eşit.
- Mustafa'nın bağımsız **tek CLI koşusu 60 ay/22 eşleşme** verdi; yeni dört çıktı
  teslim `outputs/` ile bayt eşit. Aynı girdilerle açık sabit planlı #42 wrapper'ı
  aynı evidence/grafiği verdi. #39/#40/#42 tamamlandı; rc.1 yayımlandı,
  #46 ekran kaydı ve kısa demo teslimi açık.
- Üretici/tüketici kodu, şema ve ortak sentetik fixture zaten teslim edildi.
  Bu işler yeniden istenmez. Yerel `data/` yalnızca `.gitkeep` içerir.

## Yayımlanan paylaşım talepleri ve önceki taslaklar

Mustafa talepleri [Afra için #39'da][request39] ve [Osman için #40'ta][request40]
yayımladı. **Tekrar paket talebi gönderilmez.** İki teslim ve teknik kabul
tamamlandı; Mustafa yeniden üretilen gerçek HTML'yi de tarayıcıda teyit etti.
Aşağıdaki taslaklar yalnızca önceki hazırlığın kaydıdır.

### Afra

> Hazırladığın 12 dosyalık EVDS ZIP'i ve üç örnek ay/yeniden üretim komutları
> belgesini erişim kısıtlı ekip paylaşım bağlantısıyla iletebilir misin?
> `1c925519…31ebc1` ZIP hash'ini kaydettik; paketi veya kodu yeniden hazırlamana
> gerek yok. Arşiv mevcut `data/bronze/evds/...` ve `data/silver/evds/monthly/...`
> yollarını korusun; manifestlerin gösterdiği fiziksel dosyalar aynı kökten
> açılsın. Teslim belgesinde kullanılan commit, tam komutlar/çıkış sonuçları,
> 66/60 satır kapsamı, göreli yol/bayt/SHA-256 listesi ve 2021-01, 2023-06,
> 2025-12 karşılaştırmaları varsa mevcut belge yeterli. Anahtar veya `.env` ekleme.

### Osman

> Mevcut BDDK dosyalarını ve yaptığın kontrolün erişilebilir kaydını paylaşabilir
> misin? `data/silver/bddk/housing_loans.parquet` ile kullanılan
> `data/bronze/bddk/aylik/raw/` ve `receipts/` dizinleri aynı kökte gerekli.
> Kayıtta commit/ortam, komut/çıkış sonucu, 2021-01–2026-06 için 66 ay,
> göreli yol/bayt/SHA-256 listesi ve 2021-01 / 2023-06 / 2025-12 bülten
> başlık dönemi, Milyon TL ve toplam→Silver karşılaştırmaları bulunsun.
> Afra'nın hazır paketine erişim sağlanınca mevcut offline CLI'nin 60 aylık
> koşusundan `evidence.json`, `chart.json`, `run_summary.json`, `report.html`
> ve çıktı hash'lerini paylaşalım. Bu kayıtlar zaten elindeyse yalnızca bağlantı
> yeterli; yeniden indirme, yeni connector veya kod geliştirmesi gerekmiyor.

## Paketin dizin yapısı

Mevcut dosya adlarını değiştirmeyin. Aşağıdaki köklerin altındaki adları manifest
ve makbuzların **gerçekte referans verdiği yollar** belirler:

```text
<veri/proje kökü>/
  data/
    bronze/
      evds/<seri>/raw/<mevcut dosyalar>
      evds/<seri>/receipts/<mevcut makbuzlar>
      bddk/aylik/raw/<mevcut dosyalar>
      bddk/aylik/receipts/<mevcut makbuzlar>
    silver/
      bddk/housing_loans.parquet
      evds/monthly/
        evds_monthly_2021-01_2026-06.csv
        evds_monthly_2021-01_2026-06.coverage.json
        manifest.json
        evds_monthly_2021-01_2025-12.csv
        evds_monthly_2021-01_2025-12.coverage.json
        manifest_2021-01_2025-12.json
```

ZIP hash'i taşıma bütünlüğünü kontrol eder. Dosya envanteri tüm raw/makbuz/
Silver/coverage/manifest dosyalarının yol, boyut ve hash'lerini kapsamalıdır.
Kaynak doğruluğu ayrıca manifest, makbuz ve üç örnek ay karşılaştırmasıyla
doğrulanır; yalnızca ZIP hash'i veya güvenlik taraması kabul kanıtı değildir.
Üç seri `TP.KTF12`, `TP.TUKFIY2025.GENEL`, `TP.KFE.TR`; TÜFE 2025=100,
KFE 2023=100. Haftalık yayın kapsamı resmî takvim olmadan `unverified` kalır.

## Mevcut offline doğrulama yolu

Kaynak ZIP'i koruyun; ayrı çalışma kopyasında mevcut yolları açın. Girdi,
çıktı, `.part` ve `.backup` dizinlerini ayırın. İlk adım:

```powershell
Get-FileHash -LiteralPath '<EVDS-ZIP-yolu>' -Algorithm SHA256
```

Tam fiziksel manifest doğrulaması ve modelden önce BDDK Bronze→Silver eşitliği
için mevcut [dosya soru wrapper'ının sabit plan örneğini](housing-question-files.md#offline-kullanım)
2021-01–2025-12 dönemine uyarlayın. `model_call` açıkça sabit stub olmalı;
varsayılan canlı model kullanılmamalıdır. Ardından aynı kökte:

```powershell
python -m scripts.run_housing_demo --bddk-silver data/silver/bddk/housing_loans.parquet --evds-silver data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv --evds-manifest data/silver/evds/monthly/manifest.json --start-period 2021-01 --end-period 2025-12 --output-dir out/real-demo --html
Get-ChildItem -LiteralPath out/real-demo -File | Get-FileHash -Algorithm SHA256
```

Bu CLI yalnızca yerel dosyaları kullanır. 60 tekil ay, ilk ay null değişimleri,
mevcut hesap kuralı, evidence/grafik uyumu ve üç gerçek örnek ay kontrol edilir.
Gerçek eşleşme sayısı şimdiden varsayılmaz. Kaynak dosyalarının ilk/son hash'leri,
komut sonuçları ve dört çıktı kaydedilir. [Kabul kaydı](release-acceptance.md)
gerçek sonuçlarla güncellendi; #40/#42 tamamlandı, #46 ekran kaydı ve kısa demo teslimini bekler.

## Şimdi açılacak gerçek rapor

```powershell
Start-Process .\out\housing-acceptance-20261018\reproduced\report.html
```

Mustafa 18 Ekim'de bu gerçek dosyada 60 ay/22 eşleşmeyi, hover–zoom–pan–sıfırlamayı,
seçtiği ayda tablo/grafik uyumunu, 2021-01'in eşleşmemesini ve kaynak/birim/baz yılı
ile sınırlamaların okunabilirliğini teyit etti. Bu kullanıcı incelemesidir;
Codex'in tarayıcı testi değildir. Teslimdeki orijinal `outputs/` ve inputs değişmedi.
Sürüm notu ve 60–90 saniyelik anlatım [mevcut kabul kaydındadır](release-acceptance.md).
Mustafa'nın ayrı onayıyla `abea431` main commit'i
[`v0.1.0-rc.1` prerelease](https://github.com/ekincimustafa/quad-qore-agentic-analytics/releases/tag/v0.1.0-rc.1)
olarak yayımlandı; veri/HTML/audit eki yüklenmedi. Ekran kaydı henüz alınmadı;
sunum ve demo teslimi tamamlanmış sayılmaz.

### 60–90 saniyelik ekran kaydı

Bu adımlar Mustafa'nın uygulayacağı yönergedir; henüz yapılmış kayıt değildir.

1. Yukarıdaki gerçek HTML'yi tarayıcıda açın. Grafiği sıfırlayın, üstte 60 ay/22
   eşleşme görünür olsun. Pencereyi büyütün; yazılar okunacak yakınlıkta kalsın.
2. `Win+G` ile Xbox Game Bar'ı açın. Yakalama panelinde mikrofonu açın;
   `Win+Alt+M` mikrofonu açıp kapatır. Önce kısa bir ses denemesi kaydedip dinleyin.
3. Rapor tarayıcısı aktifken `Win+Alt+R` ile kaydı başlatın. Birkaç saniye bekleyip
   [kabul kaydındaki anlatımı](release-acceptance.md) izleyin:
   **0–20 sn** kapsam/60 ay/22; **20–40 sn** Şubat 2021 hover, zoom, pan ve sıfırlama;
   **40–60 sn** eşleşme tablosu ve Ocak 2021'in listede olmaması;
   **60–90 sn** kaynaklar, birimler ve sınırlamalar.
4. `Win+Alt+R` ile durdurun. Varsayılan çıktı **Videolar > Yakalamalar
   (Videos > Captures)** altında MP4'tür. Dosyayı `housing-demo-v0.1.0-rc.1.mp4`
   gibi tanınabilir bir adla saklayın; mevcut bir dosyanın üzerine yazmayın.
5. MP4'ü baştan sona açıp 60–90 saniye olduğunu, sesinizi, sayıların ve kaynakların
   okunmasını kontrol edin. Dosya oluşması tek başına demo kabulünü tamamlamaz.
6. Kayıt hazır olduğunda yerel yolunu ve kontrol sonucunu Mustafa paylaşır;
   #46'daki demo maddesi ancak bu kanıtla güncellenir. Video yayımlama/yükleme
   bu yönergenin parçası olarak yapılmadı.

Kısayollar ve varsayılan MP4 konumu için
[Microsoft'un Xbox Game Bar yönergesi](https://support.microsoft.com/en-us/accessibility/windows/use-a-screen-reader-to-record-your-screen-with-xbox-game-bar).

## Önceki sentetik örnek

Anahtarsız sentetik HTML için repo kökünde çalışan Python 3.12 ortamıyla:

```powershell
python -m scripts.render_housing_sample
Start-Process .\out\housing-sample.html
```

Bu Windows çalışma kopyasında eski `.venv` bozuk olduğundan yeni ortamın
`.\out\clean312\Scripts\python.exe` yorumlayıcısı doğrudan kullanılabilir.
Kabul sırasında üretilmiş HTML
`out/clean-demo/out/housing-sample.html` dosyasıdır; yeniden üretmek zorunlu değildir.

Ekranda **sentetik** olduğunu söyleyin: 2021-01–2025-12, 60 ay, 55 yapay eşleşme.
Bir eşleşmenin tablo/grafik değerlerini, kaynak/yöntemi ve nedensellik
sınırlamasını gösterin. Bu sayı gerçek ekonomik bulgu veya model başarı oranı
değildir. Mevcut doğal dil endpoint'leri canlı model kullanır; offline gösterimde
[Housing](housing-question-evals.md) ve [Economic](economic-question.md#offline-değerlendirme)
stub değerlendirmelerini kullanın. Yerel TCP API için README'nin
`uvicorn app.api.main:app` ve anlatımsız `/analysis/housing` örneği anahtarsızdır.

[39]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39
[40]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40
[42]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/42
[46]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/46
[afra]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6250215723
[request39]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6250879475
[request40]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6250883464
[delivery39]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251399411
[acceptance39]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6251815563
[delivery40]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/40#issuecomment-6252930443
[receiver39]: https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/39#issuecomment-6252994701
