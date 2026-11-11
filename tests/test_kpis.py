"""The numbers quoted in the README come from the data (pandas mirror of the DAX measures)."""
import subprocess
import sys

import pandas as pd
import pytest

from conftest import ROOT
from kpi_snapshot import kpis, load


@pytest.fixture(scope="module")
def r():
    return load()


@pytest.fixture(scope="module")
def k(r):
    return kpis(r)


def test_stock_today(k):
    assert k["remnants"] == 3259
    assert k["in_stock"] == 586
    assert round(k["stock_m2"]) == 197
    assert round(k["stock_brl"] / 1000) == 63
    assert round(k["stock_age_days"]) == 104


def test_before_and_after_control(k):
    b, a = k["before"], k["after"]
    assert (round(b["reuse_rate"], 3), round(a["reuse_rate"], 3)) == (0.205, 0.741)
    assert (round(b["days_to_reuse"]), round(a["days_to_reuse"])) == (65, 28)
    assert (round(b["value_lost_brl"] / 1000), round(a["value_lost_brl"] / 1000)) == (105, 22)


def test_value_lost_is_cost_minus_scrap_sale(r):
    s = r[r.status == "Scrapped"].iloc[0]
    assert s.loss_brl == pytest.approx(s.value_brl - s.weight_kg * s.scrap_price_brl_kg)
    assert (r.loc[r.status != "Scrapped", "loss_brl"] == 0).all()


def test_reuse_rate_ignores_remnants_still_in_stock(r):
    # 586 pieces are still on the racks: counting them as "not reused" would make
    # recent months look worse than they are
    reused, scrapped = (r.status == "Reused").sum(), (r.status == "Scrapped").sum()
    assert reused / (reused + scrapped) > reused / len(r)


def test_age_of_available_pieces_counts_to_the_snapshot(r):
    stock = r[r.status == "Available"]
    snapshot = pd.Timestamp("2026-10-31")
    assert (stock.age_days == (snapshot - stock.generated_date).dt.days).all()


def test_snapshot_script_runs():
    out = subprocess.run([sys.executable, "scripts/kpi_snapshot.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert "In stock on 31 Oct 2026    586" in out
