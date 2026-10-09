# Faz 25c — SimFin `Close / Adj. Close` fiyat düzeltme oranı anomali adayları

## Kullanıcının Windows Faz25b gerçek bulguları (10 Ekim 2026)

- 21/21 aylık en az bir geçerli kaynak fiyat örtüşmesi: **3.557 SimFinId**;
- en az 400 ayrı hafta içi fiyat gözlemi: **3.557**;
- her 21 ayda en az 15 farklı hafta içi fiyat gözlemi: **3.553**;
- her ayda en az 10 gün: **3.554**;
- aynı SimFinId+gün mükerrer geçerli fiyat: **0**;
- ardışık gözlemler arasında 8+ takvim günü boşluğu olan: **0**;
- kanonik PIT ve split/temettü fiyat sertifikası: **0**.

Bu sonuçlar fiyat **derinliği** ile ilgilidir; kaynak `Adj. Close` değerlerinin gerçek temettü ve split düzeltmesine uygun olduğuna dair bağımsız kanıt **değildir**. Ayrıca 21/21 ay arşivi günlük tarihsel CIK veya delisted üyelik sağlamaz.

## Yeni Faz25c denetimi

`scripts/phase25c_simfin_adjustment_factor_triage.py` 21/21 aylık Faz25b **3.557** araştırma adayını ve SHA256 ile doğrulanmış eski ücretsiz SimFin kaynağını analiz eder; 415 MB orijinal CSV/ZIP bir kez, akış halinde okunur. Amaç **resmî kurumsal işlem kanıtı aramak için şüpheli dönemleri önceliklendirmek**:

1. Günlük `Close / Adj. Close` oranının her ay içindeki minimum–maksimum aralığı **%5** veya üstünde değişiyor mu?
2. Bir ayın son geçerli fiyatı ile sonraki ayın ilk geçerli fiyatı arasında kaynak düzeltme faktörü **%5+** değişiyor mu?
3. Bu iki aylık komşu gözlem arasında kaynak düzeltilmiş kapanış **%50+** hareket etmiş mi? (gerçek piyasa hareketi veya veri anomalisi olabilir)
4. Faz25b raporunda bulunan her SimFinId için kaynak geçerli fiyat satırı sayısı ve 21/21 ay örtüşmesi aynen korunuyor mu?
5. Bütün kaynak SHA256, Phase25b schema/status ve aylık Alpha Vantage liste arşivi kontrolleri korunuyor mu?

Bunlar **yalnızca araştırma uyarılarıdır**. `Close / Adj. Close` faktörünün değişmesi bir **split, temettü veya hatanın bağımsız kanıtı değildir**. Faktör sabit olsa bile fiyat serisi otomatik doğru sayılmaz. Belirli kurumsal işlem tarihleri ve tutarları resmî şirket/borsa kaynağıyla ayrıca doğrulanacaktır.

### Windows PowerShell

```powershell
cd E:\M10
git pull --ff-only

$file = "$env:USERPROFILE\Downloads\us-shareprices-daily\us-shareprices-daily.csv"

.\.venv\Scripts\python.exe -m scripts.phase25c_simfin_adjustment_factor_triage --input "$file"
```

Özel rapor:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25c\simfin_adjustment_factor_source_triage.json`.

Beklenen **yalnızca ilk sayı**, önceki kaynak değişmemişse: `SimFinIds_reviewed=3557`. Diğer alarm sayıları **gerçek CSV taraması olmadan bilinemez**.

Kısa sonuçta:
- `factor_5pct_intra_month_candidates`
- `factor_5pct_boundary_candidates`
- `extreme_adj_month_boundary_candidates`
- `split_verified=0`, `dividend_verified=0`, `certified_adjusted_prices=0`, `canonical_backtest_eligible_securities=0`.

## Faz25d'de gerekli bağımsız kaynak kanıtları

SEC/şirket yatırımcı ilişkileri belgeleri, FINRA/borsa kurumsal işlem duyuruları, kurumsal işlem tarihleri (ex-date/record-date/effective date), gerçek split oranı, temettü nakit miktarı, delist/son işlem ve tarihsel şirket kimliği kayıtları; kullanıcı erişim hakları kontrol edilerek gerçek kayıtlarla **bağımsız doğrulanacak**. Yalnızca bu kontrolün pozitif olması bu sonraki denetimlere alternatif değildir.

Hiçbir veritabanı, model, veri kaynağı, SEC ham dosyası veya SHA kayıtları değiştirilmez. Ağ isteği, ücretli API, yeni indirme, model eğitimi veya kanonik geçmiş test **yoktur**. Ekrandaki gerçek sonuca bakarak bir sonraki alt aşama belirlenecek.
