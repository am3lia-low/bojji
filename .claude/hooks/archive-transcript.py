"""Stop hook: copy this session's transcript into the user's archive folder.

Claude Code hands the hook a JSON payload on stdin; `transcript_path` points at
the live .jsonl. We copy rather than move so --resume keeps working.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ARCHIVE_ROOT = Path.home() / "Documents" / "AI assistant logs"

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    src = payload.get("transcript_path")
    if not src:
        return 0
    src = Path(src)
    if not src.is_file():
        return 0

    project = Path(payload.get("cwd") or Path.cwd()).name
    dest_dir = ARCHIVE_ROOT / project
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Date prefix keeps sessions sorted; the session id keeps the name stable
    # across repeated Stop events, so each session archives to one file.
    stamp = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d")
    dest = dest_dir / f"{stamp}_{src.stem}.jsonl"
    shutil.copy2(src, dest)
    return 0

if __name__ == "__main__":
    sys.exit(main())
