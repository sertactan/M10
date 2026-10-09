# Phase24c — Yerel SEC kanıt tabloları gerçekten dolu mu?

**Çıkış nedeni:** 2026-10-09 Windows Faz 24b denetimi 5.307 SimFinId için:
- 3.816 yalnızca şimdiki `security_master.cik` adayına bağlı;
- 1.485 hiç CIK adayı yok;
- 6 kimlik adayı çakışıyor;
- 0 tarihsel kimlik sertifikasyonu.
- `filing_records_source` ve `ticker_aliases` tabloları şeması kullanılabilir, fakat Faz 24b'de kanıt üreten tarihsel kayıt saptanmadı.

**Bu sıfır bulgu** tabloların boş olduğunu tek başına kanıtlamaz.
Faz 24c `scripts/phase24c_sec_evidence_source_coverage.py` ücretsiz, çevrimdışı, SQLite `mode=ro` ve `query_only=ON` modunda:
1. `filing_records_source` ve `ticker_aliases` tablolarından **en fazla ilk 300 kayıt** üzerinde varlık ve kabul zamanı / tarihli alias sinyallerini sayar (bunlar bütün tabloyu temsil etmek zorunda değildir).
2. Faz 24'e girmiş **3.973** yerel `security_id` adayından varsayılan **24 deterministik örnek** seçer. Her adayın `filing_records_source`, `fundamental_facts_source` ve `ticker_aliases` kayıtlarına yalnızca `security_id` ile başlayan indeks varsa bakar.
3. Her issuer için **150 satırdan fazla** okumaz ve sınırlı örnekte şu ayrımları yapar: SEC fact var ancak filing kaydı görünmüyor; filing var ama kabul saati boş; bazı SEC kabul saatleri var; yetersiz kanıt.
4. Örneklem yanlılığı ve kesilme bayraklarını raporlar. Yalnızca tablo varlığını denetler; 12.313.284 SEC fact satırını yeniden saymaz.

**Önemli:** `SOURCE_POPULATION_COMPLETE=false` ve `canonical_historical_identity_certified=false`. Örneklem yokluğu tüm şirkette kanıt olmadığı anlamına gelmez. SEC XBRL Companyfacts'den gelen `filing_date` orijinal SEC `acceptanceDateTime` yerine konamaz.

## Windows'ta

```powershell
cd E:\M10
git pull --ff-only

.\.venv\Scripts\python.exe -m scripts.phase24c_sec_evidence_source_coverage
```

Dosya: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24c\sec_evidence_source_population.json`

Çıktıda `global_bounded_sample`, `security_id_leading_indices`, `bounded_sample_diagnosis` değerlerini gönder.

**Bir sonraki seçim:** gerçekten SEC `filing_records_source` kayıtları boş/eksikse mevcut ücretsiz `phase14_sec_submissions_collect` aracını *tek CIK pilotunda* ve SEC rate-limit politikasına uygun kullanmayı değerlendireceğiz. Öncelikle daha önce indirilmiş SEC `submissions` arşivlerini arayacağız; aynı kaynağı tekrar indirmeyeceğiz. Yedek üstünde uzlaştırma yapılmadan canlı SEC veritabanına veya kanonik tablolara değişiklik yok.

Ağ yok, API yok, yeni büyük dosya yok, SEC/SimFin/PIT/Parquet/kanonik model değişikliği veya Learning V3 eğitimi yok.
