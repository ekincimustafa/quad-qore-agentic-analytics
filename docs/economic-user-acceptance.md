# Doğal ekonomik sorular — bağımsız 48 vakalık kabul seti

Takip: [Issue #99](https://github.com/ekincimustafa/quad-qore-agentic-analytics/issues/99). Kaynak: [`../evals/economic_user_acceptance_cases.json`](../evals/economic_user_acceptance_cases.json). Başlangıç `main` commit'i: `f3a15a8051fae6784b44ef15c62a9c382ccd3647` (22 Ekim 2026).

## Amaç ve sınırlar

Bu set, gerçek kullanıcıların üç örnek düğmesinden farklı ifadelerle sorabileceği ekonomik sorular için **bağımsız, sürümlü kabul beklentisidir**. Beklentiler ekonomik anlamdan ve kullanıcının açık taleplerinden türetilmiştir; uygulamanın şu an döndürdüğü plana göre ayarlanmamıştır. Dolayısıyla geçerli bir soruyu mevcut tarih ayrıştırıcı reddediyorsa vaka `ready` beklentisi korunur; bu, gelecekte kapatılacak bir kabul açığı olabilir. **Bu dosyalar hiçbir live/offline modele gönderilmez, evaluator'a otomatik bağlanmaz ve geçmiş vaka sonuçlarının yerine geçmez.** Başarı oranı, mevcut sürüm desteği, gerçek veri hesaplaması veya çalıştırılmış model doğruluğu iddia edilmez.

Mevcut 37 Economic + 9 Housing vakası, evaluator/prompt/runtime/API/UI/CI ve gerçek veri dosyaları değiştirilmez. Yeni vaka setindeki sayılar sadece tarih ve filtre eşiği gibi *talep parametreleridir*; TÜFE ya da kredi hesaplama sonucu üretilmez.

## Kategori dağılımı

| `category` | Adet | `capability_stage` | Kullanım amacı |
| --- | ---: | --- | --- |
| `housing_condition` | 8 | `existing_analysis` | Faiz düşerken reel konut kredisi stoku artmayan aylar |
| `cpi_summary` | 8 | `existing_analysis` | Aylık, geçen yılın aynı ayına göre yıllık, ilk-son TÜFE özeti |
| `two_full_year_comparison` | 8 | `existing_analysis` | İki tam yılın Ocak–Aralık ve Aralık yıllık oranlarının ayrı karşılaştırılması |
| `clarification` | 8 | `existing_analysis` | Eksik yıl/bitiş/nominal-reel, çelişkili tarih, belirsiz analiz |
| `unsupported` | 8 | `existing_analysis` | Tahmin, nedensellik, olmayan metrik, çoklu analiz, ilgisiz ve talimat aşımı istekleri |
| `planned_housing_filter` | 4 | `planned` | Kullanıcının belirlediği faiz/stok eşiklerine göre konut filtreleme |
| `planned_multiturn` | 4 | `planned` | Konuşma geçmişini kullanarak dönem, metrik veya yıl sırasını sürdürme |
| **Toplam** | **48** | | **24 mevcut analiz + 8 netleştirme + 8 kapsam dışı + 8 planlanan** |

## Alan sözleşmesi

Her `cases[]` kaydı şu alanları içerir:

| Alan | Anlamı |
| --- | --- |
| `id` | Kararlı, benzersiz `EUA-001`–`EUA-048` kimliği |
| `category` | Yukarıdaki kapsam sınıfı |
| `capability_stage` | `existing_analysis`: mevcut ürün karar/sözleşme kapsamı; `planned`: henüz uygulanmamış iş hedefi |
| `user_messages` | Sırayla bir veya birden fazla kullanıcı iletisi; çok turlu vakada iki ileti |
| `expected_business_meaning` | Kullanıcının ekonomik veya işlevsel olarak ne istediğinin bağımsız açıklaması |
| `expected_parameters` | Soruya göre `metric`, açık `start_period`/`end_period`, ya da sıralı `first_year`/`second_year`; planlanan filtrelerde `filters`, çok turluda `inherited_from_turn` |
| `expected_decision` | Geçerli mevcut analizlerde `ready` + gerçek `analysis_id`; belirsizlikte `clarification_required` + `reason`; kapsam dışında `unsupported` + `reason`; planlanan vakalarda **yalnızca veri kümesine ait** `planned` etiketi |
| `rationale` | Belirlenen semantik beklentinin kısa gerekçesi ve önemli ayrım |

Mevcut üç gerçek `analysis_id`: `housing_rate_down_real_credit_not_up`, `cpi_inflation_summary`, `cpi_two_year_comparison`. `planned` vakalarda yeni araç, runtime `analysis_id` veya mevcut API yanıtı **tanımlanmaz**. `expected_decision.status="planned"` ve `target_capability` alanları sadece geleceğe yönelik kabul kataloğunun işaretleridir; yürürlükteki API şeması değildir. Bir vakada `existing_analysis` etiketi, modelin soruyu bugün mutlaka doğru planladığı veya mevcut parser'ın tüm ifade biçimlerini tanıdığı anlamına gelmez.

### Dönem ve oran anlamları

- `2023 yılı boyunca` → `2023-01`–`2023-12`; `2023'ün ikinci çeyreği` → `2023-04`–`2023-06`. Başlangıç ve bitiş ayları dahildir. Tek ayın başlangıç/bitiş değerleri aynıdır.
- Aylık TÜFE = `TÜFE[t] / TÜFE[t−1] − 1`; yıllık TÜFE = `TÜFE[t] / TÜFE[t−12] − 1` (oran için ×100). **Yıllık**, on iki aylık aritmetik ortalama değildir.
- Bir seçimin ilk-son endeks değişimi `son endeks / ilk endeks − 1` ile bulunur; aylık oranlar toplanmaz ve ilk-son değişimi “yıllık enflasyon” diye adlandırılmaz.
- İki tam yıl karşılaştırmasında her yılın Ocak–Aralık endeks değişimi, Aralık yıllık enflasyonu ve **ikinci yılın Aralık yıllık oranı eksi birincinin Aralık yıllık oranı** üç ayrı sonuçtur. Son farkın birimi *yüzde puan*dır, yüzde değildir. `first_year`/`second_year` daima **kullanıcının söylediği sırayı** korur; ters sıra da geçerli bir testtir.
- Eksik geçmiş için `null` gerekir, sıfır veya uydurma oran gerekmez. Örneğin veri 2021-01 ile başlıyorsa 2021-12 için 2020-12 oran geçmişi bulunmayabilir.
- “Son altı ay”, “önceki yıl” gibi referansı açıkça kurulmamış göreli ifadeler bugüne ya da veri sonuna bağlanmaz. Eksik yıl, bitiş veya reel/nominal ölçü için netleştirme gerekir. Çelişkili tarihler sessizce yer değiştirmez.
- Konut koşulundaki faiz düşüşü ile reel kredi stokunun artmaması **birlikte** gereklidir. `enflasyondan arındırılmış` reel metriği belirtir; yalnızca “kredi” denmesi otomatik reel seçimi anlamına gelmez.
- Tahmin, nedensellik, eksik veri/analiz veya alakasız soru `unsupported` olabilir. Ekonomik ve meşru ama desteklenmeyen talepler “saçma” olarak adlandırılmaz.

## Doğrulama ve kullanım

Bu set **manuel inceleme/oracle** niteliğindedir. `expected_decision` alanını bugünkü API'ye körlemesine göndererek “48 geçti” sonucu üretmeyin; özellikle `planned` vakalar destekli değildir, bazı açık tarih ifadeleri de mevcut parser tarafından henüz kabul edilmeyebilir.

Depo kökünde mevcut Python 3.12 ortamıyla aşağıdaki **sadece-okuma** kontrolü kullanılabilir:

```bash
python - <<'PY'
import json, re
from collections import Counter
from pathlib import Path
p = Path('evals/economic_user_acceptance_cases.json')
data = json.loads(p.read_text(encoding='utf-8'))
cases = data['cases']
expected = {'housing_condition':8,'cpi_summary':8,'two_full_year_comparison':8,
            'clarification':8,'unsupported':8,'planned_housing_filter':4,'planned_multiturn':4}
assert data['schema_version'] == '1.0'
assert len(cases) == 48 and Counter(c['category'] for c in cases) == expected
assert len({c['id'] for c in cases}) == 48
assert len({tuple(m.strip().casefold() for m in c['user_messages']) for c in cases}) == 48
for index, c in enumerate(cases, 1):
    assert c['id'] == f'EUA-{index:03d}'
    assert set(c) == {'id','category','capability_stage','user_messages',
                      'expected_business_meaning','expected_parameters','expected_decision','rationale'}
    assert c['expected_business_meaning'] and c['rationale']
    assert len(c['user_messages']) == (2 if c['category']=='planned_multiturn' else 1)
    assert c['capability_stage'] == ('planned' if c['category'].startswith('planned_') else 'existing_analysis')
    params, dec = c['expected_parameters'], c['expected_decision']
    if dec['status'] == 'ready':
        if c['category'] == 'two_full_year_comparison':
            assert type(params['first_year']) is type(params['second_year']) is int
            assert params['first_year'] != params['second_year']
            assert (params['first_year'],params['second_year']) == (dec['first_year'],dec['second_year'])
        else:
            assert params['start_period'] == dec['start_period'] and params['end_period'] == dec['end_period']
    for key in ('start_period','end_period'):
        if params.get(key) is not None:
            assert re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',params[key])
    if params.get('start_period') and params.get('end_period'):
        if params['start_period'] > params['end_period']:
            assert c['category'] == 'clarification' and dec['reason'] == 'period_required'
    if c['category'].startswith('planned_'):
        assert dec['status'] == 'planned' and 'analysis_id' not in dec
print('48/48 vaka; kategori, kimlik, şema, dönem ve yıl sırası kontrolleri başarılı.')
PY

git diff --check
```

Başka bir kabul adımı: `evals/economic_question_cases.json` (**37 vaka**) ve `evals/housing_question_cases.json` (**9 vaka**) değişmeden kalmalı. Yerel README ve bu dosyanın göreli bağlantılarını kontrol edin. İçerik bağlantısı eklense dahi set otomatik evaluator'a veya CI'a bağlanmaz. Yalnız belge/JSON değişiyorsa gereksiz tam test/gerçek veri kabul tekrarı yapılmaz; GitHub'ın zorunlu CI kontrolleri ilgili PR'da beklenir. Yeni dosya ve handoff kaydı dışında fark olmamalı.

## Teslim notu

Handoff'ta kullanılan `main` commit'i, dal, dağılım, yapılan JSON/bağlantı/diff kontrolleri ve “hiçbir canlı çağrı yapılmadı, 48 vaka bugünkü model tarafından çalıştırılmadı” sınırı kısa olarak yazılmalıdır. Uygulayan oturum PR açtıktan sonra merge yapmaz; bağımsız incelemeye bırakır.
