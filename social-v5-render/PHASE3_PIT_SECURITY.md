# MERIDYEN Social V5 FREE — Phase 3, isolated staging

Status: FIRST LIVE SNAPSHOT CAPTURED, LIVE MCP UNCHANGED.
Repository: public M10, **feature/social-v5-pit-auth-phase3** only.
Deployed Render branch remains `deploy/social-v5-render-free`; no automatic deploy.
The installed private Meridyen plugin and frozen S-series model sources are unchanged.

## First observed data
- Run source: GitHub Actions with public outbound Bluesky and Mastodon GETs.
- Current scope: one INOD ticker; 15 latest returned posts max per platform per run.
- Writes `pit_data/YYYY-MM-DD.jsonl`: source ID hash, URL hash, author hash,
  text hash, UTC post creation time, **actual collection observed time**,
  network capture proof, engagement at capture, GitHub run ID.
- Raw text, social handles, clear URLs, tokens and private/community data are
  NOT saved to the public repository. Public search can still contain bias.
- Writes `pit_data/capture_runs.jsonl`: success / outage per source,
  collection start/end time, post count, GitHub run ID; success with 0 matches
  is NOT a zero-mention market survey.
- Repeat appearances preserve the first observed time within 8-day dedup horizon.
  This is initial research storage, not a permanent auditable market database;
  GitHub commit provenance is independent coarse evidence, not cryptographic
  source-of-first-seen proof.
- `pit_readiness.py` requires at least 65 distinct covered baseline hours in
  previous 72 hours and 22 in the most recent 24 hours from at least one source.
  These QA thresholds are **noncanonical** and not Meridyen model gates.
  Even after they pass, source coverage remains selective. Historical
  results cannot be retrospectively backfilled as if previously observed.

## Launch/continuity truth
A GitHub Actions `push` workflow on this feature branch performs offline
regression tests then one prospective INOD capture and commits the sanitized
output to this branch. **THIS IS NOT A RECURRING SCHEDULER**.
GitHub scheduled workflows run from the repository's default branch, so hourly
capture would require an explicitly approved small workflow addition to M10's
`main` branch (or a separately configured lawful free scheduler). This phase
does not change M10 main, YFinance, OpenBB or S15/S16 sources.
Never claim a 72-hour baseline exists after one or two collection runs.

## Authentication staging (not live)
`mcp_auth.py`: opt-in constant-time bearer middleware, all `/mcp` methods
unauthorized when a nonempty `SOCIAL_MCP_BEARER_TOKEN` is configured in the
*server* environment; token length must be 32+ UTF-8 bytes. Health stays
unauthenticated. Header duplicates rejected. Secret must NEVER enter a
GitHub commit, `mcp.json`, a chat message or application logs.
The live Render FREE MCP remains **PUBLIC READ-ONLY** until a compatible
client-side auth/consent flow is confirmed and server secret applied. DO NOT
flip the token on the live instance without updating both Codex and ChatGPT
connections; it would deliberately break live MCP. This repository file is
a staged capability, NOT proof that access is currently restricted.
No broker access, orders, paid API, or model mutations are introduced.

## Regression gate
Run `python -m unittest discover -s social-v5-render/tests -p test_phase3.py -v`.
Test network calls use fakes and never establish live source availability.
Run the GitHub Action to perform an actual prospective capture, then inspect
`capture_runs.jsonl` and `readiness.json` independently.
