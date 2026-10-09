# Faz 24h — INOD SEC 1.007 başvuruyu türe göre sınıflandır

Son yerel INOD pilotu:
- `operational_inod_offline_backup.db`: 9,21 GB, `PRAGMA quick_check=ok`
- Kaynaklar: 1 SEC submissions kök JSON, 1 tarihsel arşiv; yerel SHA manifest denetimi başarılı
- **1.007 geçerli başvuru**; ilk 1.000'de 53 adet incelemeye uygun başvuru ve 2.555 bağlı finansal fact; son 7'de eşleşme yok
- 20 adet `acceptance_before_filing_date` sayımı SEC kaynak okumasında **global** sayaçtır, iki bölümde ayrı ayrı 20 yeni hata değildir
- İlk rapor 947 `accessions_without_matching_facts`, son rapor 7: toplam **954**; bunun XBRL kaybı olup olmadığı **başvuru türü** denetlenmeden bilinemez

Yeni modül: `scripts/phase24h_inod_sec_form_gap_review.py`.

## Windows PowerShell

```powershell
cd E:\M10
git pull --ff-only
.\.venv\Scripts\python.exe -m scripts.phase24h_inod_sec_form_gap_review
```

Bu modül mevcut Faz14 ilk ve tail JSON raporlarının aynı yedek dosyaya, aynı SEC klasörüne ve doğru `accession_offset` sayfalamasına işaret ettiğini denetler. Kök+arşiv SEC belgelerinden geçerli başvuruları yeniden indeksler, 20 `acceptance_before_filing_date` satırını **bir kez** sayar ve başvuru türlerini (`10-K`, `10-Q`, `8-K`, `4` vb.) kategorize eder. Halihazırda incelemeye uygun 53 başvuruyu iki rapordan yükler; diğer 954 başvuruda 9,21 GB'lık **yedek** SQLite dosyasını `mode=ro` ile, mevcut `idx_fundamental_accession` indeksi üzerinden sadece indeksli existence sorguları yapar. `COUNT(*)` ile milyonlarca fact'i yeniden saymaz.

Ölçümler:
- `forms_without_financial_facts` ve `forms_with_reviewable_financial_facts`
- `forms_with_facts_but_not_reviewable` (ret/çelişki kontrolü)
- `source_before_filing_date_forms`, sınırlı tarih uyuşmazlığı örnekleri
- `valid_accessions_total`, `reviewable_accessions_total`, `total_without_matching_facts`

**Yorum uyarıları:** Bir 8-K veya insider işlemi belgesinde XBRL Companyfacts satırı bulunmayabilir; başvuru eşleşmedi diye eksik veri saymayız. Kaynak saatini otomatik ileri taşımayız. Bu rapor **tarihsel SimFinId–CIK kanonik sertifikasyonu, SEC kökeninin bağımsız doğrulanması veya PIT backtest onayı değildir.**

Kod/CI için yapay sentetik SEC-fixture testleri kullanılır; sonuç diye gerçek sayıları uydurulmaz. Gerçek Windows sonuçları çalıştırılmadan bilinemez. Mevcut 12.313.284 SEC kaydı, özgün SimFin CSV, 21 aylık PIT kaynakları ve S15.3/S16 modelleri değiştirilmez. Ağ yok; ücretli API yok, yeni indirme yok.

Rapor: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24h\inod_sec_form_gap_review.json`.
