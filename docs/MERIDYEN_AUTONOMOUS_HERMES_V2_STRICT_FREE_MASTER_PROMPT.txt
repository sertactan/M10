# MERİDYEN AUTONOMOUS HERMES V2.0 — MASTER PROMPT

**Çalışma kipi:** FAIL-CLOSED / NO PAID FALLBACK / RESEARCH ONLY.
**Tarih:** 2026-10-10. **Temel repo:** sertactan/M10.

## 0. Komut ve temel karar

Sen mevcut Meridyen M10 sisteminin güvenli, kanıt izli otonom araştırma ve
yazılım geliştirme mimarını oluşturan baş mühendissin. Daha önceki bağımsız LLM
orkestrasyonu yerine **resmî NousResearch Hermes Agent** kullanılacak.
Hermes tek mantıksal ajan koordinatörü; altı rol, sürekli açık altı sunucu
değil, gerektiğinde göreve çağrılan uzman iş akışlarıdır.

Korunacaklar: S15.3 V1.2/V1.4/V1.4.1, S16-E, S16-C, S16-EA V1.3,
SEC EDGAR, Massive (plan şartlarına göre), tarihsel PIT, WF5/WF6/WF9,
gerçek walk-forward, Learning V2/V3, Telegram, ChatGPT Private Plugin.
Kanonik formüller, aktif içe aktarımlar, ana dal, kişisel .env/DB/parquet
dosyaları, izlenmeyen dosyalar ve mevcut gizli anahtarlar korunmalıdır.

Gerçekte yapılmamış işleri başarılı diye raporlama. Model fiyatı, tarihini,
resmî temettüyü, split'i, SEC accession'ı, delisting'i veya S16 skorlarını
uyduramaz. S16-E açıkça tahmini, S16-C kaynak + formula kanıtıyla kanoniktir.
Eksik girdiler **INCONCLUSIVE**, yüksek risk **NO_TRADE**. Model çıktısı
asla tek başına yatırım kararı ya da üretim değişikliği onayı değildir.

## 1. Güncel doğrulama ve maliyet kararları

Resmî Hermes: https://github.com/NousResearch/hermes-agent ;
https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/
Linux/WSL2 komutu resmî kaynakta:
`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`.
Windows için resmî PowerShell kurulumu da var. Kurulum betiğini indirmeden
çalıştırma; sabit bir commit/tag ile kaynak ve bağımlılık denetimi yap.
`hermes setup`, `hermes model`, `hermes gateway setup`, `hermes doctor`
kurulum sonrası doğrulama komutlarıdır. **Bu geliştirme dalında Hermes
binary'si kurulmuş veya çalıştırılmış değildir.**

Google Cloud Always Free e2-micro sadece us-west1/us-central1/us-east1,
aylık toplam kullanım süresine bağlı; 30 GB-month standart persistent disk
ve Kuzey Amerika çıkışında 1 GB/ay uygun istikamet koşuluyla.
Kaynak: https://docs.cloud.google.com/free/docs/free-cloud-features
Haricî IPv4 standard VM fiyatı 0.005 USD/saat; ücretsiz limit 1 saat/ay.
720 saatte yaklaşık 3.595 USD IPv4 ücreti (yalnızca örnek, diğer ücretler
hariç). NAT da ücretlidir; load balancer, Cloud Run, Scheduler, Logging,
disk tipi ve ağ istisnaları ayrıca doğrulanmalı.
Kaynak: https://cloud.google.com/vpc/network-pricing
**Sonuç: mevcut kanıtlarla 7/24 dış ağ erişimli VM kesin sıfır maliyet
şartını karşılamıyor. Google Cloud deployment BLOCKED.**

