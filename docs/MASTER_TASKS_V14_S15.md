# V14 — S15.3 V1.2/V1.4/V1.4.1 gerçek kaynak kapısı

12 Ekim 2026 (JST). V13'ün mühürlü beş-hisse raporu ve canlı M10 SQLite veritabanı **salt okunur** olarak yeniden incelendi. Özgün `S153V12Model` S15.2, M10 için en az 5/7, T10 için en az 5/7 ve seçilen rotada en az %70 zorunlu bacak kapsamını ister. Bu envanter ayrıca rota geçişi, confidence ve nihai puanı tam kabul koşulu olarak ayrı doğrular; yalnız hesaplanmış bir ara değer READY değildir.

Özel [kaynak envanteri](E:/M10/.master_tasks_v14_private/s15/source_inventory_v1.json) SHA-256 `aef56cbcc0391b21c710b6ee4edb016207338af3c9d140298eb32631aae894f4` ile mühürlendi ve çevrimdışı tekrar geçti. V13 raporunun özgün SHA-256 değeri `1ff05025cf0ce7e7a76b397a5b3782203a8a21b1b7aa6c010291c7de744e2fc9`; DB 9.208.872.960 bayt olarak okundu. SQLite bağlantısı `mode=ro` ve `query_only=ON` ile açıldı; hiçbir özellik eklenmedi.

| Hisse | Rapor zamanında DB'de mevcut as-of özellik anahtarı | V1.2 asıl eksik |
|---|---:|---|
| INOD | 0 | S15.2, M10, T10, ≥%70 rota, route gate, confidence, final |
| TMDX | 0 | Aynı |
| CRMD | 9 | Aynı; 9 anahtar arasında rota hedefi veya tarihsel H yok |
| PENG | 0 | Aynı |
| ETON | 0 | Aynı |

Canlı `canonical_model_features` tablosunun **tümünde** `SUPPORTED_MC_12_R/FI/D/B`, `PLAUSIBLE_CEILING_MC`, `H10`, `HMG10`, `XR`, `CT` ve `MODEL_FIT` için kayıt sayısı **0**. CRMD'nin daha yeni bazı kanonik türetilmiş satırları raporun as-of zamanından sonradır; geçmiş puana taşınmadı. V13'ün tarihli piyasa değeri adayları, kaynaklı `SUPPORTED_MC` destinasyonları değildir. Özgün M10/T10 fonksiyonları mevcut ve incelendi; zorunlu kaynak girdileri yokken fonksiyon çağrılarıyla eksik bacaklar doldurulamaz.

**12.v12, 12.v14 ve 12.v141 OPEN; Görev 12 PARTIAL; yeni tam puan 0.** V1.4 için ayrıca 13 senaryo girdisi, dual magnitude ve model fit gerekir. V1.4.1, V1.2 READY olmadan ilerlemez. Tam sürüm kabulü için gerçek tarihli SupportedMC/timing/H ve kaynak/uyum girdileri yaratılıp ayrı referans hesabıyla doğrulanmalıdır. Çalıştırma: `python scripts/scoring_v14_s15_readiness.py --report <mühürlü V13 raporu> --db <operational.db> --out <özel JSON> --verify`. İki kapsama testi geçti.
