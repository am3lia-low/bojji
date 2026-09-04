"""Export this repository's Codex and Claude Code sessions as safe JSONL copies.

The assessment asks for coding-agent session and chat logs. This script selects
only sessions associated with the current repository, preserves one JSON object
per line, applies deterministic redactions, and writes an audit manifest.

Run from the repository root:

    python scripts/import_agent_logs.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "AI assistant logs"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _claude_project_slug(path: Path) -> str:
    """Return Claude Code's Windows folder name for a project path."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(path))


def _first_record(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        first = stream.readline()
    try:
        value = json.loads(first)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: first line is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: first line is not a JSON object")
    return value


def _codex_sources() -> list[Path]:
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"
    if not root.exists():
        return []

    wanted = os.path.normcase(str(ROOT.resolve()))
    matches: list[Path] = []
    for path in root.rglob("*.jsonl"):
        record = _first_record(path)
        payload = record.get("payload") or {}
        cwd = payload.get("cwd") if isinstance(payload, dict) else None
        if isinstance(cwd, str) and os.path.normcase(str(Path(cwd).resolve())) == wanted:
            matches.append(path)
    return sorted(matches)


def _claude_sources() -> list[Path]:
    root = Path.home() / ".claude" / "projects" / _claude_project_slug(ROOT)
    return sorted(root.rglob("*.jsonl")) if root.exists() else []


def _redaction_rules() -> list[tuple[str, re.Pattern[str], str]]:
    home = str(Path.home())
    repo = str(ROOT)
    # These project-specific private terms are encoded so the importer does not
    # reintroduce them into the anonymized repository it is meant to protect.
    private_terms = {
        "reviewer_account": bytes.fromhex("676f7673672d64732d686972696e67").decode(),
        "candidate_name": bytes.fromhex("416d656c6961204c6f77").decode(),
        "candidate_first_name": bytes.fromhex("416d656c6961").decode(),
        "candidate_alias": bytes.fromhex("3c555345523e61204c6f77").decode(),
        "organisation_short": bytes.fromhex("476f7654656368").decode(),
        "organisation_long": bytes.fromhex(
            "476f7665726e6d656e7420546563686e6f6c6f6779204167656e6379"
        ).decode(),
        "role": bytes.fromhex("4461746120536369656e74697374").decode(),
        "assessment_filename": bytes.fromhex(
            "4461746120536369656e6365202d2054616b6520486f6d6520546573742028414920547261636b292e706466"
        ).decode(),
        "scratchpad_name": bytes.fromhex("726566206d6174657269616c").decode(),
    }
    git_accounts: set[str] = set()
    remote = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    ).stdout.strip()
    remote_match = re.search(r"github\.com[/:]([^/]+)", remote, re.IGNORECASE)
    if remote_match:
        git_accounts.add(remote_match.group(1))

    rules = [
        (
            "candidate_name",
            re.compile(
                "|".join(
                    re.escape(private_terms[name])
                    for name in (
                        "candidate_name",
                        "candidate_first_name",
                        "candidate_alias",
                    )
                ),
                re.IGNORECASE,
            ),
            "<CANDIDATE>",
        ),
        (
            "repository_path",
            re.compile(re.escape(repo), re.IGNORECASE),
            "<REPOSITORY>",
        ),
        (
            "home_path",
            re.compile(re.escape(home), re.IGNORECASE),
            "<USER_HOME>",
        ),
        (
            "github_account",
            re.compile(r"https://github\.com/[^/\\\"\s]+/", re.IGNORECASE),
            "https://github.com/<USER>/",
        ),
        (
            "email_address",
            re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            "<EMAIL_REDACTED>",
        ),
        (
            "api_key",
            re.compile(
                r"(?i)(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9_-]{16,}|"
                r"AIza[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9_-]{16,}|"
                r"github_pat_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})"
            ),
            "<SECRET_REDACTED>",
        ),
        (
            "bearer_token",
            re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]{16,}"),
            "Bearer <SECRET_REDACTED>",
        ),
        (
            "environment_secret",
            re.compile(
                r"(?i)((?:GEMINI_API_KEY(?:_[23])?|GROQ_API_KEY|OPENAI_API_KEY)"
                r"\s*=\s*)[^\s\"\\]+"
            ),
            r"\1<SECRET_REDACTED>",
        ),
        (
            "reviewer_account",
            re.compile(re.escape(private_terms["reviewer_account"]), re.IGNORECASE),
            "<REVIEWER_ACCOUNT>",
        ),
        (
            "organisation",
            re.compile(
                "|".join(
                    re.escape(private_terms[name])
                    for name in ("organisation_short", "organisation_long")
                ),
                re.IGNORECASE,
            ),
            "<ORGANISATION>",
        ),
        (
            "role",
            re.compile(re.escape(private_terms["role"]), re.IGNORECASE),
            "<ROLE>",
        ),
        (
            "assessment_filename",
            re.compile(re.escape(private_terms["assessment_filename"]), re.IGNORECASE),
            "<ASSESSMENT_BRIEF>.pdf",
        ),
        (
            "scratchpad_name",
            re.compile(re.escape(private_terms["scratchpad_name"]), re.IGNORECASE),
            "<SCRATCHPAD>",
        ),
        (
            "local_username",
            re.compile(rf"\b{re.escape(Path.home().name)}\b", re.IGNORECASE),
            "<USER>",
        ),
    ]
    rules.extend(
        (
            "git_account",
            re.compile(re.escape(account), re.IGNORECASE),
            "<GIT_ACCOUNT>",
        )
        for account in sorted(git_accounts)
    )
    return rules


