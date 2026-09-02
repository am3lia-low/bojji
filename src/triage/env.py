"""Load ``.env`` into the process environment.

RUNTIME and EVAL-TIME.

``.env.example`` tells a grader to copy the file and fill in their keys, and every
client reads its key from :data:`os.environ`. Without something bridging the two,
a correctly-populated ``.env`` has no effect and the system behaves exactly as it
would with no key at all -- drafting fails on every item, the judge is skipped, and
the failure looks like a missing key rather than a missing loader. That silence is
the reason this module exists rather than being folded into each client.

**Existing environment variables always win.** A value already exported is a
deliberate act -- CI, a container, a one-off override on the command line -- and a
file on disk must not overwrite it. So this fills gaps rather than assigning.

**Never raises.** A missing ``.env`` is normal: keys may come from the real
environment, and the runtime is designed to degrade honestly when a key is absent
(a failed draft escalates carrying its SOP). Turning a missing file into a crash
would take a working degraded path and break it.

No dependency on ``python-dotenv``: the format needed here is a few lines of
``KEY=value``, and parsing it directly keeps one less package in a runtime that has
to install cleanly on a grader's machine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

#: Repository root, from this file.
DEFAULT_ENV: Final[Path] = Path(__file__).resolve().parents[2] / ".env"


def load_env(path: Path | None = None, *, override: bool = False) -> dict[str, str]:
    """Read ``KEY=value`` lines into ``os.environ``.

    Args:
        path: The file to read. Defaults to ``.env`` at the repository root.
        override: When True, replace variables already set. Off by default, so an
            exported value beats the file.

    Returns:
        The names that were actually set, mapped to their source. Names only --
        a secret must not be returned to a caller that might log it.
    """
    source = path or DEFAULT_ENV
    if not source.exists():
        return {}

    applied: dict[str, str] = {}
    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue

        if override or not os.environ.get(key):
            os.environ[key] = value
            applied[key] = str(source)

    return applied


def key_status() -> dict[str, bool]:
    """Which keys are present, without revealing any of them.

    Printed by entrypoints so a run states up front what it can and cannot do --
    an eval that silently skipped the judge is worse than one that said so.
    """
    return {
        name: bool(os.environ.get(name))
        for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY")
    }


__all__ = ["DEFAULT_ENV", "key_status", "load_env"]
