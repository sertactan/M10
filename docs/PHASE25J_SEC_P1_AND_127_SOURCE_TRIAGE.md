# Faz25j - Resmi SEC ihracci/CIK baglantilari ve 127 diger fiyat anomalisi

2024-01-01–2025-09-30 kaynak fiyat arastirmasi icin onceki Faz24, Faz25d ve Faz25e ozel JSON dosyalari kullanilir. Yeni API cagrisi veya tarihsel kimlik sertifikasi yoktur.

## Alti P1 — resmi SEC belgesi; gunluk tarihsel kimlik onayi degil

| Ticker | SimFinId | Mevcut CIK adayi | SEC kaydindaki ihracci | Form |
|---|---:|---|---|---|
| DOYU | 18842733 | 0001762417 | DouYu International Holdings Limited | 20-F |
| HUYA | 1253406 | 0001728190 | HUYA Inc. | 20-F |
| IRS | 17733533 | 0000933267 | IRSA Inversiones y Representaciones SA | 20-F |
| SITC | 998403 | 0000894315 | SITE Centers Corp. | 10-K |
| TDG | 378229 | 0001260221 | TransDigm Group Incorporated | 10-K |
| ZIM | 18525398 | 0001654126 | ZIM Integrated Shipping Services Ltd. | 20-F |

SEC belgeleri CIK–ihracci unvanini gosterir; SimFinId–CIK–ADS/common/GDS sinifini 2024–2025 **butun gunlerde** bagimsiz kanitlamaz. Resmi URL'ler JSON'da tutulur.

SITC'nin 2024 SEC 10-K'si 1-for-4 reverse stock split ile 2024-10-01 CURB spin-off (1 SITC hissesi icin 2 CURB) bildiriyor. Bu nedenle yalnizca nakit temettu duzeltmesi yeterli degildir:
https://www.sec.gov/Archives/edgar/data/894315/000095017025029989/sitc-20241231.htm

## 127 diger aday

- P2: 88 benzersiz SimFinId, 127 tarihli fiyat uyarisi.
- P3: 39 benzersiz SimFinId, 40 tarihli fiyat uyarisi.
- P1: 6 benzersiz SimFinId, 15 olay.
- Genel toplam: 133 benzersiz arastirma adayi ve 182 fiyat olayi.
- Diger 127 adayda resmi split/temettu olaylari bagimsiz onaylanmadi.

PowerShell (kodun oldugu guncel main worktree konumundan):

    & "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25j_p1_sec_issuer_and_p2p3_source_triage

Ozel raporlar:
%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25j\sec_p1_cik_and_p2p3_event_triage.json
%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25j\p2p3_127_source_event_queue.csv

SEC_document_identifies_issuer_and_CIK true degeri sadece SEC belgesi seviyesinde kanittir. Tarihsel SimFinId/CIK hissesi icin otomatik onay yoktur. Tam 21/21 ay kalmis hisselerle universel backtest yapmak survivorship bias yaratir. Ayrica tarihsel delisting, split, share-class, ADS ve geriye donuk adjusted-price kayitlari ayrica onaylanmalidir.

Production SQLite, SEC satirlari, SimFin kaynagi, S15.3, S16, S16-EA formulleri, WF9 ve Learning V3 degistirilmez.