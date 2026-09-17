import os
from pathlib import Path


def load_env(path=".env"):
    """Minimal KEY=value loader; no shell expansion or executable syntax."""
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('\"').strip("'"))
