# MERİDYEN M10 — V13 ana görev 9–18 devam ve kabul kaydı

**12 Ekim 2026, JST.** V12 kontrol noktası `baad538ea89664f94424137f103647628cb0447d` temel alındı. İzole V13 dalı `codex/master-tasks-closure-v13`. Özgün puan formülleri, canlı veritabanı ve kurulu Personal Edition 1.0.6 değiştirilmedi. [V13 JSON kabul kaydı](MASTER_TASKS_V13_REGISTER.json), V12'nin 40 zorunlu kapısını ve 13 kanıtlı kapısını korur; V13'te yalnız **18.build** eklendi: **14/40 kanıtlı, 0/10 DONE**. Bu oran model tamamlanma yüzdesi değildir.

## A. Görev sonuçları

| Görev | V13 gerçek ilerleme | Tam kabul için açık kapı | Durum |
|---:|---|---|---|
| 9 | Özgün INOD 2024/2025 10-K iXBRL baytları mühürlendi; 2023/24 kısa vadeli yatırım için iki aday bulundu. | Üç yıllık S6 muhasebe ayrımı, tam B_Q ve yetkili 7/7 S13 kararı. | PARTIAL |
| 10 | Aday veri S14'e aktarılmadı; INOD gerçek S11=0 ve üç kabul edilmiş bacak korundu. | Altı bacağın tamamı ve bağımsız geometrik tekrar. | BLOCKED |
| 11 | Dört INOD kısmi bacağı dokuz özgün SEC satırına bağlandı; ham F52/F53 büyümeleri bağımsız Decimal ile doğrulandı. | 0–100 eşikleri, Core48/Control12, tarihsel H ve tam S1/S2/S3. | PARTIAL |
| 12 | Zorunlu rota kapsamı ve tarihli SEC pay sayısından piyasa değeri adayı denetlendi. | S15.2, M10/T10 ve V1.2/V1.4/V1.4.1 sürüm kapıları. | PARTIAL |
| 13 | Yedi INOD finansal accession'ı özgün SEC submissions baytları ve kabul saatleriyle eşleştirildi. | Tarihsel ilk yayım, sağlayıcıya erişim ve sürüm/kimlik zinciri. | PARTIAL |
| 14 | SEC kabul saati ile sağlayıcıda kullanılabilir olma saati ayrı tutuldu; özellik yükseltilmedi. | Tarihli evren ve 22/22 özgün PIT normalize özellik. | BLOCKED |
| 15 | Gerçek 25 şirketli pilotta dış örneklem uygunluk kapısı işletildi: uygun vaka 0, metrik yok. | Olgun sonuçlar, geçmiş faktör yakalamaları, sayısal sözleşme ve ayrı aktivasyon onayı. | PENDING_APPROVAL |
| 16 | Özgün dakika yanıtı tekrarlandı; en fazla dört önceki aynı saat günü ve on zamanlanmamış SEC olay adayı bulundu. | En az 20 aynı saat günü, ilk haber/sağlayıcı saati ve bağımsız bar kanıtı. | PARTIAL |
| 17 | Beş hisse/17 gerçek Research puanı paketli EXE arayüzünde de karşılaştırma makbuzuyla eşleşti. | Kalan özgün modellerin ayrı tam kabulü. | PARTIAL |
| 18 | PyInstaller Windows EXE'si gerçek Qt aç/kapat/yeniden aç testini, 5 hisse/15 sütun/17 puanı ve kaynak yoksa kapalı kalma testini geçti. Özel test yükleyicisi derlendi. | Canlı kurulum, veri geçişi ve dağıtım için ayrı açık karar. | PARTIAL |

V13 teknik çalışmalarının ayrıntıları: [kalite](MASTER_TASKS_V13_QUALITY.md), [temel SEC bağı](MASTER_TASKS_V13_CORE.md), [ham F52/F53](MASTER_TASKS_V13_CORE_FACTORS.md), [S15](MASTER_TASKS_V13_S15.md), [PIT](MASTER_TASKS_V13_PIT.md), [S16-E](MASTER_TASKS_V13_ESTIMATED.md) ve [olay](MASTER_TASKS_V13_EVENT.md). Özel makbuzlar `E:/M10/.master_tasks_v13_private` altındadır; ham kaynaklar Git'e alınmaz.

## B. Kabul edilmiş gerçek puanlar

