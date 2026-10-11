"""Replay existing private SEC source clocks without network or DB writes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v4_independent import audit_cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions", type=Path, required=True)
    parser.add_argument("--submissions-receipt", type=Path, required=True)
    parser.add_argument("--filing-cache", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_cache(args.submissions, args.submissions_receipt, args.filing_cache, as_of=args.as_of)
    raw = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+"\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(raw)
    Path(str(args.output)+".sha256").write_text(sha256(raw).hexdigest()+"\n", encoding="ascii")
    print(json.dumps({k: report[k] for k in ("document_count", "research_eligible_count", "historical_pit_accepted_count", "full_model_scores_added")}))


if __name__ == "__main__":
    main()
