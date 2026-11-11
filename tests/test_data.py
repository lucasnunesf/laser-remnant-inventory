"""The synthetic dataset: reproducible, consistent keys, and the remnant rules hold."""
import pandas as pd
import pytest

from conftest import ROOT, load

DATA = ROOT / "data" / "remnant_inventory.xlsx"
SNAPSHOT = pd.Timestamp("2026-10-31")
CONTROL_START = pd.Timestamp("2026-03-01")


@pytest.fixture(scope="module")
def x():
    return load(DATA)


@pytest.fixture(scope="module")
def r(x):
    return x["fRemnants"].merge(x["dMaterial"], on="material_id").merge(x["dLocation"], on="location_id")


def test_generator_is_reproducible(fresh):
    work, logs = fresh
    assert "3,259 remnants" in logs["generate"]
    new = load(work / "data" / "remnant_inventory.xlsx")
    for sheet, df in load(DATA).items():
        pd.testing.assert_frame_equal(new[sheet], df, obj=sheet)


def test_keys(x):
    f = x["fRemnants"]
    assert f.remnant_id.is_unique
    for col, dim in (("material_id", "dMaterial"), ("machine_id", "dMachine"), ("location_id", "dLocation")):
        assert f[col].isin(x[dim][col]).all(), col
    assert f.generated_date.isin(x["dCalendar"].date).all()
    assert f.disposal_date.dropna().isin(x["dCalendar"].date).all()


def test_status_and_dates(r):
    available = r.status == "Available"
    assert set(r.status) == {"Available", "Reused", "Scrapped"}
    assert r.loc[available, "disposal_date"].isna().all()
    left = r[~available]
    assert left.disposal_date.notna().all()
    assert (left.disposal_date >= left.generated_date).all()
    assert (left.disposal_date <= SNAPSHOT).all()
    assert r.reuse_job.notna().eq(r.status == "Reused").all()


def test_weight_and_value(r):
    assert ((r.area_m2 - r.width_mm * r.length_mm / 1e6).abs() < 1e-4).all()
    weight = r.area_m2 * r.thickness_mm / 1000 * r.density_kg_m3
    assert ((r.weight_kg - weight).abs() <= 0.01 + weight * 1e-3).all()
    # weight is stored rounded to 0.01 kg, so the value can differ by half a cent per kg
    assert ((r.value_brl - r.weight_kg * r.cost_brl_kg).abs() <= 0.005 * r.cost_brl_kg + 0.01).all()
    assert (r.scrap_price_brl_kg < r.cost_brl_kg).all()


def test_120_day_policy_after_control(r):
    after = r[(r.generated_date >= CONTROL_START) & (r.status == "Scrapped") & (r.area_m2 >= 0.06)]
    assert len(after) > 0
    assert ((after.disposal_date - after.generated_date).dt.days >= 120).all()


def test_control_puts_remnants_on_racks(r):
    floor = r.groupby(r.generated_date >= CONTROL_START).is_addressed.apply(lambda s: (s == 0).mean())
    assert floor[False] > 0.30 and floor[True] < 0.12


def test_calendar_period(x):
    cal = x["dCalendar"]
    assert cal.date.max() == SNAPSHOT
    assert (cal.loc[cal.date >= CONTROL_START, "period"] == "After control").all()
    assert (cal.loc[cal.date < CONTROL_START, "period"] == "Before control").all()
