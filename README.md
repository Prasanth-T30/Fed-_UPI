# FedUPI

Run the Flask backend and React frontend in **two separate terminals**. The launchers install missing dependencies, use predictable local ports, and keep backend startup straightforward.

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the source layout and request flow.

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- About 2 GB of free RAM when running the app
- More free RAM when retraining the model

## Windows PowerShell

Terminal 1:

```powershell
.\backend.ps1
```

Terminal 2:

```powershell
.\frontend.ps1
```

## Linux or macOS

First make the launchers executable once:

```bash
chmod +x backend.sh frontend.sh
```

Terminal 1:

```bash
./backend.sh
```

Terminal 2:

```bash
./frontend.sh
```

Open <http://127.0.0.1:5173>. Check the Flask API at <http://127.0.0.1:8001/api/health>.

## Optional ports

Windows:

```powershell
.\backend.ps1 -Port 8010
.\frontend.ps1 -Port 5180 -ApiPort 8010
```

Linux/macOS:

```bash
./backend.sh --port 8010
./frontend.sh --port 5180 --api-port 8010
```

## Safe reload mode

Normal startup deliberately does **not** use backend auto-reload. PyTorch models are memory-heavy, and reload can temporarily create multiple Python processes. If reload is specifically needed, stop training and tests first, then run:

```powershell
.\backend.ps1 -Reload
```

or:

```bash
./backend.sh --reload
```

Do not run the backend, model training, and the full test suite simultaneously on a low-memory computer. Stop the backend before retraining or running all backend tests.

## Verification commands

Frontend:

```powershell
cd Frontend
npm run build
```

Backend (stop the running backend first):

```powershell
cd Backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

Linux/macOS uses `./.venv/bin/python` for the final command.

## Training data

FedUPI does not generate or silently substitute dashboard transactions. Uploads and API-scored transactions are the only records shown by the application. The tracked `samples/` files are limited to automated tests and an explicit policy demonstration.

Federated Lab trains from the signed-in user's newest uploaded dataset. The file must contain a fraud label such as `is_fraud`, `fraud`, `label` or `class`, with both legitimate and fraudulent rows.

Command-line training also requires an explicit labelled file:

```powershell
cd Backend
.\.venv\Scripts\python.exe scripts\train.py --data C:\path\to\transactions.csv --quick
```

Linux/macOS:

```bash
cd Backend
./.venv/bin/python scripts/train.py --data /path/to/transactions.csv --quick
```

CSV, Excel, JSON, TSV and Word-table files are supported. PaySim can only be used when explicitly selected with `--dataset paysim` and its source archive has been installed.

## Research-paper protocol

The Federated Lab includes a **Use research-paper preset** button. It selects the paper's single-hidden-layer MLP, FedAvg, seed 42, 20 communication rounds, two local epochs, learning rate 0.02 and mini-batches of 512. Enabling the full comparison also reports federated, centralized and institution-only logistic baselines using the paper's validation-threshold sweep.

The same preset is available from the command line:

```powershell
cd Backend
.\.venv\Scripts\python.exe scripts\train.py --data C:\path\to\transactions.csv --paper-protocol
```

The enhanced MLP, autoencoder, FedProx, secure aggregation, differential privacy and policy rules remain available; the paper preset does not remove those project extensions.
