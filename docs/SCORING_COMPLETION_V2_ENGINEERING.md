# MERİDYEN M10 — Scoring Completion V2 Engineering Verification

**Denetim tarihi:** 2026-10-11 JST  
**Alan:** `E:/M10/.phase29_scoring_completion`, branch `codex/scoring-completion-v2`  
**Yöntem:** önceden hazırlanmış çevrimdışı kanıtlar, mühürlü rapor yükleyicisi, mevcut testler ve gerçek raporla Qt `offscreen` UI doğrulaması. Bu denetim bir yeni üretim dağıtımı, kurulmuş Personal Edition kabulü, borsa sinyali, tarihsel PIT sertifikasyonu veya modellerin yeniden eğitimi değildir.

## 1. Doğrulanan yeni rapor ve Windows staging girişi

- Özel **salt okunur kaynak rapor**: `%LOCALAPPDATA%/S153ResearchTerminal/runtime/scoring_completion/v2_audit1/report.json` (923.119 byte), yanında `report.json.sha256` (64 byte).
- Raporun hesaplanan SHA-256 değeri `cb01a3923ee8a91fba901a92ee232f24e5a8823ae0ed9ff0ab2a911d7b773bb0`; yanındaki mühürle **birebir eşleşiyor**.
- Rapor `generated_at=2026-10-10T17:50:59.133218+00:00`, `schema=M10_SCORING_COMPLETION_RESEARCH_V1`. V2, ayrı bir rapor şeması iddiası değil, bu izole geliştirme/denetim aşamasının adıdır.
- Phase27 girdi: `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase27/current_scoring/staging.db`, **4.935.680 byte**, SHA-256 `1b4d410db5e09eaff4602f352fbc07d386062db6fcbc5d494decff46e398862a`.
- Phase28 girdi: `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase28/real_scoring_v1/stage.db`, **143.360 byte**, SHA-256 `170acb8d5e4b12b5a7bf06456360489869c1210b0457dc22754f488cbb824f5a`.
- **İki kaynak SHA-256 değeri de** mühürlü rapordaki `source_sha256.phase27` ve `source_sha256.phase28` alanlarına eşit. `app.scoring_completion.load_report(report, phase27, phase28)` başarılı; mühür, kaynak hash, sözleşme hashleri, beşli kohort, yirmi model satırı ve kanonik ret kapıları geçildi.
- Raporun alanları: `canonical_securities=0`, `canonical_dates=0`, `WF9=BLOCKED`, `LearningV3=NOT_TRAINED`, `S16_E_activation=PENDING_APPROVAL`, `S16_EA=PARTIAL_RAW_1M_DERIVED_5M_NEWS_AND_BASELINE_MISSING`. Yalnızca **9 tamamlanmış araştırma formül puanı** ve 5 puanlanmış hisse vardır.

| Hisse | Rapor fiyatı, USD (canlı değil) | S7 research | S12 research | Tam research formül adedi | Ayrı finansal özellik |
|---|---:|---:|---:|---:|---:|
| INOD | 62,04 | 100,00 | 91,528866 | 2 | 52 |
| TMDX | 77,87 | 100,00 | 85,403881 | 2 | 50 |
| CRMD | 7,38 | 100,00 | 95,682132 | 2 | 45 |
| PENG | 76,28 | 100,00 | 83,512058 | 2 | 19 |
| ETON | 55,21 | 100,00 | N/A | 1 | 44 |

Fiyatlar raporun **2026-10-09 UTC** tarihli önbellek fiyatlarıdır. S7/S12 aynı yıllık mali döneme hizalanmıştır (INOD/TMDX/CRMD/ETON için 2025-12-31; PENG için 2025-08-29). ETON'da pozitif yıllık net gelir şartı sağlanmadığından S12 kısmi marj tanısıdır, tamamlanmış bir puan değildir. S7=100 değerleri negatif Sloan accrual fallback kuralının çıktısıdır; güvenli şirket veya bağımsız forensic temizlik belgesi değildir.

## 2. Görev 9–18 durum matrisi — 2026-10-11

