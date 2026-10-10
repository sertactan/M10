Phase25P — SEC Accepted is not model public available_at

Three **original SEC EDGAR filing index** acceptance stamps from the 2024–2025 evidence chain are documented:

HUYA Inc CIK 0001728190: 2024 Form 20-F period-end 2024-12-31, EDGAR Accepted 2025-04-17 06:43:22 EDT / 10:43:22 UTC. Source https://www.sec.gov/Archives/edgar/data/1728190/000141057825000781/0001410578-25-000781-index.htm

TransDigm Group TDG CIK 0001260221: FY ended 2024-09-30 Form 10-K Accepted 2024-11-07 16:05:07 EST / 21:05:07 UTC. Source https://www.sec.gov/Archives/edgar/data/1260221/000126022124000083/0001260221-24-000083-index.htm

Barnes Group NYSE B CIK 0000009984: 2024-10-25 Form 8-K Accepted 2024-10-25 06:47:43 EDT / 10:47:43 UTC. Source https://www.sec.gov/Archives/edgar/data/9984/000000998424000130/0000009984-24-000130-index.htm

Actual SEC acceptance, *SEC public dissemination* and *vendor feature ingestion available_at* are three different clocks. A filing's historical period end is NOT a public-available time. This phase provides reusable core/research/sec_publication_gate.py with fail-closed decision ordering: the evidence can contribute to an historical feature only if externally observed publication time >= SEC accepted time, vendor feature available_at >= public time, and the decision clock >= feature available_at. Missing or timezone-naive timestamps reject the feature. In these three real cases the actual public dissemination and feature ingestion stamps have not been independently certified; hence model eligible records = 0 even though the acceptance stamps are documented.

This is deliberately NOT a complete SEC PIT corpus for every US company, NOT a validator of CIK-share class or issuer delisting, and NOT a claim that WF9 or Learning V3 ran. No paid APIs, source data uploads, private credentials, main model formula changes or production operational.db writes. Unit tests: actual offset conversions, period-end lookahead rejection, missing dissemination, real-clock chronological acceptance. Windows, when reconnected: python -m scripts.phase25p_sec_acceptance_floor ; a private JSON evidence report is saved under %LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25p.
