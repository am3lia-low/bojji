"""Tests for the shipped classifier artefact's contracts.

The weights, the label order and the taxonomy are three files that must agree, and
two of the three ways they can disagree are SILENT:

* a label list of the wrong LENGTH is caught by ``load_state_dict``, which refuses
  to load a 12-wide head into an 11-wide one;
* a label list of the right length in the wrong ORDER is not caught by anything.
  The linear head's output index maps positionally onto ``labels.json``, so a
  reordering permutes every prediction while the model loads cleanly, scores
  plausibly, and is wrong on every email;
* a label list naming a class the taxonomy does not define routes through
  ``bucket_of.get(label, NO_SUPPORTING_SOP)`` and escalates everything in that
  class, which looks like a weak class rather than a broken contract.

These are asserted against the artefact on disk rather than against the training
script, because the artefact is what the runtime loads and what a grader receives.

``ARCHITECTURE_AUDIT`` section 7 rules label misalignment out as the cause of the
one class scoring F1 0.000. That conclusion rested on reading the files; these
tests make it a property that stays checked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "classifier"
LABELS_PATH = MODEL_DIR / "labels.json"
TAXONOMY_PATH = ROOT / "config" / "taxonomy.yaml"

pytestmark = pytest.mark.skipif(
    not LABELS_PATH.exists(),
    reason="no trained classifier on disk; run scripts/train_encoder.py",
)


@pytest.fixture(scope="module")
def labels() -> list[str]:
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def taxonomy_classes() -> list[str]:
    doc = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    return sorted(doc["classes"])


def test_labels_are_sorted(labels: list[str]) -> None:
    """The head's output index maps positionally onto this list.

    The training notebook derives it with ``sorted(...)``, so anything else on disk
    means the artefact was not produced by the committed training path -- and a
    reordering is silent: every prediction is permuted, nothing raises.
    """
    assert labels == sorted(labels)


def test_labels_match_the_taxonomy(labels: list[str], taxonomy_classes: list[str]) -> None:
    """The classifier's label set is exactly the taxonomy's class set.

    A label the taxonomy does not define falls through ``bucket_of.get(...)`` to
    ``no_supporting_sop``, so every email the model puts in that class escalates as
    unanswerable. That presents as a weak class or as depressed coverage, not as an
    error -- which is why it is asserted here rather than left to be noticed.

    This test is EXPECTED to fail between a taxonomy change and the retrain that
    follows it. That window is exactly when the failure is worth seeing: the shipped
    weights predict a class set the corpus no longer maps, and every number produced
    in the meantime is measured against a stale label space.
    """
    stale = sorted(set(labels) - set(taxonomy_classes))
    missing = sorted(set(taxonomy_classes) - set(labels))
    assert labels == taxonomy_classes, (
        f"the shipped classifier predicts {len(labels)} classes but the taxonomy "
        f"declares {len(taxonomy_classes)}.\n"
        f"  predicted but no longer in the taxonomy: {stale or '-'}\n"
        f"  in the taxonomy but never predicted:     {missing or '-'}\n"
        "Retrain so labels.json matches config/taxonomy.yaml, or regenerate the "
        "taxonomy if the SOP corpus is what changed."
    )


def test_label_count_matches_the_head_width(labels: list[str]) -> None:
    """The saved head emits exactly one logit per label.

    ``torch.save(state_dict)`` stores tensors without architecture, so this is the
    only place the two can be compared before a prediction is made.
    """
    torch = pytest.importorskip("torch")
    state = torch.load(MODEL_DIR / "model.pt", map_location="cpu")
    assert state["head.weight"].shape[0] == len(labels)
    assert state["head.bias"].shape[0] == len(labels)


def test_training_metadata_records_the_inference_token_cap() -> None:
    """``MAX_LENGTH`` is declared independently in the encoder and the trainer.

    They agree today at 256, and the corpus has wide headroom (p95 ~107 tokens),
    so truncation is not currently a live concern. The value is nonetheless
    recorded in ``training.json`` precisely so a future change on one side is
    detectable rather than silent.
    """
    metadata_path = MODEL_DIR / "training.json"
    if not metadata_path.exists():
        pytest.skip("no training.json; run scripts/train_encoder.py")

    from triage.models.encoder import MAX_LENGTH

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["max_length"] == MAX_LENGTH
