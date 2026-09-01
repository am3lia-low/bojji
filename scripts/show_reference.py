"""Print readable text from a fetched `.scratch/` page, for the fact-review pass.

BUILD-TIME ONLY. A reading aid, not part of the pipeline: it lets a human (or the
author) check that a fact written into `data/sop_specs/*.yaml` actually appears on
the cited page. Nothing it prints is committed.

Usage:
    python scripts/show_reference.py giro_iit
    python scripts/show_reference.py giro_iit --grep "deduction" --window 200
    python scripts/show_reference.py qcr --from "Qualifying Child Relief" --chars 2000
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_reference import PAGES, SCRATCH, to_text  # noqa: E402

# The IRAS pages carry ~1,500 words of global nav before the article body.
# Content reliably starts after the breadcrumb trail ending in "Home".
_NAV_END = re.compile(r"\bHome\b\s+(?:Quick Links|Taxes|Individual Income Tax|News)")


def body_text(handle: str, *, strip_nav: bool = True) -> str:
    path = SCRATCH / f"{handle}.html"
    if not path.exists():
        raise SystemExit(f"not fetched: {path}\n  run: python scripts/fetch_reference.py {handle}")
    text = to_text(path.read_text(encoding="utf-8", errors="replace"))
    if strip_nav:
        match = _NAV_END.search(text)
        if match:
            text = text[match.start():]
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handle", help="page handle from the fetch registry")
    parser.add_argument("--grep", help="show windows around this pattern instead of the head")
    parser.add_argument("--window", type=int, default=300, help="chars either side of a --grep hit")
    parser.add_argument("--from", dest="start", help="begin output at the first match of this text")
    parser.add_argument("--chars", type=int, default=3000, help="how many chars to print")
    parser.add_argument("--raw", action="store_true", help="do not strip the site navigation")
    args = parser.parse_args()

    if args.handle not in PAGES:
        raise SystemExit(
            f"unknown handle: {args.handle}\n"
            "  see: python scripts/fetch_reference.py --list"
        )

    text = body_text(args.handle, strip_nav=not args.raw)
    print(f"# {args.handle}\n# {PAGES[args.handle]}\n")

    if args.grep:
        hits = list(re.finditer(args.grep, text, re.I))
        if not hits:
            print(f"(no match for {args.grep!r})")
            return 1
        for i, hit in enumerate(hits[:12], 1):
            lo = max(0, hit.start() - args.window)
            hi = min(len(text), hit.end() + args.window)
            print(f"--- hit {i}/{len(hits)} @ {hit.start()} ---\n...{text[lo:hi]}...\n")
        return 0

    if args.start:
        idx = text.lower().find(args.start.lower())
        if idx < 0:
            print(f"(no match for {args.start!r}; showing head)")
        else:
            text = text[idx:]

    print(text[: args.chars])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
