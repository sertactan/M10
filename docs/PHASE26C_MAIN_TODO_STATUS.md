# Meridyen M10 master To-Do status after Phase26C

**Master count (26C):** The historical 27-item reference has only 23 recoverable original task descriptions in the Phase25Z/26A/26B source files and available prior context. Of these 23: **DONE 1, PARTIAL 9, BLOCKED 13**. Four unknown original tasks remain **UNVERIFIED/UNRECOVERED**, without fabricated descriptions. All 27 slots are accounted for (1+9+13+4); this does not claim the four unknown tasks were completed. Canonical: **0 securities/0 security-dates**; WF9 **BLOCKED**; Learning V3 **NOT_TRAINED**. Phase26C produced and verified a NEW isolated 1.0.6.0 EXE/installer; the master *Windows installer, final acceptance and delivery* item remains PARTIAL because production release conditions are not satisfied.

## Faz 0 — Altyapı
- [ ] **PARTIAL** Tam sistem yedeği ve geri yükleme güvenliğini doğrula. Phase26A backup remains intact: 654 items, same SHA-256. Phase26B app-state backup is complete: 4,754 entries, 21,049,260,727 bytes; 7 SQLite backup/restore quick_check=ok; manifest per-entry SHA-256 restore matches, 0 missing files and 0 size mismatches. This is an application-state snapshot, not a full Windows OS image, live production restore or atomic global-time capture.

## Faz A — Tarihsel evren
- [ ] **BLOCKED** 2024–2025 günlük PIT evren üyeliğini kanıtla. Retrospective lists remain research-only.
- [x] **DONE** 464 kimlik çakışmasını doğrula veya karantinayı gerekçelendir. Phase25R/W carry all 464 conflict rows as quarantined; Phase25Z V2 retains the guard.
- [ ] **BLOCKED** Tarihsel CIK, CUSIP, hisse sınıfı ve borsa sürekliliğini doğrula. BKE SEC covers provide dated leads, not a full daily interval.
- [ ] **BLOCKED** Delisted ve birleşmiş şirketleri tarihsel evrene dahil et.

## Faz B — Fiyat ve corporate actions
- [ ] **BLOCKED** SITC/CURB bağımsız toplam getiri sertifikasyonu. Phase25S research pairs are not certification.
- [ ] **PARTIAL** Split, temettü, birleşme, delisting ve terminal getiri zincirini doğrula. Phase25Z adds BKE dividend announcements; BKE-specific ex-dates and full action/exit chain remain open.
- [ ] **BLOCKED** Bağımsız düzeltilmiş fiyat serisini oluştur ve doğrula. Partial public BKE raw-close probe cannot serve as adjusted total return.

## Faz C–D — SEC ve kanonik kabul
- [ ] **PARTIAL** SEC Accepted, kamuya yayım ve gerçek available_at kanıtları. Historical ingestion clock missing.
- [ ] **BLOCKED** Finansal özelliklerin tarihsel PIT kapsamını doğrula.
- [ ] **BLOCKED** Kanıtı tam hisse-tarih kayıtlarını kontrollü kanonik kabul et. Accepted 0/0.
- [ ] **BLOCKED** WF9 gerçek kanonik kabul testini çalıştır. BLOCKED.

## Faz E — Backtest
- [ ] **BLOCKED** WF5 tarihsel sinyal ve olgun 252 seans sonuçlarını üret.
- [ ] **PARTIAL** WF6 gerçek walk-forward OOS backtest. Phase25Y/Z fixed ex-post cohort arithmetic is not OOS.
- [ ] **PARTIAL** WF7/WF8 sağlamlık ve veri sızıntısı kontrolleri. Phase25Z V2 provides research-only leave-one-out/winsorization and machine risk gates, not canonical WF7/WF8.
- [ ] **BLOCKED** 2X/5X/10X ve Precision@K performansını doğrula.

## Faz F — Learning
- [ ] **BLOCKED** Olgun etiketleri Learning V2'ye kaydet.
- [ ] **BLOCKED** Learning V3 Challenger eğitimi ve gerçek OOS karşılaştırması. NOT_TRAINED.
- [ ] **BLOCKED** Güvenli öğrenme/hata analizi döngüsünü doğrula.

