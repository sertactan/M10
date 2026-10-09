# Faz 24l — INOD SEC resmî dosyalama tarihleri (9 Ekim 2026)

## SEC.gov birincil dosyalama kayıtları

| SEC accession | Kabul zamanı New York ET | Resmî dosyalama tarihi | Finansal dönem | Kaynak |
|---|---|---|---|---|
| 0001410578-24-000611 | 2024-05-07 17:48:33 | 2024-05-08 | 2024-03-31 | [SEC Index](https://www.sec.gov/Archives/edgar/data/903651/0001410578-24-000611-index.htm) |
| 0001410578-24-001246 | 2024-08-08 18:00:33 | 2024-08-09 | 2024-06-30 | [SEC Index](https://www.sec.gov/Archives/edgar/data/903651/0001410578-24-001246-index.htm) |
| 0001410578-25-001113 | 2025-05-08 17:49:06 | 2025-05-09 | 2025-03-31 | [SEC Index](https://www.sec.gov/Archives/edgar/data/903651/000141057825001113/0001410578-25-001113-index.htm) |

Üçü de INNODATA INC (CIK 0000903651), Form 10-Q. SEC kabul anı 17:30 ET sonrasında; dosyalama tarihi ertesi iş günüdür. Bu alanlar SEC'in resmî index kayıtlarında ayrı ayrı görünür. Resmî açıklama: [SEC Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) ve [EDGAR Filer Help Sheet](https://www.sec.gov/files/info/edgar/besttips.htm).

Bu üç olayda farklı kabul/dosyalama takvim günü gerçek hata değildir. Ne orijinal SEC kabul anını ne de resmî filing date değerini düzeltiyoruz.

## Kalan önemli PIT sınırı

SEC'in başvuru kabul anı, verinin piyasaya tam ne zaman açıklandığını tek başına kanıtlamaz. SEC, 17:30 ET sonrası bazı dosyalamaların izleyen iş günü yayımlandığını belirtir. Önceki Faz24k denetiminde fact available_at kabul anından önce çıkmadı; buna rağmen SEC public dissemination zamanları kanıtlanmadı.

Bu nedenle resmi tarih farkı açıklansa bile:
- PUBLIC_DISSEMINATION gate BLOCKED_UNKNOWN kalır.
- Tarihsel SimFinId/CIK/share class onayı 0 kalır.
- Genel 20 SEC tarih farkının burada sadece bu üçü doğrudan SEC.gov index alanlarıyla karşılaştırıldı. Diğer 17'ye kanonik onay yok.
- Faz24k JSON, canlı/yedek SQLite, SEC JSON, 12,3 milyon SEC fact, SimFin CSV, fiyatlar ve modeller değişmez.

## Windows çevrimdışı doğrulama

Aşağıdaki araç 2026-10-09 tarihinde birincil SEC index sayfalarından elle doğrulanıp koda kaydedilen accession/form/CIK/ET/filing_date alanlarını, Windows'taki gerçek Phase24k JSON ve SEC submissions root/archive kaynaklarına karşılaştırır. Çalışırken SEC web sayfalarını yeniden çekmez; dolayısıyla rapor *çalışma anında yeni bir canlı SEC doğrulaması* sayılmaz.

    cd E:\M10
    git pull --ff-only
    .\.venv\Scripts\python.exe -m scripts.phase24l_inod_sec_official_date_crosscheck

Rapor: %LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24l\inod_sec_primary_filing_date_review.json

Beklenen: official_SEC_10Q_filing_date_matches=3, unexplained_date_difference_in_these_three=0, public_dissemination_timestamps_verified=0, PIT_certified=false.

Sonraki iş: Kamuya yayımlanma zamanı/PIT erişilebilirlik sınırını doğrulamak, kalan diğer tarih olayları için kapsam incelemesi yapmak ve tarihsel CIK, delisted üyelik, düzeltilmiş fiyat serilerini ayrı kapılardan geçirmek. Ücretli API yok, SEC yeniden indirme yok, SQLite DB kopyalama yok.
