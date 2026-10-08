# Phase 17 — Meridyen Learning Engine V3 (Experimental Challenger)

Engineering status: CODE AND REGRESSION TESTS SUBMITTED FOR CI.
Production status: NOT DEPLOYED. Frozen S15/S16 formulas unchanged.

## Components

- scripts/phase17_export_features.py: Read-only export from COMPLETE WF5 and mature Learning V2 labels joined to canonical_model_features with original feature_as_of, available_at, source_ref. Skip every member of a snapshot date if any scored stock has missing/immature label or missing feature.
- core/learning_v3/challenger.py: train-only normalization, deterministic ridge-logistic, date-blocked OOS; training labels must have been available before first test signal.
- scripts/phase17_learning_v3.py: isolated research JSON experiment with SHA256 model/report, OOS Precision@K versus frozen S15, never auto-promotes or trades.
- scripts/phase17_improve_plan.py: P0/P1/P2 safe change suggestions and review-only GitHub PR governance; no canonical model in-place changes.

## Windows M10 local execution (requires real, complete WF5 evidence)

```powershell
python scripts/phase17_export_features.py --operational-db data/runtime/operational.db --learning-db data/runtime/meridyen_learning.sqlite3 --wf5-run-id REAL_COMPLETE_WF5_RUN_ID --wf5-batch-sha256 REAL_WF5_BATCH_SHA256 --feature-keys D01 F54_DIL --cutoff 2026-10-08 --out data/runtime/learning_v3/dataset_001.json
python scripts/phase17_learning_v3.py --dataset data/runtime/learning_v3/dataset_001.json --cutoff 2026-10-08 --k 10 --out data/runtime/learning_v3/experiment_001.json
python scripts/phase17_improve_plan.py --experiment data/runtime/learning_v3/experiment_001.json --out data/runtime/learning_v3/improvement_plan_001.json
```

## Research gate / governance

- Default min 100 mature training rows, >=8 positive and >=8 negative training outcomes, >=40 OOS rows, >=3 OOS dates. A single split is NOT enough for production.
- Features explicitly whitelisted and time-stamped; H10, WINNER_SIM, HMG10 and all future/outcome fields are rejected. No imputation.
- Every evaluated date is a complete labelled cohort; missing one stock excludes entire date.
- Model score improvement is a research finding, not a release authorization. Independent PIT, market regimes, matched controls, costs, risk review and owner approval are required.
- No ChatGPT weight fine-tuning, always-on training, automatic code mutation, auto-merge, public sharing of private trading evidence, or canonical formula modification.
- Improvement PRs must pass Python CI and be reviewed. Rollback is git revert of exact noncanonical PR commit.

## Remaining deployment blockers

- Real Windows M10 operational.db, complete 2013–2024 PIT universe/fundamentals/adjusted bars and verified WF9 COMPLETE_AND_ACTIVATED not accessible in this session.
- Genuine whole-market 10X recall and historical profit metrics cannot be claimed from incomplete data.
- Phase16 Windows Task Scheduler/Google Drive rclone crypt authentication and real cloud restore remain to be performed on owner's system.

CI passing proves engineering only, not investment performance or continuous self-learning.
