# FedUPI project structure

```text
fedupi/
|- Frontend/                 React + Vite analyst workspace
|  |- src/
|  |  |- components/        Shared cards, tables and export controls
|  |  |- pages/             Login, dashboard, monitoring, lab and reports
|  |  |- services/api.js    Single frontend-to-backend API client
|  |  |- App.jsx            Authenticated shell, navigation and routing
|  |  `- context.jsx        Authentication and theme state
|  `- vite.config.js        Development proxy to the Flask API
|- Backend/                  Flask API, persistence and ML pipeline
|  |- app/
|  |  |- api/               Authenticated HTTP endpoints
|  |  |- data/              Parsing, behaviour features and data generation
|  |  |- ml/                FedAvg/FedProx, models, privacy and evaluation
|  |  `- services/          Auth, datasets, scoring, exports and training jobs
|  |- scripts/train.py      Explicit labelled-data training entry point
|  |- tests/                 API, security, privacy and model-quality tests
|  `- artifacts/             Active model weights, metadata and report
|- samples/                  Small reproducible test and demonstration data
|- papers/                   Project research references
|- backend.ps1 / backend.sh  Backend launchers
|- frontend.ps1 / frontend.sh Frontend launchers
`- README.md                 Setup, run and verification guide
```

## Runtime flow

1. The React app sends authenticated requests through `Frontend/src/services/api.js`.
2. Vite proxies `/api` to Flask during development; Flask serves the built React app in production.
3. Uploaded data is normalized and scored locally by the active model.
4. Federated Lab trains five institution clients and shares model updates, not raw transaction rows.
5. SQLite stores users, dataset metadata, scored transactions and analyst decisions.

The paper preset uses the stated 13-input vector, one 16-unit hidden layer, seed 42, FedAvg, 20 rounds, two local epochs, learning rate 0.02 and batch size 512. The default production profile keeps the project's richer feature set and autoencoder extension.