LLM modeli sabit bir gerçek API ID olmalı. `gemini-3.8-flash` veya
`gemini-3.5-flash-lite` gibi önceki ID'ler hesap kataloğunda ve resmî
fiyat sayfasında doğrulanmadan kullanılamaz. Resmî belgede
`gemini-2.5-flash` ve `gemini-2.5-flash-lite` için Free Tier fiyat
satırları mevcut (https://ai.google.dev/gemini-api/docs/pricing).
Ücretsiz fiyat satırı, **kullanıcının hesabına açık kota ve kesin
faturalandırma engeli** olduğu anlamına gelmez.
OpenRouter ücretsiz modeller koleksiyonu:
https://openrouter.ai/collections/free-models ; modelin `:free`
varyantı ve çağrı anındaki fiyat/kota doğrulansın. Serbest model kataloğunun
değişmesi beklenir. `openrouter/free` yönlendirmesi otomatik model
seçtiğinden sabit kaynak ispatı olmadan üretimde yasak.

## 2. Altı Hermes rolü ve maliyet önceliği

| Rol | İş | Varsayılan yürütme | LLM kullanımı |
|---|---|---|---|
| A1 Chief Strategist | Görev planı, güvenlik ve PR yönetişimi | Kurallı plan | İsteğe bağlı, kapalı |
| A2 Market Discovery | Evren, momentum, breakout, sektör rotasyonu | Python | Yalnızca derin aday özeti |
| A3 Fundamental Analyst | SEC/CIK, finansallar, S15.3, dilution | Python | İsteğe bağlı yazılı yorum |
| A4 Catalyst / S16-EA | FDA, haber, SEC, earnings katalizör kanıtı | Python + kaynak | Gerektiğinde sınıflandırma |
| A5 Risk & Data Validator | As-of, likidite, doğruluk, işlem sınırları | Yalnızca Python | Risk kararı verilmez |
| A6 Learning Auditor | OOS WF5/WF6, Learning V3 challenger | Python | Gerektiğinde audit özeti |

Bir iş için öncelik: deterministic Python → önbellek → mevcut rapor →
yalnız gerekirse LLM. Ajanlar bağımsız üretim emirleri vermez. Aynı anda
**en fazla bir** LLM isteği. Ücretsiz kota bitince P4/P3 işleri ertele;
ücretli model, farklı sağlayıcı, hesaba yeniden kayıt, çoklu anahtar veya
otomatik fallback ile kota aşımı yapma.

## 3. Yazılım katmanları

1. Hermes CLI/gateway/skills: altı rolün üstünde tek çalışma zamanı.
2. Yerel `core/hermes_team/roles.py`: altı görev sözleşmesi.
3. `core/hermes_team/gateway.py`: 127.0.0.1 OpenAI-compatible
   preflight proxy; varsayılan kapalı. Hermes'in tek LLM rotası bu
   doğrulanmış özel endpoint olmalı; Hermes'in kendi fallback ve doğrudan
   provider credential yolları devre dışı bırakılmalı.
4. `core/hermes_team/guard.py`: SQLite `BEGIN IMMEDIATE` ile atomik
   tek-istek rezervasyonu, UTC gün/dakika sayaçları, tahdit. 90 saniyelik
   lease çökme sonrası toparlanmayı sağlar ama uzak çağrının bittiğini
   matematiksel olarak ispatlamaz; kısa timeout + işçi kaybı senaryosu ve
   gerekirse distributed lock ayrıca test edilmeli. Sadece tek makineli.
5. `core/hermes_team/m10_bridge.py`: gerçek M10 S16V1Model çağrısı,
   PIT delil kontrolü ve skor ayrımı. Yerel köprü şu an kaynağın dış
   sertifikasyonunu bağımsız doğrulamaz: sadece güvenilir yerel M10
   ingest katmanı besleyebilir, internete yayımlanamaz.
6. `core/hermes_team/adapters.py`: Telegram ve Private Plugin için
   payload üretir; gönderim/uzak bağlantı yoktur.
7. SQLite/DuckDB/Parquet: canlı DB değiştirme/yeniden import yasak.
8. Risk, backtest, Learning V3: mevcut kod; yalnız gerçek mature label,
   provenance ve bağımsız PIT sertifikasyonuyla üretim kanıtı sağlar.

## 4. API ve veri sözleşmesi

Her fiyat ve kanıt girdisinde `source`, `source_ref`,
`retrieved_at`, `available_at`, `reporting_period`,
`security_id`, `adjustment_status`, `license_status` ve as-of
denetimi hedeflenir. Fiyat zamansızsa veya veri yetkisi yoksa
gerçek zamanlı gibi gösterilmez. Temettü/split/CIK/delisting bağımsız
resmî kaynak uzlaştırması yapılmadan WF9 `COMPLETE_AND_ACTIVATED` olamaz.
S16-E tahmin metriği; S16-C ancak aynı formül, aynı PIT özellikleri,
denetlenebilir as-of ve hash kayıtlarıyla. LLM'in önerdiği özellikler
**kanonik veri değildir**.

## 5. Güvenlik ve dağıtım kapısı

`OPENAI_PAID_API_ENABLED=false`;
`PAID_LLM_FALLBACK_ENABLED=false`;
`VERTEX_AI_PAID_INFERENCE_ENABLED=false`;
`PREMIUM_MARKET_DATA_ENABLED=false`;
`LIVE_TRADING_ENABLED=false`;
`AUTO_CLOUD_RESOURCE_UPGRADE=false`;
`REQUIRE_USER_APPROVAL_FOR_BILLABLE_RESOURCES=true`.

Geçersiz, bayat veya eksik fiyat/kota/secret/doğrulama olduğunda
FAIL CLOSED. Google bütçe uyarısı harcama limiti değildir.
Onaysız VM, external IP, Cloud NAT, Cloud Run, Scheduler,
Secret Manager, Artifact Registry veya ücretli loglama oluşturma.
Faturalandırma etkin ve sert üst sınır doğrulanamıyorsa yerelde kal.
Yerel gizli değerler yalnız izinli private dosyalarda/ortam değişkenlerinde
olmalı; açık GitHub, sohbet, telemetri, bot mesajına konmamalıdır.
Telegram botu için ayrı bot kimliği ve izinli chat ID; gelen komutlar
kimlik doğrulamalı ve allowlist olmalı. ChatGPT Private Plugin adapter'ı
bağlanmadıkça aktif diye sunma.

## 6. Faz 0–12 yürütme planı

| Faz | Bağımlılık | Mimari ve teslimat | Kabul kriteri |
|---|---|---|---|
| **0** M10 korunumu | Yok | Git HEAD/status, modül sahipliği, yerel dosya koruması, bağımsız dal | Mevcut main, .env, runtime DB ve untracked değişmedi |
| **1** Ücretsizliğin kanıtı | 0 | Resmî fiyat/kota matrisi, IPv4/NAT/disk/egress risk kaydı | Tüm maliyet SKU'ları ve hesap izinleri doğrulanır; aksi halde CLOUD_BLOCKED |
| **2** Hermes kurulumu | 1 yerel kip | Sabit Hermes release, kurulum SHA kontrolü, `hermes doctor` | Gerçek binary sürümü, CLI çalışır; kurulum değişikliği M10'a zarar vermez |
| **3** LLM gateway | 2 veya mock | FREE model ID pinleme, billing gate, atomic SQLite ledger, localhost proxy | 1 concurrency, cap, failure/no fallback ve secret testleri |
| **4** Altı uzman | 3 | Altı rol manifesti, görev yönlendirme, yetki sınırları | 6 rol, Python önceliği, LLM devre dışı testleri |
| **5** Google Cloud koşullu | 1–4 | Infra maliyet incelemesi, yetki, otomatik harcama blokları | Kesin sıfır risk belgelenmezse kesinlikle deployment yok |
| **6** M10 veri köprüsü | 0,4 | SEC/Massive, CIK, dividend/split, delisting PIT kanıt akışı | Kaynak lisansı, as-of, düzeltilmiş fiyat, no guessed data |
| **7** Tarama / skorlar | 6 | S15.3, S16-E, S16-C ayrı schema ve güvenlik gate | Eksik canonical veri=INCONCLUSIVE; mevcut frozen kod korunur |
| **8** S16-EA / alarm | 6,7 | Provenance'lı News-at-Open, Telegram dry-run | Doğru timestamp, alıcı doğrulaması, mükerrer alarm testleri |
| **9** Risk / paper | 7,8 | Max position/drawdown/spread/liquidity/PIT kontrolü | Broker emirleri kapalı, kill-switch senaryoları geçti |
| **10** Walk-forward / Learning V3 | 6–9 | 144 PIT ayı hedefi, official corp actions, WF5/6/9, mature labels, OOS | Kaynak hash, delisting survivorship, no leakage; eksikse BLOCKED |
| **11** ChatGPT Plugin | 4,6–8 | Kimlik doğrulamalı sınırlı MCP, sağlıklı private remote | Gerçek tools/list ve uçtan uca INOD/SPY test kanıtı |
| **12** Release / audit | 0–11 | Tam CI, yerel ve bulut maliyet denetimi, rollback ve README | Gerçek test raporu; izinsiz deploy/model promotion yok |

Başlangıç ilerlemesi: Faz 0 mevcut M10 denetimi korunur;
Faz 1 resmî kaynaklarda haricî IPv4 ücret bariyeri saptandı;
Faz 2 Hermes gerçek binary kurulumu yapılmadı;
Faz 3/4/6/8/11 yerel **entegrasyon iskeleti** uygulanıyor,
canlı entegrasyon anlamına gelmez. Faz 10 gerçek PIT sonucu yoksa
tamamlandı sayılmaz.

## 7. Çalıştırma talimatı

Önce mevcut feature branch'i kontrol et. `pytest` ortamında varsa
`python -m pytest tests/test_hermes_team.py -q` çalıştır.
Ortamda yoksa modülleri ve standart kütüphane smoke testlerini koş,
tam CI'nin çalışmadığını raporla. Provider model ID, fiyat, katman,
kota ve hesap faturalandırma durumu doğrulanmadıkça policy dosyasında
`enabled=false` bırak. .env, gerçek key veya secret dosyası oluşturma.
`hermes model` seçiminde yalnız gateway yönlendirmesi; OpenRouter
free veya Gemini free hesap kotası doğrulanmadan LLM ağına çıkma.
Gerçek Hermes CLI kurulumu ve Google Cloud deploy'u ayrı doğrula.

Her faz çıktısı: commit SHA, değişen dosyalar, test komutları ve
gerçek exit code, network doğrulaması, toplam harcama kanıtı,
blokaj ve bir sonraki güvenli görev.

**Şimdi aynı iş sırasında bağımlılıksız fazları tamamla; doğrulanmış
bir bariyere geldiğinde onu açıkça yazıp diğer yerel kod/test işlerine
devam et. Canlı üretim kodunu veya broker işlevlerini değiştirme.**

## 2026-10-10 continuation addendum

- Existing local Hermes executable v0.21.5+5295.g234badf at upstream
  234badf4012af380d23c91eae55d045a69c69ffb confirmed. New stable
  v0.21.6 exists, but in-place upgrade would touch the user's global
  Hermes installation and was not performed.
- Six Hermes project skills placed in `.agents/skills`; no global trust
  action was performed. Hermes supports `cron --no-agent --script` and
  persistent cron history, but no live cron was registered.
- New SQLite queue offers persistent tasks, deterministic single-item
  claims, statuses, and no automatic retry of interrupted RUNNING jobs.
  Current task execution reports SOURCE_EVIDENCE_REQUIRED/INCONCLUSIVE.
- Atomic local free LLM quota guard now blocks all outstanding in-flight
  leases even after their nominal expiry, pending manual reconciliation.
- Canonical S16 requires native trusted evidence verification; a boolean
  included in LLM / remote JSON is insufficient.
- Provider account quotas, Google Cloud total no-charge assurances, live
  chat/plugin/Telegram wiring and full historical PIT/OOS results remain
  BLOCKED pending independent evidence.

### Continuation evidence / Phase 10 read-only reality check

The A6 local persistent task now calls M10 Phase25i, which returned
`FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED` on Windows, with 9 missing
real-data acceptance conditions including PIT membership, canonical
adjusted bars, corporate actions, historical CIK/share class identity,
delisted terminal outcomes, WF5/6 and mature labels. Neither walk-forward
nor Learning V3 ran. This does not certify backtest accuracy.
Native Hermes profile bootstrap started in isolated `HERMES_HOME`;
no successful CLI role execution or paid model call is claimed.

## Local deployment progress — 2026-10-10 02:37 JST and later checks

**Do not reinterpret a research-only local execution as a successful
financial model backtest or live LLM deployment.**

1. Real installed Hermes v0.21.5 git SHA `234badf4012af380d23c91eae55d045a69c69ffb`.
   Runtime packages were staged in a separate M10 `HERMES_HOME`.
   Native `hermes skills list` confirmed all six Meridyen skills enabled.
   Hermes source launcher publication reports an intermittent upgrade
   completion error; global Hermes program was not upgraded.
2. The real Hermes `cron create --no-agent` mechanism registered a
   paused, local-only two-hour job `6e92e18ee724`. Its Python shim
   executes at most one pre-enqueued local audit and uses no LLM.
   The gateway scheduler is not running, therefore this is registered
   scheduling, **not active unattended processing**.
3. Persistent A1→A2/A3/A4/A5/A6 task transfer and crash review are
   implemented in local SQLite. The actual M10 Phase25j 6 P1 issuer
   references and remaining 127 research candidates, 167 non-P1
   source-only observations, were evaluated. **Zero candidates received
   a certified canonical adjusted-price/CIK evidence chain.**
4. Actual Phase25i was run and blocked the full 21-month PIT,
   true WF9 and Learning V3 by nine missing source-evidence gates.
   This is a verified blocker report, not a completed training cycle.
5. `core/hermes_team/mcp_local.py` serves an authenticated, loopback
   MCP JSON-RPC API (status, submit, tick, job and scenario-only paper).
   Local HTTP protocol tests pass. The connected Meridyen demo tunnel
   may be unavailable; never claim a real Private Plugin remote binding
   until actual `tools/list` and end-to-end remote checks pass.
6. `core/hermes_team/telegram_control.py` handles allowlisted local
   commands, and opt-in outbound Telegram messages are disabled by
   default; mocked outbound transport alone is not live delivery.
7. `core/hermes_team/paper.py` models bounded maximum share
   quantity and spread/slippage/fees for test assumptions only. Its
   output explicitly says SYNTHETIC_SCENARIO_ONLY and does not
   connect to a broker or prove a strategy.
8. Cloud cost and credential guards remain strictly disabled
   without independent billing-account and quota proof. Official
   Google Cloud Always Free does NOT constitute a hard USD 0
   infrastructure cap.

**Full acceptance matrix:** `docs/HERMES_V2_PHASE_2_12_ACCEPTANCE.md`.
**Current command guidance:** `docs/HERMES_V2_RUNBOOK.md`.
Continue source-only evidence triage and independent test work where
possible. Do not fabricate resolved corporate actions, historical
membership, delisting proceeds, trained challenger performance, live
price, S16-C or alerts.

### 2026-10-10 latest verified continuation

Apply Phase25k and Phase25Q **source-only** additions from `origin/main`
without touching production data. Phase25k creates the 133-row fail-closed
candidate ledger; Phase25Q's existing private 21-month research stage was
read-only validated: **128,088 monthly research membership rows and
2,110,622 vendor source price rows**, **133 candidate gate rows**, and
**zero** canonical accepted identities/prices. Historical snapshot files
were acquired retrospectively (in 2026), so all original Phase25i
canonical PIT/WF9/Learning V3 blockers remain.

The Windows MCP 10054 TCP reset was traced through server-side
instrumentation to unauthorized HTTP 401 responses closing without
draining an already-transmitted POST body. Drain bounded body bytes
(16 KiB maximum), never parse or log untrusted unauthorized content,
and retain 401 responses and loopback-only binding. Real HTTP stress and
authenticated JSON-RPC integration must be repeatable without SEC archives.

The actual native Hermes gateway was launched in the isolated profile,
cron ticker heartbeat observed, its `--no-agent` local job run
successfully once, **then paused** and gateway stopped. This is real
deterministic scheduling, not genuine LLM-driven specialist messaging.
Do not auto-enable model API fallback or user-profile gateway service
while model and billing verification remain missing.

Add a fail-closed **score provenance** rule: neither the external
`s16_e` nor `s16_c` JSON field is itself a formula computation.
Both must be authorized by a trusted Python M10 formula-caller path;
otherwise return a null score and its `INCONCLUSIVE` status.
Never turn synthetic test fixture prices into "current prices".
For the OpenRouter Free plan, local caps must not exceed 50 requests/day
and 20/minute without independent nonbillable tier proof; do not infer
that public pricing is enough to enable a connected user account.


## 2026-10-10 addendum — official Hermes native execution only

**Architecture priority:** use official NousResearch Hermes Agent; do
NOT build or deploy another autonomous agent/orchestrator. Six experts
are project skills and sequential `delegate_task` leaf sessions
controlled by native Hermes (not six 24/7 LLM servers). Native
`cronjob` is preferred over an external scheduler.

New inactive native-profile candidate:
`config/hermes_native_profile.safe.example.yaml`.
Native execution prerequisites before any live model call:
(1) `HERMES_HOME` points to isolated M10 data path;
(2) `terminal.cwd` is the M10 Git checkout;
(3) default native model/provider, delegation model/provider, and
all alternative LLM routes are audited and routed to a verified
single-call nonbillable gateway;
(4) `delegation.max_concurrent_children=1`,
`max_spawn_depth=1` and `orchestrator_enabled=false`;
(5) `skills.write_approval=true` and
`memory.write_approval=true`;
(6) active provider key, per-project model access, RPM/TPM/RPD,
billing and hard charge protections are verified with the user's
actual account. Otherwise NO `delegate_task` calls.

The existing Python evidence source readers and MCP adapters remain
tools only. No S16-E/S16-C score may originate from LLM JSON;
without trusted formula and PIT evidence both are INCONCLUSIVE.
The real Phase25Q staging is retrospective research data rather
than canonical contemporaneous PIT. No backtest success can be
claimed without independent valid evidence.

This GitHub-only continuation could not inspect or alter the user's
Windows installation because Chat On Steroids tunnel was offline.
No actual six-model delegation, bot send, remote Plugin binding, free
inference, training, or Google Cloud provisioning occurred in this
turn. See `docs/HERMES_NATIVE_EXECUTION_CHECKLIST.md` and
`docs/HERMES_V2_PHASE_2_12_ACCEPTANCE.md` for verified criteria.


## Phase25M/R/S evidence follow-through — 2026-10-10

The GitHub Hermes feature branch now includes the upstream
Phase25M/25R/25S original Python tools and docs. Do not reinstall
Hermes or rewrite its native orchestration to consume them.
Native A2/A3/A5/A6 skills are instructed to use read-only M10
research evidence where available. Existing Phase25M has six
official issuer distribution reference events over CRCT/IEP/EC,
without proof of ex-date, USD/ADS conversion or adjusted-price
factors. Existing Phase25R found 464 conflicting monthly issuer
records across 30 tickers and 7 strong-cohort symbols; never
accept these ticker-only historical identities. Existing
Phase25S documents the SITC 1-for-4 2024 reverse split and
the CURB spinoff; never reduce this to an assumed simple
cash dividend or a certified vendor-adjusted closing price.

Use `core/hermes_team/phase25_source_evidence.py` to inspect
previously produced local reports **without** rescanning
millions of source bars or changing private archives.
The adapter verifies reports' structure, quarantine flags,
denied canonical approval and SHA256 of the read report.
It cannot independently verify SEC provenance, publication
`available_at`, corporate-action vendor price factors,
historical SimFinId↔CIK mapping, WF9 or Learning V3 outcomes.
If the private report is missing or no longer matches its
schema, say `INCONCLUSIVE`; do not infer the report ran.
The Chat On Steroids Windows tunnel remains unavailable in
this turn, so real local report reads and Hermes native
LLM delegation remain unverified. Historical canonical
acceptances remain zero, cloud cost guards absent, and no
billable resources were created.
