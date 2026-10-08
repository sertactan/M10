# Phase 14 — Tek şirket SEC kaynak indir + kanıt eşleştir + inceleme

**Sorun:** `SEC_EVIDENCE_STAGE_BLOCKED: REQUIRES_ORIGINAL_SEC_SOURCE_FOLDER` hatası, önceki SEC indirme komutunun yalnızca `DRY_RUN_ONLY` olması ve orijinal SEC JSON dosyalarının bulunmaması nedeniyle oluşur. İndirme yapılmadıkça bu hata normaldir.

**Güvenlik:** Yeni `scripts.phase14_sec_pilot_pipeline`, hiçbir zaman canlı Windows `operational.db` dosyasını yazma amacıyla açmaz. Ayrıca yedek okunur, `--stage` yalnızca özel kanıt günlüğüne yazar. S15/S16 kanonik formüller ve WF9 değişmez. Dış veri indirmesi / kod testleri M10 kullanıcısının bilgisayarında henüz yürütülmedi.

## Hazırlık

- Windows'taki diğer SEC Companyfacts indirmeleri durmuş/bitmiş olmalı. Aynı IP'den eş zamanlı SEC trafiği SEC hız sınırını aştırabilir.
- Yerel SQLite veritabanının **canlı M10 içindeki dosya değil ayrı ve bütünlüğü kontrol edilmiş yedeği** bulunmalı. Örnek: `E:\Meridyen_Backups\operational_SEC_20261008_203207.db`. Dosya adını kendi gerçek yedek adına uyarlayın.
- SEC veri dosyaları `E:\Meridyen_SEC\submissions` içinde tutulabilir. İlk pilotta bu klasör yalnızca **tek CIK** içermeli.
- `SEC_USER_AGENT` içine kendi iletişim e-postanızı yalnızca bilgisayarınızdaki ortam değişkeni olarak girin. ChatGPT veya GitHub'a yazmayın. Bu bir API anahtarı değildir.

## Windows — güvenli adımlar

Yeni PowerShell penceresi açın. M10/PIT/SEC import işlemi çalışırken eski süreçlerin kodunu `git pull` ile değiştirmeyin.

### 1. Gerçek indirme yapmayan ön kontrol

```powershell
cd E:\M10
git pull --ff-only

.\.venv\Scripts\python.exe -m scripts.phase14_sec_pilot_pipeline --cik 1408075 --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" --submissions-dir "E:\Meridyen_SEC\submissions" --journal "E:\Meridyen_Backups\sec_acceptance_review.sqlite3"
```

İlk kullanımda kaynak klasörü yoksa `WAITING_FOR_ORIGINAL_SEC_SOURCE_FOLDER` görünebilir; bu **kaynakların henüz indirilmediğini** gösterir. Ön kontrol hiçbir dosya oluşturmaz ve SEC'e ağ isteği göndermez.

### 2. Tek CIK için sınırlı gerçek indirme

```powershell
$env:SEC_USER_AGENT = 'Meridyen Research REAL_EMAIL_HERE'
# REAL_EMAIL_HERE yerine kendi gerçek iletişim adresinizi yazın.
.\.venv\Scripts\python.exe -m scripts.phase14_sec_pilot_pipeline --cik 1408075 --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" --submissions-dir "E:\Meridyen_SEC\submissions" --journal "E:\Meridyen_Backups\sec_acceptance_review.sqlite3" --download --max-requests 10 --daily-budget 60 --min-interval 1
```

Program gerçek SEC JSON kök belgesini ve `filings.files` arşivlerini yalnızca `--download` verilince edinir; günlük bütçe ve istek limiti sonunda **otomatik durur**. `DOWNLOAD_STOPPED_RESUME_OR_REVIEW` halinde `download_result.error_code` alanına bakın. `SEC_RUN_REQUEST_BUDGET_EXHAUSTED` varsa daha sonra aynı komutu tekrar vererek eksik arşivlerden devam edebilirsiniz. `SEC_ACCESS_POLICY_OR_LIMIT_403/429/503` görürseniz **tekrar tekrar denemeyin**; hizmet sağlayıcı limiti, kullanıcı kimliği ve ağ politikasını kontrol edin.

Bu adımda özel journal oluşturulmaz. SEC dosyaları ve manifest/hash kontrolleri başarılıysa `EVIDENCE_PREVIEW_READY_NO_WRITES` raporu çıkar. Büyük SEC belgeleri için `REVIEW_PAGINATION_REQUIRED_NO_AUTO_STAGE` görülebilir; bu durumda parçalı inceleme gerekir.

### 3. Kanıtı ayrı özel journal'a aktarmak (isteğe bağlı)

Kaynak doğrulaması ve `EVIDENCE_PREVIEW_READY_NO_WRITES` sonrasında:

```powershell
.\.venv\Scripts\python.exe -m scripts.phase14_sec_pilot_pipeline --cik 1408075 --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" --submissions-dir "E:\Meridyen_SEC\submissions" --journal "E:\Meridyen_Backups\sec_acceptance_review.sqlite3" --stage
```

Bu işlem yalnızca **ayrı** `sec_acceptance_review.sqlite3` günlüğüne kanıt adayı ekler. Canlı `accepted_at` ve `available_at` alanlarını değiştirmez. Tek komutta indirme ve inceleme de mümkündür: `--download --stage`, ancak öncelikle iki adımı ayrı çalıştırmak daha güvenlidir.

## Durumlar

| Durum | Anlamı |
|---|---|
| `WAITING_FOR_ORIGINAL_SEC_SOURCE_FOLDER` | Henüz gerçek indirme yapılmamış |
| `DOWNLOAD_STOPPED_RESUME_OR_REVIEW` | API erişimi, hız sınırı, günlük kota veya istek bütçesinde durdu; nedenini incele |
| `WAITING_FOR_HISTORICAL_SEC_ARCHIVES` | SEC kökü var, arşiv dosyalarının tamamı yok |
| `EVIDENCE_PREVIEW_READY_NO_WRITES` | Resmi URL/hash koşulları ve mevcut DB eşleşme önizlemesi tamam, yazma yok |
| `REVIEW_PAGINATION_REQUIRED_NO_AUTO_STAGE` | Çok sayıda accession var; parçalı manuel review gerekli |
| `PRIVATE_EVIDENCE_REVIEW_STAGED_NOT_CANONICAL` | Adaylar ayrı inceleme günlüğünde; **kanonik doğrulama değildir** |

**Önemli:** `SHA-256` kaynak dosyasının manifestle aynı olduğunu doğrular, SEC'in belgeyi bağımsız biçimde imzaladığını **kanıtlamaz**. Arşiv belgeleri tam olsa bile tarihsel ticker/CIK yeniden adlandırmaları ve delisting kontrolleri gerekir. Gerçek 2013–2024 PIT kaynakları, düzeltilmiş fiyatlar, şirket işlemleri, tarihsel S15 özellikleri ve WF9 backtest henüz tamamlanmış sayılmaz.

**Gizlilik:** Ham SEC kaynaklarını, offline veritabanını, manifesti, journal'ı ve kendi e-posta adresinizi PUBLIC GitHub deposuna commit etmeyin.
