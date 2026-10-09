"""Only manually run on a private host after third-party account verification."""
from __future__ import annotations

import argparse
from pathlib import Path

from core.hermes_team.gateway import serve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    serve(args.policy, args.ledger)


if __name__ == "__main__":
    main()
