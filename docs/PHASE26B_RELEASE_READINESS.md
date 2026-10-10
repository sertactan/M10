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

## Faz 26B kapanış — gerçek durum (10 Ekim 2026, Japonya)

### Faz 26B devam — yayın kapılarının güçlendirilmesi

US seed release doğrulaması artık `SEC_DIRECT` kökenini, tüm satırlarda tek geçerli ISO `snapshot_date` değerini ve UTC takvimine göre en fazla 30 günlük yaşı şart koşar; gelecekteki tarihler engellenir. Eski tarihli `SEC_MIRROR_EDGARTOOLS` yalnız `PRIVATE_TEST_ONLY` olarak paketlenebilir. Kaynak/snapshot bilgisi dosya SHA'sına ve seed manifestine bağlıdır; lisans değerlendirmesi ve dosya hash'lerine özel dağıtım onayı ayrıca gereklidir. 2026-06-01 tarihli önceki özel test seed'i **yayın için geçersizdir**. SEC direct 403 kaldırıldığı iddia edilmez.

PyInstaller Windows sürüm kaynağı `config/RELEASE_VERSION.txt`, `pyproject.toml` ve Inno Setup sürüm eşitliğinden türetilir. Yeni EXE oluşturulduğunda Windows PE `FileVersion` / `ProductVersion` değerinin `1.0.6.0` olması beklenir; Windows build iş akışına bu kontrol eklendi. Önceki yerel EXE/installer **halen imzasız ve metadata'sı boş eski test çıktılarıdır**; yeniden üretilmediler, düzeltme ancak sonraki yeni paket üzerinde doğrulanabilir. İmzalama sertifikası ve resmî güncel seed kaynak kararı eksik; yayın **BLOCKED** kalır.

**Karar: PARTIAL.** Faz 26B'nin temiz özel paketleme ve uygulama-durumu yedekleme işleri başarıyla tamamlandı; nihai yayın ve tam sistem kurtarma kabulü **BLOCKED**. İşler yeniden çalıştırılmadı: mevcut bitmiş işlem ve disk manifesti okundu. Kaynak operasyonel SQLite, S15/S16, Hermes ve özel fiyat girdileri değiştirilmedi. PR'lar birleştirilmedi.

### Yedek / restore denetimi

| Kanıt | Doğrulanan sonuç |
|---|---|
| Faz 26B manifesti | `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase26b/full_app_state_20261010T26B/manifest.json` |
| Manifest SHA-256 | `C5FDFEA318E6FA00EF97F3778B5983965699A4E6826A3B1AF5D72E6833BE4E6D` |
| Sonuç / tamamlanma | `BACKUP_AND_RESTORE_VERIFIED`; 2026-10-10 22:11:20.532623 JST |
| Snapshot kayıtları | 4.754; 21.049.260.727 bayt; 7 `SQLITE_ONLINE_BACKUP`, 4.747 `VERIFIED_FILE_COPY` |
| Veri güvenliği | Kaynak DB salt okunur; `source_files_modified=false`; snapshot/restore SHA eşleşme işaretleri 4.754/4.754 |
| Bağımsız fiziksel kontroller | 0 eksik snapshot/restore dosyası, 0 uzunluk farkı, 0 yinelenen etiket, 0 geçersiz SHA alanı |
| SQLite | 7/7 snapshot ve bağımsız restore için `PRAGMA quick_check=ok` (manifest kaydı) |
| Kritik dosyalar | Güncel operational.db ve eski Phase24G `operational_inod_offline_backup.db`: her biri 9.208.848.384 bayt; ikisinde de aynı snapshot SHA `4f44855451bc942645b8ccf7be240c2e0462b336227736c6167b12af54c25636` |
| Faz 26A korunumu | 654 kayıt, `BACKUP_AND_RESTORE_VERIFIED`; manifest SHA `DF78DF697A2947BAD9F3D18C96E64AF6B540A19E7EEF537380A077C87B6BC530` |

Manifestteki SHA eşleşme sonuçları yedek üretim aşamasındaki bağımsız geri yükleme kopyalarına yönelik hesaplamalardır; kapanış denetiminde tüm dosyaların fiziksel varlıkları/boyutları ve manifestin kendi SHA değeri tekrar kontrol edildi. 21 GB'lık snapshot tekrar kopyalanmadı veya 42 GB'lık kanıtlanmış işlemin tümü ikinci defa hash'lenmedi.

