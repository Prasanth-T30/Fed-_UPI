"""Neural networks used by the federation."""

from torch import nn


class LogisticFraudClassifier(nn.Module):
    """Single linear logit used for the research paper's logistic baseline."""

    def __init__(self, n_in: int):
        super().__init__()
        self.linear = nn.Linear(n_in, 1)

    def forward(self, x):
        return self.linear(x).squeeze(-1)


class FraudMLP(nn.Module):
    """Supervised fraud classifier; outputs a logit."""

    def __init__(self, n_in: int, hidden=(64, 32), dropout: float = 0.1):
        super().__init__()
        layers, prev = [], n_in
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU()]
            if dropout:
                layers.append(nn.Dropout(dropout))
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


class AutoEncoder(nn.Module):
    """Unsupervised anomaly detector trained on legitimate traffic only.
    High reconstruction error = behaviour never seen in normal UPI use (novel fraud)."""

    def __init__(self, n_in: int, bottleneck: int = 6):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(n_in, 24), nn.ReLU(), nn.Linear(24, bottleneck), nn.ReLU())
        self.dec = nn.Sequential(nn.Linear(bottleneck, 24), nn.ReLU(), nn.Linear(24, n_in))

    def forward(self, x):
        return self.dec(self.enc(x))

    def error(self, x):
        return ((self(x) - x) ** 2).mean(dim=1)
