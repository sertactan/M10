# Faz 1 — SEC Companyfacts aktarımı: güvenli tamamlanma kanıtı

**Tarih:** 2026-10-09 (Asia/Tokyo)
**Takip:** https://github.com/sertactan/M10/issues/117
**Faz 0 temel PR:** https://github.com/sertactan/M10/pull/118

## Başlangıç durumu

Gerçek Windows SEC aktarımının güncel PID/stage bilgisi uzaktan görülemiyor.
Önceden bildirilen ~1,3 GB SEC aktarımı, bugün tamamlandı anlamına gelmez.
Çalışan eski importer yeni progress.json/lock üretmemiş olabilir.

### Güvenli çalışma sırası

1. Windows Görev Yöneticisi ile **eski veya yeni SEC importer işlemi var mı** kontrol et. Varsa hiçbir indirme/import başlatma ve canlı veritabanını kopyalama.
2. SEC işi bittikten sonra gerekirse M10'u da kapat, canlı SQLite üzerinde geçerli bir **SQLite online backup** oluştur. Veritabanını Windows Explorer ile gelişigüzel kopyalama; WAL verisi kaybolabilir.
3. Önce Faz 0 envanteri ve Data Control paneliyle ilerleme/checkpoint/lock durumunu kontrol et.
4. Faz 1 aracı **varsayılan güvenli modda** yalnızca Faz 0 metadata okur. Aşağıdaki onaylar olmadan ZIP ya da SQLite backup açmaz.
5. Üretimde aktif kodu değiştirirken mevcut importer çalışmıyor olmalı. Bu PR bağımlı taslak branch'tedir; Faz 0'ın öncesinde main'e merge edilmemelidir.

### Komutlar (Windows PowerShell, gerçek M10 checkout)

Sadece metadata (yan etkisiz; başlangıçta çalıştırılabilir):

    cd E:\M10
    $root = Join-Path $env:LOCALAPPDATA 'S153ResearchTerminal\runtime'
    python -m scripts.sec_companyfacts_phase1_audit --runtime-root "$root"

**Mevcut SEC importer durmadan diğer komutlara geçme.** İşlemin durduğunu Görev Yöneticisi üzerinden, SQLite online backup'ın bağımsız olduğunu kullanıcı olarak doğruladıktan sonra:

    python -m scripts.sec_companyfacts_phase1_audit --runtime-root "$root" --backup-db "E:\Meridyen_Backups\operational_SEC_online_backup.db" --operator-import-stopped --operator-online-backup-confirmed

Bu hafif sürüm ZIP central directory'yi kontrol eder, ancak tüm ZIP üyelerinin CRC taramasını yapmadığı için production geçişine izin vermez. Gerçek, durdurulmuş iş + bağımsız online backup varsa CRC taramasını isteyerek başlat:

    python -m scripts.sec_companyfacts_phase1_audit --runtime-root "$root" --backup-db "E:\Meridyen_Backups\operational_SEC_online_backup.db" --operator-import-stopped --operator-online-backup-confirmed --verify-zip-crc

CRC kontrolü sıkıştırılmış 1+ GB arşivi okuyup açabilir ve ciddi disk/CPU tüketebilir; importer çalışırken yapma. ZIP üyeleri diske çıkarılmaz. Araç yalnızca stdout'a JSON yazar; veri tabanına, SEC kaynağına veya GitHub'a hiçbir şey yazmaz.

**Not:** Bu komut ancak Phase1 branch dosyaları gerçekten Windows checkout'unda olduğunda çalışır. PR hâlâ draft ise aktif M10 çalışma kopyasının dalını değiştirme; gerekiyorsa ayrı checkout üzerinde çalış.

## Denetlenen kanıtlar

- SEC ZIP gerçekten var mı; .part veya lock kaldı mı?
- Yeni importer'ın checkpoint.stage == FINISHED ve bütün arşiv üyelerini taradığı kayda geçmiş mi?
- Arşiv central directory açılıyor mu, şüpheli/yinelenen CIK adı var mı, isteğe bağlı ZIP CRC tüm üyelerde doğru mu?
- Kullanıcının online backup dosyası **canlı operational.db ile aynı dosya mı?** Aynıysa kesin ret.
- Bağımsız SQLite backup quick_check ve SEC_EDGAR kaynaklı satır/issuer sayıları.
- Import checkpoint counters, backup SEC satır ve issuer sayılarından büyükse ret.
- Eski importer için checkpoint yoksa veya süreç bitişi kanıtlanmıyorsa **otomatik tamamlandı denmez**.
- SEC accepted_at gibi tarihsel PIT kaynak kanıtları bu fazda DOGRULANMAZ; Faz 2/3'ün görevidir.

## Durum sözlüğü

- BLOCKED_IMPORT_RUNNING_OR_OPERATOR_UNCONFIRMED: Olası importer/lock/.part veya manuel stop teyidi yok.
- AWAITING_VERIFIED_ONLINE_BACKUP: Gerçek SQLite online backup teyidi gerekli.
- BLOCKED_PARTIAL_OR_UNVERIFIED_SEC_EVIDENCE: ZIP CRC, checkpoint veya sayım uyuşmazlığı var.
- PHASE1_TECHNICAL_EVIDENCE_RECONCILED_REVIEW_REQUIRED: Sadece teknik F1 kanıtları tutarlı; **SEC PIT, kabul zamanı, tüm finansallar veya WF9 onayı DEĞİL.**

## Eksik kalan gerçek operasyon

Gerçek yerel veri tabanına bu GitHub/ChatGPT oturumundan erişemiyoruz. F1 "bitti" işareti için Windows'ta gerçek importer bitişi, doğru backup ve rapor sonucu gerekir. Çalışmayan veya başarısız bir importer'a rastlanırsa ayrı, kontrollü kurtarma planı hazırlanır; tekrar başlatmak bu audit aracının görevi değildir.