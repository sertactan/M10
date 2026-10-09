# Faz 24j — INOD SEC kabul zamanı ve New York dosyalama tarihi incelemesi

## Windows'ta kanıtlanmış başlangıç durumu

Faz 24i (2026-10-09): 1.007 SEC başvurusundan 53'ünde incelemeye uygun SEC fact bağlantısı; 954'ünde fact bağlantısı yok. Eşleşmeyen **64 adet 10-K/Q (düzeltmeler dahil)** 2024–2025 hedef dönemi **dışında** (eski yıllarda). Hedef 2024-01-01–2025-09-30 dosyalama tarihinde *tarih filtresini geçen* finansal başvurularda missing accession–fact: **0**. Ancak **20** SEC kaydı `acceptance_UTC_date < filing_date` nedeniyle ana eşleştirme setine alınmamış; dolayısıyla bu sonuç kanonik PIT onayı değildir.

Kaynak görüntülerde 2025-05-08 21:49 UTC → 2025-05-09 `filing_date` örneği var. ABD Doğu yaz saatinde 21:49 UTC = 17:49 ET, yani belirli SEC formları için saat 17:30 sonrası işleme ihtimali vardır. **Bu yalnızca aday açıklama**; her formun resmi dosyalama günü kuralı, SEC tatil takvimi ve gerçek SEC kaynak kaydı doğrulanmadan `filing_date` veya `accepted_at` tarihlerini değiştirmiyoruz.

## Yeni araç

`scripts/phase24j_inod_sec_acceptance_et_review.py`:
- Önceki Faz 24i/24h özel raporlarının durumlarını ve gerçek SEC root/archive dosyalarını yeniden karşılaştırır;
- 20 karantinadaki kaydı tam listeler; `America/New_York` saat diliminde orijinal kabul zamanını gösterir;
- **17:30 ET sonrasında** ve `filing_date` bir sonraki **hafta içi günü** ise `AFTER_1730_ET_NEXT_WEEKDAY_CANDIDATE_REVIEW` (resmî onay DEĞİL) sınıfını verir;
- ABD tatilleri, belirli form kuralları veya uyumsuz mesai saatleri için ayrı insan incelemesi ister;
- İndeksli SQLite **yedekten**, karantinadaki SEC `accessionNumber` kaydının finansal fact'i olup olmadığını ölçer;
- Hedef döneme düşen karantinadaki **10-K/Q kayıtlarını** özellikle sayar.

İnceleme sonucu:
- Mesai sonrası adaylarının tamamını kanonik PIT evrenine otomatik geri **almaz**;
- `SEC acceptanceDateTime` / `filingDate` değerlerini **asla değiştirmez**;
- Ağ/ücretli API/indirme, canlı SQLite veya yedek üzerine yazma ve Learning V3 yok.

## Windows komutu

```powershell
cd E:\M10
git pull --ff-only
.\.venv\Scripts\python.exe -m scripts.phase24j_inod_sec_acceptance_et_review
```

Rapor: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24j\inod_sec_acceptance_ET_review.json`

Özellikle `by_class`, `target_financial_anomalies`, `target_financial_with_existing_SEC_facts`, `target_financial_without_existing_SEC_facts` değerlerini paylaş.

Windows Python `tzdata` zaman dilimi verisi bulunmadığından `PHASE24J_BLOCKED` oluşursa, sistem tarihini tahmin etmeye çalışma. Gerekirse mevcut Python ortamında `tzdata` sağlayıcısını kurduktan sonra tekrar dene; canlı DB veya SEC dosyalarını değiştirme.

Bu audit, gelecekteki SEC fiyat/PIT doğrulamalarında sahte tarih düzeltmesi veya geleceği bilme (look-ahead) hatasını önlemek içindir.
