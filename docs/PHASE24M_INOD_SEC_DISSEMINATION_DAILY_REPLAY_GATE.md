# Faz 24m — SEC kamuya dağıtım zamanı bilinmeden günlük PIT backtest açılmaz

## Kanıtlanmış INOD durumu

Faz 24k gerçek Windows çalışması: 01.01.2024–30.09.2025 arası 7 finansal SEC accession, 337 fact satırı; 4 kaynak alanı tutarlı, 3 mesai sonrası dosyalama inceleme kaydı; SEC kabul anından önce available_at işareti raporlanmadı. Faz 24l Windows çalışmasında bu üç 10-Q için resmî SEC filing_date doğrulaması 3/3, açıklanamayan idari tarih farkı 0. **Public dissemination timestamp doğrulanan = 0. Kanonik PIT = false.**

SEC [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) açıklamasına göre bazı EDGAR dosyalamaları 17:30 ET sonrası başlatılırsa izleyen iş gününde kamuya dağıtılır; SEC kabul ve resmî dosyalama günü, kamuya yayım zamanını otomatik olarak kanıtlamaz. Bu kuralın her form / istisna / zaman aralığındaki ayrıntısı ayrıca kontrol edilmelidir.

## Yeni koruma aracı

`scripts/phase24m_inod_sec_dissemination_replay_gate.py`, yalnızca önceki Faz24k ve Faz24l özel JSON raporlarını çevrimdışı okur. Gerekli kanıtlar yetersizken:
- Hedef 7 accession'dan **7'si günlük PIT replay için BLOCKED** kalır;
- 3 onaylı **resmî dosyalama tarihi**, kamuya duyurulma zamanı olarak yorumlanmaz;
- İzleyen *hafta içi* gün sadece **inceleme için takvim adayıdır**, tatil/özel seans içermez ve *işlem onayı değildir*;
- Gerçek SEC kamuya yayım anı, tarihsel SimFinId/CIK/share-class eşleştirmesi ve NYSE/Nasdaq gerçek işlem seansı doğrulanana kadar **kanonik PIT ve Learning V3 izni sıfırdır**;
- SEC accepted_at, filing_date, available_at, fiyatlar, kanonik S15.3/S16 modeli, üretim/backup SQLite hiçbir şekilde değiştirilmez.

Bu kontrol **daha fazla kamuya-yayım kanıtı elde etmez**, yalnızca eksik kaynakla yanlışlıkla tarihi backtest'i açılmasını önler. Dolayısıyla 7/7 BLOCKED çıktısı araştırmanın başarısızlığı değil, doğru fail-closed davranışıdır.

## Windows çalıştırma

```powershell
cd E:\M10
git pull --ff-only
.\.venv\Scripts\python.exe -m scripts.phase24m_inod_sec_dissemination_replay_gate
```

Rapor: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24m\inod_sec_dissemination_replay_gate.json`

Beklenen:
- `financial_accessions_scoped=7`
- `official_filing_date_crosschecked=3`
- `SEC_public_dissemination_proven=0`
- `PIT_replay_eligible_count=0`
- `weekday_proxy_is_market_session=false`

## Sıradaki karar

PIT eğitimine geçmeden:
1. SEC kamuya yayımlanma zamanlarının resmî kanıtını edin veya açıkça timestamp belirsizliğiyle *ayrı, araştırma amaçlı, gecikmeli veri senaryosu* olarak tut;
2. Tarihsel SimFinId–CIK/pay sınıfı, delisted evren, düzeltilmiş fiyat ve gerçek borsa seansı takvimini doğrula;
3. Ancak tüm kapılar ayrı ayrı gerçek kanıtla açıldığında Phase25/26/27 kanonik backtest/öğrenme denemesi başlatılabilir.

**Ücretli API, yeni SEC indirmesi, 9,21 GB tekrar yedekleme ve üretim veritabanına yazma yok.**
