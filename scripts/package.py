"""Create and inspect a clean submission archive; no credentials/runtime data."""
import hashlib
import json
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    output = root.parent / "agentic-sdlc-submission.zip"
    excluded = {".git", ".venv", "__pycache__", ".runtime", "dist"}
    files = [p for p in root.rglob("*") if p.is_file() and not any(x in excluded for x in p.relative_to(root).parts)
             and p.name != ".env" and p.suffix not in {".pyc", ".db"}]
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            if path.is_symlink():
                raise ValueError("Symlink in submission")
            archive.write(path, "agentic-sdlc/" + path.relative_to(root).as_posix())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
        required = {"agentic-sdlc/README.md", "agentic-sdlc/.env.example", "agentic-sdlc/docs/openapi.json",
                    "agentic-sdlc/evidence/verification.json", "agentic-sdlc/.github/workflows/ci.yml"}
        if not required <= set(archive.namelist()):
            raise ValueError("Missing deliverable")
    print(json.dumps({"archive": str(output), "files": len(files), "bytes": output.stat().st_size,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
