"""Persistent dependency-graph scheduler with human gates and bounded repair loops.

CLI commands are serialized by an OS-level lock file; independent read-only nodes
run in a thread pool. Workers return outputs; only the coordinator commits state.
"""
import ast
import contextlib
import difflib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from orchestrator.provider import Provider
from orchestrator.state import StateDB, digest

ROOT = Path(__file__).resolve().parents[1]
GRAPH = {
    "requirements": [],
    "architecture": ["requirements"],
    "test_design": ["requirements"],
    "implementation": ["architecture", "test_design"],
    "change_approval": ["implementation"],
    "apply": ["change_approval"],
    "tests": ["apply"],
    "security": ["apply"],
    "documentation": ["tests", "security"],
    "release_approval": ["documentation"],
    "summary": ["release_approval"],
}
ALLOWED = {"shortener/__init__.py", "shortener/service.py", "shortener/api.py", "shortener/policy.py"}
BASE_POLICY = '"""Initial expiration policy; exact-boundary bug is addressed in brownfield."""\n\ndef is_expired(expires_at, now):\n    return expires_at is not None and expires_at < now\n'


def graph_valid(graph):
    seen = set()
    while len(seen) < len(graph):
        ready = {n for n, deps in graph.items() if n not in seen and set(deps) <= seen}
        if not ready:
            raise ValueError("Dependency cycle or unknown dependency")
        seen |= ready
    return True


def check_patch(files, scenario):
    allowed = ALLOWED if scenario == "greenfield" else {"shortener/policy.py"}
    if not isinstance(files, dict) or not files or set(files) - allowed:
        raise ValueError("Policy: file outside approved change scope")
    if scenario == "greenfield" and set(files) != ALLOWED:
        raise ValueError("Greenfield output must contain all four application modules")
    for name, content in files.items():
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            raise ValueError("Policy: path traversal")
        if not isinstance(content, str) or len(content.encode()) > 100000:
            raise ValueError("Policy: invalid content size")
        ast.parse(content, filename=name)
        for forbidden in ("BEGIN PRIVATE KEY", "sk-ant-", "gsk_", "os.system(", "shell=True", "eval(", "exec("):
            if forbidden in content:
                raise ValueError("Policy: suspicious executable code or secret")
    return True


