.PHONY: corpus check test lint

## Regenerate the SOP corpus and the taxonomy projection derived from it.
## Order matters: the taxonomy is derived FROM the corpus, never the reverse.
corpus:
	python scripts/generate_sops.py
	python scripts/derive_taxonomy.py

## Validate without writing: citations resolve, no relief-cap leak, holdouts
## stay empty, and config/taxonomy.yaml is not stale.
check:
	python scripts/generate_sops.py --check
	python scripts/derive_taxonomy.py --check

test:
	python -m pytest tests/ -q

lint:
	python -m ruff check src scripts tests