## Faz G — Windows ve teslimat
- [ ] **PARTIAL** Research / PIT / Learning masaüstü entegrasyonu. Phase26A opened the real Windows Research tab with 25 private candidates and the PIT/Learning evidence dialog twice. Full canonical PIT and Learning workflows remain blocked by evidence.
- [ ] **PARTIAL** Windows regresyonları ve uçtan uca CI. Phase26A 734/734 tests passed; Phase26B focused 53/53 passed. Phase26C ran 7/7 relevant seed safety tests, aligned 1.0.6 version/PE resource and completed independent Windows build + isolated install smoke; PR #171 Python CI SUCCESS at b01ba5a. Canonical end-to-end workflows, signed production acceptance and Windows GitHub production-build workflow on this PR remain unverified.
- [ ] **PARTIAL** Üretim yedeği ve kurtarma testi. Complete Phase26B application-state backup/restore probe is verified (4,754 entries and 7 SQLite files). No destructive restoration into active runtime, disk/OS image, live-write catch-up or full disaster-recovery drill has been accepted.
- [ ] **PARTIAL** Windows kurulum paketi, nihai kabul ve teslimat. **Phase26C technical milestone DONE:** NEW Python3.11 EXE (SHA `9E4A04A7...`), real Windows PE FileVersion/ProductVersion `1.0.6.0`, ProductName/FileDescription/CompanyName populated. NEW Inno installer (SHA `A9D28E81...`), isolated doctor/SQLite/Qt/install/uninstall/reinstall all PASS; test DB preserved. Production release is still BLOCKED: Authenticode unsigned, 2026-06-01 mirror US test seed cannot pass SEC_DIRECT/freshness gate, redistribution approval and user publishing approval absent.


## Unrecovered master items (4)
Original task titles/descriptions #24–#27 are not present in the Phase25Z/26A/26B tracked checklists or recoverable earlier task text. They are **UNKNOWN / UNVERIFIED**, not DONE, and must not be silently reconstructed from adjacent topics. The count of 27 is a historical reference, not a verified 27-row inventory.

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

## Phase26B completed backup evidence (2026-10-10 JST)

- %LOCALAPPDATA%/S153ResearchTerminal/runtime/phase26b/full_app_state_20261010T26B/manifest.json: SHA-256 `C5FDFEA318E6FA00EF97F3778B5983965699A4E6826A3B1AF5D72E6833BE4E6D`; `BACKUP_AND_RESTORE_VERIFIED`, 4,754 entries, 21,049,260,727 bytes.
- Backup process completed at 2026-10-10 **22:11:20 JST**. The live operational SQLite source had LastWriteTime **20:49:46 JST** and was copied around **21:19–21:21 JST**; this is not a new 22:11 live DB snapshot. Remaining application files were captured sequentially, not atomically. Later live writes are not included.
- All entries have valid 64-character SHA-256 hashes and `restored_sha256_matches=true` as recorded by the snapshot creator; independently checked physical existence and sizes of all snapshot/restore pairs (0 missing, 0 length mismatches); all 7 SQLite source-to-snapshot methods have backup and restored `quick_check=ok`.
- Historical Phase24G 9,208,848,384-byte SQLite snapshot is independently included, with a verified restore copy. Phase26A old backup manifest retains its original SHA `DF78DF697A2947BAD9F3D18C96E64AF6B540A19E7EEF537380A077C87B6BC530` (654 entries).
- Scope excludes Windows OS/system image, credentials outside app state, post-capture writes, and active-runtime destructive restore. Release remains **BLOCKED**, overall Phase26B **PARTIAL** pending final acceptance. PR #171 remains OPEN and unmerged.

## Phase26C milestone completed (outside 27-item master count)

- [x] **DONE** Isolated fresh 1.0.6.0 Windows portable EXE built and all five real version metadata strings checked, with SHA-256 and `NotSigned` recorded.
- [x] **DONE** Source/provenance manifest `PRIVATE_TEST_ONLY` verified; legacy DB-export/stale/future/mirror production seed restrictions passed targeted tests; release gate rejected old SEC mirror.
- [x] **DONE** New Inno installer built, SHA-256 and `NotSigned` recorded, isolated install, Qt normal close, doctor/SQLite `quick_check`, uninstall/reinstall/final uninstall PASS.
- [x] **DONE** Existing Phase26A/B manifests retain original SHA-256, main live DB last-modified time unchanged, S15/S16/Hermes/canonical statuses protected; files not published.
- [ ] **BLOCKED (release-only)** Fresh official SEC_DIRECT seed, written redistribution approval tied to exact hashes, suitable signing certificate, final production acceptance and explicit publish permission.

These Phase26C deliverables are **milestones** within master tasks #21 and #23, not five additional master tasks. **FAZ26C_DONE (private-test engineering) / RELEASE_BLOCKED.** Detailed evidence: `PHASE26C_WINDOWS_ACCEPTANCE.md`.