| Görev | Denetlenen faaliyet ve gerçek kanıt | V2 mühendislik durumu |
|---|---|---|
| **9 — S14 kaynak/formüller** | Kurtarılan S1–S14 kaynak hashleri ve altı ayak sözleşmesi mevcut. `recovered_quality` S7/S12'yi gerçek yıllık girdilerle hesaplıyor. Ayrı `recovered_beneish`, `recovered_dechow`, `recovered_jones`, `forensic_evidence` yardımcılarının sentetik/fail-closed testleri geçti; mühürlü raporda yeni tam B_Q/S6/S11/S13 puanı **yok**. | **PARTIAL** |
| **10 — INOD tam S14** | INOD S7=100 ve S12=91,528866; B_Q/S6/S11/S13 `DATA_MISSING` ve dört ayak daha gerektiriyor. Frozen altı ayaklı S14 tam kabulü **0**. | **BLOCKED / DATA_MISSING** |
| **11 — S1–S3** | Gerçek 3Y/5Y CAGR, margin, leverage ve kontrol zinciri kısmen kurulmuş; eksik ileriye dönük, DNA/router ve tarihsel karşılaştırma delilleri giderilmiş değil. S1/S2/S3 tam puanı **0**. | **PARTIAL** |
| **12 — S15.3** | V1.2/V1.4/V1.4.1 motorları önceki araştırma kanıtında çağrılmıştır; mühürlü raporda gereken tüm kaynaklar/model fit/yol kapıları sağlanmadığından tamamlanmış puan **0**. | **PARTIAL / INCONCLUSIVE** |
| **13 — SEC kabul saati** | Önbellekte INOD için iki accession form+filingDate+accepted-at eşleşti. Gerçek ilk kamuya açıklama ve tarihsel provider `available_at` kesinleşmedi; kalite girdi kanıtındaki `accepted_at` hâlâ null (ayrıntı §3). | **PARTIAL / NOT HISTORICAL PIT** |
| **14 — S16-C** | Günlük ham volume/momentum/risk araştırma ölçüleri mevcut. 22 özellikten bağımsız kanonik PIT normalize edilmiş kabul **0/22**; S16-C skoru yok. | **PARTIAL / BLOCKED SCORE** |
| **15 — S16-E** | Sayısal tasarım/prototip ve çevrimdışı sentetik testler var; gerçek piyasa kalibrasyonu/etkinleştirme onayı yok. Rapor `PENDING_APPROVAL`. | **PARTIAL / PENDING_APPROVAL** |
| **16 — S16-EA** | Kaynak hashli 2.126 geçerli 1m bar, 218 türetilmiş 5m, 254 premarket-clock bar. Bağımsız seans takvimi, haberin ilk yayımı ve yeterli same-clock baseline eksik. **0** doğrulanmış alarm. | **PARTIAL / BLOCKED ALERT** |
| **17 — Beşli kohort** | Gerçek kanıtla 5 S7 + 4 S12 = **9** tamamlanmış research puanı; ETON S12 N/A. Diğer S1–S16 modelleri tamamlanmadı. | **PARTIAL; FORMULA SUBTASK VERIFIED** |
| **18 — Windows staging UI** | Yeni rapor ve staging DB hashleriyle Qt offscreen GUI iki açılış/kapanışta doğrulandı; 8 sekme, 5 hisse, hisse başına 20 model ve uyarılar doğru. Personal EXE kurulumu/üretim servisleri denenmedi. | **STAGING VERIFIED; PE DEPLOYMENT PENDING** |

**Tüm 10 görevi uçtan uca DONE ilan etmek için kanıt yok.** Gerçek skorların tamamı `CURRENT_RESEARCH_ONLY` / `RESEARCH_ONLY_NOT_CANONICAL_PIT` kapsamındadır.

## 3. Gerçek arşivlenmiş SEC/fact kanıtındaki eksik alanlar

Bu alanlar `v2_audit1/report.json` içindeki **gerçek quality evidence ve `missing` listeleri** üzerinden yeniden sayıldı; SEC'in genel veri tabanında bu verilerin hiçbir yerde bulunmadığı anlamına gelmez. Ama rapora kabul edilmiş, dönemi ve erişim koşulları doğru hizalanmış girdi paketinde mevcut **değiller**:

