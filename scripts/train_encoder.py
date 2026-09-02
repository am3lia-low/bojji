"""Fine-tune MiniLM-L6 on the generated corpus.

BUILD-TIME ONLY. Runs on CPU in a few minutes; no GPU and no API key required.

The same work the training notebook does, as a script. Both exist on purpose: the
notebook is where the dataset is interrogated and the decisions are visible, and
this is what a Makefile target or a clean-machine rebuild calls. The architecture
comes from ``triage.models.head`` in both cases, so they cannot drift into training
a different model from the one the runtime loads.

**No result is produced here.** Accuracy against the calibration split is printed as
a convergence signal only. Every reported number comes from ``eval/run_eval.py`` on
the held-out test split, so a figure in the writeup can always be traced to a
committed file rather than to a training log.

Usage:
    python scripts/train_encoder.py
    python scripts/train_encoder.py --epochs 6 --batch-size 16
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

EMAILS: Final[Path] = ROOT / "data" / "generated" / "emails.jsonl"
SPLITS: Final[Path] = ROOT / "data" / "splits" / "splits.json"
BASE_DIR: Final[Path] = ROOT / "models" / "all-MiniLM-L6-v2"
OUT_DIR: Final[Path] = ROOT / "models" / "classifier"

SEED: Final[int] = 42
MAX_LENGTH: Final[int] = 256


def load_data() -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not EMAILS.exists():
        raise SystemExit(f"{EMAILS.relative_to(ROOT)} not found.\n"
                         "Run: python scripts/generate_emails.py")
    if not SPLITS.exists():
        raise SystemExit(f"{SPLITS.relative_to(ROOT)} not found.\n"
                         "Run: python scripts/make_splits.py")
    rows = [json.loads(line) for line in EMAILS.read_text(encoding="utf-8").splitlines()]
    assignment = json.loads(SPLITS.read_text(encoding="utf-8"))["assignment"]
    return rows, assignment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoTokenizer

    from triage.models.head import MiniLMClassifier

    rows, assignment = load_data()
    labels = sorted({str(r["label"]) for r in rows})
    label_to_index = {label: i for i, label in enumerate(labels)}

    def subset(name: str) -> list[dict[str, Any]]:
        return [r for r in rows if assignment.get(str(r["id"])) == name]

    train_rows, calib_rows = subset("train"), subset("calibration")
    print(f"{len(rows)} emails | train {len(train_rows)} | "
          f"calibration {len(calib_rows)} | test {len(subset('test'))}")
    print(f"{len(labels)} classes")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(BASE_DIR, local_files_only=True)

    def collate(batch: list[dict[str, Any]]) -> tuple[dict[str, Any], Any]:
        texts = [f"{r.get('subject', '')}\n\n{r['body']}".strip() for r in batch]
        encoded = tokenizer(texts, padding=True, truncation=True,
                            max_length=MAX_LENGTH, return_tensors="pt")
        targets = torch.tensor([label_to_index[str(r["label"])] for r in batch])
        return encoded, targets

    train_loader = DataLoader(train_rows, batch_size=args.batch_size,  # type: ignore[arg-type]
                              shuffle=True, collate_fn=collate)
    calib_loader = DataLoader(calib_rows, batch_size=64,  # type: ignore[arg-type]
                              collate_fn=collate)

    torch.manual_seed(SEED)
    model = MiniLMClassifier(BASE_DIR, len(labels)).to(device)
    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimiser, max_lr=args.lr, total_steps=args.epochs * len(train_loader),
        pct_start=0.1,
    )
    loss_fn = torch.nn.CrossEntropyLoss()

    print(f"\ndevice {device} | {sum(p.numel() for p in model.parameters()):,} parameters")
    history: list[dict[str, float]] = []
    started = time.time()

    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for encoded, targets in train_loader:
            encoded = {k: v.to(device) for k, v in encoded.items()}
            targets = targets.to(device)
            optimiser.zero_grad()
            loss = loss_fn(model(**encoded), targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
            scheduler.step()
            total += float(loss.item())

        model.eval()
        correct = seen = 0
        with torch.no_grad():
            for encoded, targets in calib_loader:
                encoded = {k: v.to(device) for k, v in encoded.items()}
                correct += int((model(**encoded).argmax(1).cpu() == targets).sum())
                seen += len(targets)

        entry = {"epoch": epoch + 1,
                 "train_loss": total / max(len(train_loader), 1),
                 "calibration_accuracy": correct / max(seen, 1)}
        history.append(entry)
        print(f"  epoch {entry['epoch']}  loss {entry['train_loss']:.4f}  "
              f"calib acc {entry['calibration_accuracy']:.4f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), OUT_DIR / "model.pt")
    tokenizer.save_pretrained(OUT_DIR)
    (OUT_DIR / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    (OUT_DIR / "training.json").write_text(json.dumps({
        "base_model": "sentence-transformers/all-MiniLM-L6-v2",
        "seed": SEED,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.lr,
        "max_length": MAX_LENGTH,
        "n_train": len(train_rows),
        "n_calibration": len(calib_rows),
        "elapsed_seconds": round(time.time() - started, 1),
        "history": history,
        "note": ("calibration_accuracy is a convergence signal, not a result. "
                 "Reported numbers come from eval/run_eval.py on the test split."),
    }, indent=2), encoding="utf-8")

    size_mb = sum(f.stat().st_size for f in OUT_DIR.rglob("*") if f.is_file()) / 1024**2
    print(f"\nsaved -> {OUT_DIR.relative_to(ROOT)}  ({size_mb:.1f}MB)")
    if size_mb > 95:
        print("WARNING: approaching GitHub's 100MB limit; git-lfs would be needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
