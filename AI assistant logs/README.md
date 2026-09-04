# Coding-agent session logs

This directory contains the project-specific coding-agent records requested by the
assessment.

- `claude/` contains sanitized Claude Code session exports in JSONL format.
- `codex/` contains sanitized Codex session exports in JSONL format.
- `manifest.json` records session IDs, record counts, hashes, and redaction counts.
- `brainstorm_log.txt` is the earlier consolidated development log.

## Sanitization

The exports retain JSONL record order and object structure. Deterministic redactions
replace credentials, email addresses, personal paths and account names, and references
that would identify the assessment organization or role. The manifest stores hashes
for both the local source and sanitized export so that the transformation is auditable.

## Refresh before submission

Finish active agent sessions, then run:

```bash
python scripts/import_agent_logs.py
```

The importer selects Codex sessions whose recorded working directory is this repository
and Claude Code sessions from this repository's project-history directory. It does not
copy sessions from unrelated projects.
