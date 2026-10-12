# MERİDYEN M10 — V14 ana görev 9–18 kabul kapanışı

**MASTER TASKS DONE: 0/10 → 0/10**

**KABUL KAPILARI: 14/40 → 14/40**

**GERÇEK RESEARCH PUANI: 17 → 17**

**S16-C PIT: 0/22 → 0/22**

**S16-EA DOĞRULANMIŞ ALARM: 0 → 0**

12 Ekim 2026, JST. Bu sayılar [V14 40 kapılı kayıt](MASTER_TASKS_V14_REGISTER.json) ve V13 kontrol noktasına dayanır. V14 kaynak araştırması yeni tam model puanı ya da yeni kapı kabulü üretmedi. Aşağıdaki PARTIAL ve BLOCKED etiketleri tamamlanmış görev anlamına gelmez. V13 dalı `cb6c75521443cf9ce322e4025eeb89a149a1939c` temel alınmıştır.

## A. On görev ve somut V14 ilerlemesi

| Görev | V13 → V14 | Yeni kaynak/bağımsız denetim | Kalan zorunlu kabul | Durum |
|---:|---|---|---|---|
| 9 | 0 yeni kapı | İki özgün INOD 10-K içinde 1.800 sayısal iXBRL olgusu tarandı; STI adayı ve etiket boşlukları sınıflandırıldı. | S6 5/7, B_Q 5/7; S13 0/7 yetkili imza. | PARTIAL |
| 10 | 0 yeni kapı | Altı S14 bacağından yalnız üç kabul edilmiş bacak, INOD S11=0 dahil, tekrar korundu. | Altı özgün bacak ve bağımsız Decimal/geometrik tekrar. | BLOCKED |
| 11 | 0 yeni kapı | 48/12 özgün sözleşme ve dört kısmi INOD SEC bacağı tekrar bağlandı; çevrimdışı tarihsel H tablosunda 0 satır bulundu. | D/F faktör aileleri, F52/F53 kalite eşikleri, tarihsel H, ayrı tam S1/S2/S3. | PARTIAL |
| 12 | 0 yeni kapı | Beş hisse için S15.3 as-of canlı özellik envanteri salt okunur incelendi; V1.2/V1.4/V1.4.1 READY değil. | S15.2, M10/T10, desteklenen MC, rota, güven, senaryo ve fit girdileri. | PARTIAL |
| 13 | 0 yeni kapı | Yedi SEC idari join korundu; iki özgün 10-K'deki FY2024 karşılaştırmalı nakit ve allowance farkı saatleriyle saptandı. | İlk kamusal yayımlanma, sağlayıcı available-at, tam sürüm ve günlük kimlik zinciri. | PARTIAL |
| 14 | 0 yeni kapı | SEC kabul saati sağlayıcı saatine dönüştürülmedi; 22 özellikten hiçbiri PIT kabulü almadı. | Tarihli evren ve 22/22 kaynaklı, normalize PIT özellik. | BLOCKED |
| 15 | 0 yeni kapı | V13 dış örneklem uygunluğu 0 ve öğrenme/üretim ayrımı korundu. | Olgun sonuç, eski faktör yakalamaları, sayısal sözleşme, ayrı aktivasyon kararı. | PENDING_APPROVAL |
| 16 | 0 yeni kapı | Nasdaq takvimine göre 20 önceki seansın dördü özgün dakika kaynağında var; 16 tarih eksik. | Bağımsız 5m, bar available-at, haberin ilk yayım ve sağlayıcı saatleri, tepki/sonuç tekrarı. | PARTIAL |
| 17 | 0 yeni kapı | V13 beş hisse/17 gerçek Research değeri korundu; yeni tam model yok. | Geri kalan özgün modellerin ayrı tam kabulleri. | PARTIAL |
| 18 | 0 yeni kapı | V13 özel EXE/yükleyici kabulü korundu; V14 üretim tohum/lisans/dağıtım kapısı incelendi ve beklenen biçimde reddetti. | Taze SEC_DIRECT tohumu, hash'e bağlı lisans/dağıtım kararı, yeni üretim paketi ve ayrı canlı geçiş kararı. | PARTIAL |

İlgili ayrıntılı kanıtlar: [9–10 kalite](MASTER_TASKS_V14_QUALITY.md), [11 core](MASTER_TASKS_V14_CORE.md), [12 S15](MASTER_TASKS_V14_S15.md), [13–14 PIT](MASTER_TASKS_V14_PIT.md), [16 olay](MASTER_TASKS_V14_EVENT.md), [18 Windows](MASTER_TASKS_V14_WINDOWS.md). Her kapının sözleşme testi, gerçek kaynak, kaynak zamanı, bağımsız test, özel makbuz SHA-256, eksik girdi ve insan kararı alanları JSON kayıtta ayrı tutulur. V14 makbuzları `E:/M10/.master_tasks_v14_private` altındadır; ham SEC/veritabanı içeriği dalda yoktur.

## B. Gerçek puan matrisi

V13'ten gelen aşağıdaki **17 değer** V14'te değiştirilmedi. INOD S11 **0** kabul edilmiş gerçek sayıdır; N/A değildir. 9 Ekim fiyatları önbellek kapanışıdır, canlı fiyat değildir.

