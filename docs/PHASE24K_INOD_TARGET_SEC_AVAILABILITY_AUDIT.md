# Faz 24k — INOD 2024–2025 SEC kabul zamanı ↔ finansal available_at kanıtı

## Önceki gerçek Windows sonuçları

- Faz 24g/24h: 1.007 geçerli SEC başvuru numarası, bunların 53'ünde 2.555 `fundamental_facts_source` satırı eşleşmesine uygun kanıt.
- Faz 24i: 64 adet eski 10-K/10-Q (amendment dahil) başvurusunun finansal fact karşılığı yok; **2024-01-01–2025-09-30 arasında geçerli/karantina dışı raporlarda eşleşmeyen = 0**.
- Faz 24j: 20 tarih uyuşmazlığının **19'u** 17:30 New York saati sonrası takip eden hafta içi günle tutarlı; **1'i** tatil/forma özgü kural incelemesi istiyor.
- Bu 20 kayıt arasından **3 adet 2024–2025 finansal raporunda mevcut SEC accession–fact eşleşmesi var (3/3)**. Bu raporların kabul/erişilebilirlik zamanları henüz kanonik PIT düzeyinde doğrulanmadı.

## Yeni salt-okunur kontrol

`scripts/phase24k_inod_target_sec_availability_audit.py` indirilmiş INOD root+arşiv SEC JSON belgeleri ile önceki Faz 24i/24j sonuçlarını karşılaştırır, hedef dönemde dosyalanmış **tüm 10-K/10-Q (amendment dahil)** accession'larını, 3 karantinadaki finansal accession dahil, tek sefer inceler. Elde bulunan 9,21 GB **SQLite yedeğini** `mode=ro` ve mevcut `idx_fundamental_accession` indeksini kullanarak tarar. Tüm 12,3 milyon fact'i yeniden saymaz.

Her SEC accession için mevcut SEC fact'lerde:
- `available_at` parse edilebilir ve **özgün SEC accepted_at anından önce değil mi?** Look-ahead riski varsa kesinlikle blokla.
- Var olan fact `accepted_at` SEC kaynak anıyla çelişiyor mu?
- `filing_date`, `form_type`, `period_end` kaynakla uyumlu mu?
- SEC'in after-hours idari filing_date kaydı ilgili form için henüz doğrulanmamış mı?
- Fact sayısı 2.500 satır güvenli sınırını aşıyor mu?

Sonuçlar iki sınıfın birine girer: `SOURCE_AND_FACT_TIME_FIELDS_CONSISTENT_NOT_PIT` veya `EVIDENCE_GAPS_REQUIRE_HUMAN_REVIEW_NOT_PIT`. İlki bile **kanonik PIT sertifikasyonu değildir**.

## Windows PowerShell

```powershell
cd E:\M10
git pull --ff-only
.\.venv\Scripts\python.exe -m scripts.phase24k_inod_target_sec_availability_audit
```

Rapor:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24k\inod_sec_financial_timestamp_evidence.json`

Özellikle `review_class` ve `reason_counts` çıktısını gönder. Bu iki alan gerçek `available_at` problemlerini, şimdilik doğal olarak bekleyen SEC dosyalama günü kurallarından ayıracak.

## Kısıtlar

- Ücretli API/ağ/SEC indirmesi **yok**.
- Yeniden 9,21 GB yedek **yok**.
- Canlı/yedek SQLite, SEC JSON, SimFin, kanonik fiyatlar veya S15.3/S16 modelleri **değişmez**.
- SEC kabul zamanı, `filing_date` ve `available_at` **otomatik düzeltilmez**.
- Tarihsel SimFinId–CIK/share-class doğrulaması, delisting ve adjust edilmiş fiyatlar ayrı kapıdır.
- Learning V3 başlatılmaz; gerçek 2024–2025 Windows çalışması tamamlanmadan **hiçbir kanonik onay veya öğrenme başarısı** iddia edilmez.
