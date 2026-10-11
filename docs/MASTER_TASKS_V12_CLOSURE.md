# MERİDYEN M10 — V12 Ana Görev 9–18 kabul kaydı

**11 Ekim 2026, JST.** Başlangıç: PR #185 / `f211205bffb66ab8145ee9cdde896d31ff455cdb`.
İzole çalışma ağacı `E:/M10/.master_tasks_v12`, dal
`codex/master-tasks-closure-v12`. Özgün S1–S14 kaynak SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`
yerel dosya baytlarından tekrar doğrulandı. Dondurulmuş formüller değişmedi.

Kalıcı [JSON kabul kaydı](MASTER_TASKS_V12_REGISTER.json), her görevin
zorunlu kapılarını, kanıtını, testini, bağımlılığını, teknik sonraki işini ve
dış kararını tutar. `scripts/master_tasks_v12_register.py` herhangi bir
eksik kapıyla `DONE` yazılmasını reddeder. Kayıt, V12'de tanımlanmış **40
ayrık zorunlu kapıyı** sayar: V11 başlangıcında 10'u kanıtlıydı; V12'de
17. görev karşılaştırma matrisi ve fiyat/kapsam ayrımı ile 18. görev Qt
regresyonu olmak üzere 3 kapı daha geçti (**13/40**). Bu sayı özgün
modellerin tamamlanma yüzdesi olarak yorumlanmaz; yalnız kayıtlı kapı
envanterinin sayımıdır. Diğer kaynak daraltmaları gerçek ilerlemedir fakat
henüz zorunlu bir tam kabul kapısını kapatmamıştır.

## A. Ana görev sonuçları

| Görev | V11 | V12 gerçek iş | DONE için kalan | V12 |
|---:|---|---|---|---|
| 9 | PARTIAL | S6/B_Q kaynakları çevrimdışı tekrarlandı; CRMD/ETON/PENG için aynı accession alternatif etiket adayları ve 27 bulgulu S13 uzman paketi oluşturuldu. | Özgün S6 ayrıştırma, tam B_Q ve 7/7 imzalı S13. | PARTIAL |
| 10 | BLOCKED | INOD üç kabul edilmiş bacak ve gerçek S11=0 korundu; tam altı-bacak için bağımsız Decimal referans kapısı test edildi. | S6/B_Q/S13 gerçek kabulü, sonra kaynaklı geometrik hesap. | BLOCKED |
| 11 | PARTIAL | Beş şirketin S1/S2/S3 kapıları ve kaynaklı 14 kısmi araştırma girdisi denetlendi. | Core48, Control12, Historical H, DNA/router/Gate6 ve bağımsız tam hesap. | PARTIAL |
| 12 | PARTIAL | Üç S15.3 sürümü ayrı denetlendi; V1.4 manifest hashleri doğrulandı. | S15.2, M10/T10, route, magnitude, fit ve sürüm ön koşulları. | PARTIAL |
| 13 | PARTIAL | INOD'un iki gerçek 10-K SEC kabul saati kaynak baytlarından tekrarlandı; as-of sürüm kapısı uygulandı. | İlk yayım, geçmiş sağlayıcı erişimi, revizyon ve tarihsel kimlik kanıtı. | PARTIAL |
| 14 | BLOCKED | 22 özellik için PIT kabul kapısı korunup geçersiz tarihsel yükseltme reddedildi. | Görev 13, tarihli evren ve 22/22 normalize kaynaklı özellik. | BLOCKED |
| 15 | PENDING_APPROVAL | Estimated/Canonical ayrımı ve sürümlü onay paketi hazırlandı; etkinleştirme yapılmadı. | OOS kalibrasyon, onaylı sayısal sözleşme, ayrı kullanıcı aktivasyon kararı. | PENDING_APPROVAL |
| 16 | PARTIAL | Haber/seans/as-of kapıları denetlendi; geçmiş alarm üretilmedi. | İlk yayımlanma, sağlayıcı gecikmesi, aynı-saat OHLCV ve sonuç replay'i. | PARTIAL |
| 17 | PARTIAL | Beş hissenin 17 gerçek puanı kaynaklı yeniden oynatıldı; özgün 20 model satırı, N/A nedenleri, fiyat tarihi ve S16-E/C ayrımı mühürlü karşılaştırmaya alındı. | Görevin özgün tam model seti ve yeni kabul edilen modellerin UI entegrasyonu. | PARTIAL |
| 18 | PARTIAL | V12 Windows Qt kaynaklı kabul: 5 hisse, 15 sütun, 17 puan, INOD S11=0, N/A, fiyatın canlı olmadığı etiketi, S16-E/C ayrı; PASS. | Yeni yüklenebilir V12 build, kurulu uygulama kabulü ve açık dağıtım onayı. | PARTIAL |

**DONE: 0/10.** `BLOCKED`: 2 (10, 14). `PENDING_APPROVAL`: 1 (15).
Görev 9 ayrıca uzman incelemesi gerektirir; kayıt durumu PARTIAL çünkü
finansal veri kapıları da açıktır. Yeni kabul edilmiş kanonik PIT özellik:
**0/22**. Yeni doğrulanmış erken uyarı alarmı: **0**.

## B. Kabul edilmiş puanlar

| Hisse | S6 | S7 | S8 | S9 | S10 | S11 | S12 | B_Q | S14 | S16-E | S16-C |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| INOD | N/A | 100 | N/A | 55.555556 | N/A | **0** | 91.528866 | N/A | N/A | OFF/N/A | N/A |
| TMDX | N/A | 100 | N/A | 77.777778 | N/A | N/A | 85.403881 | N/A | N/A | OFF/N/A | N/A |
| CRMD | N/A | 100 | N/A | 55.555556 | N/A | 86.015359 | 95.682132 | N/A | N/A | OFF/N/A | N/A |
| PENG | N/A | 100 | N/A | 66.666667 | N/A | N/A | 83.512058 | N/A | N/A | OFF/N/A | N/A |
| ETON | N/A | 100 | N/A | 55.555556 | N/A | 7.860332 | N/A | N/A | N/A | OFF/N/A | N/A |

**Yeni tam Research puanı: 0; toplam: 17.** Bunlar güncel Research
hesaplarıdır, tarihsel PIT değildir. Fiyatlar 9 Ekim 2026 tarihli önbellek
kapanışlarıdır; V12 canlı fiyat göstermez. Kaynaklı beş-hisse makbuzu
`E:/M10/.master_tasks_v12_private/comparison/five_stock_v2.json`, SHA-256
`81cc4bdd7b634bb482bf8a1adfb417efd00c6f3c6965a8a8edca019bbbfc7c8b`.
Makbuz, V9'un 17 kabul edilmiş skorunu yalnız orijinal özel SEC kaynaklarından
yeniden oynatan yükleyiciden üretildi ve ayrıca çevrimdışı tekrarlandı.

## C. Açık kabul engelleri ve kararlar

| Koşul | Kanıt durumu | Teknik sonraki iş | İnsan/onay |
|---|---|---|---|
| S6/B_Q | ETON koşullu F_D ve üç gerçek DEPI korunuyor; aynı accession alternatif Beneish etiketleri **aday**. | STI/LTI/PREF, WC/NCO/FIN, COGS/SGA/TOTAL_DEBT kapsamı ve filing byte seal. | Muhasebe sınıflaması gerektiğinde bağımsız değerlendirme. |
| S13 ve INOD S14 | 14 SEC gövdesi, 27 bulgu, yedi imzasız bölüm; INOD 3/6. | İmzalı bulguları kaynakla doğrulayıp S13 ve ardından S14 Decimal replay. | Yetkili uzman 7/7 risk/maddilik/serious flag kararı. |
| S1–S3/S15.3 | Kısmi kaynaklı faktörler ve sürüm manifesti doğrulandı. | Eksik faktör aileleri, H, S15.2, M10/T10 ve senaryoları tarihli kaynakla kurma. | Şimdilik onay kapısı yok. |
| SEC PIT/S16-C | İki SEC accepted-at zamanı gerçek; geçmiş ilk yayım/sağlayıcı zamanı yok. | Tarihsel capture, issuer mapping, evren ve 22 özellik replay'i. | Gerekirse tarihsel kaynak erişim kararı. |
| S16-E | OFF, sayısal tasarım taslak. | Ön kayıtlı OOS cohort/holdout ve kalibrasyon. | Ayrı sözleşme ve üretim aktivasyon onayı. |
| S16-EA | Doğrulanmış alarm yok. | İlk haber yayımı, aynı-saat seans ve OHLCV sağlayıcı zamanları. | Şimdilik onay kapısı yok. |
| Windows PE | Kaynak kodu Qt staging PASS. | İzole V12 build, sürüm/kurulum testleri. | Kurulum, EXE dağıtımı, canlı DB geçişi ve PR merge ayrı açık onay. |

[Kalite/uzman paketi](MASTER_TASKS_V12_QUALITY.md),
[S1–S3/S15.3 kapıları](MASTER_TASKS_V12_CORE.md) ve
[PIT/S16 karar paketi](MASTER_TASKS_V12_PIT.md) ayrıntılı kaynak, SHA,
test ve fail-closed nedenlerini içerir.

## D. Windows dağıtım kararı

**Güvenli mevcut durum:** kurulu Personal Edition 1.0.6 ve canlı veritabanları
yerinde kalır. İzole kaynak ve özel veritabanı kopyasıyla yüklenebilir build
test edildikten sonra kullanıcı, belirli build hash'i ve hedef kurulum için
ayrı onay verebilir veya kurulu sürümü koruyabilir. Onay verilmezse görev 18
PARTIAL kalır. Onay sonrası kabul testi: build hash/sürüm doğrulama, yedek
doğrulama, kontrollü DB geçişi, 17 Research puanı/N/A ayrımı, Estimated OFF,
Canonical 0/22, tarihli fiyat, aç-kapat ve geri dönüş sınaması. Bu V12
çalışması kurulum, dağıtım, canlı DB geçişi veya merge yapmadı.
Depodaki Windows PyInstaller tarifi mevcut olsa da V12 ortamının Python
kurulumunda PyInstaller bulunmadığı doğrulandı; bu yüzden yeni bir V12 EXE
üretilmedi ve eski Phase27 EXE'si V12 build kabulü sayılmadı.

## E. Doğrulama sınırı

V12 özel kaynak makbuzları `E:/M10/.master_tasks_v12_private` altında;
ham SEC gövdeleri veya canlı DB Git'e alınmaz. Çevrimdışı kalite, temel model,
PIT, beş-hisse ve Windows kaynak tekrarları ayrı çalıştırılır. Windows Qt
staging makbuzu SHA-256
`4bacfafeb2543a7752b0192cf1942b3670f1588351129c81a8f76f14d8ace39a`.
Kaynak kodu/regresyon testleri, gerçek özel SEC kaynak doğrulaması ve kamu
CI testleri ayrı sayılır. Test veya başarılı PR, tek başına `DONE` değildir.
V12 `test_scoring_v12_*.py` kümesi **17/17**, kayıt kapısı testleri **3/3**,
Windows özel kaynak gerektiren V10 kümesi **43/43** geçti. V12 Windows Qt
makbuzu çevrimdışı yeniden oynatılarak da doğrulandı.
