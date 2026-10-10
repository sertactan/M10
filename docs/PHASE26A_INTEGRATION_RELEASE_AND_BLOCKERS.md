# MERİDYEN M10 — Faz 26A entegrasyon, Windows paket ve blocker raporu

Tarih: 2026-10-10 (Asia/Tokyo). Staging: codex/phase26a-integration. Sürüm dosyaları değişmedi: 1.0.6. Bu dal ve aşağıdaki PR'lar açıktır; hiçbir PR birleştirilmedi. Bu rapor araştırma fiyat aritmetiğini kanonik performans olarak sunmaz.

## PR bağımlılık ve çakışma matrisi

| PR | Taban | İçerik | Entegrasyon |
|---|---|---|---|
| #162 | main | Resmî kimlik sınırı ve salt okunur Learning envanteri | Bağımsız; staging'e yalnızca kendi beş commit'i alındı |
| #163 | main | 464 kimlik çakışması karantinası ve 25 research adayı | Research zincirinin kökü |
| #164 | #163 dalı | Sekiz hisse kanıt matrisi; canonical 0 | #163'e bağımlı |
| #165 | #164 dalı | Deneysel 25 hisse araştırma aritmetiği | Research kolu |
| #166 | #164 dalı | BKE sağlayıcı uygulanabilirliği | #165 ile kardeş kol; staging'e kendi commit'i alındı |
| #167 | #165 dalı | Research Backtest V2 ve risk kapıları | Research kolu |
| #168 | #166 dalı | BKE resmî temettü ve kısmi ücretsiz fiyat erişimi | #167 ile kardeş kol; staging'e kendi commit'i alındı |
| #169 | #167 dalı | PySide6 Research Backtest sekmesi | Staging tabanı |

PR dosya listeleri karşılaştırıldı. #162, #166 ve #168'in eklediği dosyalar Research kolunun dosyalarıyla çakışmıyor; cherry-pick çatışması olmadı. Staging yalnızca bu bağımsız commit'leri ve Faz 26A entegrasyon değişikliklerini içerir. Frozen S15/S16 model kodu, Hermes, üretim DB ve lisanslı kaynak dosyaları değiştirilmedi. Windows git autocrlf nedeniyle kanonik spec checkout baytları manifest hash'inden ayrılıyordu; .gitattributes sadece specs altındaki checkout satır sonunu LF'ye sabitler. Commit'teki frozen spec içerik blobları değişmedi.

## Research ekranı ve kanonik kapı

Gerçek özel Phase25Z V2 raporu: 25 hisse, 20 aylık aralık, 25 katkı satırı, 15 uç hareket ve iki grafik serisi. Rapor SHA-256: cab8f4f9e6523b73594a44e0bb8beb373740e0a7cf2179329e484ea2a1486322. Ekran açılmadan önce dört özel girdinin ve orijinal fiyat CSV'sinin gerçek SHA-256 değeri okunur; manifestin staging sürümü ve fiyat hash'i raporla karşılaştırılır. Eksik, bozuk, eski dönemli, değişmiş hash'li veya kanonik kabul iddiası içeren rapor reddedilir; önceki grafik ve tablolar temizlenir.

Gerçek Windows Qt kaynak uygulaması iki kez açılıp kapatıldı. Altı sekme, Research tabı, PIT/Learning kanıt penceresi, 25 satır, 15 uç hareket, iki grafik serisi ve S15/S16 model sekmelerinin görünürlüğü doğrulandı. Research etiketi EXPERIMENTAL ONLY; Canonical 0 hisse / 0 tarih; WF9 BLOCKED; Learning V3 NOT_TRAINED. SEC Accepted saati gerçek sağlayıcı available_at saati sayılmaz.

## Windows regresyonlarının sınıflandırması

İlk geniş yerel Windows koşusunda 15 hata vardı; Faz 26A öncesi #169 worktree'sinde temsilî hash ve SQLite kilidi hataları tekrarlandı.

| Hata grubu | Sayı | Kök neden | Düzeltme |
|---|---:|---|---|
| Faz14 testleri | 2 | Windows'ta context manager sonrası açık kalan SQLite fixture handle'ı rename testini kilitledi | Test fixture'ı explicit closing ile kapatıldı |
| Faz24J/K testleri | 8 | TemporaryDirectory temizlenirken fixture SQLite handle'ı hâlâ açıktı | Test fixture'ları explicit closing ile kapatıldı |
| Faz5/6 spec hash | 5 | Bir gerçek checkout CRLF/manifest uyuşmazlığı; dört sentetik testte write_text Windows newline dönüşümü | Frozen spec için LF checkout kuralı; sentetik dosyaları byte olarak yazma |