1. **B_Q / Beneish:** INOD, TMDX, CRMD, ETON için `AR_T_EXACT_FY`, `COGS_T_EXACT_FY`, `PPE_T_EXACT_FY`, `DEP_T_EXACT_FY`, `SGA_T_EXACT_FY`, `DEBT_T_EXACT_FY` ve altı alanın `*_PREV_EXACT_FY` karşılıkları (toplam **12 eksik girdi etiketi/hisse**). Bu etiketler hesaplamanın talep ettiği exact FY kaynağı/periodu belirtir; SEC kavram alias'larının başka yıllarda olması eşdeğer sayılmaz. PENG için önce `CONTIGUOUS_PRIOR_FISCAL_YEAR` engeli var; sonraki alanların kabul edilebilirliği bu aşamada ispatlanmadı.
2. **S6 / Dechow:** Beş hissede `RSST_COMPONENTS`, `THREE_PERIOD_CASH_SALES_ROA`, `ISSUANCE_EVIDENCE`, `PEER_OR_UNAMBIGUOUS_FALLBACK` eksik. Kaynak formülün test edilmesi, bu gözlemsel alanları üretmez.
3. **S11 / Modified Jones:** Beş hissede `INDUSTRY_YEAR_JONES_REGRESSION` ve `EVIDENCED_DISCRETIONARY_ACCRUAL` eksik. Gerçek industry-year peer evreni, PIT uygun katsayılar ve filing kanıtı olmadan OLS sonucu kabul edilmedi.
4. **S13 / forensic:** Beş hissede AUD, RPT, REC, DIL, REV, ACQ, GOV için **yedi ayrı dosya-temelli karar** ve `INDEPENDENT_SERIOUS_FLAG_COUNT` eksik. Kaynakta kayıt olmaması `0 risk` veya `0 ciddi flag` sonucuna dönüştürülmedi.
5. **S12 / ETON:** `CCR_POSITIVE_NET_INCOME` ile `FCFCR_POSITIVE_NET_INCOME` koşulları yok; sonuç bilerek `PARTIAL` ve `score=null`.
6. **Saat ve kaynak meta kanıtı:** Beş hissede S7/S12'nin quality `evidence.inputs` dizilerinde **40 satır** bulundu (5×4 S7 + 5×4 S12); bunların **0/40** satırında `accepted_at` dolu. `available_at` bulunsa da bu veri tek başına **ilk kamuya yayım** veya tarihsel sağlayıcı erişilebilirliği kanıtlamaz. Raporda ayrı `sec_acceptance_verifications` yalnızca INOD için iki accession içeriyor; öteki dört hissenin bu haritadan kanıtlandığı iddia edilemez.

**INOD SEC resmi submissions önbelleği:** 162.393 byte; SHA-256 `070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3`. Kaynak bytes/hash receipt ile eşleşti ve kullanılan 8 satırın 2 benzersiz accession'a dayandığı denetlendi:

| SEC accession | Form | SEC filingDate | SEC accepted UTC | İlk kamuya yayım | Tarihsel provider available_at |
|---|---|---|---|---|---|
| `0001104659-26-020655` | 10-K | 2026-02-26 | 2026-02-26T22:22:13Z | **Bilinmiyor** | **Bilinmiyor** |
| `0001104659-26-092021` | 10-Q | 2026-08-06 | 2026-08-06T20:15:14Z | **Bilinmiyor** | **Bilinmiyor** |

SEC `accepted-at` idari kayıt zamanıdır. İlk kamuya duyuru, satıcının ilk erişim saati ve geçmişte stratejinin gerçekten görebildiği en erken zamanla eşitlenemez.

