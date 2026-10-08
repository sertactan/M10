# Phase14 — SEC kabul zamanı ayrı kanıt günlüğü

**Durum: kod ve testler hazır; gerçek Windows kaynak indirmesi / SEC kanıt yayını BEKLİYOR.** Bu aşama original SEC submissions belgelerini ve daha önce oluşturduğumuz offline uzlaştırıcıyı tekrar okuyup, adayları yalnızca ayrı bir inceleme günlüğüne yazar. Canlı operational.db, SEC Companyfacts içe aktarımı, mevcut PIT zamanlayıcısı, S15/S16 kanonik modeller ve WF9 değişmez.

## Güvenli sıra

1. Diğer SEC/PIT indirmeleri bitsin; API kotası dolmuşsa yeni istek denemeyin.
2. Resmi SEC submissions kaynaklarının gerçek, orijinal JSON'larını Phase14 kolektörüyle yerel SEC klasörüne alın. Örnek bir CIK için önce küçük --execute pilotu, 403/429/503 görülürse durun.
3. Canlı veritabanı çalışırken asla ona yazmayın. Önceden alınmış bütünlüğü doğrulanmış SQLite offline yedeğini kullanın.
4. Önce önizleme, sonra gerekirse --execute ile yalnızca ayrı, PRIVATE SQLite kanıt günlüğüne ekleme.

PowerShell (kaynak belgeler gerçek anlamda indirilip doğrulandıktan sonra):

    cd E:\M10
    git pull --ff-only
    .\.venv\Scripts\python.exe -m scripts.phase14_sec_acceptance_evidence_journal --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" --submissions-dir "E:\Meridyen_SEC\submissions" --journal "E:\Meridyen_Backups\sec_acceptance_review.sqlite3" --max-issuers 1 --max-accessions 1000

Önizleme hiçbir journal dosyası oluşturmaz. Sonuçta candidate_accessions, reconciliation_counts, archival_coverage_complete ve source_provenance_manifest_checked alanlarını inceleyin. Yeni veri bulunması **WF9 aktivasyonu değildir**.

Aynı komutu sonuna --execute ekleyerek tekrar çalıştırabilirsiniz:

    .\.venv\Scripts\python.exe -m scripts.phase14_sec_acceptance_evidence_journal --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" --submissions-dir "E:\Meridyen_SEC\submissions" --journal "E:\Meridyen_Backups\sec_acceptance_review.sqlite3" --max-issuers 1 --max-accessions 1000 --execute

## Güvenlik koşulları ve doğrulama

- Doğrudan SEC JSON kaynaklarının SHA-256 değerleri ile sec_sources_manifest.json belgesindeki SHA, resmi https://data.sec.gov/submissions/CIK....json URL'si ve dosya boyutu tutarlı olmalıdır.
- Kolektörün origin=FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT kaydı olmayan, örneğin eski elle indirilen PREEXISTING_LOCAL_SOURCE_NOT_VERIFIED dosyaları journal'a yazılmaz. Manifest ve hash eşleşmesi yalnızca **kaynak tutarlılığı sağlar**, bağımsız SEC özgünlük sertifikası değildir.
- Kaynaklar ve offline veritabanı sadece okunur; SQLite mode=ro, PRAGMA query_only ile önce yeniden uzlaştırılır. CIK-share class belirsizliği, accession kabul zamanı çatışması, tarih/form uyuşmazlığı, look-ahead, veya mevcut kayıtla çelişki bulunan accession aday olarak yayımlanmaz.
- --execute yalnızca bağımsız PRIVATE kanıt günlüğüne STAGED_FOR_MANUAL_REVIEW_NOT_CANONICAL statüsüyle yazar. Aynı aday ikinci kez eklenmez, çelişen bir sonraki kayıt geldiğinde bütün batch geri alınır. Orijinal SEC finansal verilerindeki available_at **erken tarihe çekilmez** ve accepted_at değiştirilmez.
- En fazla 1 şirket ve 1000 accession varsayılan partidir. Kalanları işlemek için --issuer-offset, --accession-offset ile yeni batch çalıştırın. Sonuçlarda next_issuer_offset, next_accession_offset vardır.
- Eksik tarihsel filings.files kaynakları varken bile güncel güvenli adaylar bulunabilir; bunlar 2013–2024 geçmişinin tam olduğunun kanıtı değildir.
- Ayrı journal ve kaynak JSON/DB asla herkese açık GitHub M10 deposuna commit edilmez. --journal deposunun içinde veya SEC kaynağı klasöründe olamaz.

Gerçek SEC indirmesi, şirket-hisse sınıfı tarihsel kimliği, resmi kaynak tarihleri, sonradan güncellenen/restated değerler ve kapsam gözden geçirilmedikçe hiçbir review adayı kanonik faktör üretimine geçirilmez. **WF9 hâlâ fail-closed.**
