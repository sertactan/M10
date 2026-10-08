# Phase 14 — SEC Submissions güvenli kaynak indirme

**Kod durumu:** Kaynak indirici ve offline birim testleri geliştirildi. **Windows gerçek SEC indirmesi ve 12,2 milyon satırlık kabul saati düzeltmesi henüz yapılmadı.** Kanonik model, WF9 ve Learning V3 durumları değişmedi.

## Amaç

Orijinal SEC submissions JSON yanıtlarının güncel filings.recent bölümünü ve kökteki filings.files listesinin işaret ettiği tarihsel CIKxxxxxxxxxx-submissions-xxx.json arşiv dosyalarını, güvenli ve kademeli biçimde kaydetmek. Bu kaynaklar daha sonra salt-okunur phase14_sec_submissions_archive_reconcile aracıyla test edilir. Collector **SQLite'a bağlanmaz**; operational.db, mevcut fiyatlar, API anahtarları ve PIT zamanlayıcısı ile etkileşime girmez.

**SEC resmi kuralı:** En fazla **10 istek/saniye** (aynı kullanıcı/IP toplamı). Bu uygulama varsayılan olarak **her 0,5 saniyede en fazla bir istek** yapar. Başka SEC importer/araçları aynı anda açıkken çalıştırmayın: farklı uygulamaların toplam isteklerini ölçemez. Kullanıcıya ait gerçek irtibat bilgisi içeren SEC_USER_AGENT gerekir; program otomatik sahte iletişim bilgisi kullanmaz.

Kaynak: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data

## Windows üzerinde test (önce yalnızca önizleme)

Önce var olan SEC Companyfacts aktarımının ve PIT toplama işleminin bitmesini bekleyin. Güncelleme yapan yerel süreç varken git pull ile çalışan kodu değiştirmeyin.

PowerShell:

    cd E:\M10
    git pull --ff-only

    # Hiç ağ isteği veya dosya oluşturma yapmaz.
    .\.venv\Scripts\python.exe -m scripts.phase14_sec_submissions_collect --cik 1408075 --out-dir "E:\Meridyen_SEC\submissions"

## Bilinçli tek şirket pilotu

API anahtarı gerekmez. SEC kimlik tanımı için **yerel** PowerShell'de, gerçek kendi e-postanızı kullanarak ayarlayın (e-postanızı GitHub'a veya bu sohbet içine yapıştırmayın):

    $env:SEC_USER_AGENT = 'MeridyenResearch contact@your-real-domain.tld'

Örnekteki e-postayı kendi gerçek iletişim adresinle değiştir. Sonra:

    .\.venv\Scripts\python.exe -m scripts.phase14_sec_submissions_collect --cik 1408075 --out-dir "E:\Meridyen_SEC\submissions" --max-issuers 1 --max-requests 10 --daily-budget 60 --min-interval 1.0 --execute

**Önemli:** İndirme işlemi yalnızca --execute ile başlar. 10 istekten fazla arşiv dosyası varsa STOPPED_REVIEW_REQUIRED ve SEC_RUN_REQUEST_BUDGET_EXHAUSTED raporu gelir; bu beklenen güvenli durdurmadır. Aynı komutu sonra tekrar çalıştırınca sağlam yerel dosyalar checksum ile doğrulanarak atlanır ve yalnızca eksikler indirilir. 60 günlük sınır UTC gününe göre yerel dosyada tutulur; SEC'in kendi sunucu sınırı bundan ayrıca bağımsızdır. 403/429/503'te otomatik retry veya anahtar rotasyonu yoktur.

İndirme sonrası (yalnızca doğrulanmış ayrı SQLite yedeğinde):

    .\.venv\Scripts\python.exe -m scripts.phase14_sec_submissions_archive_reconcile --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" --submissions-dir "E:\Meridyen_SEC\submissions" --max-issuers 1 --max-accessions 1000 --out "E:\Meridyen_Backups\sec_acceptance_archive_review_pilot.json"

## Çıktılar ve sınırlar

E:\Meridyen_SEC\submissions klasöründe:
- CIKxxxxxxxxxx.json: orijinal yanıt, tek sefer saklanır.
- Kökün bildirdiği CIKxxxxxxxxxx-submissions-xxx.json arşivleri.
- sec_sources_manifest.json: SHA-256, SEC URL'si, edinme saati ve edinme biçimi.
- sec_utc_request_budget.json: yerel UTC/gün deneme sayısı, ağ isteğinden **önce** ayrılır.
- sec_download_progress.json: COMPLETE_SOURCE_DOWNLOADS_NOT_PIT_CERTIFIED veya STOPPED_REVIEW_REQUIRED, son belge ve sayaçlar.
- .phase14_sec_submissions_collect.lock: tek süreç kilidi. **Görev aktifken elle silmeyin.** Program aniden kapanırsa kilit kalabilir; önce işlem PID'sini ve SEC durumunu kontrol edin.

Aynı CIK tekrar çalıştırıldığında indirilen kaynakların üstüne yazılmaz. filings.recent zaman içinde değiştiği için yeni bir ham SEC sürümü almak istiyorsanız eski seti bozmadan **ayrı tarihli çıktı klasörü** açın.

Program yalnızca sabit https://data.sec.gov/submissions/ HTTPS kaynağına izin verir; HTTP yönlendirmelerini kabul etmez, 20 MB/dosya üst sınırını uygular, JSON dizilerini ve CIK/dosya adlarını doğrular; şüpheli içerik, uyumsuz checksum veya eksik arşiv durumunda fail-closed davranır. Diskte var olan ama bağımsız alınmış kaynaklar PREEXISTING_LOCAL_SOURCE_NOT_VERIFIED olarak işaretlenir.

Kaynağın SHA-256'sı tek başına SEC'den geldiğini veya SEC kabul zamanının tam PIT kalitesini **kanıtlamaz**. Bu kod kabul tarihlerini canlı veritabanına yazmaz, historical share-class kimlik problemlerini çözmez, veri düzeltmesi/promotion yapmaz. Kapsam ve kaynak onayı sonrası ayrı kanıt ve gerçek WF9 kontrolleri gereklidir.

**Güvenlik:** SEC belgelerini, operational.db veritabanını, kullanıcı e-postasını ya da ham şirket arşivlerini herkese açık sertactan/M10 GitHub deposuna commit etmeyin.