**S16-EA çevrimdışı intraday:** SEC'ten farklı Yahoo araştırma kaynağı; 172.979 byte response SHA-256 `6f3746effd4dad60c5944a65b7c6f989757e61f14cd5772475cefd176bd400f1` receipt ile eşleşti. `2026-10-05`–`2026-10-09` arası yalnız **5 ET takvim tarihi**, örnek 09:33 ET için 5 distinct-date bar; öneri araştırma alt sınırı 20 same-clock session için yetersiz. Kaydedilen bar kayıtlarında tarihsel `available_at` ve doğrulanmış `source_ref` yok. Receipt: `same_clock_baseline_validated=false`, `session_calendar_validated=false`, `exchange_certified=false`, `news_first_public_time=null`, `alert_generated=false`. Eksik premarket verisi sıfır hareket varsayılmadı.

## 4. Bağımsız modüller, kanıt sınırları ve testler

| İlgili modül / test | Test adedi | Sonuç, kullanılan gerçek yorum |
|---|---:|---|
| `app/recovered_quality.py` / `test_recovered_quality` | 11 | **PASS** — S7/S12 formül/period/hata kapıları, sentetik mali testler |
| `app/recovered_beneish.py` / `test_recovered_beneish` | 5 | **PASS** — explicit risk ve bağımsız flag review koşulları; gerçek B_Q henüz N/A |
| `app/recovered_dechow.py` / `test_recovered_dechow` | 4 | **PASS** — logit/3 yıllık veri/eşiksiz kanıt kapıları; gerçek S6 henüz N/A |
| `app/recovered_jones.py` / `test_recovered_jones` | 18 | **PASS** — OLS rank/kohort/SEC time gate; gerçek S11 henüz N/A |
| `app/forensic_evidence.py` / `test_forensic_evidence` | 14 | **PASS** — yedi forensic blok ve bağımsız bayraklar; gerçek filing body gözlemleri eksik |
| `app/scoring_intraday_research.py` / `test_scoring_intraday_research` | 3 | **PASS** — kapalı 1m bar, 5m aggregation, DST |
| `app/scoring_estimated_draft.py` / `test_scoring_estimated_draft` | 13 | **PASS** — offline deneysel tasarım; etkinleştirme yok |
| `app/scoring_event_evidence.py` / `test_scoring_event_evidence` | 14 | **PASS** — SEC accession/form/date/clock ve S16-EA ilk haber yayımı, as-of, same-clock, takvim, eksik-bar kapıları; score ve alarm üretmiyor |
| `app/ui/scoring_completion_page.py` / `test_scoring_completion_ui` | 2 | **PASS** — geçersiz rapor ve eski skor temizliği |
| `app/scoring_completion.py` / `test_scoring_completion` | 7 | **PASS** — kaynak hash, sıra/kaynak uyuşmazlığı ve research model kapsamı |
| Phase27 `test_phase27_current_scoring` | 8 | **PASS** — mevcut research staging regresyonları |
| Phase28 `test_phase28_real_scoring` | 7 | **PASS** — mevcut real-scoring staging regresyonları |

Test çalıştırıcı: `E:/M10/.venv/Scripts/python.exe` (Python 3.13.3, PySide6 6.11.2), `PYTHONDONTWRITEBYTECODE=1`, UI için `QT_QPA_PLATFORM=offscreen`.

**Temiz test yürütmeleri:**

1. `python -m unittest -q tests.test_scoring_completion_ui tests.test_scoring_completion tests.test_phase27_current_scoring tests.test_phase28_real_scoring` → **24 test, OK, exit 0**.
2. `python -m unittest -v tests.test_recovered_quality tests.test_recovered_beneish tests.test_recovered_dechow tests.test_recovered_jones tests.test_forensic_evidence tests.test_scoring_intraday_research tests.test_scoring_estimated_draft` → **68 test, OK, exit 0**.
3. `python -m tests.test_scoring_event_evidence` → **14 test, OK, exit 0**.
4. İlk geniş denemede yukarıdaki 24 teste eklenen `tests.test_phase9_ui` modülü `import pytest` sırasında **ModuleNotFoundError: No module named 'pytest'** ile yüklenemedi: 24 geçerli test başarılı, 1 test-modülü import error, komutun çıkışı **1**. Bu testin assertion sonucu değildir; Phase9 pytest kapsaması bu ortamda doğrulanmış sayılmaz. Daha sonra temiz 24-test çağrısı ayrı çalıştırılıp exit 0 alındı. Paket kurulmadı.

