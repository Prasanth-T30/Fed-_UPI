"""Train FedUPI from an explicitly supplied labelled dataset.

Examples:
    python scripts/train.py --data path/to/transactions.csv
    python scripts/train.py --data path/to/transactions.xlsx --quick
    python scripts/train.py --dataset paysim  # requires data/raw/paysim.zip
    python scripts/train.py --use my_dataset  # activate an existing artifact set
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch  # noqa: E402

from app.config import ARTIFACT_DIR, DATA_DIR, META_PATH, MODEL_PATH, REPORT_PATH  # noqa: E402
from app.data import behavior  # noqa: E402
from app.ml.experiments import run_pipeline  # noqa: E402
from app.ml.federated import FedConfig  # noqa: E402
from app.services import datasets  # noqa: E402


def load_user_data(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Training dataset not found: {path}")
    frame = datasets.parse(path.name, path.read_bytes())
    frame = behavior.compute(datasets.normalize_transactions(frame))
    if "is_fraud" not in frame.columns:
        raise ValueError("Training data must contain an is_fraud or fraud-label column.")
    if frame["is_fraud"].nunique() < 2:
        raise ValueError("Training data must contain both legitimate and fraudulent rows.")
    return frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train only from data explicitly supplied by the user.")
    parser.add_argument("--data", type=Path, help="labelled CSV, Excel, JSON, TSV or Word-table file")
    parser.add_argument("--dataset", choices=["paysim"], help="use an explicitly installed public dataset")
    parser.add_argument("--max-rows", type=int, default=150_000, help="maximum PaySim rows (all fraud retained)")
    parser.add_argument("--quick", action="store_true", help="skip comparison-only models")
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument("--use", metavar="NAME", help="activate an already trained artifact set")
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    ARTIFACT_DIR.mkdir(exist_ok=True)

    if args.use:
        source = ARTIFACT_DIR / args.use
        for filename, destination in (
            ("fedupi_model.pt", MODEL_PATH), ("fedupi_meta.json", META_PATH), ("report.json", REPORT_PATH)
        ):
            candidate = source / filename
            if not candidate.is_file():
                parser.error(f"missing artifact: {candidate}")
            shutil.copy(candidate, destination)
        print(f"production model switched to '{args.use}'")
        sys.exit(0)

    if args.dataset == "paysim":
        from app.data.paysim import load_paysim
        frame = load_paysim(args.max_rows)
        name = "paysim"
    elif args.data:
        frame = load_user_data(args.data.resolve())
        name = re.sub(r"[^a-z0-9_-]+", "_", args.data.stem.lower()).strip("_") or "uploaded"
    else:
        parser.error("provide --data PATH (or explicitly select --dataset paysim)")

    print(f"dataset {name}: {len(frame)} rows, fraud {frame.is_fraud.mean():.2%}")

    def show(progress):
        if progress.get("round") and (progress["round"] % 5 == 0 or progress["round"] == 1):
            print(f"  [{progress['stage']}] round {progress['round']:>2}  f1={progress['f1']:.3f} pr_auc={progress['pr_auc']:.3f}")

    report, artifact = run_pipeline(frame, FedConfig(secure_agg=True), progress=show, full=not args.quick)
    report["dataset"]["name"] = name
    artifact["meta"]["dataset"] = name
    output = ARTIFACT_DIR / name
    output.mkdir(exist_ok=True)
    torch.save({"mlp": artifact["mlp"], "ae": artifact["ae"]}, output / "fedupi_model.pt")
    (output / "fedupi_meta.json").write_text(json.dumps(artifact["meta"], indent=2))
    (output / "report.json").write_text(json.dumps(report, indent=2))
    if not args.no_activate:
        shutil.copy(output / "fedupi_model.pt", MODEL_PATH)
        shutil.copy(output / "fedupi_meta.json", META_PATH)
        shutil.copy(output / "report.json", REPORT_PATH)
        print(f"activated '{name}' as the production model")

    print("\n%-52s %6s %6s %6s %7s" % ("model", "prec", "rec", "f1", "pr_auc"))
    for experiment in report["experiments"].values():
        metrics = experiment["metrics"]
        print("%-52s %6.3f %6.3f %6.3f %7.3f  eps=%s" % (
            experiment["label"][:52], metrics["precision"], metrics["recall"], metrics["f1"], metrics["pr_auc"],
            experiment.get("epsilon", "-"),
        ))
    print("\nFINAL ensemble:", report["final"]["metrics"])
    print(f"done in {report['duration_sec']}s")
