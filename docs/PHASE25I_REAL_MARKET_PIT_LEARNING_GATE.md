# Faz25i — gerçek 2024-01-01–2025-09-30 kanonik veri / walk-forward / Learning V3 kapı matrisi

## Neden gerekli?

Yerel M10 \`operational.db\` (Windows, yaklaşık 8.58 GiB) içinde **SEC finansal fact verileri** ve ayrı SimFin 21 aylık arşivleri mevcut olabilir. Ancak veri dosyalarının varlığı, *kanıtlanmış* 21 aylık \`universe_snapshot_membership\` veya \`canonical_price_selection(purpose='BACKTEST_ADJUSTED')\` kayıtlarının bulunduğu anlamına gelmez. Mevcut faz25h uzlaştırması (6 hisse/15 fiyat uyarısı/13 resmî nakit dağıtım referansı) **araştırma düzeyidir**, kanonik veri kabulü değildir.

Bu komut kaynakları **salt okunur** denetler ve sonraki görevlerin hangi gerçek şartta açılacağını görünür kılar:

- 21 aylık \`universe_snapshot_membership\` kapsamı + source türleri;
- \`BACKTEST_ADJUSTED\` seçim sayısı ve benzersiz security_id;
- Dönemsel resmî işlem kayıtlarının mevcut \`corporate_actions\` tablosuna alınıp alınmadığı;
- \`security_master.delisted_date\` alanının dönemsel doluluğu; sıfır delisted sayısı **gerçekte delist yok** anlamına GELMEZ;
- Ayrı tarihsel issuer-CIK-share class zaman aralığı eşleme ve explicit delisting/terminal return tablosu var mı;
- WF5 ve WF6 COMPLETE kayıtları ve olgun etiket tablosu var mı;
- Faz24/25b/25h önceki özel araştırma raporlarının sertifikasız bayrakları korunuyor mu.

**ÖNEMLİ:** Tablonun şemada bulunmaması başka tablo/Parquet'te işlevsel veri olmadığı anlamına gelmeyebilir; bu audit *kendi sertifikasyon yolu* için fail-closed kalır. Hiçbir tablo otomatik oluşturulmaz, silinmez veya başlatılmaz.

## Kullanım

Güncel M10 kodunda, kullanıcının mevcut ayrı kod dalı korunarak ayrı worktree'ye alınmış güncel \`main\` üzerinden:

\`\`\`powershell
cd E:\M10
git fetch origin main
$code = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25i\code_checkout"
if (-not (Test-Path $code)) { git worktree add --detach $code origin/main }
Set-Location $code
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25i_real_market_gate_matrix
\`\`\`

Çıktı:
\`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25i\real_market_gate_matrix_2024_2025.json\`

Eğer \`PIT_BACKTEST/LEARNING\` kapıları bloklanırsa, rapor tam blocker ve gerçek sayıları verir; çıkış kodu 2 **istenen fail-closed** davranışıdır. Önceki \`phase25h\` raporu gerekli ve doğru olmalıdır.

## Hangi işleri durdurur?

Kanonik tarihsel kimlik ve fiyat kanıtı yokken:
- WF9 live production / gerçek OOS metrikleri **asla sentetik veriyle üretilmez**.
- \`Phase17 Learning V3\` için doğrulanmamış \`hit_10x\`, 252-session matured labels, gün bazlı PIT feature, risk-free returns veya fark/precision metrikleri uydurulmaz.
- S15.3/S16/S16-EA formülleri değiştirilmez, score \`COMPLETE\` yazılmaz.
- Özel yerel SimFin CSV, Alpha Vantage aylık listeler, 8.58 GiB SEC/operational SQLite ve Parquet dosyaları GitHub'a yüklenmez.
- Önce gerçek **kaynak ve telif/lisans**, tarihsel CIK/share class, split/temettü/ADR, delisting/terminal return ve SEC kamuya-yayım zamanları doğrulanmalıdır.

Bu script yalnızca yeni özel JSON raporu oluşturur; gerçek veri aktarımı, 2025 walk-forward veya Learning V3 çalıştırması **DEĞİLDİR**.