**Zaman ve kapsam:** Canlı operasyonel DB'nin son dosya değişiklik zamanı 2026-10-10 **20:49:46 JST**. SQLite online backup yaklaşık **21:19–21:21 JST** sürecinin tutarlı DB görünümünü kapsar (snapshot dosyası 21:21:18'de yazıldı). 22:11:20 tarihi yalnızca bütün uygulama-durumu yedeğinin tamamlandığı zaman; verilerin tümünün o ana ait olduğu anlamına gelmez. Phase24G bağımsız tarihsel dosyası ~21:45–21:48 JST kopyalandı; diğer 4.747 dosya sırayla işlendi. Tüm dizinler için tek, atomik sistem anı yoktur. Daha sonraki canlı değişimler, Windows sistem görüntüsü, dış kimlik bilgileri ve etkin üretim ortamına fiili restore bu test kapsamının dışındadır. Bu nedenle **tam sistem yedeği ve üretim kurtarma kabulü PARTIAL** kalır. SQLite içerik/kayıt kaybı kanıtı bulunmadı; canlı DB başlığındaki dört sayaç baytını hangi süreç değiştirdiği hâlâ belirsizdir.

### Paket ve PR kesinleştirme

- EXE: Python 3.11 / sürüm 1.0.6, **10.899.860 bayt**, SHA-256 `9604159E4AA418A25C3B6B0CA3DC7E39AB1760D1CBAF69A4598A4641CD536DE4`; Authenticode `NotSigned`. Windows PE `FileVersion` ve `ProductVersion` alanları boş.
- Inno Setup installer: **72.688.769 bayt**, SHA-256 `8D16F0D4181DBE2F855F86CCC1F1C10B40F7F3A35CEE0964B4581040C8ECE294`; Authenticode `NotSigned`. Mevcut özel EXE ve installer'ın SHA değerleri tekrar hesaplanıp eşleştirildi.
- Kullanılan kanıtlar: 53/53 odaklanmış test, temiz paket ilk çalıştırma, Qt pencere açılış/kapanış, kur/kaldır/yeniden kur ve kullanıcı DB korunumu. Faz 26A 734/734 tekrar koşturulmadı; paket tekrar derlenmedi.
- PR **#171** `codex/phase26b-release` → **#170** `codex/phase26a-integration`, 2026-10-10 doğrulamasında **OPEN**, **MERGEABLE**, unmerged. Kod ve özel testler `d51dfe6`; bu kapanış belgeleri ek commit'lerde olabilir. GitHub **Python CI** `d51dfe6` için **SUCCESS**, run `38053378761` / job `114216855765`. Dokümantasyon commitleri için yeni kontroller ayrı değerlendirilir.
- Dağıtım izinleri: özel test `PRIVATE_TEST_ONLY`; US SEC direct HTTP 403 ve 2026-06-01 tarihli ayna veri kaynağı, EXE/installer için kod imzalama sertifikası yok, tüm seed SHA'larına bağlı açık dağıtım onayı yok. Yayın kesin olarak **BLOCKED**.

### Ana görev özeti

Depoda özgün adları mevcut **23/27** ana maddenin durumu: **DONE 1 / PARTIAL 9 / BLOCKED 13**. Kalan dört özgün madde başlığı geri getirilemediği için **UNKNOWN/UNVERIFIED 4** olarak tutulur; bu maddeler sonuçlandırılmış sayılmaz. Ayrıntılı satırlar `docs/PHASE26B_MAIN_TODO_STATUS.md` içindedir. Canonical **0 hisse/0 hisse-tarih**, WF9 **BLOCKED**, Learning V3 **NOT_TRAINED**.

Sonraki öncelik: bağımsız ve lisanslı güncel US seed kaynağına karar vermek ve dağıtım haklarını yazılı şekilde doğrulamak; sonrasında Authenticode imza/Windows PE sürüm kaynaklarını hazırlamak; ayrıca açıkça tanımlı tam sistem/OS yedeği ve kontrollü izole kurtarma kabulünü ayrı işlemek. Kanonik tarihsel kabul için SITC/CURB, total-return adjusted fiyatlar, SEC gerçek `available_at`, delisting ve PIT sürekliliği hâlâ delil bekliyor. Bu önkoşullar karşılanana kadar yayımlama, merge, WF9 veya Learning V3 eğitimi yapılmaz.
