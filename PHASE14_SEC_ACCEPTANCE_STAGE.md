# Görev 4 — SEC Submissions Kabul Saati Kanıtlarının Hazırlanması

**Durum:** Denetim başarılı; gerçek SEC accepted_at onarımı henüz TAMAMLANMADI.
Windows Companyfacts importer çalışırken canlı SQLite veritabanına ikinci
bir yazma işlemi yapılmaz. Bu yeni araç yalnızca kanıt hazırlığı yapar.

## Denetim neden 500/500 eksik bildirdi?

`bootstrap_wf1_free_data` toplu Companyfacts ZIP içe aktarırken SEC
`filing_map` boş olabilir. Companyfacts finansal değerler ve dosyalama
tarihi sağlar, ancak orijinal SEC `acceptanceDateTime` için ilişkili
SEC submissions belgesini ayrıca elde etmek ve accession numarasıyla
eşleştirmek gerekir. Böyle bir dosya indirildi diye tarihsel
erişilebilirlik hemen onaylanamaz: security_id/CIK, accession, filing
tarihi, timezone, eski available_at ve olası yeniden bildirilen değerler
birlikte doğrulanmalıdır.

## GitHub üzerinde hazırlanan güvenli aşama

`scripts/phase14_sec_acceptance_stage.py`: mevcut kurulu DB'yi
SQLite `mode=ro` ve `PRAGMA query_only=ON` ile okur. **Hiç SEC API
çağrısı, ağ isteği, veri yazımı, migrasyon veya otomatik düzeltme yapmaz.**
Bir yerel SEC submissions JSON dosyasını okuyup CIK, accession,
acceptanceDateTime (mutlaka timezone-aware) ve fact kayıtlarını
eşleştirerek kimlik veya zaman çelişkisi bulunmayan kanıt adaylarını
JSON raporuna koyar. Tek CIK birden fazla security_id'ye aitse
otomatik eşleştirme yapmaz; tarihsel share-class kimliğini ayrıca
doğrulamak gerekir.

Önemli: Bu araç *ilk aşamadır*. En fazla 25 örnek fact_id verir;
tüm veritabanındaki kayıtları veya tüm şirketleri dönüştürmez.
Kaynak dosyasının SHA256 değerini rapora koyar; SHA256 tek başına
dosyanın gerçekten SEC'den geldiğini kanıtlamaz.

## Çalıştırma (SEC aktarımı tamamlandıktan sonra)

Kaynak: resmi SEC submissions dosyası, örnek CIK (maskeli olmayan
kamuya açık issuer kodunu kullanın):
`https://data.sec.gov/submissions/CIK0001408075.json`

Orijinal SEC HTTP yanıtını değiştirmeden `E:\Meridyen_SEC\CIK0001408075.json`
adıyla bilgisayara kaydedin. API anahtarı kullanılmaz; SEC'in erişim
kurallarına ve User-Agent tanımlama gereğine uyulmalıdır. Yeni
indirme yapmadan önce mevcut SEC Companyfacts aktarımı bitsin.

    cd E:\M10
    git pull
    $db = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\operational.db"
    .\.venv\Scripts\python.exe -m scripts.phase14_sec_acceptance_stage --db "$db" --submissions-json "E:\Meridyen_SEC\CIK0001408075.json" --out "E:\Meridyen_Backups\sec_acceptance_stage_0001408075.json"

Bu rapor `EVIDENCE_STAGED_REVIEW_REQUIRED` veya
`NO_SAFE_MATCHES_REQUIRE_REVIEW` veya
`BLOCKED_CIK_IDENTITY_AMBIGUOUS` durumları üretir. Hepsi, henüz
veri tamirinin ve kanonik PIT doğrulamasının yapılmadığını belirtir.

## Görev 4'ün eksik kalan asıl işi

1. SEC toplu aktarımın tamamen bitmesi ve SQLite online backup.
2. Asıl SEC submissions kabul zamanı için kaynağı doğrulanmış ve
   oran sınırlı, indeksli toplu toplama; geçmiş `filings.files`
   parçalarını da ele alma.