class Engine:
    def __init__(self, root=".runtime/engineering"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = StateDB(self.root / "state.db")
        graph_valid(GRAPH)

    @contextlib.contextmanager
    def lock(self):
        path = self.root / "coordinator.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError("Coordinator already active; see recovery runbook for stale locks") from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def work(self, state):
        return self.root / state["id"] / "workspace"

    def capture(self, state):
        work = self.work(state)
        result = {}
        for name in sorted(ALLOWED):
            path = work / name
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != self.root.parent):
                raise ValueError("Symlinks are forbidden in managed workspaces")
            if path.exists():
                result[name] = path.read_text(encoding="utf-8")
        return result

    def restore(self, state):
        # Only named managed files inside this run's private workspace are touched.
        self.capture(state)  # Validate paths before writes.
        work = self.work(state)
        for name in ALLOWED:
            path = work / name
            if name in state["baseline"]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(state["baseline"][name], encoding="utf-8")
            else:
                path.unlink(missing_ok=True)

    def create(self, scenario, requirement=None, mode="fixture", parent=None, inject="none"):
        if scenario not in {"greenfield", "brownfield", "ambiguous"} or mode not in {"fixture", "live"}:
            raise ValueError("Invalid scenario or mode")
        if inject not in {"none", "once", "always"} or (mode == "live" and inject != "none"):
            raise ValueError("Fault injection is restricted to fixture mode")
        scenario_data = json.loads((ROOT / "scenarios" / (scenario + ".json")).read_text())
        run_id = uuid.uuid4().hex[:12]
        state = {"id": run_id, "scenario": scenario, "mode": mode, "requirement": requirement or scenario_data["requirement"],
                 "revision": 1, "status": "created", "started": time.time(), "ended": None,
                 "graph": GRAPH, "completed": {}, "approvals": [], "pending": None,
                 "baseline": {}, "repair_count": 0, "retry_count": 0, "rollback_count": 0,
                 "recoveries": [], "failure_started": None, "inject": inject, "parent": parent,
                 "clarification": None, "scenario_contract": scenario_data}
        if not 1 <= len(state["requirement"]) <= 8000:
            raise ValueError("Requirement must contain 1-8000 characters")
        with self.lock():
            self.work(state).mkdir(parents=True)
            if scenario != "greenfield":
                if parent:
                    previous = self.db.load(parent)
                    if previous["status"] != "completed" or previous["mode"] != mode:
                        raise ValueError("Parent must be a completed run in the same mode")
                    if digest(self.capture(previous)) != previous["completed"]["apply"]["workspace_hash"]:
                        raise ValueError("Parent workspace changed since approval")
                    state["baseline"] = self.capture(previous)
                else:
                    state["baseline"] = {n: (ROOT / n).read_text() for n in ALLOWED}
                    state["baseline"]["shortener/policy.py"] = BASE_POLICY
                self.restore(state)
            self.db.save(state, "created", {"mode": mode, "scenario": scenario, "parent": parent,
                                           "baseline_hash": digest(state["baseline"])})
        return state

    def save_artifact(self, state, name, value):
        path = self.root / state["id"] / "artifacts" / f"v{state['revision']}" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")

    def advance(self, run_id):
        with self.lock():
            s = self.db.load(run_id)
            if s["status"] in {"completed", "stopped", "waiting_approval", "waiting_clarification"}:
                return s
            # If a process died mid-node, require explicit recovery rather than replay side effects.
            if s["status"] == "running":
                raise ValueError("Interrupted execution: use recover before resuming")
            s["status"] = "running"
            self.db.save(s, "execution_started", {})
            for _ in range(40):
                ready = [n for n, deps in GRAPH.items() if n not in s["completed"] and all(d in s["completed"] for d in deps)]
                if not ready:
                    break
                if ready == ["requirements"] and s["scenario"] == "ambiguous" and not s["clarification"]:
                    s["status"] = "waiting_clarification"
                    s["questions"] = s["scenario_contract"]["questions"]
                    self.db.save(s, "clarification_required", {"questions": s["questions"]})
                    return s
                if len(ready) == 1 and ready[0].endswith("approval"):
                    node = ready[0]
                    if node == "release_approval" and digest(self.capture(s)) != s["completed"]["apply"]["workspace_hash"]:
                        self.restore(s)
                        s["rollback_count"] += 1
                        s["status"], s["ended"] = "stopped", time.time()
                        self.db.save(s, "safe_stop", {"reason": "Workspace drift after validation"})
                        return s
                    pending = {"stage": node, "revision": s["revision"],
                               "binding": self.binding(s), "rationale": "Human review required before file changes or release"}
                    if not any(a["stage"] == node and a["binding"] == pending["binding"] for a in s["approvals"]):
                        s["pending"], s["status"] = pending, "waiting_approval"
                        self.db.save(s, "approval_requested", pending)
                        return s
                    s["completed"][node] = pending
                    self.db.save(s, "gate_passed", pending)
                    continue
                self.db.save(s, "batch_started", {"nodes": ready, "parallel": len(ready) > 1})
                try:
                    with ThreadPoolExecutor(max_workers=3) as pool:
                        outputs = list(pool.map(lambda n: (n, self.node(s, n)), ready))
                    for node, output in outputs:
                        if not isinstance(output, dict) or not output:
                            raise ValueError("Exit gate: nonempty structured output required")
                        s["completed"][node] = output
                        self.save_artifact(s, node + ".json", output)
                        self.db.save(s, "node_completed", {"node": node, "output_hash": digest(output),
                            "input_hashes": {d: digest(s["completed"][d]) for d in GRAPH[node]}})
                    if "requirements" in ready and s["completed"]["requirements"].get("analysis", {}).get("questions"):
                        s["questions"] = s["completed"]["requirements"]["analysis"]["questions"]
                        s["status"] = "waiting_clarification"
                        self.db.save(s, "clarification_required", {"questions": s["questions"]})
                        return s
                    if "tests" in ready:
                        if not s["completed"]["tests"]["passed"] or not s["completed"]["security"]["passed"]:
                            self.failed_validation(s)
                            if s["status"] == "stopped":
                                return s
                            continue
                        if s["failure_started"]:
                            s["recoveries"].append(time.time() - s["failure_started"])
                            s["failure_started"] = None
                    if "summary" in ready:
                        s["status"], s["ended"] = "completed", time.time()
                        self.db.save(s, "completed", {"release": "review-ready local artifact; not deployed"})
                        return s
                except Exception as exc:
                    self.restore(s)
                    s["rollback_count"] += 1
                    s["status"], s["ended"] = "stopped", time.time()
                    s["stop_reason"] = str(exc)[:500]
                    self.db.save(s, "safe_stop", {"reason": s["stop_reason"], "rollback": True,
                                                  "provider_calls": getattr(exc, "calls", [])})
                    return s
            s["status"], s["ended"] = "stopped", time.time()
            self.db.save(s, "safe_stop", {"reason": "Transition budget exhausted"})
            return s

    def binding(self, s):
        return digest({"revision": s["revision"], "requirement": s["requirement"],
                       "completed": s["completed"], "workspace": self.capture(s)})

    def approve(self, run_id, actor, note, expected_binding, reject=False):
        if not actor.strip() or not note.strip():
            raise ValueError("Named human reviewer and rationale required")
        with self.lock():
            s = self.db.load(run_id)
            if s["status"] != "waiting_approval":
                raise ValueError("No pending approval")
            pending = s["pending"]
            if expected_binding != pending["binding"] or self.binding(s) != expected_binding:
                raise ValueError("Stale approval: revision or workspace changed")
            if pending["stage"] == "release_approval" and digest(self.capture(s)) != s["completed"]["apply"]["workspace_hash"]:
                raise ValueError("Release workspace does not match validated content")
            if reject:
                self.restore(s)
                s["rollback_count"] += 1
                s["status"], s["ended"] = "stopped", time.time()
            else:
                s["approvals"].append(dict(pending, actor=actor, note=note, time=time.time()))
                # Capture the approved gate immediately; its binding precedes this node.
                s["completed"][pending["stage"]] = dict(pending)
                s["status"] = "ready"
            s["pending"] = None
            self.db.save(s, "approval_rejected" if reject else "approval_granted", {"actor": actor, "note": note, **pending})
            return s

    def revise(self, run_id, requirement, actor, clarification=False):
        if not actor.strip() or not 1 <= len(requirement.strip()) <= 8000:
            raise ValueError("Named human and nonempty requirement required")
        with self.lock():
            s = self.db.load(run_id)
            if clarification and s["mode"] == "fixture" and s["scenario"] == "ambiguous" and requirement != s["scenario_contract"]["fixture_answer"]:
                raise ValueError("Fixture replay accepts only its documented clarification; use live mode for other answers")
            old = {"revision": s["revision"], "completed_hash": digest(s["completed"]), "requirement": s["requirement"]}
            self.restore(s)
            s["rollback_count"] += 1
            s["revision"] += 1
            if clarification:
                s["clarification"] = requirement
            else:
                s["requirement"] = requirement
                s["clarification"] = None
            s["completed"], s["approvals"], s["pending"] = {}, [], None
            s["status"], s["ended"], s["repair_count"] = "ready", None, 0
            self.db.save(s, "replanned", {"actor": actor, "supersedes": old,
                                          "invalidated": list(GRAPH), "reason": "Upstream requirement changed"})
            return s

    def recover(self, run_id, actor):
        with self.lock():
            s = self.db.load(run_id)
            if s["status"] != "running" or not actor.strip():
                raise ValueError("Recovery requires interrupted run and named reviewer")
            self.restore(s)
            s["rollback_count"] += 1
            s["revision"] += 1
            s["completed"], s["approvals"], s["pending"], s["status"] = {}, [], None, "ready"
            self.db.save(s, "recovered", {"actor": actor, "action": "Restore baseline; invalidate all approvals"})
            return s

    def failed_validation(self, s):
        s["failure_started"] = s["failure_started"] or time.time()
        s["feedback"] = {n: s["completed"][n] for n in ("tests", "security")}
        self.restore(s)
        s["rollback_count"] += 1
        self.db.save(s, "rolled_back", {"reason": "Quality gate failed", "feedback": s["feedback"]})
        if s["repair_count"] >= 2:
            s["status"], s["ended"] = "stopped", time.time()
            self.db.save(s, "safe_stop", {"reason": "Two repair attempts exhausted"})
            return
        s["repair_count"] += 1
        s["retry_count"] += 1
        s["revision"] += 1
        s["completed"] = {k: v for k, v in s["completed"].items() if k in {"requirements", "architecture", "test_design"}}
        s["approvals"], s["pending"] = [], None
        self.db.save(s, "repair_planned", {"attempt": s["repair_count"], "invalidated": list(GRAPH)[3:]})

    def node(self, s, name):
        completed = s["completed"]
        if name == "requirements":
            data = {"intent": s["requirement"], "clarification": s["clarification"],
                    "acceptance": s["scenario_contract"]["acceptance"],
                    "assumptions": ["Local prototype", "Single trusted reviewer", "No production deployment"],
                    "scope": sorted(ALLOWED if s["scenario"] == "greenfield" else {"shortener/policy.py"})}
            if s["mode"] == "live":
                provider = Provider()
                data["analysis"] = provider.complete("Requirements analyst", {"requirement": s["requirement"],
                    "clarification": s["clarification"], "contract": {"normalized": "string", "questions": [], "risks": []}})
                data["provider_calls"] = provider.calls
                if not isinstance(data["analysis"].get("normalized"), str) or not isinstance(data["analysis"].get("questions"), list):
                    raise ValueError("Requirements output contract failed")
            elif s["requirement"] != s["scenario_contract"]["requirement"] and not s["clarification"]:
                raise ValueError("Fixture supports only bundled scenario requirements; use live mode for custom requirements")
            return data
        if name == "architecture":
            sources = self.capture(s)
            symbols = {}
            for path, code in sources.items():
                symbols[path] = [n.name for n in ast.walk(ast.parse(code)) if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
            result = {"components": ["HTTP adapter", "transactional SQLite store", "expiration policy"],
                    "flow": "HTTP -> auth/input validation -> Store -> policy -> SQLite -> response",
                    "inspected_files": {k: digest(v) for k, v in sources.items()}, "symbols": symbols,
                    "impacted": completed["requirements"]["scope"],
                    "decision": "Use a policy seam for the boundary fix; no schema migration needed",
                    "dependencies": GRAPH, "baseline_hash": digest(s["baseline"]),
                    "tasks": [{"id": n, "depends_on": deps, "exit_gate": "Structured output and policy validation",
                               "role": n, "status": "pending"} for n, deps in GRAPH.items()]}
            if s["mode"] == "live":
                p = Provider()
                result["design"] = p.complete("Architect and dependency planner", {"requirements": completed["requirements"],
                    "source": sources, "controlled_lifecycle": GRAPH,
                    "contract": {"impacted_modules": [], "tasks": [], "decisions": [], "risks": []}})
                if not all(isinstance(result["design"].get(k), list) for k in ("impacted_modules", "tasks", "decisions", "risks")):
                    raise ValueError("Architecture output contract failed")
                result["provider_calls"] = p.calls
            return result
        if name == "test_design":
            source = ('import unittest\nfrom shortener.policy import is_expired\n\n'
                      'class GeneratedAcceptance(unittest.TestCase):\n'
                      '    def test_no_expiry(self):\n        self.assertFalse(is_expired(None, 100))\n'
                      '    def test_past_expiry(self):\n        self.assertTrue(is_expired(99, 100))\n')
            calls = []
            if s["mode"] == "live":
                p = Provider()
                response = p.complete("Independent test engineer", {"requirements": completed["requirements"],
                    "public_interfaces": {n: (ROOT / n).read_text() for n in ALLOWED},
                    "contract": {"source": "Python unittest module; use TemporaryDirectory for any database", "rationale": "string"}})
                source, calls = response.get("source"), p.calls
                if not isinstance(source, str) or len(source) > 50000:
                    raise ValueError("Generated test output contract failed")
            ast.parse(source)
            return {"suite": "tests/test_shortener.py", "protected": True, "generated_source": source, "provider_calls": calls,
                    "acceptance": completed["requirements"]["acceptance"],
                    "additional": "exact expiry boundary" if s["scenario"] != "greenfield" else "baseline API contract",
                    "gate": "Zero failed tests AND static policy checks AND approved content hash"}
        if name == "implementation":
            if s["mode"] == "fixture":
                files = {n: (ROOT / n).read_text() for n in ALLOWED} if s["scenario"] == "greenfield" else {}
                files["shortener/policy.py"] = BASE_POLICY if s["scenario"] == "greenfield" else (ROOT / "shortener/policy.py").read_text()
                calls = []
            else:
                p = Provider()
                reference = {n: (ROOT / n).read_text() for n in ALLOWED} if s["scenario"] == "greenfield" else self.capture(s)
                implementation_context = {
                    "requirements": {k: completed["requirements"].get(k) for k in ("intent", "acceptance", "scope", "analysis")},
                    "architecture": {k: completed["architecture"].get(k) for k in ("impacted", "decision", "tasks")},
                    "test_plan": {k: completed["test_design"].get(k) for k in ("acceptance", "additional", "gate")},
                    "reference_modules": reference, "feedback": s.get("feedback"),
                    "contract": {"files": {"allowed/path.py": "complete Python source"}, "rationale": "string"},
                    "rules": "Preserve public interfaces; emit only allowed modules. Never alter tests. Exact expiration boundary is expired."
                }
                answer = p.complete("Implementation engineer", implementation_context)
                files, calls = answer.get("files"), p.calls
            check_patch(files, s["scenario"])
            before = self.capture(s)
            diffs = {p: "".join(difflib.unified_diff(before.get(p, "").splitlines(True), c.splitlines(True),
                                                    fromfile=p, tofile=p)) for p, c in files.items()}
            return {"files": files, "diffs": diffs, "mode": s["mode"], "provider_calls": calls,
                    "rationale": "Implement approved contract; keep test suite immutable", "patch_hash": digest(files)}
        if name == "apply":
            if digest(self.capture(s)) != digest(s["baseline"]):
                raise ValueError("Workspace drift before apply")
            files = completed["implementation"]["files"]
            check_patch(files, s["scenario"])
            for path, content in files.items():
                dest = self.work(s) / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
            return {"workspace_hash": digest(self.capture(s)), "files": sorted(files)}
        if name == "tests":
            return self.run_tests(s)
        if name == "security":
            issues = []
            try:
                check_patch(completed["implementation"]["files"], s["scenario"])
                if digest(self.capture(s)) != completed["apply"]["workspace_hash"]:
                    issues.append("Workspace drift")
            except ValueError as exc:
                issues.append(str(exc))
            return {"passed": not issues, "issues": issues,
                    "checks": ["allowlisted paths", "Python syntax", "basic dangerous-pattern scan", "approved workspace hash"],
                    "limitation": "Not a comprehensive SAST or malware detector; live code executes only in Docker"}
        if name == "documentation":
            return {"architecture": completed["architecture"], "api_spec": "docs/openapi.json",
                    "setup": "README.md", "test_results": completed["tests"],
                    "change": completed["implementation"]["diffs"], "risks": "docs/SECURITY.md",
                    "release_checklist": {"tests": True, "policy": True, "human_release": "pending"}}
        if name == "summary":
            return {"requirement": completed["requirements"], "plan": GRAPH, "mode": s["mode"],
                    "decisions": completed["architecture"], "validation": completed["tests"],
                    "approvals": s["approvals"], "revision": s["revision"],
                    "artifacts": sorted(completed), "risks": ["Local-only identity", "SQLite write serialization", "No external audit anchor"],
                    "limitations": ["Fixture is deterministic replay, not live inference", "No production deployment"],
                    "outcome": "Review-ready artifact; human owns final quality"}
        raise ValueError("Unknown node")

    def run_tests(self, s):
        # Protected tests copied to a separate directory; implementation scope excludes tests.
        test_dir = self.root / s["id"] / "validation"
        test_dir.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "tests/test_shortener.py", test_dir / "test_shortener.py")
        if s["scenario"] != "greenfield":
            shutil.copyfile(ROOT / "tests/test_boundary.py", test_dir / "test_boundary.py")
        generated = s.get("completed", {}).get("test_design", {}).get("generated_source")
        if generated:
            (test_dir / "test_generated.py").write_text(generated, encoding="utf-8")
        cwd = self.work(s)
        cmd = [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(test_dir), "-v"]
        if s["mode"] == "live":
            if not shutil.which("docker"):
                raise ValueError("Docker required for live-generated code; install Docker and pre-pull SANDBOX_IMAGE")
            container_name = "sdlc-" + s["id"] + "-v" + str(s["revision"])
            cmd = ["docker", "run", "--name", container_name, "--rm", "--network=none", "--read-only", "--cap-drop=ALL",
                   "--security-opt=no-new-privileges", "--pids-limit=64", "--memory=256m", "--cpus=1",
                   "--user=65534:65534", "--tmpfs=/tmp:rw,noexec,nosuid,size=64m", "--env=PYTHONDONTWRITEBYTECODE=1",
                   "--mount", f"type=bind,source={cwd},target=/app,readonly",
                   "--mount", f"type=bind,source={test_dir},target=/validation,readonly", "-w", "/app",
                   os.getenv("SANDBOX_IMAGE", "python:3.12-slim"),
                   "python", "-B", "-m", "unittest", "discover", "-s", "/validation", "-v"]
        else:
            # Only exact bundled trusted code is allowed on the host; never LLM text.
            for name, content in self.capture(s).items():
                if content not in {(ROOT / name).read_text(), BASE_POLICY if name == "shortener/policy.py" else ""}:
                    raise ValueError("Host runner refuses untrusted source")
        # Bound stdout/stderr by spooling; no shell, no credentials inherited.
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
               "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"}}
        import tempfile
        with tempfile.TemporaryFile() as log:
            try:
                result = subprocess.run(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=False)
            finally:
                if s["mode"] == "live":
                    subprocess.run(["docker", "rm", "-f", container_name], env=env, capture_output=True, timeout=15, check=False)
            log.seek(0)
            output = log.read(65536).decode(errors="replace")
        injected = s["inject"] == "always" or (s["inject"] == "once" and s["repair_count"] == 0)
        if injected:
            output += "\nEXPLICIT FAULT INJECTION: synthetic validation failure for recovery demonstration.\n"
        return {"passed": result.returncode == 0 and not injected, "returncode": result.returncode,
                "fault_injected": injected, "log": output, "executor": "docker" if s["mode"] == "live" else "trusted-fixture-host"}

    def metrics(self):
        runs = self.db.all()
        terminal = [r for r in runs if r["status"] in {"completed", "stopped"}]
        recovery = [t for r in runs for t in r["recoveries"]]
        return {"runs": len(runs), "terminal_runs": len(terminal),
                "success_rate": sum(r["status"] == "completed" for r in terminal) / len(terminal) if terminal else None,
                "retry_frequency_per_run": sum(r["retry_count"] for r in runs) / len(runs) if runs else 0,
                "rollback_frequency_per_run": sum(r["rollback_count"] for r in runs) / len(runs) if runs else 0,
                "mttr_seconds": sum(recovery) / len(recovery) if recovery else None,
                "end_to_end_latency_seconds": {r["id"]: r["ended"] - r["started"] for r in terminal},
                "definitions": "Latency and MTTR include human waiting; terminal failures stay in success denominator. MTTR includes recovered incidents only."}

    def export(self, run_id, directory):
        s = self.db.load(run_id)
        dest = Path(directory)
        dest.mkdir(parents=True, exist_ok=True)
        for name, data in {"state.json": s, "events.json": self.db.events(run_id), "metrics.json": self.metrics()}.items():
            (dest / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
        (dest / "graph.mmd").write_text("flowchart TD\n" + "\n".join(
            f"  {dep} --> {node}" for node, deps in GRAPH.items() for dep in deps), encoding="utf-8")
        c = s["completed"]
        lines = ["# Run engineering report", "", f"Run: `{run_id}` | Scenario: {s['scenario']} | Mode: {s['mode']}",
                 f"Status: **{s['status']}** | Revision: {s['revision']}", "", "## Requirement", "", s["requirement"], "",
                 "## Decisions and plan", "", "See graph.mmd and state.json for exact tasks, dependencies, role outputs and hashes.",
                 "Snapshot rollback protects the managed workspace. Change and release approval are separate.", "",
                 "## Changes", "", *[f"- `{p}`" for p in c.get("implementation", {}).get("files", {})], "",
                 "## Validation", "", f"Final validation passed: {c.get('tests', {}).get('passed', 'not reached')}",
                 f"Repair retries: {s['retry_count']}; snapshot restores: {s['rollback_count']}", "",
                 "```text", c.get("tests", {}).get("log", "No final test log; see events.json for earlier failures."), "```", "",
                 "## Approval evidence", ""]
        lines.extend(f"- {a['stage']}: {a['actor']}; revision {a['revision']}; {a['note']}" for a in s["approvals"])
        live_note = ("Live provider calls and Docker validation are recorded in this report."
                 if s["mode"] == "live" else
                 "Live model and Docker results must be verified separately from this fixture replay.")
        lines.extend(["", "## Assumptions, risks and limitations", "",
                      "Local trusted reviewer, no deployment, single coordinator. Fixture output is deterministic replay, not live inference.",
                  "Replay approvals are simulated and labelled. " + live_note,
                      "Hash-linked local audit is not externally immutable. Source rollback does not restore production databases.",
                      "See repository docs/SECURITY.md and docs/TRACEABILITY.md for full limits and acceptance mapping."])
        (dest / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"directory": str(dest.resolve()), "audit_valid": self.db.verify(run_id)}
