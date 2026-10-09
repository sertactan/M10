# Faz 25a — SimFin 21 aylık fiyat derinliği ve tarihsel kimlik araştırma kapısı

## Mevcut Windows sonuçları (2026-10-09)

Kullanıcının **gerçek** Faz24 yerel raporundan yapılan PowerShell sayımı:

- **5.307** tarihsel pencerede SimFinId.
- **4.236** SimFinId için tarihsel liste ayı ↔ en az 1 geçerli ve pozitif `Adj. Close` fiyat satırı örtüşmesi.
- **4.119** SimFinId için bu şartta **100+ satır**.
- **3.736** SimFinId: **100+ satır**, **1 mevcut SEC CIK adayı**, **1 ticker dizgesi**, **o ayda çoklu borsa uyarısı yok**.
- **0** kanonik tarihsel SimFinId–CIK kimlik sertifikası.

**Önemli:** 3.736, tarihsel olarak kanıtlanmış 3.736 ayrı ABD hissesi değildir. Aynı ticker geçmişte başka şirkete ait olabilir, bir CIK birçok pay sınıfını kapsayabilir. 100 günlük fiyat satırı 21 aylık tam seri demek değildir; satırların bağımsız işlem günleri de ayrıca denetlenmelidir.

## Yeni Faz 25a çevrimdışı ölçümü

`scripts/phase25a_simfin_universe_price_depth_audit.py` yalnızca:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24\simfin_sec_cik_candidates.json`

dosyasını açar ve kaynak raporun `schema/status`, dönem, eski kanonik onay bayrakları ve kayıt sayıları tutarlılığını doğrular. **415 MB SimFin fiyat CSV'si tekrar taranmaz.** Hiçbir SEC veritabanı, API veya ek yedek gerekmez.

Şunları raporlar:

1. Tarihsel fiyatla aynı liste ayında örtüşen `SimFinId` dağılımı: **0**, **1–5**, **6–11**, **12–17**, **18–20**, **21/21** ay.
2. **100 / 200 / 300 / 400+** geçerli OHLC ve pozitif adjusted-close kaynak satırı sayısına ulaşan adaylar.
3. Daha önce ölçülen **3.736 ilk filtre havuzu**, bu havuzun **6/12/18/21 ay** kapsam kırılımı.
4. Bilinen ticker reuse, bir SimFinId'de çok ticker ve çoklu CIK/borsa uyarısı içeren kayıtları ayrı araştırma sınıfına alır: `preliminary_excluding_known_identity_risk_not_pit`. Bu sayı, 3.736'dan küçük olabilir.
5. Mevcut CIK adayı tek olsa bile **tarihsel kimlik kanıtı**, true `BACKTEST_ADJUSTED`, delisted return ve kanonik backtest izni **0** tutulur.

### Windows PowerShell

```powershell
cd E:\M10
git pull --ff-only

.\.venv\Scripts\python.exe -m scripts.phase25a_simfin_universe_price_depth_audit
```

Özel rapor:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25a\simfin_price_depth_research_audit.json`.

Beklenen kısa çıktıda `SimFinIds_reviewed: 5307`, `preliminary_single_CIK_100row_not_pit: 3736`, `excluding_known_identity_risk`, `research_18months_single_CIK` ve `research_21months_single_CIK` görünür. 5307/3736 beklenenler yalnızca **aynı kaynak rapor değişmediyse** doğrulanır; yeni sonuçları önceden uydurmayız.

### Güvenlik ve sonraki işler

Bu, gerçek bir **veri uygunluk ön raporudur**; fiyat/split/temettü metodunu onaylamaz, kapanış getirisi veya 10X sonucu üretmez. `0 kanonik` beklenen fail-closed işaretidir.

Devamda 21 aylık kapsama sahip adaylar için:
- Farklı gün/tarih tekrarları ve seans günleri,
- Split ve temettü düzeltmesi ile kapanış metodunun kaynağı,
- Halihazırda borsadan çıkarılmış hisseler, son satış/tasfiye kazanç-kayıpları,
- Aynı SimFinId'nin dönem içi şirket kimliği/CIK/FIGI değişimleri ve ticker reuse,
- SEC fact'in gerçek kamuya erişilebilirlik zamanı,
- Veri kullanım lisansı ve ardından independent walk-forward/OOS değerlendirmesi

gerekir. Ücretsiz API limitleri atlanmaz; ağ/ücretli API/SimFin tekrar indirme/SEC yeniden indirme/yedek kopyalama/üretim veritabanı veya S15.3/S16 modeli yazımı/öğrenme **yok**.
