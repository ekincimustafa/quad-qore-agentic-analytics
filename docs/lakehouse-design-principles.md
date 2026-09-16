# Quad-Qore Lakehouse Mimari Prensipleri

Bu doküman, Quad-Qore projesindeki veri mühendisliği süreçlerinde (özellikle Silver katmanında) uyulması zorunlu olan mimari kuralları barındırır. Yapay zekâ (MIA) ve veri ardışık düzenleri (pipelines) tasarlanırken bu prensiplerden kesinlikle taviz verilmez.

## Kural 1: Spesifik İş Mantığı (Domain Logic) ile Evrensel Denetimin Ayrılması

Gelecekte sisteme finans dışı veriler (Sağlık, Eğitim, vb.) veya BDDK harici kaynaklar (TCMB, TÜİK) eklendiğinde sistemin "tek ve hantal bir dönüştürücü" üzerinden çalışarak çökmesini engellemek için:

1. **Özel Dönüştürücüler (Specific Transformers):** Her veri kaynağı veya formatı için ayrı bir Silver script'i yazılır (örn: `bddk_silver.py`, `health_silver.py`). Bu scriptler sadece o verinin özel JSON/CSV/HTML hiyerarşisinden ilgili değerleri bulup çıkartmaktan sorumludur. "Her şeyi okuyabilen sihirli script" yazılmaya **çalışılmaz**.
2. **Merkezi Denetleyiciler (Core Validators):** Eksik ay tespiti, aynı aya ait çoklu verilerin (mükerrer) tekilleştirilmesi, NaN/Inf kontrolü, SHA-256 bütünlüğü, dosya boyutu kontrolü ve Path Traversal (güvenlik) gibi kurallar **kesinlikle** kaynak kodun içine gömülemez (hardcoded). Bu kontroller `app/lakehouse/core_validators.py` gibi merkezi kütüphanelerden çağrılır.
3. **Mükemmel Genişletilebilirlik:** Bu sayede yarın sisteme eklenecek tamamen yepyeni bir veri türü için sadece "JSON'dan sayıyı çekme" kısmı yazılır, geri kalan tüm güvenlik ve bütünlük altyapısı %100 test edilmiş `core_validators` üzerinden hazır olarak devralınır.

## Kural 2: Fail-Closed Yaklaşımı

Tüm merkezi denetleyiciler (`core_validators`) bir anormallik (örn. takvimde eksik ay, geçersiz hash, negatif sayı) tespit ettiğinde süreci uyarısız iptal eder (Exception fırlatır). Silver katmanı hiçbir zaman hatalı veriyi "tahmin ederek" düzeltmeye veya es geçmeye (fail-open) çalışmaz.

## Kural 3: Otonomi (AI) Katmanının Veriye Bakış Açısı

Yapay zeka (MIA) ve onun araçları (tools), karmaşık ham verilerle (Bronze) uğraşmaz. MIA, yukarıdaki kurallarla temizlenip standardize edilmiş, evrensel testlerden geçerek doğruluğu kanıtlanmış (Silver/Gold) Parquet dosyalarını okuyarak analiz yapar. MIA'nın gücü (esnekliği), veriyi her formattan okuyabilmesinde değil; her türlü temiz veriyi (sağlık, finans vs.) ortak "Evidence" motoru üzerinden otonom şekilde birleştirip analiz edebilmesindedir.