**Gerçek kaynaklı Qt offscreen Windows GUI smoke:** Aynı mühürlü rapor ve iki staging DB ortam değişkeni kullanılarak `ResearchTerminalWindow` **iki ayrı açılış/kapanış** döngüsünde çalıştırıldı: `platform=offscreen`, her döngüde **8 sekme**, **5 hisse**, hisse başına **20 model**, beş S7=100 görsel satırı, dört S12 sayısı ve ETON S12=`N/A`; S14 uyarısı, research-only/canonical 0/0 ve `not live` mesajları kontrol edildi. Model ayrıntı alanı salt okunur; sekme geçişleri, pencere kapanışı ve yeniden açılış **PASS**. Analysis/scanner/data-health/control-center servis fabrikaları yapılandırılmadı. Rapor, Phase27 ve Phase28 girdi dosyalarının **önce/sonra SHA-256** değerleri aynı kaldı. GUI testi bir gerçek Windows platform screenshot/pencere kabulü değildir; `offscreen` olduğundan ekran kartı, OS pencere yöneticisi ve kurulmuş EXE ayrıca doğrulanmalıdır.

Aynı izole dalda başka işçilerin `app/ui/scoring_completion_page.py` dosyasına sonradan eklediği dört araştırma sütunu nedeniyle **güncel 11 sütunlu UI** üzerinde ayrıca iki taze döngü gerçekleştirildi: 8 sekme, 5 hisse, her hissede 20 model **PASS, exit 0**; S14 alanı beş hissede `N/A`, S14 bacak kapsamı INOD/TMDX/CRMD/PENG için `2/6`, ETON için `1/6`; S16-E ve S16-C hücreleri `N/A`. Kontrollerden sonra rapor ile iki staging DB'nin SHA-256 değerleri değişmedi. Böylece son UI değişikliği eski rapordaki eksik alanları sayıya çevirmedi. `app/scoring_completion.py` içine başka işçi tarafından eklenen SEC Companyfacts kısmi araştırma bağlama yolu ayrıca incelendi; bu yolun sonraki raporlara olası etkisi **bu sabit `v2_audit1` raporundaki gerçekleşmiş tam skor** sayılmadı. Güncel modülle tekrar koşulan 24 UI/Phase27/Phase28 testi de **OK, exit 0**.

İlk özel Qt offscreen denemesinde PowerShell'den Python'a aktarılan Unicode sekme adı bir replacement karakterle karşılaştırıldığı için **harness assertion exit 1** oluştu. Devamında kaynak dosyayı değiştirmeden sekme sayısı ve ASCII `SCORING COMPLETION` kimliğiyle doğrulama tekrarlandı; iki döngünün tamamı **PASS, exit 0**. İlk hata GUI veri/hesaplama hatası olarak sınıflandırılmadı.

## 5. Koruma sınırı ve sonraki kanıt

Bu bağımsız çalışma sırasında sadece **yeni** `docs/SCORING_COMPLETION_V2_ENGINEERING.md` oluşturuldu. Aktif kullanıcı DB'sine, Personal Edition EXE'ye, mevcut staging dosyalarına, M10 ana worktree'sine, üretim servislerine ve Hermes'e dokunulmadı. Özel rapor/DB tekrar hesaplanmadı veya yazılmadı; bağımsız repo işçilerinin diğer yeni/çalışan dosyaları değiştirilmedi. Kaynak doğrulama ve UI deneyleri veri okuma ile sınırlıydı.

Tam S14/S16 için exact-period finansal alanlar, Beneish geçerli peer+flag incelemesi, doğrulanabilir Dechow RSST/issuance, tarihli industry-year Jones kohortu, yedi filing-body forensic incelemesi, ilk SEC yayım/provider saatleri ve 22/22 S16-C PIT normalize özellikler gereklidir. S16-EA için kaynaklı haber first-published, doğrulanmış gerçek takvim, her geçmiş dakika barı için provider `available_at` ve yeterli same-clock geçmiş günleri gereklidir. Bunlar olmadan yeni skor, geçmişte yakalanmış alarm, WF9 başarı veya Learning V3 eğitim çıktısı ilan edilmemelidir.

