"""Human-operated CLI; intentionally no automatic approval in normal execution."""
import argparse
import json
import sys
from orchestrator.config import load_env
from orchestrator.engine import Engine


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Governed SDLC orchestrator")
    parser.add_argument("--root", default=".runtime/engineering")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new")
    new.add_argument("scenario", choices=["greenfield", "brownfield", "ambiguous"])
    new.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    new.add_argument("--requirement")
    new.add_argument("--parent")
    new.add_argument("--inject", choices=["none", "once", "always"], default="none")
    for command in ("run", "status", "verify", "inspect"):
        sub.add_parser(command).add_argument("id")
    for command in ("approve", "reject"):
        p = sub.add_parser(command)
        p.add_argument("id")
        p.add_argument("--actor", required=True)
        p.add_argument("--note", required=True)
        p.add_argument("--binding", required=True)
    for command in ("revise", "clarify"):
        p = sub.add_parser(command)
        p.add_argument("id")
        p.add_argument("--text", required=True)
        p.add_argument("--actor", required=True)
    p = sub.add_parser("recover")
    p.add_argument("id")
    p.add_argument("--actor", required=True)
    p = sub.add_parser("export")
    p.add_argument("id")
    p.add_argument("--output", required=True)
    sub.add_parser("metrics")
    args = parser.parse_args()
    engine = Engine(args.root)
    try:
        if args.command == "new":
            value = engine.create(args.scenario, args.requirement, args.mode, args.parent, args.inject)
        elif args.command == "run":
            value = engine.advance(args.id)
        elif args.command in {"status", "inspect"}:
            value = engine.db.load(args.id)
            if args.command == "inspect":
                print(json.dumps(value, indent=2))
                return
        elif args.command == "verify":
            engine.db.load(args.id)
            value = {"audit_valid": True}
        elif args.command in {"approve", "reject"}:
            value = engine.approve(args.id, args.actor, args.note, args.binding, args.command == "reject")
        elif args.command in {"revise", "clarify"}:
            value = engine.revise(args.id, args.text, args.actor, args.command == "clarify")
        elif args.command == "recover":
            value = engine.recover(args.id, args.actor)
        elif args.command == "export":
            value = engine.export(args.id, args.output)
        else:
            value = engine.metrics()
        if "completed" in value:
            value = {k: value.get(k) for k in ("id", "scenario", "mode", "status", "revision", "pending", "questions", "stop_reason")}
        print(json.dumps(value, indent=2))
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
