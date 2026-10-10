# Meridyen M10 master To-Do status after Phase25Z

The owner supplied **23 visible checklist items** on 2026-10-10 while referring to a 27-item master list. The four absent items are not invented here. `x` means that the entire supplied item is evidenced complete; partial progress is described under the still-open item. Canonical acceptance remains 0 security/0 date; WF9 BLOCKED; Learning V3 NOT_TRAINED.

## Faz 0 — Altyapı
- [ ] Tam sistem yedeği ve geri yükleme güvenliğini doğrula. Phase25Z did not run a recovery test.

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
- [ ] Research / PIT / Learning masaüstü entegrasyonu. Phase25Z completes a read-only Research Backtest screen; full PIT/Learning workflow is not complete.
- [ ] Windows regresyonları ve uçtan uca CI. New Windows Qt screen check and focused tests pass; complete canonical end-to-end delivery is outstanding.
- [ ] Üretim yedeği ve kurtarma testi.
- [ ] Windows kurulum paketi, nihai kabul ve teslimat.

## Phase25Z incremental deliveries completed
- [x] Research Backtest V2 source-price sensitivity, exact attribution and fail-closed tests in PR #167.
- [x] Actual Windows Research Backtest screen, native screenshot inspection and research/canonical UI separation in this PR.
- [x] BKE official dividend chronology plus bounded free raw-price availability probe in PR #168; canonical BKE remains blocked.
