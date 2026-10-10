# Meridyen M10 master To-Do status after Phase26B

The owner supplied **23 visible checklist items** on 2026-10-10 while referring to a 27-item master list. The four absent items are not invented here. Exactly **1 of the supplied 23 is complete and 22 remain open**. Full completion alone earns a check mark. Canonical acceptance remains 0 securities/0 dates; WF9 BLOCKED; Learning V3 NOT_TRAINED. Phase26B completed clean private Windows packaging checks but did not close any of the 22 evidence/release items.

## Faz 0 — Altyapı
- [ ] Tam sistem yedeği ve geri yükleme güvenliğini doğrula. Phase26A backup remains intact (654 entries). Phase26B found only four SQLite header-counter bytes differ from the live DB; no data pages differ. A newer full M10 application-state backup is under independent restore verification. A Windows OS image and later live writes are outside this acceptance.

## Faz A — Tarihsel evren
- [ ] 2024–2025 günlük PIT evren üyeliğini kanıtla. Retrospective lists remain research-only.
- [x] 464 kimlik çakışmasını doğrula veya karantinayı gerekçelendir. Phase25R/W carry all 464 conflict rows as quarantined; Phase25Z V2 retains the guard.
- [ ] Tarihsel CIK, CUSIP, hisse sınıfı ve borsa sürekliliğini doğrula. BKE SEC covers provide dated leads, not a full daily interval.
- [ ] Delisted ve birleşmiş şirketleri tarihsel evrene dahil et.

## Faz B — Fiyat ve corporate actions
- [ ] SITC/CURB bağımsız toplam getiri sertifikasyonu. Phase25S research pairs are not certification.
- [ ] Split, temettü, birleşme, delisting ve terminal getiri zincirini doğrula. Phase25Z adds BKE dividend announcements; BKE-specific ex-dates and full action/exit chain remain open.
- [ ] Bağımsız düzeltilmiş fiyat serisini oluştur ve doğrula. Partial public BKE raw-close probe cannot serve as adjusted total return.

## Faz C–D — SEC ve kanonik kabul
- [ ] SEC Accepted, kamuya yayım ve gerçek available_at kanıtları. Historical ingestion clock missing.
- [ ] Finansal özelliklerin tarihsel PIT kapsamını doğrula.
- [ ] Kanıtı tam hisse-tarih kayıtlarını kontrollü kanonik kabul et. Accepted 0/0.
- [ ] WF9 gerçek kanonik kabul testini çalıştır. BLOCKED.

## Faz E — Backtest
- [ ] WF5 tarihsel sinyal ve olgun 252 seans sonuçlarını üret.
- [ ] WF6 gerçek walk-forward OOS backtest. Phase25Y/Z fixed ex-post cohort arithmetic is not OOS.
- [ ] WF7/WF8 sağlamlık ve veri sızıntısı kontrolleri. Phase25Z V2 provides research-only leave-one-out/winsorization and machine risk gates, not canonical WF7/WF8.
- [ ] 2X/5X/10X ve Precision@K performansını doğrula.

## Faz F — Learning
- [ ] Olgun etiketleri Learning V2'ye kaydet.
- [ ] Learning V3 Challenger eğitimi ve gerçek OOS karşılaştırması. NOT_TRAINED.
- [ ] Güvenli öğrenme/hata analizi döngüsünü doğrula.

## Faz G — Windows ve teslimat
- [ ] Research / PIT / Learning masaüstü entegrasyonu. Phase26A opened the real Windows Research tab with 25 private candidates and the PIT/Learning evidence dialog twice. Full canonical PIT and Learning workflows remain blocked by evidence.
- [ ] Windows regresyonları ve uçtan uca CI. Phase26A had 734/734 local Windows tests and passing GitHub CI on PR #170. Phase26B selected 53 relevant tests passed; exact Phase26B PR CI and signed installer acceptance remain open.
- [ ] Üretim yedeği ve kurtarma testi. SQLite online snapshot and separate restore-probe quick_check passed. No restoration into the active runtime or protection of later live DB writes is claimed.
- [ ] Windows kurulum paketi, nihai kabul ve teslimat. Phase26B replaced DB-derived test seeds with public-source private-test seeds and built Python 3.11 EXE plus unsigned Inno installer. Publication remains blocked by a code-signing certificate, explicit seed distribution approval and a fresh official US seed decision.

## Phase26B release evidence

- PR dependency matrix and release blockers: PHASE26B_RELEASE_READINESS.md.
- Research V2 rejects missing, malformed, stale, hash-changed and canonical-promoted reports.
- Phase26A private backup remains intact; Phase26B app-state backup/restore status is tracked in PHASE26B_RELEASE_READINESS.md.
- Live DB and old snapshot differ in only four SQLite header-counter bytes; record pages match. The writer process is not identified.
- Frozen S15/S16 model contents and Hermes remain unchanged; no PR merged.

## Phase25Z incremental deliveries completed
- [x] Research Backtest V2 source-price sensitivity, exact attribution and fail-closed tests in PR #167.
- [x] Actual Windows Research Backtest screen, native screenshot inspection and research/canonical UI separation in PR #169.
- [x] BKE official dividend chronology plus bounded free raw-price availability probe in PR #168; canonical BKE remains blocked.
