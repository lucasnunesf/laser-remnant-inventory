"""
Print the main numbers of the dashboard straight from the Excel file, using pandas.

The logic mirrors the DAX measures in build_pbip.py, so the numbers can be checked
without Power BI (and the tests compare both).
Usage:  python scripts/kpi_snapshot.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "remnant_inventory.xlsx"
CONTROL_START = pd.Timestamp("2026-03-01")


def load(path=DATA):
    x = pd.read_excel(path, sheet_name=None)
    r = x["fRemnants"].merge(x["dMaterial"], on="material_id").merge(x["dLocation"], on="location_id")
    snapshot = x["dCalendar"].date.max()
    end = r.disposal_date.where(r.status != "Available", snapshot)
    r["age_days"] = (end - r.generated_date).dt.days
    r["loss_brl"] = (r.value_brl - r.weight_kg * r.scrap_price_brl_kg).where(r.status == "Scrapped", 0.0)
    r["period"] = r.generated_date.ge(CONTROL_START).map({False: "Before control", True: "After control"})
    return r


def outcome(r):
    reused, scrapped = (r.status == "Reused").sum(), (r.status == "Scrapped").sum()
    return {
        "reuse_rate": reused / (reused + scrapped),
        "days_to_reuse": r.loc[r.status == "Reused", "age_days"].mean(),
        "value_lost_brl": r.loss_brl.sum(),
    }


def kpis(r):
    stock = r[r.status == "Available"]
    return {
        "remnants": len(r),
        "in_stock": len(stock),
        "stock_m2": stock.area_m2.sum(),
        "stock_brl": stock.value_brl.sum(),
        "stock_age_days": stock.age_days.mean(),
        "stock_on_floor": (stock.is_addressed == 0).mean(),
        "before": outcome(r[r.period == "Before control"]),
        "after": outcome(r[r.period == "After control"]),
    }


if __name__ == "__main__":
    k = kpis(load())
    print(f"Remnants generated         {k['remnants']:,}")
    print(f"In stock on 31 Oct 2026    {k['in_stock']}  ·  {k['stock_m2']:.0f} m²  ·  "
          f"BRL {k['stock_brl'] / 1e3:.0f}k  ·  avg age {k['stock_age_days']:.0f} days")
    print(f"Stock on the floor         {k['stock_on_floor']:.1%}")
    print(f"\n{'':27}{'Before control':>16}{'After control':>16}")
    b, a = k["before"], k["after"]
    print(f"{'Reuse rate':27}{b['reuse_rate']:>16.1%}{a['reuse_rate']:>16.1%}")
    print(f"{'Avg days until reused':27}{b['days_to_reuse']:>16.0f}{a['days_to_reuse']:>16.0f}")
    print(f"{'Value lost to scrap (BRL)':27}{b['value_lost_brl']:>16,.0f}{a['value_lost_brl']:>16,.0f}")
