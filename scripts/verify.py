"""Execute the test suite and write reproducible verification evidence."""
import json
import platform
import time
import unittest
from pathlib import Path


def main():
    directory = Path("evidence")
    directory.mkdir(exist_ok=True)
    start = time.time()
    with (directory / "test-results.txt").open("w", encoding="utf-8") as stream:
        suite = unittest.defaultTestLoader.discover("tests")
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    summary = {"python": platform.python_version(), "platform": platform.system(),
               "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped), "seconds": time.time() - start,
               "live_provider_tested": False, "docker_execution_tested": False,
               "note": "Provider transport and failure/fallback tests use mocks. No claim of production certification."}
    (directory / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