def _redact_value(
    value: Any,
    rules: list[tuple[str, re.Pattern[str], str]],
    counts: Counter[str],
) -> Any:
    if isinstance(value, str):
        for name, pattern, replacement in rules:
            value, count = pattern.subn(replacement, value)
            counts[name] += count
        return value
    if isinstance(value, list):
        return [_redact_value(item, rules, counts) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            clean_key = _redact_value(key, rules, counts)
            if clean_key in redacted and clean_key != key:
                raise ValueError(f"redaction makes two JSON keys identical: {clean_key!r}")
            redacted[clean_key] = _redact_value(item, rules, counts)
        return redacted
    return value


def _sanitise(lines: Iterable[str]) -> tuple[list[str], Counter[str]]:
    output: list[str] = []
    counts: Counter[str] = Counter()
    rules = _redaction_rules()

    for line_number, original in enumerate(lines, 1):
        line = original.rstrip("\r\n")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"source line {line_number} is not valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError(f"line {line_number} is not a JSON object")
        value = _redact_value(value, rules, counts)
        output.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    return output, counts


def _export(provider: str, sources: list[Path]) -> list[dict[str, Any]]:
    destination = OUTPUT_ROOT / provider
    destination.mkdir(parents=True, exist_ok=True)

    expected_names = {path.name for path in sources}
    for stale in destination.glob("*.jsonl"):
        if stale.name not in expected_names:
            stale.unlink()

    manifest: list[dict[str, Any]] = []
    for source in sources:
        source_bytes = source.read_bytes()
        text = source_bytes.decode("utf-8")
        output, counts = _sanitise(text.splitlines(keepends=True))
        output_bytes = "".join(output).encode("utf-8")
        target = destination / source.name
        target.write_bytes(output_bytes)

        first = _first_record(source)
        payload = first.get("payload") or {}
        session_id = (
            payload.get("session_id") or payload.get("id")
            if isinstance(payload, dict)
            else None
        )
        session_id = session_id or first.get("sessionId") or source.stem
        manifest.append(
            {
                "file": f"{provider}/{target.name}",
                "session_id": session_id,
                "records": len(output),
                "source_bytes": len(source_bytes),
                "export_bytes": len(output_bytes),
                "source_sha256": _sha256(source_bytes),
                "export_sha256": _sha256(output_bytes),
                "redactions": dict(sorted(counts.items())),
            }
        )
    return manifest


def main() -> int:
    codex = _codex_sources()
    claude = _claude_sources()
    if not codex and not claude:
        raise SystemExit("No project-specific Codex or Claude Code sessions found.")

    OUTPUT_ROOT.mkdir(exist_ok=True)
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "Sessions associated with this repository only",
        "format": "Sanitised JSONL; record order and JSON structure are preserved",
        "providers": {
            "codex": _export("codex", codex),
            "claude": _export("claude", claude),
        },
    }
    target = OUTPUT_ROOT / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Codex sessions: {len(codex)}")
    print(f"Claude sessions: {len(claude)}")
    print(f"Manifest: {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
