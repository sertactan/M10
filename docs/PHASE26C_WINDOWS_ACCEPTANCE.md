# MERİDYEN M10 — Faz 26C Windows 1.0.6.0 paket kabulü

**Tarih:** 2026-10-10 (Asia/Tokyo)  
**Kod tabanı:** `sertactan/M10`, PR #171 (`codex/phase26b-release`), kaynak HEAD `b01ba5a` (Faz 26B koruma commit'i `cdb2de4` dahil); taban PR #170.  
**Karar:** **FAZ26C_DONE** (izole Windows özel test mühendisliği), **RELEASE_BLOCKED** (üretim dağıtımı). Bu belge ve testler yayın ya da PR merge onayı değildir.

## 1. Bağımsız temiz build

- Faz26B'nin önceki tamamlanmış EXE/installer ve büyük DB yedekleri tekrar üretilmedi. Faz26C **yeni** çıktı kökü: `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase26c/windows_1060/`.
- İzole paket manifesti `PRIVATE_TEST_ONLY`, `release_approved=false`, `contains_operational_or_user_data=false`. Eski kamu kaynaklı test CSV'leri ayrı hedefe kopyalanıp yeni manifest oluşturuldu; özel operasyonel DB'den seed çıkartılmadı.
- US: `SEC_MIRROR_EDGARTOOLS`, 10.141 satır, `snapshot_date=2026-06-01`; JP/TR/HK: `FINANCEDATABASE_MIT_REFERENCE`, 7.840 ham satır. CSV ve üçüncü taraf lisans notu hash'leri `verify-test` ile kabul edildi; paket içindeki manifest yeniden doğrulandı. Release gate, bu US seed'ini `Release requires directly fetched SEC US seed` hatasıyla (exit 1, **beklenen**) reddetti.
- Python **3.11.9**, PyInstaller **6.22.3**, PySide6 **6.12.0**; temiz PATH; proje dalı değişmedi. PyInstaller **exit 0** ve `Copying version information to EXE` / `Build complete` kanıtı mevcut.

## 2. Gerçek Windows EXE

| Gerçek dosya özelliği | Sonuç |
|---|---|
| Dosya | `dist/S153ResearchTerminal/S153ResearchTerminal.exe` |
| Boyut | **10.900.385 bayt** |
| SHA-256 | `9E4A04A7749D198F0C36349CDD6BD393DC9D407B8F6F19DECAF2310B20613782` |
| FileVersion | **1.0.6.0** |
| ProductVersion | **1.0.6.0** |
| ProductName | `S15.3 Research Terminal` |
| FileDescription | `S15.3 Research Terminal` |
| CompanyName | `Tancodes` |
| Authenticode | **NotSigned** |

Paket kökünde istenmeyen `icuuc.dll` tespit edilmedi. `s153_v141/canonical_completion_specification.md` ve `data/database/schema.sql` pakette mevcut. Ana Windows exe dosyası üzerinde `System.Diagnostics.FileVersionInfo`, hash için `Get-FileHash` ve imza için `Get-AuthenticodeSignature` kullanıldı. Kod imzası yoktur ve imzalı paket iddiası yapılmaz.

## 3. Inno test installer

| Alan | Sonuç |
|---|---|
| Inno Setup | 6.7.3, derleme **exit 0** |
| Dosya | `installer_smoke/S153ResearchTerminal-Setup.exe` |
| Boyut | **72.685.997 bayt** |
| SHA-256 | `A9D28E816EFCA5E1D991A320F128808FBB79AB2177FA2F79096A5BC2E66DFB3E` |
| Installer ProductVersion | `1.0.6` |
| Installer Authenticode | **NotSigned** |

İzole test kaynağında `.iss` dosyasının yalnız `Source` ve `OutputDir` yolları özel test hedefine uyarlandı. Gerçek üretim kurulumuna veya başka kurulu Meridyen uygulamalarına müdahale edilmedi.

## 4. Gerçek Windows smoke ve veri korunumu

| Kabul kontrolü | Gerçek sonuç |
|---|---|
| Portable ilk `--doctor` | **exit 0** |
| Portable yeni SQLite `PRAGMA quick_check` | **ok** |
| Başlangıç security master | US **8.071**, JP **4.280**, TR **485**, HK **3.075** |
| Portable Qt ana pencere | `S15.3 Research Terminal` bulundu; `WM_CLOSE` sonrası **exit 0** |
| İlk izole Inno kurulumu | **exit 0** |
| Kurulu EXE SHA / PE sürümü | Portable EXE hash'iyle aynı; `1.0.6.0` |
| Kurulu `--doctor` ve SQLite quick_check | **exit 0**, **ok** |
| Kurulu Qt ana pencere | Gerçek pencere bulundu; normal kapanış **exit 0** |
| İlk kaldırma | **exit 0**, kurulu EXE silindi, kullanıcı DB değişmedi |
| Aynı yere yeniden kurulum | **exit 0**, sürüm `1.0.6.0`, DB hash değişmedi |
| Yeniden kurulu `--doctor` | **exit 0** |
| Son test kaldırması | **exit 0**, EXE silindi, kullanıcı DB korundu |

