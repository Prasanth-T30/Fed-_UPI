# FedUPI — Financial Fraud Detection System using Federated Learning on UPI

Five banks jointly train one fraud model **without sharing any transaction data**. Only model weights
leave each bank; the server averages them (FedAvg / FedProx, optional DP clipping + noise).
The result is served through a FastAPI scoring service with plain-language explanations and a React analyst dashboard.

## Run it

Two terminals, one command each (the first run installs everything and trains the model):

```powershell
.\backend.ps1     # terminal 1 -> API on http://127.0.0.1:8000
.\frontend.ps1    # terminal 2 -> open http://127.0.0.1:5173
```

If the backend uses a different port, set `VITE_API_TARGET` before starting the frontend, for example:

```powershell
$env:VITE_API_TARGET = "http://127.0.0.1:8001"
.\frontend.ps1
```

Tests: `cd Backend; .\.venv\Scripts\python.exe -m pytest -q`

## Tech stack (kept simple)

| Layer | Tools |
| --- | --- |
| AI / ML | PyTorch (MLP classifier + autoencoder), scikit-learn (gradient-boosting baseline, metrics), NumPy, pandas |
| Federated | Own transparent implementation: FedAvg, FedProx, DP-FedAvg (clip + Gaussian noise) |
| Backend | FastAPI, Pydantic, SQLAlchemy + SQLite |
| Frontend | React 18, Vite, React Router, Recharts |

## Structure

```
Backend/
  app/
    api/routes.py          REST endpoints (score, batch, simulate, alerts, federated train, report, papers)
    data/generator.py      UPI-style synthetic data: 5 non-IID banks, 6 fraud typologies
    data/features.py       Fixed-scale feature engineering (no cross-bank statistics shared)
    ml/networks.py         FraudMLP + AutoEncoder
    ml/federated.py        Client, FedAvg/FedProx, DP aggregation, training loop
    ml/experiments.py      Split, federated run, baselines, report + artifacts
    ml/explain.py          Gradient x input attribution
    ml/metrics.py          Precision/recall/F1/PR-AUC/ROC-AUC, threshold search
    services/scoring.py    Model loading, scoring, risk decision, reasons
    services/store.py      SQLite: scored transactions + analyst alert queue
    services/training.py   Background training jobs for the UI
  scripts/train.py         Full research run -> artifacts/
  tests/                   Unit + API tests
Frontend/src/pages/        Dashboard, Live Monitor, Check Transaction, Batch Upload,
                           Alert Queue, Federated Lab, Model Insights, Research
samples/                   Ready-to-upload datasets (xlsx / csv / json)
backups/                   Your original project zip
```

## AI models

1. **Federated MLP classifier** (main) — class-weighted BCE, trained with FedAvg across 5 banks.
2. **Federated autoencoder** — trained on legitimate traffic only, anomaly score for novel fraud. It is fused into the final score only if it improves validation F1 (currently weight 0 on this data; its score is still shown).
3. **Baselines for the paper-style comparison**: local-only per bank, centralized MLP, centralized gradient boosting, FedProx, FedAvg + DP.
4. **Explainability**: per-transaction gradient×input drivers rendered as reasons ("First payment to this beneficiary", "4 failed logins in 24h"…).

Decisions: `BLOCK` (score ≥ validation-tuned threshold), `STEP_UP_AUTH` (≥ half of it), else `ALLOW`.

## Measured results (held-out test, seed 42, synthetic data)

| Approach | Precision | Recall | F1 | PR-AUC |
| --- | --- | --- | --- | --- |
| Local-only (mean of 5 banks) | 84.1% | 73.6% | 77.9% | 0.854 |
| **Federated FedAvg (production)** | 89.9% | 75.6% | 82.2% | 0.887 |
| Federated FedProx | 88.8% | 75.6% | 81.7% | 0.887 |
| Federated FedAvg + Secure Aggregation | 89.9% | 75.6% | 82.2% | 0.887 |
| Federated FedAvg + DP (clip 1.0, z 0.3) — ε ≈ 143 | 74.3% | 73.5% | 73.9% | 0.789 |
| Federated FedAvg + DP + SecAgg (clip 1.0, z 1.0) — ε ≈ 24.8 | 22.8% | 26.9% | 24.6% | 0.162 |
| Centralized MLP | 88.9% | 82.0% | 85.3% | 0.905 |
| Centralized gradient boosting | 91.6% | 80.6% | 85.7% | 0.920 |

**Privacy:** the production model is trained with secure aggregation (`ml/secagg.py`: pairwise masks in Z_2^40, server sees only the sum; verified to match plain FedAvg to ~2e-6) and the accountant in `ml/privacy.py` reports client-level (ε, δ) via Rényi DP. With only five banks, meaningful DP is very costly: z=0.3 gives ε≈143 (no real guarantee), z=1.0 gives ε≈25 and destroys accuracy. Treat DP here as a measured trade-off, not a deployable guarantee. Secure aggregation simulates key agreement and has no dropout recovery.

Federated beats banks working alone and approaches pooled training; DP costs accuracy; gradient boosting on pooled data is still the strongest. These numbers come from **synthetic** data — no labelled real UPI fraud dataset is public — so they show the method, not real-world accuracy.

## Risk policy, repeat-payment detection and datasets

Scope: only **P2P, merchant and investment** payments (other categories are rejected).

| Tier | Rule | Action |
| --- | --- | --- |
| **High risk** | amount above Rs 99,999 (>= Rs 1,00,000) - the only way to reach High | Block / hold |
| **Moderate risk** | amount Rs 70,000-99,999, **or** the federated model flags it, **or** repeated payments (see below) | Step-up authentication |
| **Low risk** | everything else (below Rs 70,000 is never High on amount alone) | Allow |

