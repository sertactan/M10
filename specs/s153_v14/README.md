# S15.3 V1.4 canonical specification bundle

This directory is the **only repository drop location** for the authoritative Phase 5 V1.4
specification set.

Do not place inferred formulas, UI examples, reconstructed rules, or model guesses here.

Required artifacts are exactly:

1. `S15.3 V1.4 Canonical Specification`
2. `V1.4 Factor / DNA Definitions`
3. `V1.4 Router and Gate Specification`
4. `Dual-Magnitude / Destination Specification`
5. `Golden Test Cases`

When the authoritative files are supplied:

1. save each file in this directory;
2. compute its SHA-256;
3. copy `manifest.template.json` to `manifest.json`;
4. replace every placeholder path/hash and the bundle id;
5. run the test suite.

`load_verified_bundle()` rejects missing files, duplicate artifacts, path traversal, invalid hashes,
tampered files, incomplete manifests, and PENDING bundle ids.

A verified bundle **does not itself authorize invented executable math**. The exact formulas and
Golden expected results must still be encoded faithfully from those verified artifacts before
`config/s153_v14.yaml` can be enabled.
