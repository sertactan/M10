# Faz25k — 133 aday icin kanonik PIT kabul defteri

Phase25i Windows read-only DB kapilari ile Phase25j altı P1 SEC kaynak belgesi ve diger 127 kaynaktaki anomaliler birlesir.

Bu rapor sunlari verir: 133 benzersiz SimFinId icin eksik tarihsel CIK/share-class, gunluk issuer/exchange uyumu, tum split/temettu/ADR, vendor adjusted-price tanimi, delist/terminal return, SEC available_at, 21 aylik kanonik snapshot ve 252 oturumluk mature label kanitlari.

Onemli: Bu **kanıt yoklugu ve kabul tablosudur**, kanonik PIT dataset ya da WF9 backtest degildir. Sadece 21 aylik listelerde surekli gorunen hisse kohortu tum piyasa yerine konursa survivorship bias dogar. IRS nakit+hisse dagitimi ve SITC reverse split+CURB spin-off ayri cozulmeli.

PowerShell guncel worktree:
    & "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25k_canonical_acceptance_ledger

Cikti: %LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25k\canonical_acceptance_133_research_ledger.json
       %LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25k\canonical_acceptance_133_research_ledger.csv

Veri silinmez, DB'ye yazilmaz, backtest ve Learning V3 kendi kendine baslamaz.