Every payment shows a **risk %**: Low 0-39, Moderate 40-79, High 80-99, positioned inside its band by the model's fraud score. It is not a calibrated probability.

**Repeat detection** (`app/data/behavior.py`, features are learned by the model *and* enforced as rules): for each payment the system counts earlier payments by the same user in the last hour and 24 h, and earlier payments by the same user to the same receiver in 24 h. Two or more earlier payments to the same receiver, or four or more by the user in an hour, make it at least Moderate. Single scoring reads this history from the database when you give a sender and receiver ID; uploaded files compute it from `sender_id`, `receiver_id`, `timestamp`.

Measured on the held-out synthetic test set: model F1 ~74% (precision 81%, recall 68%); with the policy, flagged (Moderate + High) precision ~54% and recall ~73%. The High tier is only ~22% fraud, because most legitimate large payments are also above Rs 99,999 - that is the cost of the amount rule you chose. Weak spots: `stealth` and `qr_phishing` fraud, and the first payment of a repeat burst (nothing repeated yet).

**Ready-to-upload datasets** (`samples/`, generated by `Backend/scripts/make_datasets.py`, unseen seeds):

| File | Content |
| --- | --- |
| `upi_test_transactions.xlsx / .csv / .json` | ~2,100 mixed payments from five banks with ground-truth `is_fraud` |
| `policy_rules_demo.csv / .xlsx` | hand-made rows: every amount band, 6 repeat payments to one receiver, a 7-payment burst, scams, normal traffic |
| `upi_training_dataset.csv` | the ~52,000-row dataset the model trains on |

## Real public data: PaySim

`app/data/paysim.py` loads the real [PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1) dataset (Lopez-Rojas et al., EMSS 2016; synthetic-from-real mobile-money logs, **not** Indian UPI). Put `paysim.zip` or `paysim.csv` in `Backend/data/raw/`, then:

```powershell
cd Backend
.\.venv\Scripts\python.exe scripts\train.py --dataset paysim --no-activate   # train, keep current production model
.\.venv\Scripts\python.exe scripts\train.py --use paysim                     # switch production model (or --use upi)
```

Only pre-transaction fields are used (post-transaction balances leak the label); TRANSFER + CASH_OUT rows, all 8,213 fraud rows kept and legitimate rows down-sampled to 150k total (raises prevalence to ~5.5%). Fields PaySim lacks (login/PIN failures, device, account age, …) are neutral constants, and two extra features are used: `balance_drain` and `dest_empty`. PaySim has no banks, so rows are hash-partitioned into five IID simulated banks.

| PaySim, held-out test | Precision | Recall | F1 | PR-AUC |
| --- | --- | --- | --- | --- |
| Local-only (mean) | 75.6% | 73.5% | 74.0% | 0.813 |
| Federated FedAvg | 73.4% | 74.4% | 73.9% | 0.817 |
| Centralized MLP | 80.3% | 72.8% | 76.4% | 0.840 |
| Centralized gradient boosting | 77.4% | 75.3% | 76.3% | 0.846 |

On PaySim with IID banks, federated training matches local-only models — there is no federated gain to claim, because no bank is missing patterns the others have. The gain on the synthetic UPI data comes from its deliberately non-IID banks.

## Accounts, uploads and downloads

- **Authentication**: register / sign in (scrypt password hashes, HMAC-signed 12 h bearer tokens, stdlib only). Every API route except `/api/health` and `/api/auth/*` needs the token. Set `FEDUPI_SECRET` in production; otherwise a key is generated in `Backend/storage/secret.key`.
- **Profile**: edit name / organization / role, change password, choose light or dark theme (also toggled from the top bar; saved in the browser).
- **Upload & Datasets**: upload `.xlsx`, `.csv`, `.json`, `.tsv` or a `.docx` table (10 MB / 20,000 rows). Files are stored in `Backend/storage/datasets/`, listed in a per-user library, scored immediately, and can be re-scored, downloaded or deleted. A sample is in `samples/`.
- **Downloads**: flagged-fraud downloads offer Excel, CSV, Word, PDF or JSON from a dropdown on the Upload, Downloads and Alert Queue pages (`GET /api/export/flagged?format=xlsx&dataset_id=...`).

## Base papers

- McMahan et al., *Communication-Efficient Learning of Deep Networks from Decentralized Data* (FedAvg), AISTATS 2017
- Li et al., *Federated Optimization in Heterogeneous Networks* (FedProx), MLSys 2020
- McMahan et al., *Learning Differentially Private Recurrent Language Models*, ICLR 2018
- Bonawitz et al., *Practical Secure Aggregation*, CCS 2017
- Yang et al., *Federated Machine Learning: Concept and Applications*, ACM TIST 2019
- Yang et al., *FFD: A Federated Learning Based Method for Credit Card Fraud Detection*, 2019
- *Privacy-Preserving Federated Fraud Detection in Payment Transactions with NVIDIA FLARE*, arXiv 2603.13617
- Sreeji et al., *FedUpi: Federated Learning for Fraudulent UPI Transaction Detection*, IJRASET 2026
- *Hybrid Deep Learning Models for Real-Time UPI Fraud Detection*, IJRASET

(Links in the app under **Research & Papers**.) Verify citations before putting them in your report.

## Limitations

Synthetic data; secure aggregation is simulated (no real key exchange, no dropout handling); ε covers supervised-model training only; all banks are simulated in one process; the scoring API sees plain transaction signals; the risk score is not a calibrated probability.
