# Faz 25b — 21/21 ay örtüşen SimFin hisselerinin gerçek günlük fiyat derinliği

## Gerçek Windows Faz 25a gözlemi

10 Ekim 2026 ekranında kullanıcının **gerçek** `phase25a` çıktı değerleri:
- 5.307 araştırma kapsamındaki SimFinId;
- 3.736 ilk araştırma adayı (100+ geçerli kaynak fiyat satırı, 1 mevcut CIK adayı, 1 ticker);
- Aynı 3.736, mevcut açık kimlik çakışması sınıfları çıkarıldıktan sonraki araştırma havuzu;
- En az 18/21 aylık fiyat örtüşmesi: **3.598** SimFinId;
- 21/21 ay kaynak `Adj. Close` pozitif ve geçerli OHLC örtüşmesi: **3.557** SimFinId;
- **0** kanonik backtest onayı ve **0** tarihsel SimFinId ↔ CIK sertifikası.

Bu **3.557 ayrı tarihsel şirket** veya **3.557 güvenli backtest hissesi** demek değildir. Aylık pozitif adjusted-close gözlemi ve o ayın liste üyeliği yalnızca araştırma adaylığını açıklar.

## Faz25b'nin gerçek katkısı

`scripts/phase25b_simfin_distinct_daily_depth_audit.py` orijinal **415 MB** SimFin CSV dosyasını SHA-256 ile doğrular, 21 aylık yerel Alpha Vantage liste dosyasının önceki bütünlük denetimini tekrar kullanır ve ardından fiyat CSV'sini *bir kez akış halinde* tarar. Orijinal 6,2 milyon kaynak satırını belleğe yüklemez.

Seçilen 3.557 SimFinId için:
1. **SimFinId + işlem tarihi** özelinde benzersiz geçerli fiyat gözlem sayısı;
2. Aynı tarihin **mükerrer** pozitif `Adj. Close` ve geçerli OHLC kayıtları;
3. Hafta sonuna düşen ve ayrıca incelenecek fiyat kayıtları;
4. Her 21 takvim ayının **en az 10 ve en az 15 farklı hafta içi günü** kapsayıp kapsamadığı;
5. Toplamda 100/200/300/400+ farklı hafta içi gün; en uzun **takvim günü** aralığı ve 8/15+ günlük boşluk uyarıları;
6. Her SimFinId'nin **yalnızca o ay liste arşivinde bulunan ticker'ı** ile örtüşen gözlemleri (bu **günlük** PIT üyeliği veya tarihsel CIK onayı değildir).

CSV değişmişse kaynak SHA uyuşmazlığıyla **fail-closed**. Her adayın satır ve aylık örtüşme sayısı Faz24 toplamıyla birebir uyuşmazsa da **durur**. Kaynağı otomatik düzeltmez veya kanonik tablolara yazmaz.

### Windows PowerShell komutu

```powershell
cd E:\M10
git pull --ff-only

$file = "$env:USERPROFILE\Downloads\us-shareprices-daily\us-shareprices-daily.csv"

.\.venv\Scripts\python.exe -m scripts.phase25b_simfin_distinct_daily_depth_audit --input "$file"
```

Özel yerel JSON:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25b\simfin_distinct_daily_depth_research.json`.

**Beklenen ilk sayı** `SimFinIds_21_month_cohort=3557` (kaynak aynıysa). Şunları gerçek çıktından öğreneceğiz:
- `at_least_400_distinct_weekdays`
- `15_plus_days_each_of_21_months`
- `10_plus_days_each_of_21_months`
- `duplicates_id_date`
- `ids_with_8_plus_day_calendar_gaps`

Bu işlem büyük CSV'yi yeniden okuyacağı için saniyeler değil, disk/CPU hızına bağlı olarak **birkaç dakika veya daha fazla** sürebilir. Dosya GitHub'a **yüklenmeyecek**, ücretli API yok. Eksik fiyatları burada otomatik tamamlama yok.

## Kısıtlar ve Faz 25c'ye geçiş

Faz25b **NYSE/NASDAQ tatil takvimini** veya kapanış fiyatlarına split, temettü ve delist sonrası getiriyi doğrulamaz. **Hafta içi günü**, resmi borsa **işlem seansı** değildir. `Adj.Close` pozitifliği, düzeltilmiş fiyatların matematiksel/kurumsal işlem doğruluğunu kanıtlamaz.

S15.3/S16/S16-EA modelleri ve üretim 9,21 GB SQLite finansalları değiştirilmez. Kanonik fiyat, şirket kimliği, PIT backtest ve Learning V3 kapalı kalır. Faz25c'de gerçek piyasa günleri ve fiyat düzeltme kanıtı ayrıca ele alınır.
