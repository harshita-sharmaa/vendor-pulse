"""Build a synthetic procurement database in SQLite.

Three tables: suppliers, purchase_orders and receipts. The data is simulated
with a fixed seed. Each supplier is given its own hidden reliability profile
(lateness, defect rate, short shipments, price drift) so the scorecard has
real differences to find. One supplier is set to get worse over time.
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
N_ORDERS = 3000
START, END = "2025-07-01", "2026-06-30"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "procurement.db"

SUPPLIERS = [
    # name, region, category, late probability, defect rate, short-ship probability, price drift
    ("Northwind Components", "North America", "Electronics", 0.04, 0.004, 0.02, 0.00),
    ("Pacific Circuit Co", "Asia", "Electronics", 0.10, 0.008, 0.04, -0.02),
    ("Baltic Metalworks", "Europe", "Metals", 0.07, 0.006, 0.03, 0.01),
    ("Sierra Packaging", "North America", "Packaging", 0.05, 0.003, 0.02, 0.00),
    ("Delta Plastics", "Asia", "Plastics", 0.22, 0.015, 0.08, -0.03),
    ("Orion Fasteners", "Europe", "Metals", 0.12, 0.010, 0.05, 0.02),
    ("Lotus Cable Works", "Asia", "Electronics", 0.30, 0.030, 0.12, -0.04),
    ("Granite Logistics Supply", "North America", "Packaging", 0.15, 0.007, 0.06, 0.03),
    ("Helix Polymers", "Europe", "Plastics", 0.09, 0.020, 0.04, 0.05),
    ("Monsoon Electricals", "Asia", "Electronics", 0.10, 0.009, 0.05, 0.00),
]
DETERIORATING = "Monsoon Electricals"  # late deliveries rise through the year

SCHEMA = """
DROP TABLE IF EXISTS receipts;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS suppliers;

CREATE TABLE suppliers (
    supplier_id   INTEGER PRIMARY KEY,
    supplier_name TEXT NOT NULL,
    region        TEXT NOT NULL,
    category      TEXT NOT NULL
);

CREATE TABLE purchase_orders (
    po_id          INTEGER PRIMARY KEY,
    supplier_id    INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    order_date     TEXT NOT NULL,
    promised_date  TEXT NOT NULL,
    qty_ordered    INTEGER NOT NULL,
    contract_price REAL NOT NULL,
    unit_price     REAL NOT NULL
);

CREATE TABLE receipts (
    receipt_id    INTEGER PRIMARY KEY,
    po_id         INTEGER NOT NULL REFERENCES purchase_orders(po_id),
    received_date TEXT NOT NULL,
    qty_received  INTEGER NOT NULL,
    qty_rejected  INTEGER NOT NULL
);
"""


def main():
    rng = np.random.default_rng(SEED)
    days = pd.date_range(START, END, freq="D")

    suppliers = pd.DataFrame(
        [(i + 1, s[0], s[1], s[2]) for i, s in enumerate(SUPPLIERS)],
        columns=["supplier_id", "supplier_name", "region", "category"],
    )

    orders, receipts = [], []
    for po_id in range(1, N_ORDERS + 1):
        idx = int(rng.integers(0, len(SUPPLIERS)))
        name, region, _, p_late, defect_rate, p_short, drift = SUPPLIERS[idx]

        order_date = days[int(rng.integers(0, len(days)))]
        year_progress = (order_date - days[0]).days / len(days)
        if name == DETERIORATING:
            p_late = 0.04 + 0.40 * year_progress

        promised_lead = int(rng.integers(20, 40)) if region == "Asia" else int(rng.integers(7, 21))
        promised_date = order_date + pd.Timedelta(days=promised_lead)
        days_late = int(rng.integers(1, 15)) if rng.random() < p_late else int(rng.integers(-3, 1))
        received_date = promised_date + pd.Timedelta(days=days_late)

        qty = int(rng.integers(2, 60)) * 50
        qty_received = int(qty * rng.uniform(0.7, 0.95)) if rng.random() < p_short else qty
        qty_rejected = int(rng.binomial(qty_received, defect_rate))

        contract_price = round(float(rng.uniform(2, 40)), 2)
        unit_price = round(contract_price * (1 + drift + rng.normal(0, 0.015)), 2)

        orders.append((po_id, idx + 1, order_date.date().isoformat(), promised_date.date().isoformat(),
                       qty, contract_price, unit_price))
        receipts.append((po_id, po_id, received_date.date().isoformat(), qty_received, qty_rejected))

    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    suppliers.to_sql("suppliers", con, if_exists="append", index=False)
    con.executemany("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?)", orders)
    con.executemany("INSERT INTO receipts VALUES (?,?,?,?,?)", receipts)
    con.commit()
    con.close()
    print(f"Wrote {len(suppliers)} suppliers and {N_ORDERS} purchase orders to {DB_PATH}")


if __name__ == "__main__":
    main()