İlgili taban belgeleri: `docs/SCORING_TASKS_09_18_STATUS.md` ve `docs/RECOVERED_QUALITY_CONTRACTS.md`; bunlar bu teslimde değiştirilmedi.

## 6. V2 ek SEC Companyfacts kurtarma, bağlı Windows raporu ve nihai testler

Bu bölüm, yukarıdaki `v2_audit1` mühürlü GUI denetiminden **sonra** gerçekleştirilen mühendislik adımlarını kaydeder. Orijinal SEC Companyfacts dosyası mevcut normalize arşivde olmadığından, mevcut gerçek SEC iletişim yapılandırmasıyla tek resmî HTTP 200 isteği sonucunda **2.949.045 bayt** veri `%LOCALAPPDATA%/S153ResearchTerminal/runtime/scoring_completion/v2_sec_probe1/companyfacts.json` dosyasına özel olarak kaydedildi. Ham kaynak SHA-256: `6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`. İleti kaydındaki SEC 10-K `0001104659-26-020655` ile 2024/2025 exact-period XBRL kayıtları doğrulandı; içeren tekil türetme makbuzunun hash'i `286bcf1289515b7eae2b5765bc6a9207e7766bfaa5f47337f8ebe32a3c2338cb`.

| Özgün Beneish ara oranı | INOD FY2025/FY2024 | Tam bileşen mi? |
|---|---:|---|
| DSRI | 1,1245852440 | Kaynaklı ara hesap |
| AQI | 0,5989734840 | Kaynaklı ara hesap |
| SGAI | 0,9446728769 | Kaynaklı ara hesap |
| SGI | 1,4763670282 | Kaynaklı ara hesap, tek başına ceza değil |
| TATA | -0,08642707586 | Kaynaklı ara hesap |

COGS, yalnız amortisman/depreciation tanımı, toplam faizli borç ve inventory resmi exact tag'leri eksiktir. Eşdeğer olmayan `Liabilities`, `LongTermDebt` veya genel `DepreciationDepletionAndAmortization` alanı yerine kabul edilmedi. Tam B_Q ve S14 skorları N/A kaldı. SEC acceptance, ilk kamu yayımı ve tarihsel sağlayıcı erişimi ayrı zaman alanları olarak korundu. Bu yeni indirme önceden tamamlanmış 2026-10-10 tarihli `v2_audit1` çalışmasının aşaması değildir.

Bağlanan yeni mühürlü rapor: `%LOCALAPPDATA%/S153ResearchTerminal/runtime/scoring_completion/v2_audit2/report.json` ve `.sha256`. `app/scoring_completion.py` içindeki `attach_sec_companyfacts_partial` gerçek ham dosya hash'ini ve exact SEC tag araştırma makbuzunu yeniden hesaplayarak doğrular; mevcut 9 tam S7/S12 puanını, S14/N/A veya kanonik ret kapılarını değiştirmez. `app/ui/scoring_completion_page.py` 11 sütuna genişletilerek S14 ve 2/6 kapsamı ile S16-E ve S16-C ayrı N/A sütunlarını gösterir, beş ham SEC oranını yalnız salt okunur ayrıntıda sunar. Yeni `scripts/scoring_stage_smoke.py` komutu gerçek mühürlü `v2_audit2` ve kaynak DB hashleriyle Windows PySide6 offscreen **PASS**: 5 hisse, 11 sütun, S14 2/6, 5 SEC oranı, kanonik 0, kurulu Personal Edition ve DB değişikliği yok.

**Son tekil test koşuları:** mevcut staging/Phase27/Phase28 testleri **24/24 PASS**, kalite/B_Q/S6/S11/S13 ve SEC raw/opsiyonel entegrasyon/estimated/intraday **75/75 PASS**, olay-zaman doğrulaması **14/14 PASS**. Toplam **113 test PASS**; dosyalardaki kaynak düzeni/ikincil pytest kapsamı için ayrıca eski PR CI geçerliliği korunmuştur. Bu skor/analiz sonuçlarının hiçbirisi sentetik test çıktılarıyla gerçek INOD S14 olarak genişletilmedi.