3. Accession/CIK + share-class ve tarih doğrulamasından geçen
   fact'lerin yeni kanıt katmanına eklenmesi, hiçbir kaydı
   daha erken erişilebilir hale getirmeme.
4. Zaman tutarlılığı testleri, tam dönem örnekleme ve WF9
   fail-closed kontrolü.

Bu adımlar kanıtlanmadan Görev 4 veya WF9 `COMPLETE` sayılmaz.


## Sonraki adım: çok-dosyali SEC arşiv uzlaştırması (2026-10-08)

Yeni \`scripts/phase14_sec_submissions_archive_reconcile.py\` mevcut **tek CIK/son 25 örnek** raporunun yerine geçmeden, şirketin SEC \`filings.recent\` kayıtlarını ve aynı kök dosyadaki \`filings.files\` listesinde belirtilen **eski** \`CIK##########-submissions-001.json\` gibi arşivleri, yerel diskte varsa, birlikte uzlaştırır. SEC'ten otomatik indirme yapmaz; 2013–2024 tarihsel derinlik için bu eski JSON belgelerinin ayrıca SEC'den saklanmış olması gereklidir.

Önce canlı SEC importu bittikten sonra daha önce alınmış, **bütünlük kontrolü yapılmış, ayrı** SQLite yedeğini kullanın. Mevcut PIT otomasyonu ve canlı SQLite üzerinde işlem yapmayın. İndirilmiş SEC orijinal yanıtlarını \`E:\Meridyen_SEC\submissions\` içinde saklayın; CIK ile arşiv dosya adları tam eşleşmelidir.

PowerShell örneği:

\`\`\`powershell
cd E:\M10
git pull --ff-only

.\.venv\Scripts\python.exe -m scripts.phase14_sec_submissions_archive_reconcile \`
  --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" \`
  --submissions-dir "E:\Meridyen_SEC\submissions" \`
  --max-issuers 5 --max-accessions 1000 --max-facts-per-accession 2000 \`
  --out "E:\Meridyen_Backups\sec_acceptance_archive_review.json"
\`\`\`

**Güvenlik ve sınırlar:**

- SQLite bağlantısı \`mode=ro\`, \`PRAGMA query_only=ON\`. Sadece mevcut \`idx_fundamental_accession\` indeksi üzerinden sınırlı eşleştirmeler yapılır; yeni DB, index, ALTER/UPDATE, SEC ağ isteği veya indirme **yoktur**.
- Accession, kaynak SHA-256, SEC \`acceptanceDateTime\` timezone, form, filingDate, fact period_end, stored accepted_at/available_at kontrol edilir. Ayrı \`security_id\`'lere bağlanan tek CIK, eksik kaynak, çelişkili accession veya lookahead otomatik onaylanmaz.
- \`--max-issuers\`, \`--max-accessions\` ve \`--max-facts-per-accession\` sınırları sonuçları **kısıtlar**; kapsam tam sayılamaz. \`missing_archival_documents\` varsa tarihsel arşiv kapsaması tamamlanmış değildir. Arşivi eksik bir şirkette son dönem kanıt adayları bulunabilse bile tüm 2013–2024 tarihi doğrulanmış olmaz.
- Araç dosya hash'ini kaydeder ancak indirmenin gerçekten SEC kaynaklı olduğunu **bağımsız olarak doğrulamaz**. Bir adayı \`evidence_candidates\` listesine koymak, fact kaydına \`accepted_at\` eklemek, mevcut \`available_at\` değerini erkene almak, S15 skorlarını yeniden hesaplamak veya WF9'u açmak değildir.
- Sonraki ayrı görev: SEC yanıtlarının meşruiyetini ve historical share-class kimliğini doğrulayan kontrollü indirme; uzman gözden geçirme ve ayrı kanıt deposu; mevcut fact tarihlerini ileri alma gereksiniminin ayrı PIT testleri. **Canonical kapalı kalır.**
