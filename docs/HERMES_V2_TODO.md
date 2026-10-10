# MERİDYEN AUTONOMOUS HERMES V2.0 — Kalan İşler / TO-DO

**Durum tarihi:** 2026-10-10 (JST)  
**Kaynak:** [PR #150](https://github.com/sertactan/M10/pull/150), `feat/hermes-autonomous-v2-strict-free`, başlangıç HEAD `8742862606b422401899b91217b17e4cd9d7cd5c`.  
**Doğrulanmış:** Son HEAD için GitHub Actions `38019049346` başarılı; GitHub dalı main ile birleştirilmiş durumda; PR taslak ve birleştirilmemiş. Windows tüneli son kontrolde çevrimdışı.  
**Kesin yasaklar:** S15.3/S16/S16-EA kanonik formül değiştirme; `main` ve kişisel Hermes kurulumunu değiştirme; takip edilmeyen dosyalar ile SEC/SimFin arşivlerini silme/yeniden yazma; ücretli model/fallback/VM açma; gerçek broker işlemi; sahte skor/backtest/öğrenme sonucu üretme.

## P0 — Resmî Hermes'i gerçekten çalıştırma (Windows gerekiyor)

- [ ] **01 — Windows tünelini bağla.** Chat On Steroids Core/Windows bağlantısını doğrula; yanıt yoksa Windows işlerini bloke işaretleyip GitHub işlerine devam et. *Kabul:* gerçek terminal komutu ve sonuç zaman damgası.
- [ ] **02 — Çalışma ağacını güvenle uzlaştır.** `git status`, yerel branch/commit/untracked ve PR #150 karşılaştırması; `main`, gizli ayarlar ve özel arşivler korunmalı. *Kabul:* kayıpsız Git raporu.
- [ ] **03 — Resmî Hermes sürümünü ve launcher'ı doğrula.** Kurulu NousResearch sürüm/commit, `hermes doctor`, launcher uyarısının gerçek nedeni; global kişisel kurulumu yükseltme. *Kabul:* izole profilde doğrulanmış CLI.
- [ ] **04 — Native izole profili uygula.** `config/hermes_native_profile.safe.example.yaml` ayarlarını yerel sürümle karşılaştır; kişisel `HERMES_HOME` yerine M10 izole profili, `cwd=E:\\M10`, tek çocuk, izin onayı. *Kabul:* `hermes config/tools/skills` gerçek sonuçları ve yerel prova.
- [ ] **05 — M10 depo bağlamını resmî Hermes'e okut.** `.hermes.md`, altı `.agents/skills` ve yalnız izinli feature-branch çalışma dizinini kontrol et. *Kabul:* Hermes'in kendi araçlarından güvenli okuma ve Git durum kanıtı.
- [ ] **06 — Native gateway/cron/kurtarmayı kalıcı doğrula.** Önceki tek başarılı `--no-agent` cron testini tekrarlamadan, kapat-aç sonrası görev kayıtları, duraklatma, çökme kurtarma, log/izlenebilirlik. *Kabul:* güvenli ve secretsiz kalıcı görev izi; cron inceleme sonrası tekrar **paused**.

## P0 — Gerçek ücretsiz LLM erişimi ve altı uzman

- [ ] **07 — Resmî model kataloğunu güncelle.** Gemini ve OpenRouter gerçek model ID'leri, yayınlanmış ücretsiz katman, bölge ve kullanım koşulları; eski veya belirsiz model isimlerini etkinleştirme. *Kabul:* resmî URL + doğrulanmış model kimliği.
- [ ] **08 — Kullanıcı hesabı kotası/fatura kontrolü.** İlgili AI Studio/OpenRouter projesinin ücretsiz erişimi, RPM/TPM/RPD ve faturalandırma riskini, anahtarları ifşa etmeden doğrula. *Kabul:* hesap özelinde doğrulanabilir non-billable teknik sınır; yoksa `DISABLED`.
- [ ] **09 — Native model yolunda sistem-geneli emniyet.** Hermes parent/child ve cron dahil her LLM isteği tek doğrulanmış geçitten geçmeli; en fazla 1 in-flight, kalıcı rezervasyon, sınır aşımı fail-closed, ücretli fallback yok. *Kabul:* paralellik, kota, 429, crash, tekrar deneme ve sızma negatif testleri.
- [ ] **10 — A1 → A2 gerçek `delegate_task` smoke testi.** Yalnız 08–09 onaylandıktan sonra; saf okuma/görev devri, 1 alt ajan, gerçek model yanıtı ve kanıt. *Kabul:* gerçek Hermes child session kaydı, sıfır ücret.
- [ ] **11 — A1 → A3/A4/A5/A6 ardışık native devir.** Bağımsız görev bağlamı, kanıt, veto, sonuç izi ve görev kapanışı; çocukların birbirini çoğaltması kapalı. *Kabul:* Hermes native alt-ajan oturum kayıtları.
- [ ] **12 — Kaynak/kod yetkileri ve restart güvenliği.** Native terminal/code-execution araçları yalnız gözden geçirilmiş dosyalara/sınırlandırılmış git dalına ulaşabilsin. Ücret/anahtar/trade/deploy araçları kilitli. *Kabul:* olumsuz izin ve kurtarma testleri.

## P0/P1 — M10 finans kanıt zinciri (kanıt yoksa INCONCLUSIVE)

- [ ] **13 — Resmî Hermes → gerçek M10 Python çağrısı.** Native terminal/execute_code ile mevcut SEC/Massive/fiyat/finans modüllerinden read-only gerçek sonuç; özel orkestratör geliştirme. *Kabul:* gerçek girdi/çıktı, kaynak ve zaman damgası.
- [ ] **14 — 133 aday tarihsel hisse kimliği.** Phase25Q/R karantinası: 464 çelişkili satır, 30 ticker, güçlü kohortta 7 ticker; SEC/NYSE tarihlenmiş CIK–ticker–share class–SimFinId kanıtı. *Kabul:* her aday için ayrı `PASS` veya `INCONCLUSIVE`, karantina kaldı mı?
- [ ] **15 — Phase25L `B`/`FUN` geçişlerini uzlaştır.** Barnes, Barrick, Cedar Fair/Six Flags resmi olayları ile veri sağlayıcısının ID/bölünmüş serilerini kanıtla. *Kabul:* yanlış hisse serisi birleştirmesi yok.
- [ ] **16 — Kurumsal işlemler.** Phase25M CRCT/IEP/EC altı dağıtım olayı, Phase25S SITC ters split ve CURB spinoff; ex-date, ödeme koşulu, ADS/FX, fiyat düzeltme faktörünü kaynakla kanıtla. *Kabul:* sertifikalı olaylar hariç karantina.
- [ ] **17 — Delisting ve terminal getirileri.** Barnes $47.50 şartını işlem yapılabilir kapanış fiyatı diye sunma; delist, birleşme, spin-off hak ve terminal-getiri zincirlerini uzlaştır. *Kabul:* gerçek total-return bazları.
- [ ] **18 — SEC `available_at` / Phase25P.** Üç belgede Accepted alt sınırının yanında gerçek yayımlanma ve vendor feature erişim saatlerini ayrı kanıtla. *Kabul:* `Accepted ≤ public ≤ feature ≤ decision` ve no-lookahead.
- [ ] **19 — 21 aylık PIT üyeliği.** 128.088 retrospektif üyelik, 2.110.622 kaynak fiyat satırı; tarihsel gerçekte erişilebilir üyelik ve survivorship/delisting düzeltmeleri. *Kabul:* kaynağı/tarihi kanıtlı seçim; retrospektif kayıt otomatik kabul edilmez.
- [ ] **20 — Kanonik adjusted-price ve resmi sağlayıcı doğrulaması.** SEC/Massive/ücretsiz diğer kaynaklar, OHLCV, temettü/split/spin-off, CIK ve günlük güvenilir provenance; üretim verisini yazmadan ayrı onay. *Kabul:* bağımsız PASS sayısı, başarısızlık gerekçesi, her değer için kaynak hash.
- [ ] **21 — S15.3 / S16-E / S16-C gerçek yürütüm.** Güncel fiyat `timestamp`, S16-E yalnız gerçek Python formül kanıtı, S16-C yalnız tam kanonik kanıtla. *Kabul:* ayrı skor/status, eksikte `INCONCLUSIVE`.
- [ ] **22 — S16-EA alarm, risk ve paper trading.** Güncel haber/katalizör `available_at`, alarmın zamanı, sentetik ile gerçek veri ayrımı; emir yok. *Kabul:* gerçek kaynaklı test + false alert analizi, gerçek broker talebi 0.
- [ ] **23 — WF5/WF6/WF9 ve Learning V3.** Sadece kabul edilen tarihsel altkümede gerçek OOS walk-forward, survivorship/look-ahead/komisyon/slippage ve 252 oturumluk olgun etiket; üretim modelini otomatik değiştirme. *Kabul:* yeniden üretilebilir gerçek metrikler, veri yetersizse `BLOCKED_NOT_TRAINED`.

## P1/P2 — Telegram, Plugin ve koşullu Google Cloud

- [ ] **24 — Native Hermes Telegram.** Bot izni, yalnız izinli chat, `/status`, görev sorgusu, bildirimler, zamanlanan rapor; önce kimlik/doğru sohbet testi. *Kabul:* gerçek Telegram API teslim onayı, sahte teslimat yok.
- [ ] **25 — ChatGPT Private Meridyen Plugin / MCP.** TLS, auth, araç listesi ve mevcut M10 adaptörüyle dış uçtan uca bağlantı; loopback testi tek başına yeterli değil. *Kabul:* gerçek ChatGPT remote MCP handshake.
- [ ] **26 — Google Cloud 0 maliyet denetimi.** e2-micro uygun bölgeleri, CPU/RAM, standart disk, snapshot, haricî IPv4/IPv6/NAT, egress ve veri aktarımı; ilgili hesapta gerçek sınırları doğrula. *Kabul:* 0 USD **garantisi** yoksa `CLOUD_BLOCKED`, hiçbir ücretli kaynak açma.
- [ ] **27 — Koşullu resmî Hermes bulut dağıtımı.** Yalnız 26 geçerse resmi Agent'ı sürüm sabitli, secretsiz imaj/kısıtlı erişimle kur; 6 uzman, cron, Telegram, maliyet telemetrisi smoke testi. *Kabul:* gerçek VM/servis kanıtı, restart, 0 harcama.
- [ ] **28 — Güvenlik/regresyon/CI.** Değişen native Hermes ayarı, adapter, PIT ve mesajlaşma sözleşmeleri için yerel ve GitHub birim/entegrasyon/kota/concurrency/fail-closed testleri. *Kabul:* son PR HEAD yeşil; sentetik, canlı ve bloke testler ayrılmış.
- [ ] **29 — Belgeler ve PR senkronizasyonu.** MASTER PROMPT MD/TXT, native runbook, Faz0–12 kabul matrisi, gerçek test/rapor kaynakları; güvenli geliştirme dalında commit, PR #150 güncelle. *Kabul:* eski olmayan commit, başarılı CI ve taslak PR.
- [ ] **30 — Üretim öncesi kabul.** Kullanıcıdan gereken harcama/işlem/model terfi onaylarını ayrı al; kanonik deneyler ve geri alma planı olmadan production-a geçme. *Kabul:* bütün PASS/BLOCKED durumları ve dış bağımlılıklar belgelendi.

## Önceden bitenler — tekrar yapılmayacak

- [x] Resmî NousResearch Hermes Windows kurulumuna ilişkin önceki CLI/gateway/tek `--no-agent` cron kanıtları; kişisel kurulum korunuyor.
- [x] Altı uzman skill dosyası, `.hermes.md`, izole profil şablonu ve native görev devri kuralları GitHub'da.
- [x] M10 yerel MCP HTTP `401` TCP reset düzeltmesi ve önceki gerçek 60-istek testi.
- [x] Phase25Q retrospektif araştırma verisi salt okunur bütünlük kontrolü; 21 ay, 128.088 üye satırı, 2.110.622 fiyat satırı ve 133 inceleme adayı.
- [x] Phase25M/R/S/L/P kaynak kod ve rapor kontrolleri feature dalına alındı; M10 kanonik hesaplamalar değişmedi.
- [x] Son doğrulanmış PR HEAD GitHub Actions (run `38019049346`) başarıyla tamamlandı.

**Yorum:** [x] geçmişte doğrulanan işi gösterir; canlı 6-LLM veya kanonik veri kabulü anlamına gelmez. Açık görevlerin bir bölümü gerçek Windows/harici hesap/veri olmadan tamamlanamaz.
