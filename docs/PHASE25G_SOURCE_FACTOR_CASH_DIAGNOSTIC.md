# Faz25g — resmî dağıtım karşılaştırması öncesi kaynak fiyat oranı denetimi

## Neden?

Faz25f Windows raporunda **altı P1 hisse** (DOYU, HUYA, IRS, SITC, TDG, ZIM) için **15 kaynak fiyat gözlem çifti** var. SimFin \`Close\` ile \`Adj. Close\` çifti muhtemel temettü/split/ADR düzeltmesi araştırması için değerlidir, ancak kaynağın düzeltilmiş fiyatı veya resmî ex-date **kanıtlanmış değildir**.

Bu araç 15 çifte aynı fiyat formülünü tekrarlanabilir biçimde uygular:

- \`f_before = raw_close_before / adj_close_before\`
- \`f_after  = raw_close_after / adj_close_after\`
- Koşullu *tek nakit dağıtımı varsayımıyla* \`implied_cash = raw_close_before * (1 - f_after/f_before)\`
- Hem ham hem düzeltilmiş kaynağın fiyat hareketini hesaplar.
- Gözlem çiftlerini **tarihe göre sıralar**; faz25f'nin ay içi min/max faktörü ters tarihle döndürebildiği durumları düzeltir.
- **Tarihsel CIK, gerçek ex-date ve borsa işlem seansı doğrulamaz**. Formül, gerçek nakit ödemesi veya doğru düzeltilmiş fiyat **kanıtı değildir**. Bir ADR ratio change, split, özel temettü, delist veya birden çok olay için bu formül tek başına geçerli değildir.
- Önceki kaynak SHA/provenans raporunu değiştirmez; üretim veritabanına veya ML'e yazmaz.

Bu araç **Faz25g'nin tamamlandığı** anlamına gelmez. Devamında önceden araştırılan kaynak duyurularındaki resmî tarih/nakit miktarıyla matematiksel farkların **bağımsız kaynak incelemesi** yapılacaktır. Kullanıcının önceki Faz25g resmi kaynak CSV'sinde 13/15 referans olay tarihi gözlem aralığında, **DOYU Ağustos 2024 ve SITC Ağustos 2025** aralık dışındadır; bu da tek başına resmî ex-date sertifikası değildir.

## Windows PowerShell

\`\`\`powershell
cd E:\M10
git pull --ff-only

.\.venv\Scripts\python.exe -m scripts.phase25g_source_factor_cash_diagnostic
\`\`\`

Varsayılan özel çıkışlar:
- \`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25g\p1_source_factor_cash_diagnostic.json\`
- \`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25g\p1_source_factor_cash_diagnostic.csv\`

**Hiçbir ek API anahtarı, ücretli kaynak, yeni dosya indirme veya 415MB CSV taraması gerekmez**: yalnızca özel Faz25f JSON okunur. Beklenen sonuç: 6 ticker, 15 kaynak oranı teşhisi, bağımsız ve kanonik onay sıfır.

## Bir sonraki görev

Faz25g resmî referans eşleştirmesi: kaynak fiyat çiftlerinden türetilmiş koşullu dağıtım etkisini, resmî evraklarda belirtilen **gerçek** temettü veya ADR düzeltmesiyle, *eğer* tarih ve hisse birimleri doğrudan eşleşiyorsa uzlaştır. Referansları issuer/SEC/OCC/borsa bağlantısı, resmi yayımlama tarihi, effective/ex date, amount, share class/ADS şeklinde ayrı kaydet; paraya, dövize, ADR birimine veya hisse sınıfına ait belirsizliği kapatmadan otomatik kanonik onay verme.

**Özellikle IRS Kasım 2024**: nakit dağıtımı ve hisse dağıtımı birbiriyle karışabilir, eşleştirme yalnız nakit ilanına dayanamaz. Dolayısıyla doğrulanmış eylem sayısı ve fiyat sertifikası sıfır kalır.

Mevcut 9,21GB yerel SQLite, 12,3M+ SEC fact, 21 aylık liste, Faz25f özel dosyalar, S15.3/S16/S16-EA kanonik formülleri ve backtest kapıları korunur.
