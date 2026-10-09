# Faz 25h — P1 resmî kaynaklı nakit/kurumsal işlem referans mutabakatı (araştırma)

Altı hisse için 15 kaynak anomalisi satırı, **13 farklı nakit dağıtımı referansı** (aynı gerçek dağıtım iki kaynak alarmını doğurabilir) ile ilişkilendirilir. IRS Kasım 2024 için ayrıca **nakitten farklı hisse dağıtımı** var, dolayısıyla bu araç yalnız nakit etki tahmini için kullanılır.

Her satırda:
- İki tarihli SimFin kaynağının \`Close/Adj.Close\` faktöründen Phase25g'nin ürettiği **koşullu tek-nakit etkisi**,
- İhraççı/OCC resmî kaynak URL'si, dağıtım miktarı, **EX_DATE ile RECORD_DATE ayrımı**, kaynak yayın tarihi bilgisi,
- Nakit tutarı arasındaki yaklaşık USD / yüzde fark, rakamsal %2 yakınlık ve tarih aralığı uyumu,
- Kanonik PIT/fiyat onayından farklı **araştırma kategorisi** tutulur.

**Kesinlikle fiyat düzeltmesi doğrulaması değildir:** resmî işlem tutarına yakın sonuç, vendor formülünün, ADR biriminin, fiyat günlerinin borsa takviminin, delisting getirisinin veya SEC issuer-CIK'in kanıtlandığı anlamına gelmez. Fiyat gözlem çifti birbirini izleyen iki borsa günü olmayabilir. Yalnız \`source_before_date < official_date <= source_after_date\` kontrol edilir; aralık dışı olay reddedilir.

### Özel uyarılar

- DOYU 2024 Ağustos ve SITC 2025 Ağustos **resmî ex-date dışı** kayıtlardır; esas nedenleri bilinmiyor.
- IRS 2024 Haziran/Kasım ihraççı belgeleri **nakit için RECORD_DATE** veriyor, otomatik EX_DATE kabul edilmez; Kasım sonunda OCC #55581'de %3.6013447 **hisse dağıtımı** vardır.
- SITC 2025 Haziran 1.50 USD borsa kayıtları: https://www.miaxglobal.com/sites/default/files/alert-files/SITC_Dividend__56736.pdf
- SITC 2025 Eylül 3.25 USD OCC #57019: https://infomemo.theocc.com/infomemos?number=57019
- TDG 2024 Ekim 75 USD OCC #55249: https://infomemo.theocc.com/infomemos?number=55249
- TDG 2025 Eylül 90 USD OCC #57110: https://infomemo.theocc.com/infomemos?number=57110
- DOYU Nasdaq ex-date ve due-bill açıklamaları: https://ir.douyu.com/Press-Releases/68f8babd610466245f518985 ve https://ir.douyu.com/Press-Releases/68f8babd610466245f518973
- HUYA: 2024 Mayıs, Ekim ve 2025 Temmuz tarihli ihraççı açıklamaları (kaynak bağlantıları makine okunabilir raporda ayrı tutulur).
- IRS Haziran issuer cash USD 0.630247/GDS: https://www.irsa.com.ar/en/dividend-distribution-record-date-for-gds-holders/
- IRS Kasım issuer cash USD 0.998325/GDS + ayrı hisse dağıtımı: https://www.irsa.com.ar/en/dividend-and-treasury-share-distribution-record-payment-date-for-gds-holders/
- ZIM geçmiş ex-date + nakit geçmişi: https://investors.zim.com/stock-info/default.aspx . Geçmiş tablonun bugün erişilebilir olması o bilgiyle geçmişte işlem yapılabileceğinin kanıtı **değildir**.

### Çalıştırma

M10 deposunun güncel **main kodu** üzerinden:

\`\`\`powershell
.\.venv\Scripts\python.exe -m scripts.phase25h_official_cash_source_reconciliation
\`\`\`

Bir önceki Faz25g özel JSON dosyasını okur, sadece:
\`\`\`
%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25h\p1_official_cash_source_reconciliation.json
%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25h\p1_official_cash_source_reconciliation.csv
\`\`\`
çıktılarını oluşturur.

Çalışma *ücretsiz*, **0 ağ/API erişimi**, SEC SQLite, Parquet, fiyat CSV ve model dosyalarında **0 değişiklik**. Kanonik veri, backtest ve Learning V3 durumları özellikle **0/KAPALI** olarak kalır. Gerçek backtest için tarihsel issuer-CIK, share/ADR unit, tüm corporate actions, delist ve PIT \`available_at\` bağımsız onayı gerekir.
