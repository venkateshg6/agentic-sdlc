import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from orchestrator.engine import Engine, GRAPH, graph_valid, check_patch


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = Engine(self.temp.name)

    def drive(self, state):
        for _ in range(12):
            state = self.engine.advance(state["id"])
            if state["status"] == "waiting_approval":
                state = self.engine.approve(state["id"], "test-reviewer", "Automated test approval only", state["pending"]["binding"])
            else:
                return state
        self.fail("Transition loop")

    def test_three_scenarios(self):
        first = self.drive(self.engine.create("greenfield"))
        self.assertEqual(first["status"], "completed", first.get("stop_reason"))
        second = self.drive(self.engine.create("brownfield", parent=first["id"]))
        self.assertEqual(second["status"], "completed", second.get("stop_reason"))
        self.assertEqual(second["completed"]["implementation"]["files"].keys(), {"shortener/policy.py"})
        ambiguous = self.engine.create("ambiguous")
        paused = self.engine.advance(ambiguous["id"])
        self.assertEqual(paused["status"], "waiting_clarification")
        revised = self.engine.revise(paused["id"], paused["scenario_contract"]["fixture_answer"], "test-reviewer", True)
        final = self.drive(revised)
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["revision"], 2)

    def test_gate_blocks_writes(self):
        s = self.engine.advance(self.engine.create("greenfield")["id"])
        self.assertEqual(s["status"], "waiting_approval")
        self.assertEqual(self.engine.capture(s), {})
        self.assertEqual(s["pending"]["stage"], "change_approval")

    def test_stale_binding(self):
        s = self.engine.advance(self.engine.create("brownfield")["id"])
        with self.assertRaises(ValueError):
            self.engine.approve(s["id"], "reviewer", "reviewed", "wrong")
        p = self.engine.work(s) / "shortener/policy.py"
        p.write_text(p.read_text() + "\n# external change")
        with self.assertRaises(ValueError):
            self.engine.approve(s["id"], "reviewer", "reviewed", s["pending"]["binding"])

    def test_reject_rolls_back(self):
        s = self.engine.advance(self.engine.create("greenfield")["id"])
        s = self.engine.approve(s["id"], "reviewer", "Not acceptable", s["pending"]["binding"], True)
        self.assertEqual(s["status"], "stopped")
        self.assertEqual(self.engine.capture(s), {})

    def test_retry_and_reapproval(self):
        s = self.drive(self.engine.create("brownfield", inject="once"))
        self.assertEqual(s["status"], "completed")
        self.assertEqual(s["retry_count"], 1)
        self.assertEqual(s["rollback_count"], 1)
        self.assertEqual(len(s["recoveries"]), 1)
        events = self.engine.db.events(s["id"])
        self.assertEqual(sum(e["kind"] == "approval_granted" for e in events), 3)

    def test_safe_stop_budget(self):
        s = self.drive(self.engine.create("brownfield", inject="always"))
        self.assertEqual(s["status"], "stopped")
        self.assertEqual(s["retry_count"], 2)
        self.assertEqual(s["rollback_count"], 3)
        self.assertEqual(self.engine.capture(s), s["baseline"])

    def test_revision_invalidates(self):
        s = self.engine.advance(self.engine.create("greenfield")["id"])
        old = s["pending"]["binding"]
        s = self.engine.revise(s["id"], s["requirement"], "reviewer")
        s = self.engine.advance(s["id"])
        self.assertNotEqual(s["pending"]["binding"], old)
        self.assertEqual(s["revision"], 2)

    def test_parallel_batches_and_join(self):
        s = self.drive(self.engine.create("greenfield"))
        events = self.engine.db.events(s["id"])
        batches = [e["detail"]["nodes"] for e in events if e["kind"] == "batch_started"]
        self.assertIn(["architecture", "test_design"], batches)
        self.assertIn(["tests", "security"], batches)
        self.assertLess(batches.index(["tests", "security"]), batches.index(["documentation"]))

    def test_checkpoint_resume_new_process_object(self):
        s = self.engine.advance(self.engine.create("greenfield")["id"])
        self.engine = Engine(self.temp.name)
        s = self.engine.approve(s["id"], "reviewer", "Reviewed diff", s["pending"]["binding"])
        self.assertEqual(self.drive(s)["status"], "completed")

    def test_integrity_tamper(self):
        s = self.engine.create("greenfield")
        with self.engine.db.db() as db:
            db.execute("UPDATE events SET payload='{}'")
        self.assertFalse(self.engine.db.verify(s["id"]))
        with self.assertRaises(ValueError):
            self.engine.db.load(s["id"])

    def test_state_tamper(self):
        s = self.engine.create("greenfield")
        s["status"] = "completed"
        with self.engine.db.db() as db:
            db.execute("UPDATE runs SET state=?", (json.dumps(s),))
        with self.assertRaises(ValueError):
            self.engine.db.load(s["id"])

    def test_graph_and_path_guard(self):
        self.assertTrue(graph_valid(GRAPH))
        for graph in ({"a": ["a"]}, {"a": ["missing"]}):
            with self.assertRaises(ValueError):
                graph_valid(graph)
        for files in ({"../../escape.py": "x=1"}, {"tests/test.py": "x=1"}, {"shortener/policy.py": "eval('1')"}):
            with self.assertRaises(ValueError):
                check_patch(files, "brownfield")

    def test_metrics(self):
        self.drive(self.engine.create("greenfield"))
        self.drive(self.engine.create("brownfield", inject="always"))
        metrics = self.engine.metrics()
        self.assertEqual(metrics["success_rate"], 0.5)
        self.assertEqual(metrics["retry_frequency_per_run"], 1)

    def test_lock(self):
        with self.engine.lock(), self.assertRaises(ValueError):
            with self.engine.lock():
                pass

    def test_crash_recovery(self):
        s = self.engine.create("brownfield")
        s["status"] = "running"
        self.engine.db.save(s, "injected_process_crash", {})
        with self.assertRaises(ValueError):
            self.engine.advance(s["id"])
        s = self.engine.recover(s["id"], "reviewer")
        self.assertEqual(s["revision"], 2)
        self.assertEqual(self.drive(s)["status"], "completed")

    def test_live_requires_isolation(self):
        s = self.engine.create("brownfield", mode="live")
        with patch("orchestrator.engine.shutil.which", return_value=None), self.assertRaises(ValueError):
            self.engine.run_tests(s)

    def test_fixture_custom_requirement_refused(self):
        s = self.engine.advance(self.engine.create("greenfield", requirement="Build a banking app")["id"])
        self.assertEqual(s["status"], "stopped")

    def test_live_role_contracts_with_mock_provider_and_executor(self):
        from orchestrator.engine import ROOT
        def complete(provider, role, context):
            if role == "Requirements analyst":
                return {"normalized": "Fix expiration boundary", "questions": [], "risks": []}
            if role == "Architect and dependency planner":
                return {"impacted_modules": ["shortener/policy.py"], "tasks": ["Fix comparison"], "decisions": [], "risks": []}
            if role == "Independent test engineer":
                return {"source": "import unittest\nclass Test(unittest.TestCase):\n def test_boundary(self):\n  from shortener.policy import is_expired\n  self.assertTrue(is_expired(1,1))\n", "rationale": "Boundary regression"}
            return {"files": {"shortener/policy.py": (ROOT / "shortener/policy.py").read_text()}, "rationale": "Fix boundary"}
        with patch("orchestrator.engine.Provider.complete", complete), patch.object(Engine, "run_tests", return_value={"passed": True, "executor": "MOCK-only"}):
            s = self.drive(self.engine.create("brownfield", mode="live"))
        self.assertEqual(s["status"], "completed")
        self.assertEqual(s["completed"]["requirements"]["analysis"]["normalized"], "Fix expiration boundary")

    def test_live_analyst_can_pause_for_clarification(self):
        with patch("orchestrator.engine.Provider.complete", return_value={"normalized": "Unclear", "questions": ["Which boundary?"], "risks": []}):
            s = self.engine.advance(self.engine.create("brownfield", mode="live")["id"])
        self.assertEqual(s["status"], "waiting_clarification")
        self.assertEqual(s["questions"], ["Which boundary?"])

    def test_live_malformed_role_output_stops(self):
        with patch("orchestrator.engine.Provider.complete", return_value={"normalized": 42}):
            s = self.engine.advance(self.engine.create("brownfield", mode="live")["id"])
        self.assertEqual(s["status"], "stopped")
        self.assertEqual(self.engine.capture(s), s["baseline"])

    def test_release_workspace_mutation_refused(self):
        s = self.engine.advance(self.engine.create("greenfield")["id"])
        self.engine.approve(s["id"], "reviewer", "Approved", s["pending"]["binding"])
        s = self.engine.advance(s["id"])
        self.assertEqual(s["pending"]["stage"], "release_approval")
        path = self.engine.work(s) / "shortener/policy.py"
        path.write_text(path.read_text() + "\n# external drift")
        with self.assertRaises(ValueError):
            self.engine.approve(s["id"], "reviewer", "Approved", s["pending"]["binding"])

    def test_invalid_fixture_clarification_has_no_side_effects(self):
        s = self.engine.advance(self.engine.create("ambiguous")["id"])
        before = self.engine.capture(s)
        with self.assertRaises(ValueError):
            self.engine.revise(s["id"], "Do something else", "reviewer", True)
        self.assertEqual(self.engine.capture(s), before)
        self.assertEqual(self.engine.db.load(s["id"])["revision"], s["revision"])

    def test_untrusted_host_code_refused(self):
        s = self.engine.create("brownfield")
        (self.engine.work(s) / "shortener/policy.py").write_text("# Not a bundled fixture\n")
        with self.assertRaises(ValueError):
            self.engine.run_tests(s)

    def test_blank_reviewer_refused(self):
        s = self.engine.advance(self.engine.create("greenfield")["id"])
        with self.assertRaises(ValueError):
            self.engine.approve(s["id"], "", "reviewed", s["pending"]["binding"])


if __name__ == "__main__":
    unittest.main()