Kaldırma ve yeniden kurulum karşılaştırmalarında izole test DB SHA-256 sabit kaldı: `19E388C0ED34247BD3839D521268657BE8D3DD568D43EFE5A09AABFC82518022`. Uygulamanın GUI açılışı DB başlık sayaçlarını değiştirebildiğinden bu hash, **GUI kabulü tamamlandıktan sonraki** geri kurulum/kaldırma sınırı içindir. Gerçek M10 operasyonel DB'nin kaydı `9.208.848.384` bayt, `2026-10-10 20:49:46 JST` son değişim olarak aynı kaldı; kaynak DB restore edilmedi/üzerine yazılmadı. Eski manifest hash'leri değişmedi: Faz26A `DF78DF697A2947BAD9F3D18C96E64AF6B540A19E7EEF537380A077C87B6BC530`; Faz26B `C5FDFEA318E6FA00EF97F3778B5983965699A4E6826A3B1AF5D72E6833BE4E6D`.

## 5. Güvenlik ve test

- `python -m unittest tests.test_phase26b_release_safety -q`: **7/7 PASS**. İçinde özel DB export reddi, mirror-private-only, future/stale tarih, karışık snapshot ve hash-bağlı dış onay reddi testleri bulunur.
- `check_release_version.py --root .`: **1.0.6 PASS**. PE sürüm metni üretimi `1.0.6.0`: **PASS**. Paket manifesti `verify-test`: **PASS**. `verify-release`: **EXPECTED REJECT**.
- Faz26B'nin odaklı **53/53** ve Faz26A'nın **734/734** tarihsel PASS kayıtları bu fazda yeniden çalıştırılmadı. Kanonik performans testi veya Learning V3 eğitimi yapılmadı.
- Kod, test ve paketleme kaynaklarında bu Faz26C için uygulama değişikliği gerekmedi. S15/S16 frozen formülleri, Hermes ve Research-only/CANONICAL ayrımı korunmuştur. Eksik Research JSON için sahte grafik oluşturulduğuna dair yeni bulgu yok; Faz26A/B'deki fail-closed davranış önceki kanıt olarak korunur. Bu fazın UI smoke testi her ekran içeriği için kanonik analiz kabulü değildir.
- Yerel kullanıcı sertifika deposunda uygun özel anahtarlı Code Signing sertifikası sayısı **0**; ilgili imzalama ortamı yapılandırılmamış. Özel seedler, fiyat verileri, EXE ve installer **GitHub'a yüklenmedi**.

## 6. GitHub ve release engelleri

PR #171 `codex/phase26b-release` dalında, tabanı PR #170 `codex/phase26a-integration`; kaynak `b01ba5a` için Python CI **SUCCESS** (GitHub Actions run `38059633481`). Bu rapor eklendikten sonra yeni dokümantasyon commit'inin CI sonucu ayrıca kontrol edilir. GitHub Windows production-build workflow bu dalda otomatik çalışmaz; burada raporlanan paketler yerel gerçek Windows derlemesidir.

**RELEASE_BLOCKED:** (1) güncel ve doğrudan SEC'den doğrulanmış US seed, (2) seedlerin tamamı için açık dağıtım/lisans onayı, (3) gerekli geçerli Authenticode imzası/sertifikası, (4) son üretim kabul ve sürüm kontrolü, (5) kullanıcının açık yayın onayı eksik. İmzasız/private-test installer hiçbir GitHub release'e konulmadı; hiçbir PR birleştirilmedi.

**Kanonik durum değişmedi:** **0 hisse / 0 hisse-tarih**; **WF9 BLOCKED**; **Learning V3 NOT_TRAINED**.

**Nihai karar:** **FAZ 26C DONE** (gerçek Windows EXE/installer özel test mühendisliği ve izole kabul); **RELEASE_BLOCKED** (yayın için gereken kanıt ve izinler eksik). Ana To-Do özeti için `docs/PHASE26C_MAIN_TODO_STATUS.md` dosyasına bakın.
