# Faz 24 — SimFinId ↔ SEC CIK aday eşleştirme (araştırma; kanonik DEĞİL)

**Kod ve çevrimdışı testler hazır. Gerçek Windows veri setinde Faz 24 henüz çalıştırılmadı.**

## Faz 19–23'ten gerçek bulgular (2026-10-09)

- 21/21 Alpha Vantage tarihsel liste arşivi SHA doğrulandı.
- 6.839 benzersiz ticker+borsa **anahtarı**, 6.831 ticker dizgesi.
- Faz 20: 4.917 CIK bilgili mevcut veritabanı adayı; 231 CIK'siz mevcut eşleşme; 1.691 doğrudan eşleşmeyen liste anahtarı. Bunlar tarihsel kimlik sertifikasyonu **değildir**.
- SimFin ücretsiz günlük CSV: 6.216.939 tüm kaynak satırı; 2024-01-01–2025-09-30 arası 2.139.602 satır; 2.110.654 sıkı OHLC geçerli; 4.242 ticker dizgesi PIT arşiviyle herhangi bir ayda örtüşüyor.
- Faz 23: 28.948 geçersiz OHLC satırından 27.610'unda tüm OHLC sıfır. **0 kayıt değiştirildi veya silindi.**

## Faz 24'ün görevi

`scripts/phase24_simfinid_cik_candidate_audit.py` şunları yapar:

1. Var olan Faz 20, 21, 23 raporlarını, SEC veritabanının **salt-okunur** halini ve Phase19 CSV/manifest SHA bütünlüğünü doğrular.
2. SimFin fiyat CSV'sini belleğe bütünüyle almadan tarar; SimFinId ↔ ticker dizgesi ilişkileri, olası symbol reuse, SimFinId'nin birden fazla ticker'da görünmesi, ay-sonu listesiyle **aynı takvim ayında** örtüşme, geçerli OHLC/Adj.Close adedini raporlar.
3. Faz 20 yerel `security_id` eşleşme adaylarını **şimdiki** SEC CIK alanlarıyla karşılaştırır. Aday CIK'ler listelenir, ancak **tarihsel CIK / FIGI kimliği onaylanmaz**.
4. CIK çakışması, ticker tekrar kullanımı, farklı borsalar ve eksik kanıtları inceleme sınıflarına ayırır. **Kanonik eşleşme sayısı daima sıfır**.
5. Tek özel rapor üretir; **yeni indirme/API, ücretli kaynak, SQLite veya Parquet veri değişimi, SEC yeniden indirme, kanonik fiyat seçimi, S15.3/S16 formül değişikliği ve model eğitimi yok**.

## Windows'ta çalıştır

```powershell
cd E:\M10
git pull --ff-only

$file = "$env:USERPROFILE\Downloads\us-shareprices-daily\us-shareprices-daily.csv"
.\.venv\Scripts\python.exe -m scripts.phase24_simfinid_cik_candidate_audit --input "$file"
```

Mevcut yerel dosyalar varsayılan yollarda aranır:

- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase19\pit_staging` (21 liste)
- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase19\pit_identity_candidates.json` (Faz 20)
- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase21\simfin_free_price_source_audit.json`
- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase23\simfin_nonpositive_ohlc_diagnostics.json`
- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\data\runtime\operational.db` (salt-okunur)

Rapor: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24\simfin_sec_cik_candidates.json`

Büyük özel raporu veya lisanslı SimFin fiyat CSV'sini **herkese açık GitHub deposuna yükleme**. Yalnızca kısa komut çıktısını paylaş.

## Gelecek aşamalar

**Faz 24b — bağımsız tarihsel kimlik kanıtı:** Şirketin tarihsel ticker/CIK/FIGI sınıfı ve etkinlik tarihleri, yeniden isimlendirme, borsa değişimi, relisting, ticker reuse, SEC kabul zamanı. SimFinId tek başına SEC CIK kanıtı değildir.

**Faz 25 — fiyat kanoniklik kapısı:** Split, temettü, adjusted yöntemleri, ticarete açık olmayan günler, delisted returns, veri gecikmesi ve lisans haklarının doğrulanması.

**Faz 26 — geçmiş test:** Eğitim, doğrulama, ileriye dönük test kesitleri ayrılarak mevcut S15.3/S16 algoritmaları değiştirilmeden gerçek sonuç ölçümü.

**Faz 27 — Learning V3:** Yalnızca olgunlaşmış, yeniden üretilebilir, out-of-sample ve PIT kanıtlı geçmiş çıktılar üzerinde challenger öğrenme. Öğrenme canlı olarak veya daha erken tamamlanmış gibi raporlanmaz.
