# Phase 6 authoritative backtest specification bundle

This directory is the repository drop location for the complete Phase 6 specification set.

Required artifacts are exactly:

1. `Historical Backtest Specification`
2. `Point-in-Time Controls Specification`
3. `Corporate Action Adjustment Specification`
4. `Trading Calendar Specification`
5. `Benchmark Specification`
6. `Golden Backtest Test Cases`

Existing matched-control material remains useful evidence, but partial coverage must not be promoted to
a complete authoritative artifact unless the missing rules are explicitly supplied.

When the complete authoritative files are available:

1. save all six artifacts in this directory;
2. compute SHA-256 for each file;
3. copy `manifest.template.json` to `manifest.json`;
4. replace all placeholder paths/hashes and the bundle id;
5. run the Phase 6 test suite;
6. implement only the exact calendar, corporate-action, benchmark and Golden-case rules contained
   in the verified files.

The loader rejects missing, duplicate, empty, path-escaping, tampered, invalid-hash and incomplete
bundles. A verified bundle does not permit guessed benchmark mappings or Golden expected values.
