import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANNED = re.compile(
    r"Path\(r?['\"](C:[\\\\/]|[A-Za-z]:[\\\\/])"   # any drive-letter absolute path
    r"|antigravity"                                  # IDE session cache
    r"|\.gemini[\\\\/]",
    re.IGNORECASE,
)

# Pruned during the walk itself (never enumerated) — large dirs that can never
# contain project source: model/UI code, the vectorcraft submodule, caches.
PRUNE_DIRS = {"ComfyUI", "tools", "node_modules", "__pycache__", ".git", ".venv", ".pytest_cache"}


def _py_files():
    self_file = os.path.abspath(__file__)
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for f in filenames:
            p = os.path.join(dirpath, f)
            if f.endswith(".py") and p != self_file:
                yield p


def test_no_hardcoded_absolute_or_agent_paths():
    offenders = []
    for i_path in _py_files():
        rel = os.path.relpath(i_path, PROJECT_ROOT)
        with open(i_path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        for i, line in enumerate(src.splitlines(), 1):
            if BANNED.search(line):
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, "Hardcoded absolute/agent paths found:\n" + "\n".join(offenders)
