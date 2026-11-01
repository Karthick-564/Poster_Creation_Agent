import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BANNED = re.compile(
    r"Path\(r?['\"](C:[\\\\/]|[A-Za-z]:[\\\\/])"   # any drive-letter absolute path
    r"|antigravity"                                  # IDE session cache
    r"|\.gemini[\\\\/]",
    re.IGNORECASE,
)


def test_no_hardcoded_absolute_or_agent_paths():
    offenders = []
    current_file = Path(__file__).resolve()
    for py in PROJECT_ROOT.rglob("*.py"):
        if py.resolve() == current_file or "__pycache__" in py.parts or "ComfyUI" in py.parts or "tools" in py.parts:
            continue
        src = py.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(src.splitlines(), 1):
            if BANNED.search(line):
                offenders.append(f"{py.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
    assert not offenders, "Hardcoded absolute/agent paths found:\n" + "\n".join(offenders)
