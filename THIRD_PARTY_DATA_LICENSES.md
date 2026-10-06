# Third-Party Data / Reference Notices

S15.3 Research Terminal keeps security-reference coverage separate from
authoritative model evidence. The presence of a symbol in an embedded reference
seed does not by itself make that row canonical S15.3 evidence.

## FinanceDatabase

Project: FinanceDatabase  
Repository: https://github.com/JerBouma/FinanceDatabase  
Copyright: Copyright (c) 2023 Jeroen Bouma  
License: MIT License

MIT License

Copyright (c) 2023 Jeroen Bouma

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

### How M10 uses this reference

The packaged Japan, Turkey and Hong Kong security-master seed is generated from
the FinanceDatabase exchange reference exports for JPX, Istanbul and Hong Kong.

These records are tagged:

- source = FINANCEDATABASE_MIT_REFERENCE
- source_scope = REFERENCE_ONLY
- redistribution_status = MIT_REFERENCE_REQUIRES_SOURCE_POLICY

They are intended for offline symbol discovery, security identity, exchange /
country filtering and source reconciliation. They are not automatically used as
authoritative historical prices, fundamentals, corporate actions or S15.3 model
evidence.

Exchange-originated facts may remain subject to source-specific exchange terms.
M10 therefore keeps official market-data adapters and canonical evidence policy
separate from this convenience reference seed.

## SEC EDGAR US security identity seed

The packaged US security-master seed is generated from the SEC company ticker /
exchange reference endpoint when available. GitHub-hosted build runners may be
blocked by SEC fair-access controls; in that case the build uses a dated clean
SEC-derived mirror and records its snapshot date. Installed applications can
refresh the current universe from SEC directly subject to SEC fair-access rules.

This seed is security identity/reference metadata, not multi-year OHLCV history.


## Stock-Data public PIT universe archive

Project: Stock-Data  
Repository: https://github.com/TylerJForstrom/Stock-Data  
Dataset used: `data/symbols/pit/sec_company_tickers_exchange.jsonl`

The upstream manifest identifies this PIT interval dataset as derived from
US-government public-domain SEC data and exchange reference directories and
marks the derived work freely redistributable. M10 verifies the published
SHA256 before ingest and enforces the upstream `reconstructable_from` floor.

M10 uses this source only for historical security-universe membership. It does
not silently infer membership before the archive's provable boundary, and it
does not treat the source as price, fundamental, analyst, catalyst, or S15.3
factor evidence.
