"""Offline deterministic queue interface, suitable for Hermes --no-agent cron."""
import argparse
import json
from pathlib import Path
from core.hermes_team.tasks import LocalTasks


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, required=True)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("tick")
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("task", choices=["strategy","scan","fundamental","catalyst","risk","learning"])
    status = sub.add_parser("status")
    status.add_argument("job_id")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("parent_id")
    handoff.add_argument("task", choices=["scan","fundamental","catalyst","risk","learning"])
    review = sub.add_parser("review-interrupted")
    review.add_argument("job_id")
    args = p.parse_args()
    queue = LocalTasks(args.db)
    if args.command == "tick":
        result = queue.dispatch_one() or {"status": "NO_PENDING_WORK"}
    elif args.command == "enqueue":
        result = {"job_id": queue.submit(args.task), "status": "QUEUED"}
    elif args.command == "handoff":
        result = {"job_id": queue.handoff(args.parent_id, args.task), "status": "QUEUED"}
    elif args.command == "review-interrupted":
        result = {"status": "BLOCKED_OPERATOR_REVIEW" if queue.review_interrupted(args.job_id)
                  else "NOT_RUNNING"}
    else:
        result = queue.status(args.job_id) or {"status": "NOT_FOUND"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
