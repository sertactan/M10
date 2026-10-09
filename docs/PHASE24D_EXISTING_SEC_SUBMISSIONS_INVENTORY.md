# Faz 24d — Mevcut SEC submissions arşivini bul, yeniden indirme

## Son gerçek Windows kanıtı

Faz 24c salt-okunur test, `filing_records_source` tablosunda **0 kayıt**
buldu. `ticker_aliases` tablosu mevcut, ancak ilk 300 kaydın hiçbirinde
tarih/kaynak alanlarının tümü birlikte yeterli değildi. 24 SEC security_id
örneğinin **23'ünde** fact vardı ancak başvuru kaydı yoktu. Bu bulgu,
12.313.284 Companyfacts finansal kaydını *yeniden indirmemiz* gerektiğini
göstermez. SEC XBRL Companyfacts ile özgün `submissions` kaynakları
aynı ürün değildir.

## Amaç ve sınırlar

`scripts/phase24d_sec_submissions_existing_inventory.py`:
- Kullanıcının Faz24 raporundaki **CIK adaylarını** çıkarır.
- Yalnızca açıkça adlandırılan özel Windows dizinlerinin **doğrudan**
  içeriğini tarar (tüm diski taramaz).
- `CIK##########.json` ve bunların kökteki manifestin belirttiği
  `CIK##########-submissions-NNN.json` arşivlerini yapı/CIK yönünden
  kontrol eder; `sec_sources_manifest.json` varsa kaynak SHA-256'sını
  karşılaştırır.
- Bir CIK için kök bulunmasını, tüm tarihsel arşiv ve özgün
  kabul zamanlarının eksiksiz olmasıyla **karıştırmaz**.
- Üzerinde `FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT` yazılı olsa
  dahi manifesti **bağımsız özgünlük kanıtı olarak saymaz**.
- Ağ çağrısı, SEC veri indirme, SQLite okuma/yazma, model eğitimi veya
  kanonik PIT/fiyat seçimi yapmaz.
- Source dosyalarını hiçbir zaman açık GitHub reposuna yüklemez.

## Windows PowerShell

```powershell
cd E:\M10
git pull --ff-only
.\.venv\Scripts\python.exe -m scripts.phase24d_sec_submissions_existing_inventory
```

Varsayılan araştırılan dizinler:
1. `E:\Meridyen_SEC\submissions`
2. `%LOCALAPPDATA%\S153ResearchTerminal\runtime\sec_mirror\submissions`
3. `%LOCALAPPDATA%\S153ResearchTerminal\runtime\sec_submissions`

SEC arşivlerin **başka** klasördeyse, yalnızca doğru gerçek klasörü
belirterek tekrar tara:

```powershell
.\.venv\Scripts\python.exe -m scripts.phase24d_sec_submissions_existing_inventory --dir "D:\Actual_SEC_Submissions_Folder"
```

`--dir` birden fazla kez yazılabilir. Geçersiz veya eksik dizinler
`NOT_FOUND_OR_NOT_DIRECTORY` gösterilir; yok sayılarak bütün
bilgisayarda hiç SEC verisi olmadığı iddia edilmez.

Rapor:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase24d\sec_submissions_existing_inventory.json`

## Sonraki karar

1. Kanıt varsa yeni kaynak çekmeden, bağımsız kaynak ve timestamp
   doğrulamasını bu SEC dosyaları üzerinde yap.
2. Kanıt yoksa önce 1 **tek CIK** için mevcut
   `scripts.phase14_sec_submissions_collect` aracının dry-run
   moduyla ihtiyaç ve dosya yolunu doğrula. Ağ indirmesi yalnızca
   kullanıcının yerel açık `--execute` komutuyla, resmi SEC rate-limit
   altında yapılmalıdır.
3. Gerçek tarihler ve accession eşleşmeleri, yerel SQLite
   **yedek kopyası** üzerinde `phase14_sec_submissions_archive_reconcile`
   ile denetlenir. Mevcut üretim tablolarına otomatik yazma yoktur.

**Durum:** Kanonik SimFinId–CIK tarihsel kimliği 0, kanonik
backtest ve Learning V3 henüz başlatılmadı.
