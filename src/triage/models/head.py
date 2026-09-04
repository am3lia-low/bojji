"""The classifier architecture: mean-pooled MiniLM plus a linear head.

RUNTIME, but imported by training too. Defined here once rather than inline in the
notebook, because training and inference must instantiate *identical* architecture:
a mismatch would load the saved weights into a differently-shaped model and produce
predictions that are wrong without erroring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import torch
from torch import nn
from transformers import AutoModel


class MiniLMClassifier(nn.Module):
    """MiniLM-L6 with a linear classification head over the pooled embedding.

    **Mean pooling, not the CLS token.** MiniLM was trained as a sentence encoder
    with mean pooling, so its CLS position never learned to be a sentence
    representation. Using CLS here would discard most of what the pretrained model
    knows and force the head to relearn it from 900 training examples.

    The head is a single linear layer: 384 dimensions to 12 logits. Softmax over
    those logits is the distribution the router calibrates, which is the point of
    choosing an encoder at all.
    """

    def __init__(self, base_dir: Path | str, n_labels: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.encoder = AutoModel.from_pretrained(base_dir, local_files_only=True)
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(self.encoder.config.hidden_size, n_labels)

    def forward(self, **encoded: Any) -> torch.Tensor:
        """Return raw logits. Softmax is applied by the caller.

        Logits rather than probabilities because temperature scaling divides the
        logits before the softmax; returning probabilities here would force
        calibration to invert them.
        """
        hidden = self.encoder(**encoded).last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).float()
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return cast(torch.Tensor, self.head(self.dropout(pooled)))
