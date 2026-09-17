"""Test Docker isolation with bundled code (no LLM); executed in CI or manually."""
import tempfile
from orchestrator.engine import Engine
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory() as root:
        engine = Engine(root)
        state = engine.create("brownfield", mode="live")
        policy = Path("shortener/policy.py").read_text()
        (engine.work(state) / "shortener/policy.py").write_text(policy)
        result = engine.run_tests(state)
        print(result["log"])
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
