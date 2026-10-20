import pandas as pd

from app.data import paysim
from app.data.features import FEATURES, transform


def _fake_raw():
    rows = []
    for i in range(400):
        fraud = int(i % 20 == 0)
        rows.append(dict(step=i % 72 + 1, type="TRANSFER" if i % 2 else "CASH_OUT", amount=100.0 + i,
                         nameOrig=f"C{i}", oldbalanceOrg=100.0 + i if fraud else 5000.0,
                         oldbalanceDest=0.0 if fraud else 300.0, isFraud=fraud))
    rows.append(dict(step=1, type="PAYMENT", amount=5.0, nameOrig="Cx", oldbalanceOrg=9.0, oldbalanceDest=0.0, isFraud=0))
    return pd.DataFrame(rows)


def test_paysim_mapping(monkeypatch):
    monkeypatch.setattr(paysim, "_read_raw", _fake_raw)
    df = paysim.load_paysim(max_rows=300)
    assert set(df.bank) <= set(paysim.BANKS) and (df.merchant_category.isin(["p2p", "merchant"])).all()
    assert df.is_fraud.sum() == 20                         # every fraud row kept, PAYMENT rows dropped
    f = df[df.is_fraud == 1]
    assert (f.balance_drain == 1.0).all() and (f.dest_empty == 1).all()
    assert transform(df).shape[1] == len(FEATURES)
    assert df.transaction_hour.between(0, 23).all()
