# Faz 25d — 3.557 SimFin fiyat kaydında uyarı kesişimi ve bağımsız kanıt iş listesi

## 10 Ekim 2026 — kullanıcının gerçek Windows faz25c sonucu

- **3.557** SimFinId gözlemlendi.
- Ay içinde **%5+ `Close/Adj. Close` faktör değişimi olan 92 SimFinId**.
- Ay sınırında **%5+ kaynak düzeltme faktörü değişimi olan 8 SimFinId**.
- Ay sınırında **%50+ `Adj. Close` fiyat hareketi olan 39 SimFinId**.
- SEC/şirket/borsa kaynaklarıyla bağımsız doğrulanmış **split 0, temettü 0, kanonik backtest 0**.
- Orijinal SQLite veritabanı, eski fiyat dosyası ve modeller değişmedi.

**92 + 8 + 39 = 139 benzersiz hisse değildir**: aynı SimFinId iki veya üç alarm kategorisine girebilir. Borsa/şirket fiyat düzeltmesi için asıl araştırma önceliği benzersiz ve çakışan uyarıları ölçmektir.

## Faz25d ne yapar?

`scripts/phase25d_simfin_adjustment_review_queue.py` yalnızca yereldeki Faz25b ve Faz25c özel JSON raporlarını okur; **415 MB fiyat dosyasını tekrar taramaz**, SEC'den veya ücretli API'dan veri çekmez.

- `SimFinId` bazında gerçek **alarm birleşimini (union)** ve 2+/3 kategori kesişimini belirler.
- Özellikle **`P1_MULTI_ALERT`** (2+ kategori), **`P2_FACTOR_CHANGE`** (bir kaynak oran uyarısı), **`P3_EXTREME_ADJ_RETURN_ONLY`** (yalnız aşırı piyasa/düzeltilmiş fiyat hareketi) olarak **araştırma iş sırası** oluşturur.
- 21 aylık aday listesi, özel raporun `SHA256` kimliği, ticker, CIK adayı, SimFinId, geçerli fiyat kayıt sayısı ve uyarı toplamlarının iki raporda uyuştuğunu doğrular. **Herhangi bir çelişkide durur**.
- Araştırma adaylarının listesi yerel özel **JSON ve Excel'de açılabilir CSV** olarak kaydedilir; CSV formül enjeksiyon riski azaltılmıştır.
- `no alert` kategorisi **kanıtlanmış doğru fiyat** demek değildir. İlk taramada uyarı bulunmaması, uzun vadeli 10X backtest için delisted, split, dividend, eski ticker ve PIT doğrulamasını ortadan kaldırmaz.

## Windows PowerShell — tek komut

```powershell
cd E:\M10
git pull --ff-only

.\.venv\Scripts\python.exe -m scripts.phase25d_simfin_adjustment_review_queue
```

**Beklenen, yalnızca kullanıcı Windows'taki eski raporları değiştirmediyse:** `SimFinIds_reviewed=3557`, `unique_candidate_ids_requiring_research` rakamı ise **henüz bilinmiyor** ve sadece gerçek dosyalardan hesaplanacak.

Yerel raporlar:
- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25d\simfin_adjustment_review_worklist.json`
- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25d\simfin_adjustment_review_worklist.csv`

## Bu fazda hâlâ kapalı kalan kapılar

`P1` etiketi gerçek bir split gerçekleştiği, veri hatası olduğu veya tahmin gücü yüksek hisse bulunduğu anlamına gelmez. Sadece **bağımsız kanıtı daha önce toplanacak fiyat düzeltme araştırması** sırasıdır.

Faz25e ve sonrasında gerekenler:
1. Şirket/borsa kaynaklarında tam etkin tarih, split oranı veya temettü ex-date/miktarı ve geçmiş fiyatların nasıl adjust edildiğinin belgesi;
2. Günlük resmî işlem/tatil seansı doğrulaması ve delisting/merger son işlem fiyatları/getirileri;
3. Gerçek zamana duyarlı, **tarihsel** SimFinId–CIK–ticker–borsa ve SEC kamuya erişim zamanı kanıtı;
4. Ancak bunlardan sonra ayrı kanonik fiyat kabul, OOS geçmiş testleri ve Learning V3.

M10 üretim DB'si, yerel SEC 12,3M kayıtları, modeller, fiyat dosyası ve önceki özel raporlar **değiştirilmez**. Hiçbir hisse kanonik olarak otomatik onaylanmaz.