S1/S2/S3, S6, B_Q, S14, S16-E ve S16-C için yeni tam puan yoktur. Aşağıdaki 17 değer V12'nin mühürlü özgün Research karşılaştırmasından gelir; V13'ta paketli arayüzle tekrar eşleştirildi. **INOD S11 sıfırı gerçek kabul edilmiş değerdir; N/A değildir.** S16-E kapalıdır, S16-C için 0/22 özellik kabul edilmiştir.

| Hisse | S1/S2/S3 | S6 | S7 | S9 | S11 | S12 | B_Q | S14 | S16-E | S16-C |
|---|---|---|---:|---:|---:|---:|---|---|---|---|
| INOD | N/A | N/A | 100 | 55.555556 | **0** | 91.528866 | N/A | N/A | OFF/N/A | N/A |
| TMDX | N/A | N/A | 100 | 77.777778 | N/A | 85.403881 | N/A | N/A | OFF/N/A | N/A |
| CRMD | N/A | N/A | 100 | 55.555556 | 86.015359 | 95.682132 | N/A | N/A | OFF/N/A | N/A |
| PENG | N/A | N/A | 100 | 66.666667 | N/A | 83.512058 | N/A | N/A | OFF/N/A | N/A |
| ETON | N/A | N/A | 100 | 55.555556 | 7.860332 | N/A | N/A | N/A | OFF/N/A | N/A |

Fiyatlar 9 Ekim 2026 tarihli önbellek kapanışıdır; canlı fiyat olarak gösterilmez. Yeni tam puan **0**, toplam kabul edilmiş puan **17**; doğrulanmış S16-EA alarmı **0**.

## C. Windows ve dağıtım kanıtı

Son özel test EXE'si `E:/M10/.master_tasks_v13_private/windows/acceptance_dist/S153ResearchTerminal/S153ResearchTerminal.exe`, SHA-256 `b57b392bf774e2f5a398b429f70a748c9130c1ab0689e20946b5d890ba6be23c`. Paketli Qt kabul makbuzu `E:/M10/.master_tasks_v13_private/windows/acceptance_ui.json`: `PASS`, 5 hisse, 15 sütun, 17 Research puanı, S14 INOD `N/A`, S16-E `OFF`, kanonik özellik 0, eksik kaynak fail-closed, pencere aç/kapat/yeniden aç. Karşılaştırma kaynağı SHA-256 `81cc4bdd7b634bb482bf8a1adfb417efd00c6f3c6965a8a8edca019bbbfc7c8b`. Test, gerçek paketli EXE'de Qt `offscreen` platformuyla çalıştı; görünür masaüstü ekran görüntüsü olarak sunulmaz.

İlk özel yükleyici kurulum denemesi kayıt anahtarı izni yüzünden otomatik geri alındı; gerekli izinle ikinci deneme **exit 0** verdi. Yükleyici SHA-256 `c187775e89514fe408fe3939ab6c10ddf7d8607f47a3cbf3fa11094a51dad5f5`. Kurulu EXE'nin hash'i taşınabilir EXE ile aynıdır. Kurulu kopyanın ayrı [özel Qt kabul makbuzu](E:/M10/.master_tasks_v13_private/windows/acceptance_installed_ui.json) **PASS**, SHA-256 `995572265cfd058bf741f354ecb973e35ff45847ca4c3f6bbbc5eb2d9ab79ebb`; yine 5 hisse/15 sütun/17 puan, eksik kaynakta kapalı kalma ve pencere yeniden açma doğrulandı. Özel kaldırıcı **exit 0** verdi ve kurulu EXE kaldırıldı. Canlı 9.208.872.960 bayt veritabanının son değişiklik zamanı `2026-10-10 16:23:10 UTC` olarak kaldı. Test hedefi yalnız `E:/M10/.master_tasks_v13_private/windows/installed_test` idi. Paket ve yükleyici özel test tohumları taşır, imzasızdır ve üretim dağıtımı için onaylı değildir. Canlı kurulum, canlı DB geçişi ve PR birleştirme yapılmadı.

## D. Sınırlar ve karar

S6/B_Q ve yedi S13 kategorisi için muhasebe/uzman kararı, tarihsel PIT ve haber/sağlayıcı zamanları için özgün veri, S16-E için gerçek olgunlaşmış dış örneklem gerekir. Bu kaynaklar gelmeden N/A ve OFF korunur. V13 dalı kod ve denetim belgelerini incelemeye açar. Canlı kurulum, veritabanı geçişi ve üretim aktivasyonu ancak paket hash'i, hedef ve geri dönüş adımı belirtilmiş ayrı kullanıcı onayıyla ele alınır.