Bu düzeltmeler test fixture ve Git checkout davranışıyla sınırlıdır. Faz14/24 audit iş mantığı ve frozen model formülleri değiştirilmedi. İlgili beş test modülü tek başına Windows'ta geçti. Son geniş Windows koşusunda 734/734 test geçti; test çıkış kodu 0. Sekiz Qt QDateTime deprecation uyarısı kaldı; bunlar hata değildir. Exact staging-commit GitHub CI durumu PR bölümünde ayrıca belirtilir.

## Özel yedek ve geri yükleme

Özel manifest: LOCALAPPDATA/S153ResearchTerminal/runtime/phase26a/verified_backup_20261010T26A/manifest.json. 654 girdi; toplam kaynak snapshot boyutu 10.333.748.978 bayt. Operasyonel SQLite ve research staging SQLite dosyaları salt okunur kaynaktan SQLite online backup API ile yeni dosyalara alındı; bağımsız restore_probe kopyaları üretildi. Bütün dosyalar SHA-256 ile geri yükleme kopyalarına eşleşti; SQLite yedek ve restore quick_check sonucu ok. Üretim DB veya özel kaynakların üzerine yazılmadı.

Önemli tazelik sınırı: canlı operasyonel DB'nin 2026-10-10 20:30:22 +09:00 zaman damgası ve güncel SHA-256 değeri, alınan snapshot'tan farklıdır. Yedek geri yüklenebilir bir anlık görüntüdür, ancak canlı DB'nin daha sonraki hâlini içerdiği iddia edilmez. Değişikliğin hangi süreçten geldiği kanıtlanmadı. Tam sistem yedeği ve üretim ortamına geri yükleme kabulü hâlâ açık.

## Windows paketleme

Python 3.11.9, PyInstaller 6.22.3, mevcut spec ve sürüm 1.0.6 kullanıldı. İlk yerel build, Codex Poppler PATH girdisinden uyumsuz icuuc.dll taşıdı; QtWidgets açılışı WinError 127 ile başarısızdı. Temiz PATH ile tekrar build edildi: analiz manifestinde sıfır Codex runtime yolu ve paket kökünde uyumsuz icuuc.dll yok. Elle DLL değişikliği yapılmamış portable EXE, temiz yalıtılmış runtime'da doctor exit 0 verdi ve gerçek Qt ana penceresi iki kez WM_CLOSE ile exit 0 kapandı. Ağ, paket UI denemesinde yalnızca yerel başarısız proxy ile izole edildi. Geçici build seedleri, mevcut özel DB'den salt okunur türetilmiştir ve dağıtım için yetkilendirilmiş seed değildir; paket özeldir.

Inno Setup 6.7.3 kullanıcı kapsamındaki kurulumda bulundu. Mevcut .iss içeriğinin yalnızca kaynak/çıktı yolu özel test dizinine uyarlanmış kopyasıyla 72.609.907 baytlık imzasız installer üretildi; SHA-256: 02327da5cff3402a6dd12b5c641c7de170227b51f929a2c26cd6fe5a9608ccc2. Yalıtılmış kullanıcı dizinine sessiz kurulum exit 0 verdi. Kurulu EXE yeni runtime ile doctor exit 0 verdi; gerçek Qt ana penceresi açıldı ve WM_CLOSE sonrası exit 0 kapandı. MSI üretilmez; mevcut dağıtım yapılandırması Inno EXE üretir. İmzalama sertifikası ve yayın onayı yoktur. Test paketleri ve özel seedler GitHub'a eklenmeyecek.

## Birleştirme ve release kararı

Kullanıcı onayından sonra gözden geçirilebilir sıra: #163, #164, ardından #165→#167→#169 Research hattı; #166→#168 BKE hattı #164 üstünden; #162 bağımsız. Staging PR, #169 tabanlı olarak bağımsız #162/#166/#168 değişikliklerini ve Faz 26A kapılarını gösterir. Her adımda tabanı güncelleme, CI ve hash kontrolü gerekir. Bu bir plan; otomatik merge yok.

Şu anda canonical kabul 0/0, WF9 BLOCKED ve Learning V3 NOT_TRAINED korunur. Kanonik veri sağlayıcısı, çağdaş PIT available_at, tarihsel sınıf/CIK sürekliliği, resmî corporate-action/delisting ve bağımsız düzeltilmiş fiyat zinciri eksik olduğu için yeni kabul yapılmadı. Release, imzalı ve yetkili seedli installer ile tam sistem tazelik/geri yükleme kabulü sağlanmadan yayımlanmaz.
