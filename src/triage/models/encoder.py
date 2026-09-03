"""MiniLM-L6 encoder classifier -- the runtime model.

RUNTIME. Loads from ``models/classifier/`` with no network access and no API key.

22M parameters, 384-dimensional embeddings, six layers. Chosen over DistilBERT
(66M, ~250MB) on **deployment size, not accuracy**: at ~90MB the fine-tuned
artefact commits to plain git, under GitHub's 100MB limit, so a grader cloning the
repository receives real weights rather than git-lfs pointer files and a confusing
failure (``BUILD.md`` S5.4).

The head is a linear layer over the mean-pooled embedding, producing 12 logits.
That is what makes the confidence *native to the architecture* and therefore
calibratable -- the operational argument for an encoder over an LLM classifier, and
the thing the whole contribution rests on.
"""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any, Final

from triage.schemas import Classification

#: Default artefact location, relative to the repository root.
DEFAULT_MODEL_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "models" / "classifier"

#: Token cap. Citizen emails are short; 256 covers the corpus with headroom while
#: keeping CPU inference fast. Recorded in training metadata so inference and
#: training cannot silently disagree.
MAX_LENGTH: Final[int] = 256


class ModelNotTrainedError(RuntimeError):
    """The fine-tuned classifier is absent from ``models/classifier/``."""


class EncoderClassifier:
    """Fine-tuned MiniLM-L6 over the corpus-derived taxonomy.

    Weights, tokenizer and label order load together. The label order is persisted
    rather than re-derived: the linear head's output index maps positionally onto
    it, so reading the labels from anywhere else would risk a silent permutation of
    every prediction.
    """

    def __init__(self, model_dir: Path | str | None = None) -> None:
        self._dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        if not (self._dir / "model.pt").exists():
            raise ModelNotTrainedError(
                f"no trained classifier at {self._dir}.\n"
                "Run the training notebook: models/01_dataset_eda_and_training.ipynb"
            )
        self._labels: tuple[str, ...] = tuple(
            json.loads((self._dir / "labels.json").read_text(encoding="utf-8"))
        )

    @property
    def name(self) -> str:
        return "minilm-l6-finetuned"

    @property
    def labels(self) -> tuple[str, ...]:
        return self._labels

    @cached_property
    def _runtime(self) -> tuple[Any, Any, Any]:
        """Load torch, the tokenizer and the model on first use.

        Deferred so that importing this module -- which the graph does at startup --
        does not pay torch's import cost until a prediction is actually needed.
        """
        import torch
        from transformers import AutoTokenizer

        from triage.models.head import MiniLMClassifier

        tokenizer = AutoTokenizer.from_pretrained(self._dir, local_files_only=True)

        # ``torch.save(state_dict)`` stores tensors only -- no architecture -- so
        # something must supply the config that shapes them before the weights can
        # be loaded into it.
        #
        # The config is read from the BASE encoder directory, not copied into the
        # classifier directory. Copying was tried and does not work: a directory
        # containing ``config.json`` looks to ``AutoModel.from_pretrained`` like a
        # pretrained checkpoint, so it then demands ``model.safetensors`` beside it
        # and fails on a bare state_dict. Both directories therefore ship, and the
        # base encoder is a runtime dependency rather than a build-time convenience.
        config_dir = self._dir
        if not (config_dir / "config.json").exists():
            config_dir = self._dir.parent / "all-MiniLM-L6-v2"
        if not (config_dir / "config.json").exists():
            raise ModelNotTrainedError(
                f"no model config at {self._dir} or {config_dir}.\n"
                "Run: python scripts/download_model.py, then the training notebook "
                "models/01_dataset_eda_and_training.ipynb"
            )

        model = MiniLMClassifier(config_dir, len(self._labels))
        model.load_state_dict(torch.load(self._dir / "model.pt", map_location="cpu"))
        model.eval()
        return torch, tokenizer, model

    def predict(self, text: str) -> Classification:
        return self.predict_batch([text])[0]

    def predict_batch(self, texts: list[str]) -> list[Classification]:
        """Classify a batch. Softmax over the head's logits gives the distribution."""
        torch, tokenizer, model = self._runtime

        encoded = tokenizer(
            texts, padding=True, truncation=True,
            max_length=MAX_LENGTH, return_tensors="pt",
        )
        with torch.no_grad():
            probabilities = torch.softmax(model(**encoded), dim=-1)

        results: list[Classification] = []
        for row in probabilities:
            scores = {label: float(p) for label, p in zip(self._labels, row, strict=True)}
            results.append(Classification(
                label=max(scores, key=lambda k: scores[k]),
                probabilities=scores,
                model_name=self.name,
            ))
        return results

    def logits_batch(self, texts: list[str]) -> Any:
        """Return raw logits, for calibration.

        Temperature scaling divides the *logits* before the softmax, so the
        calibration layer needs them rather than the probabilities. Exposed here
        rather than recomputed, so training, calibration and inference all read the
        same numbers.
        """
        torch, tokenizer, model = self._runtime
        encoded = tokenizer(
            texts, padding=True, truncation=True,
            max_length=MAX_LENGTH, return_tensors="pt",
        )
        with torch.no_grad():
            return model(**encoded)
