"""Run the SQL in sql/ against the procurement database and publish results.

Writes one CSV per query plus two charts to outputs/, and prints a summary.
The CSVs can be loaded straight into Power BI or Excel.
"""
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "procurement.db"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"

TIER_COLORS = {"Preferred": "#0ca30c", "Approved": "#2a78d6", "Watchlist": "#fab219", "At risk": "#d03b3b"}
BLUE, INK, MUTED, GRID, SURFACE = "#2a78d6", "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": "#c3c2b7",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "text.color": INK,
        "axes.labelcolor": "#52514e",
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "font.size": 10,
    }
)


def run_query(con, filename):
    return pd.read_sql_query((SQL_DIR / filename).read_text(), con)


def chart_scorecard(scorecard):
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    bars = ax.barh(
        scorecard["supplier_name"],
        scorecard["total_score"],
        color=scorecard["tier"].map(TIER_COLORS),
        height=0.6,
    )
    ax.bar_label(bars, labels=[f"{s:.0f}  {t}" for s, t in zip(scorecard["total_score"], scorecard["tier"])],
                 padding=5, color=INK)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 118)
    ax.set_xlabel("Weighted score (0-100)")
    ax.set_title("Supplier scorecard: delivery 40%, quality 30%, fill 20%, price 10%")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "scorecard.png", dpi=160)
    plt.close(fig)


def chart_trend(trend, flagged):
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    for name, grp in trend.groupby("supplier_name"):
        highlight = name == flagged
        ax.plot(grp["quarter"], grp["on_time_pct"],
                color="#d03b3b" if highlight else "#c3c2b7",
                linewidth=2.5 if highlight else 1.2,
                marker="o" if highlight else None,
                zorder=3 if highlight else 2)
    last = trend[trend["supplier_name"] == flagged].iloc[-1]
    ax.annotate(f"{flagged}: {last['on_time_pct']:.0f}%", (last["quarter"], last["on_time_pct"]),
                xytext=(-8, -16), textcoords="offset points", ha="right", color=INK, fontweight="bold")
    ax.set_ylim(40, 100)
    ax.set_ylabel("On-time delivery %")
    ax.set_title("Quarterly on-time delivery: one supplier is slipping (others in grey)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "on_time_trend.png", dpi=160)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    kpis = run_query(con, "01_supplier_kpis.sql")
    scorecard = run_query(con, "02_scorecard.sql")
    trend = run_query(con, "03_quarterly_trend.sql")
    con.close()

    kpis.to_csv(OUT_DIR / "supplier_kpis.csv", index=False)
    scorecard.to_csv(OUT_DIR / "scorecard.csv", index=False)
    trend.to_csv(OUT_DIR / "quarterly_trend.csv", index=False)

    # Supplier with the biggest drop in on-time delivery from first to last quarter
    final_quarter = trend[trend["quarter"] == trend["quarter"].max()]
    worst = final_quarter.loc[final_quarter["change_vs_first_qtr"].idxmin()]

    chart_scorecard(scorecard)
    chart_trend(trend, worst["supplier_name"])

    print(scorecard[["rank", "supplier_name", "total_score", "tier", "on_time_pct",
                     "defect_ppm", "fill_rate_pct", "price_variance_pct", "spend_share_pct"]].to_string(index=False))
    weak = scorecard[scorecard["tier"].isin(["Watchlist", "At risk"])]
    print(f"\nSpend with Watchlist / At risk suppliers: {weak['spend_share_pct'].sum():.1f}%")
    print(f"Biggest on-time decline: {worst['supplier_name']} "
          f"({worst['change_vs_first_qtr']:+.1f} pts since first quarter, now {worst['on_time_pct']:.1f}%)")
    print(f"Outputs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
