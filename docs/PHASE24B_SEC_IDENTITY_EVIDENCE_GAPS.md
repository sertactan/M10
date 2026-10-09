# Faz 24b — SEC kabul zamanı ve tarihsel ticker kanıtı denetimi

**Kapsam:** 2024-01-01 ile 2025-09-30 tarihleri arasında SimFinId ↔ yerel CIK adayları. Gerçek Faz 24 Windows sonucu: 5.307 SimFinId, 3.638 tek mevcut CIK adayı, 178 zayıf mevcut CIK adayı, 1.485 CIK adayı yok, 6 çoklu/çakışan aday; **0 tarihsel kimlik sertifikasyonu**.

Bu yeni araç `scripts/phase24b_sec_identity_evidence_gaps.py` sadece mevcut kaynakları okur:
- Önceki `phase24/simfin_sec_cik_candidates.json` raporunu;
- M10'un var olan `operational.db` dosyasındaki `security_master`, varsa tarihsel `ticker_aliases` ve `filing_records_source` tablolarını;
- Tüm SQLite erişimi `mode=ro` ve `query_only=ON`. Tablolardaki on milyonlarca SEC fact satırını yeniden saymaz ve SHA ile doğrulanmış fiyat kaynağını tekrar indirmez.

**İki ayrı kanıt sınıfı:** SEC'de aynı aday CIK için ilgili tarih aralığında, erişilebilir `accepted_at` saatli bir filing kaydı bulunması; tarih aralığı, kaynak ve availability tarihleri tanımlanmış ticker takma adı kaydı bulunması. Bunlar **ayrı ayrı bile SimFinId'nin SEC şirketiyle kesin tarihsel eşleştiğini kanıtlamaz**: bir CIK birden çok hisse sınıfına sahip olabilir ve yerel SEC kaynak eşleştirmesi hatalı olabilir.

Sorgular güvenlik için sınırlandırılır: CIK başına en fazla 500 ilgili SEC filing ve 100 alias; sınırı aşan kayıtlar `evidence_lookup_truncated` ile raporlanır. `filing_records_source` tablosunda `security_id` ile başlayan indeks yoksa binlerce pahalı arama yapılmaz; tablo kanıt için kullanılamaz işaretlenir. Eksik kanıtlar **eksik** kalır; 0 otomatik CIK sertifikasyonu.

## Windows komutu

```powershell
cd E:\M10
git pull --ff-only
.\.venv\Scripts\python.exe -m scripts.phase24b_sec_identity_evidence_gaps
```

Rapor: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24b\sec_identity_evidence_gaps.json`.

Kısa çıktıda `review_classes`, `filings_table_available`, `aliases_table_available`, `simfin_ids_reviewed` ve `evidence_lookup_truncated_ids` incele. Herhangi bir CIK eşleşmesini otomatik olarak kanonik üyeliğe/promosyon listesine taşıma.

**Henüz yapılmamış zorunlu doğrulamalar:** SEC submissions ORİJİNAL kabul timestamp/JSON arşivlerinin ve gerçek ticker effective-date olaylarının kanıtı; share-class FIGI / tam şirket kimliği; delisting ve cash-payoff; kurumsal işlemler ve adjusted-close metodunun bağımsız kontrolü; gerçek fiyat kapsamı ve veri kullanım hakları; ileri-yürüyen backtest ve bağımsız out-of-sample değerlendirme.

Ücretli API, ağ isteği, yeni indirme, SEC fact güncellemesi, fiyat/kanonik model değişimi veya model eğitimi gerçekleştirmez.
