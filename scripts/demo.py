"""Noninteractive evidence REPLAY. Approvals are explicitly simulated, never human evidence."""
import argparse
import json
import tempfile
from pathlib import Path
from orchestrator.engine import Engine


def drive(engine, state):
    for _ in range(15):
        state = engine.advance(state["id"])
        if state["status"] == "waiting_clarification":
            state = engine.revise(state["id"], state["scenario_contract"]["fixture_answer"], "SIMULATED-DEMO-REVIEWER", True)
        elif state["status"] == "waiting_approval":
            state = engine.approve(state["id"], "SIMULATED-DEMO-REVIEWER", "Automated replay approval; not a human sign-off", state["pending"]["binding"])
        else:
            return state
    raise RuntimeError("Demo transition budget exhausted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/replay")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as root:
        engine = Engine(root)
        green = drive(engine, engine.create("greenfield"))
        runs = {"greenfield": green,
                "brownfield": drive(engine, engine.create("brownfield", parent=green["id"])),
                "ambiguous": drive(engine, engine.create("ambiguous", parent=green["id"])),
                "retry_recovery": drive(engine, engine.create("brownfield", inject="once")),
                "safe_stop": drive(engine, engine.create("brownfield", inject="always"))}
        replan = engine.advance(engine.create("greenfield")["id"])
        replan = engine.revise(replan["id"], replan["requirement"], "SIMULATED-DEMO-REVIEWER")
        runs["replan"] = drive(engine, replan)
        for name, state in runs.items():
            expected = "stopped" if name == "safe_stop" else "completed"
            if state["status"] != expected:
                raise RuntimeError(f"{name}: expected {expected}, got {state['status']}: {state.get('stop_reason')}")
            engine.export(state["id"], output / name)
        summary = {"mode": "fixture replay; approvals simulated", "live_llm_tested": False,
                   "scenarios": {n: {"id": s["id"], "status": s["status"], "revision": s["revision"]} for n, s in runs.items()},
                   "metrics": engine.metrics()}
        (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
