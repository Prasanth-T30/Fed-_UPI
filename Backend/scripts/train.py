"""Prepare a dataset, run the full federated experiment suite and save model + report.

    python scripts/train.py                      # synthetic UPI data (default)
    python scripts/train.py --dataset paysim     # real public PaySim data (needs data/raw/paysim.zip)
    python scripts/train.py --dataset paysim --no-activate   # keep the current production model
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import torch  # noqa: E402

from app.config import ARTIFACT_DIR, DATA_DIR, DATASET_PATH, META_PATH, MODEL_PATH, REPORT_PATH  # noqa: E402
from app.data.generator import generate  # noqa: E402
from app.ml.experiments import run_pipeline  # noqa: E402
from app.ml.federated import FedConfig  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["upi", "paysim"], default="upi")
    ap.add_argument("--max-rows", type=int, default=150_000, help="PaySim sample size (all fraud kept)")
    ap.add_argument("--no-activate", action="store_true")
    ap.add_argument("--use", choices=["upi", "paysim"], help="only switch the production model to a trained dataset")
    a = ap.parse_args()
    DATA_DIR.mkdir(exist_ok=True); ARTIFACT_DIR.mkdir(exist_ok=True)
    if a.use:
        src = ARTIFACT_DIR / a.use
        shutil.copy(src / "fedupi_model.pt", MODEL_PATH); shutil.copy(src / "fedupi_meta.json", META_PATH)
        shutil.copy(src / "report.json", REPORT_PATH)
        print(f"production model switched to '{a.use}'"); sys.exit(0)

    if a.dataset == "paysim":
        from app.data.paysim import load_paysim, SAMPLE_PATH
        df = load_paysim(a.max_rows)
        df.to_csv(SAMPLE_PATH, index=False)
        name = "paysim"
    else:
        df = generate(seed=42)
        df.to_csv(DATASET_PATH, index=False)
        name = "upi"
    print(f"dataset {name}: {len(df)} rows, fraud {df.is_fraud.mean():.2%}")

    def show(p):
        if p.get("round") and (p["round"] % 5 == 0 or p["round"] == 1):
            print(f"  [{p['stage']}] round {p['round']:>2}  f1={p['f1']:.3f} pr_auc={p['pr_auc']:.3f}")

    report, art = run_pipeline(df, FedConfig(secure_agg=True), progress=show, full=True)
    report["dataset"]["name"] = name
    art["meta"]["dataset"] = name
    out = ARTIFACT_DIR / name
    out.mkdir(exist_ok=True)
    torch.save({"mlp": art["mlp"], "ae": art["ae"]}, out / "fedupi_model.pt")
    (out / "fedupi_meta.json").write_text(json.dumps(art["meta"], indent=2))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    if not a.no_activate:
        shutil.copy(out / "fedupi_model.pt", MODEL_PATH)
        shutil.copy(out / "fedupi_meta.json", META_PATH)
        shutil.copy(out / "report.json", REPORT_PATH)
        print(f"activated '{name}' as the production model")

    print("\n%-52s %6s %6s %6s %7s" % ("model", "prec", "rec", "f1", "pr_auc"))
    for k, e in report["experiments"].items():
        m = e["metrics"]
        print("%-52s %6.3f %6.3f %6.3f %7.3f  eps=%s" % (e["label"][:52], m["precision"], m["recall"], m["f1"], m["pr_auc"], e.get("epsilon", "-")))
    print("\nFINAL ensemble:", report["final"]["metrics"])
    print(f"done in {report['duration_sec']}s")
