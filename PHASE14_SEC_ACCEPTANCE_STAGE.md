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
