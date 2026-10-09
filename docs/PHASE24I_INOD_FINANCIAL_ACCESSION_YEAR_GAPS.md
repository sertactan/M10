# Faz 24i — INOD 10-K/10-Q eksiklerini hedef tarih aralığına ayır

**Son gerçek Windows Faz 24h sonuçları (2026-10-09):**
- INOD SEC CIK *adayı* `0000903651` için 1.007 kaynak başvurusu indekslendi.
- 53 başvuru / 2.555 finansal fact eşleşmesi yalnızca incelemeye uygun aday, **kanonik PIT değil**.
- 954 başvurunun fact eşleşmesi yok. Bunların yalnızca **64 adedi** SEC `10-K`, `10-K/A`, `10-Q`, `10-Q/A` formlarında: sırasıyla 15,3,43,3 (tüm tarihsel yıllar).
- SEC kaynaklarında 20 `acceptance_UTC_date < filing_date` görünümü var; tarih hesapları ve özgün kanıt incelenmeden otomatik düzeltme yapılmayacak. 10-K'da 2, 10-Q'da 8 görünüm var; diğer formlarda 10.
- Ekran görüntüsünde 2021 ve 2023 döneminden örnekler de görülüyor. Bu nedenle **64 belgenin hepsini 2024–2025 veri açığı kabul etmek hatalı**.

## Yapılan iş

`scripts/phase24i_inod_financial_accession_year_gaps.py` aşağıdaki kaynakları **salt-okunur** kullanır:
1. Önceki `phase24h/inod_sec_form_gap_review.json` raporu,
2. Mevcut yerel `sec_submissions/CIK0000903651.json` kök + 1 tarihsel SEC arşiv JSON,
3. Önceden `quick_check=ok` denetiminden geçmiş **SQLite yedek** `phase24g/operational_inod_offline_backup.db`.

Kayıt türü ve SEC `filing_date` yılı bazında ayrı ayrı hesaplar:
- 10-K/10-Q ve amendment'ların tüm tarihsel yıllardaki fact eşleşme / eşleşmeme sayısı
- **01.01.2024–30.09.2025 dosyalama tarihli** ve eşleşme bulunmayan belgelerin adedi ve accession aday listesi
- Bu aralık **dışında** bulunan ve yanlışlıkla 2024–25'e eklenmemesi gereken raporlar
- SEC kaynak zamanındaki uyumsuzlukları ayrı karantina/sınırlı insan inceleme örnekleri (kaynakta 20 adet)
- Önceki Faz 24h form ve sayım rakamlarıyla fail-closed uzlaştırma.

**Bu ölçüm raporun finansal dönemini sertifikalandırmaz** (yalnızca SEC filing_date).
Accession match yokluğu SEC kaynak belgelerinin veya XBRL finansalların eksik olduğunu tek başına ispatlamaz. (\text{SEC accepted UTC date} < \text{filing date}\) görünümünü keyfi bir gün öteye taşımıyoruz.

## Windows komutu

```powershell
cd E:\M10
git pull --ff-only
.\.venv\Scripts\python.exe -m scripts.phase24i_inod_financial_accession_year_gaps
```

Rapor `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24i\inod_financial_accession_gaps.json`.

Sadece kısa PowerShell çıktısını paylaş: `2024_2025_financial_no_fact_count`, `2024_2025_financial_no_fact_by_form`, `out_of_window_no_fact_by_year` ve `UTC_acceptance_before_filing_date_count`. Özel SEC JSON/SQLite/SimFin arşivini GitHub'a yükleme.

## Çıkış kapısı

**Faz 24j için:** Kaynak SEC arşivden 2024–2025'e düşen her 10-K/10-Q accession ve reddedilen 20 tarih olayını belge türü, doğru özgün zaman, gerçek SEC accession ve 2024–25 PIT erişilebilirlik kurallarıyla kaynak kanıtına bağla; bağımsız doğrulama olmadan hiçbir SimFinId ↔ CIK veya adjusted fiyat serisini otomatik sertifikalandırma.

**Bu aşamada:** SEC'yi yeniden indirmiyoruz, 9,21 GB yedeği yenilemiyoruz, ücretli API/ağ kullanmıyoruz, SEC/SimFin fiyatı, üretim DB'si, kanonik modeller veya Learning V3'ü değiştirmiyoruz.
