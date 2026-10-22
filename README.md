# FedUPI

Run the backend and frontend in **two separate terminals**. The launchers install missing dependencies, prevent duplicate servers, use fixed ports, and keep backend memory bounded.

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

Open <http://127.0.0.1:5173>. API documentation is at <http://127.0.0.1:8001/docs>.

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
