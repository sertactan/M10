# Faz 25f — Altı P1 hissenin bağımsız kurumsal işlem kanıtı inceleme listesi

## Gerçek Faz25e Windows sonucu, 10 Ekim 2026

Kullanıcının PowerShell çıktısı (kaynak verinin kapsamını gösterir; olayların kanonikliğini değil):

- 133 benzersiz fiyat anomalisi araştırma adayı;
- **P1 listesi: HUYA, IRS, ZIM, DOYU, TDG, SITC** (6 SimFinId);
- Faz25e tarafından çıkarılan **134 ay içi kaynak Close/Adj.Close faktör aralığı**, **8 ay sınırı faktör değişimi**, **40 adet ay sınırı kaynak Adj.Close hareketi** olayı;
- Kaynak tarihlerine bağlanmış olay sayısı **182**; bunların her biri bir split ya da temettü değildir. Bir hisse birden fazla kayıtta bulunabilir.
- Gerçek, bağımsız kanıtla onaylanmış split, temettü ve kanonik backtest sayısı **0**.

## Faz25f neden gerekli?

Faz25e 133 hissenin bütün olayları için kaynak gözlemleri \`source_only_event_observations\` içine kaydetmiştir; ancak ilk P1 altı hissenin şirket duyurularıyla eşleştirilecek **tam tarih ve ham/düzeltilmiş fiyat gözlemleri** sade bir inceleme formuna dönüştürülmelidir.

Faz25f aracı önce **yalnızca yerel Faz25e raporunu** okur, internete erişmez, API veya fiyat dosyası indirmez, CSV/PIT raporlarını yeniden taramaz. Ardından **P1 altı hissenin olaylarını birer Excel satırı** olarak yazar. Şunları verir:

- Orijinal SimFinId, ticker, **henüz tarihsel olarak doğrulanmamış** mevcut CIK adayı.
- Ay içi veya iki ay sınırı kaynağındaki anomali sınıfı.
- Kaynak fiyat gözlemlerinin **tarihleri** ve aynı iki gözlemdeki **ham Close ile kaynak Adj. Close**.
- Önceki kaynak tanımındaki **oran farkı veya aşırı fiyat hareketi yüzdesi**.
- Resmî kaynak URL'si, hukuki şirket adı, etkin/ex-dividend tarihi, SEC kamuya yayımlanma zamanı ve tarihsel CIK kanıtı için **boş araştırma sütunları**.

Araç tüm 133 aday için olay sayıları, her SimFinId'nin alt olay sayıları, kaynak şema/durum, önceki zero-canonical bayrakları ve 2024-01-01–2025-09-30 tarih penceresini kontrol eder; herhangi bir çelişkide dosyaları üretmek yerine **durur**.

### Windows PowerShell

\`\`\`powershell
cd E:\M10
git pull --ff-only

.\.venv\Scripts\python.exe -m scripts.phase25f_p1_official_evidence_worklist
\`\`\`

Kısa çıktı \`P1_SimFinIds: 6\`, \`P1_ticker_event_date_ranges\` ve altı hissenin en erken/en son anomalili kaynak gözlemini gösterecek; **olay satırlarının sayısını önce uydurmayız**.

Yerel özel dosyalar:

\`\`\`text
%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25f\p1_independent_source_review_queue.json
%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25f\p1_independent_source_review_queue.csv
\`\`\`

### Sonraki gerçek bağımsız doğrulama adımı

Önce **P1 olaylarının kaynak tarihlerini** açacağız. Her olay için kaynak güvenliği için resmî **SEC EDGAR, şirketin yatırımcı ilişkileri, Nasdaq/NYSE/FINRA kurumsal işlem duyurularından** split veya temettü var mı araştıracağız. Doğrulama için olay tipini, *gerçek effective/ex-date*, split oranı/temettü nakit miktarı, orijinal belge bağlantısı ve **o tarihte kamuya açıklanmış olup olmadığını** ayrı kaydedeceğiz. Bir **ADR oran değişimi**, **özel temettü**, **merger**, **tür değişikliği** veya veri sağlayıcı algoritma farkı da araştırma hipotezidir, olay olarak varsayılmaz.

Sadece listede resmi kaynak alanını doldurmak **kanonik onay vermez**. İleride bağımsız kanıt doğrulaması, tarihsel SimFinId↔CIK↔ticker doğrulaması, delisted getirileri ve piyasadaki gerçek işlem günleri ayrıca denetlenecek. Aksi durumda **Learning V3 / S15.3/S16 kanonik backtest kapalı kalır**.

Bu fazda hiçbir production SQLite, 12,3M SEC fact, SimFin kaynağı, fiyat dosyası, modeller, üçüncü taraf hosting, önceki araştırma raporu değişmez. Bu araç doğrulama yapılmadan \`official_exchange_or_issuer_corporate_action_verified = 0\` ve \`canonical_backtest_eligible_securities = 0\` durumunu sürdürür.