| Hisse | S1/S2/S3 | S6 | S7 | S9 | S11 | S12 | B_Q | S14 | S16-E | S16-C |
|---|---|---:|---:|---:|---:|---|---|---|---|
| INOD | N/A | N/A | 100 | 55.555556 | **0** | 91.528866 | N/A | N/A | OFF/N/A | N/A |
| TMDX | N/A | N/A | 100 | 77.777778 | N/A | 85.403881 | N/A | N/A | OFF/N/A | N/A |
| CRMD | N/A | N/A | 100 | 55.555556 | 86.015359 | 95.682132 | N/A | N/A | OFF/N/A | N/A |
| PENG | N/A | N/A | 100 | 66.666667 | N/A | 83.512058 | N/A | N/A | OFF/N/A | N/A |
| ETON | N/A | N/A | 100 | 55.555556 | 7.860332 | N/A | N/A | N/A | OFF/N/A | N/A |

S16-E **OFF**, S16-C **N/A**, S16-EA alarm **0**. FY2024 karşılaştırmalı farkı resmi restatement kanıtı sayılmadı. Eksik etiket sıfır değer sayılmadı. Takvim günü bağımsız fiyat barı ya da olay saati sayılmadı.

## C. Açık kapıların kapanması için karar/girdi

| Blok | Gerekli veri veya karar | Kabulün tekrar koşulu |
|---|---|---|
| 9–10 muhasebe/uzman | Özgün dönem eşleşmiş STI/LTI, stok, toplam borç, saf amortisman ve yetkili S13 yedi kategori kararı. | S6 7/7, B_Q 7/7 ve S14 6/6 bacak; frozen formüllerle ayrı hesap. |
| 11–12 model | Tarihli Core48/Control12, sayısal eşikler, tarihsel H, S15.2/M10/T10, SupportedMC, rota ve fit. | Her model ve S15.3 sürümü için bağımsız referans puanı ve kaynak saatleri. |
| 13–14 PIT | Yedi accession için tüm sürümler, ilk kamusal/sağlayıcı zamanı, günlük CIK/ticker/share-class geçmişi. | As-of tekrar ve 22/22 cross-sectional normalizasyon. |
| 15 öğrenme | Olgun dış örneklem sonuçları ve geçmiş faktör yakalamaları; aktivasyon için ayrı yetkili karar. | Orijinal metrik sözleşmesiyle uygun vaka ve bağımsız değerlendirme. |
| 16 olay | Eksik 16 karşılaştırma seansı, bağımsız 5m ve bar available-at; haber ilk yayım/sağlayıcı saatleri. | Geçerli olay, tepki ve sonuç as-of tekrarı. |
| 18 dağıtım | Son 30 gün SEC_DIRECT US tohumu, hash'e bağlı kaynak/lisans ve kullanıcı dağıtım kararı. | Yeni imzalı/uygun paket, kurulu Qt kabulü; canlı kurulum/DB geçişi için ayrı hedef/yedek/geri alma kararı. |

~~18.build~~ V13'te doğrulandı; **18.deployment açık**. Özel test EXE SHA-256 `b57b392bf774e2f5a398b429f70a748c9130c1ab0689e20946b5d890ba6be23c`, imzasız ve `PRIVATE_TEST_ONLY` tohumlu. V14 üretim hazırlığı makbuzu SHA-256 `8fe15b28515e6fa607e846f34cfb22fc89ecd342d4329e0ef671cbadbc2d8609`; geçersiz eski/mirror tohumla yayın kapısı reddi beklenen sonuçtur. Canlı 9.208.872.960 bayt DB son değişim zamanı `2026-10-10 16:23:10 UTC` gözlendi. Canlı kurulum, migration ve PR merge yapılmadı.

## D. V14 tekrar kanıtları

| Denetim | Özel mühür SHA-256 | Sonuç |
|---|---|---|
| Core48/Control12 | `00843e643c21f8cc6c912e736a5721a0f8a1ff3bb9c41911da989b94419d98fb` | Kaynak tekrar PASS; tam puan yok |
| Kalite geniş iXBRL | `02d18b62418d1cf37d0e639ab850fe8b28aaa2b8549ac0b2df045dcf373b1188` | Kaynak tekrar PASS; S13 imza yok |
| S15.3 as-of envanter | `aef56cbcc0391b21c710b6ee4edb016207338af3c9d140298eb32631aae894f4` | Salt okunur tekrar PASS; üç sürüm OPEN |
| PIT sürüm farkı | `504497b2cea46ba6612dc53e14661182b975d67f295e58603e37f8b6a3734471` | Kaynak tekrar PASS; PIT kapıları OPEN |
| Olay takvimi | `e7a3568b3c4396f05d354f42aa92fa10d3e9b01fc1c150ba5009e112ee8f8b48` | Kaynak tekrar PASS; alarm 0 |
| Windows yayın hazırlığı | `8fe15b28515e6fa607e846f34cfb22fc89ecd342d4329e0ef671cbadbc2d8609` | Tekrar PASS; yayın kapısı beklenen ret |

Özel tekrarların PASS sonucu üretim kabulü değildir. Son dal HEAD'i için CI sonucu PR üzerinde ayrıca doğrulanır.
