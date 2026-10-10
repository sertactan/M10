# MERİDYEN M10 — Faz 26B Windows yayın hazırlığı ve engeller

Tarih: 2026-10-10 (Asia/Tokyo). Taban: Faz 26A staging commit `fc21b3a`; ayrı dal `codex/phase26b-release`. Sürüm değişmedi: 1.0.6. Bu çalışma özel test paketi hazırlar; GitHub release ve PR merge yapmaz.

## Canlı DB değişiminin salt okunur incelemesi

Faz 26A snapshot'ı ve canlı `operational.db` aynı 9.208.848.384 bayt uzunluğundadır. Tam dosya karşılaştırmasında değişen blok yalnızca ilk 4 MiB bloktur; 9,2 GB boyunca **yalnızca dört bayt** farklıdır: SQLite başlığındaki change-counter ve version-valid-for sayaçları (26, 27, 94, 95 ofsetleri). Veri sayfalarının tamamı aynıdır. Seçilmiş tablo sayıları ve en yeni zaman alanları da eşleşti. Bu nedenle içerik kaybı veya kayıt değişikliği kanıtı bulunmadı. Online SQLite backup'ın başlık sayacı 1, canlı dosyanın sayacı 7935'tir; farklı dosya SHA değerini bu başlık farkı açıklar. Canlı dosyanın 20:49:46 +09:00 son değişim damgasına hangi sürecin sebep olduğu mevcut uygulama günlüğü ve çalışan süreç envanterinden tespit edilemedi. Nedeni kesin olarak bir sürece atfetmiyoruz.

Eski özel yedek manifesti `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase26a/verified_backup_20261010T26A/manifest.json` korunmuştur. Manifest SHA-256 `DF78DF697A2947BAD9F3D18C96E64AF6B540A19E7EEF537380A077C87B6BC530`; durum `BACKUP_AND_RESTORE_VERIFIED`, 654 girdi. Yeni M10 uygulama durumu yedeği, eski yedeğin kapsamını kopyalamadan, runtime, logs, backups, settings ve özgün fiyat kaynağını ayrı hedefte kapsar. Operasyonel DB'ye `mode=ro` ve `query_only=ON` ile bağlanıp SQLite online backup API kullanır; bağımsız restore probe ve SHA-256/SQLite quick_check uygular. Windows işletim sistemi imajı veya diğer kullanıcı dosyaları bu kapsamda değildir.

## Temiz seed ve paket

Faz 26A özel test paketindeki her iki seedin köken etiketi `LOCAL_DB_EXPORT_SMOKE_ONLY` idi; Faz 26B kapısı bunları reddeder. Ayrı boş dizinde mevcut kamu kaynak oluşturucuları çalıştırıldı: US 10.141 ham kayıt, `SEC_MIRROR_EDGARTOOLS` (SEC direct 403, ayna tarihi 2026-06-01); JP 4.280, TR 485, HK 3.075 kayıt, `FINANCEDATABASE_MIT_REFERENCE`. Yerel DB okunarak seed üretilmedi. Paket manifesti seed SHA-256, kayıt sayısı, köken ve üçüncü taraf lisans bildirimi hash'ini bağlar. Yerel manifest `PRIVATE_TEST_ONLY` durumundadır. Gerçek dağıtım, ayrı bir hak/lisans inceleme referansı ve tam bu seed hash'lerini onaylayan dış dosya olmadan kapıda reddedilir. Bu onay üretilmedi.

Temiz Python 3.11 EXE SHA-256 `9604159E4AA418A25C3B6B0CA3DC7E39AB1760D1CBAF69A4598A4641CD536DE4`; 10.899.860 bayt. PyInstaller analizinde Codex runtime yolu yok, paket kökünde uyumsuz `icuuc.dll` yok. Paket içi seed manifesti tekrar doğrulandı. Yalıtılmış ilk çalıştırmada doctor exit 0, gerçek Qt penceresi açıldı/kapandı exit 0, yeni SQLite quick_check `ok`; bootstrap market sayıları US 8.071, JP 4.280, TR 485, HK 3.075. Research dosyası olmayan temiz ortamda varsayımsal research sonucu sunulmaz. S15/S16 formül ve Hermes dosyaları değiştirilmedi.

Inno Setup 6.7.3 ile mevcut .iss dosyasının yalnızca özel test kaynak/çıktı yolları ayarlanmış kopyasından 72.688.769 baytlık installer üretildi; SHA-256 `8D16F0D4181DBE2F855F86CCC1F1C10B40F7F3A35CEE0964B4581040C8ECE294`. EXE ve installer Authenticode durumu `NotSigned`; kullanıcı sertifika deposunda özel anahtarlı Code Signing sertifikası yok ve yerel imzalama çevre değişkeni tanımlı değil. Sertifika satın alınmadı. Bu özel test installer'ı yayımlanmaz. İlk yalıtılmış kurulum exit 0; kurulu EXE doctor exit 0, gerçek Qt penceresi açılış/kapanış exit 0. Inno uninstaller exit 0; yalnızca test uygulaması silindi, yalıtılmış kullanıcı DB'si korundu. Aynı dizine yeniden kurulum exit 0, manifest ve kullanıcı DB'si yerinde, doctor ve Qt pencere tekrar exit 0. Son kaldırma exit 0 ve test uygulama dosyası kaldırıldı; kullanıcı DB'si korundu.

## PR bağımlılıkları ve test kapsamı

#162 bağımsız `main`; #163 `main`; #164→#163; #165 ve #166→#164; #167→#165; #168→#166; #169→#167; #170→#169. 2026-10-10 denetiminde #162–170 açık, mergeable ve Python CI başarılıydı. Faz 26B bu zinciri bozmaz, #170 üstüne ayrı PR açılır. Merge planı kullanıcı incelemesi ve onayından sonra uygulanabilir; otomatik merge yok.

Faz 26A'nın 734 Windows testi tekrarlanmadı. Faz 26B için Research Backtest, PIT/Learning, S15/S16, data health ve yeni seed/backup kapılarını kapsayan seçili **53 test geçti**. Sürüm hizası Python 3.11 ile `1.0.6` PASS. GitHub Windows build akışı bu PR dalında otomatik çalışmaz; gerçek Windows EXE/installer testleri yereldir.

## Yayın kararı

Canonical **0 hisse / 0 tarih**; WF9 **BLOCKED**; Learning V3 **NOT_TRAINED**. Tarihsel kimlik, kurumsal eylem, bağımsız düzeltilmiş fiyat ve çağdaş SEC available_at kanıtları hâlâ yok. Araştırma hesapları kanonik performans değildir. Yayın, kod imzası, seedlerin açık dağıtım onayı ve güncel resmi US seed/freshness kararı gelene kadar **BLOCKED**.