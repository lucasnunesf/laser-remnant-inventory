"""
Generate synthetic data for the laser-cutting remnant inventory dashboard.

Scenario (inspired by AC Metais, a Brazilian laser-cutting and metal fabrication shop):
every sheet nested on a laser leaves an offcut ("remnant"). Without control, remnants
pile up on the floor, nobody knows what is in stock, and most of it ends up sold as scrap.
In March 2026 a remnant control process starts (every remnant gets an ID, dimensions and
a rack address), so reuse goes up and the floor pile goes down.

All numbers are synthetic. Output: data/remnant_inventory.xlsx
Sheets: fRemnants, dMaterial, dMachine, dLocation, dCalendar

Usage:  python scripts/generate_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START = pd.Timestamp("2025-05-01")
SNAPSHOT = pd.Timestamp("2026-10-31")          # "today" for the report
CONTROL_START = pd.Timestamp("2026-03-01")     # remnant control process goes live
OUT = Path(__file__).resolve().parents[1] / "data" / "remnant_inventory.xlsx"

rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- dMaterial
# material, density kg/m3, cost BRL/kg, scrap sale BRL/kg, thicknesses (mm), share of mix
MATERIALS = [
    ("Carbon steel SAE 1020", 7850, 7.5, 1.1, [1.5, 2.0, 3.0, 4.75, 6.35, 9.5, 12.7], 0.45),
    ("Galvanized steel",      7850, 9.2, 1.0, [0.9, 1.25, 1.5, 2.0],                0.15),
    ("Stainless AISI 304",    7930, 29.0, 6.5, [1.0, 1.5, 2.0, 3.0, 4.0, 6.0],      0.18),
    ("Stainless AISI 430",    7700, 18.5, 4.0, [0.8, 1.0, 1.5, 2.0],                0.08),
    ("Aluminum 5052",         2680, 33.0, 7.5, [1.5, 2.0, 3.0, 4.0, 6.0],           0.14),
]
rows, mix = [], []
for name, dens, cost, scrap, thicknesses, share in MATERIALS:
    for t in thicknesses:
        rows.append(dict(
            material_id=f"M{len(rows) + 1:03d}",
            material=name,
            thickness_mm=t,
            material_description=f"{name} {t:g} mm",
            density_kg_m3=dens,
            cost_brl_kg=cost,
            scrap_price_brl_kg=scrap,
        ))
        # mid-range thicknesses are cut more often
        mix.append(share / len(thicknesses) * (1.4 if 1.5 <= t <= 4.75 else 0.8))
dMaterial = pd.DataFrame(rows)
mix = np.array(mix) / np.sum(mix)

# ---------------------------------------------------------------- dMachine
dMachine = pd.DataFrame([
    dict(machine_id="L1", machine="Fiber laser 1 (6 kW)",  bed_size="3000 x 1500"),
    dict(machine_id="L2", machine="Fiber laser 2 (12 kW)", bed_size="4000 x 2000"),
    dict(machine_id="L3", machine="CO2 laser (4 kW)",      bed_size="3000 x 1500"),
])

# ---------------------------------------------------------------- dLocation
locs = []
for aisle in "ABCD":
    for level in range(1, 6):
        locs.append(dict(location_id=f"R{aisle}-{level:02d}", area="Remnant rack",
                         aisle=f"Rack {aisle}", level=level, is_addressed=1))
for i in range(1, 5):
    locs.append(dict(location_id=f"FLOOR-{i:02d}", area="Shop floor (no address)",
                     aisle="Floor", level=0, is_addressed=0))
dLocation = pd.DataFrame(locs)

# ---------------------------------------------------------------- fRemnants
days = pd.date_range(START, SNAPSHOT, freq="D")
workdays = days[days.dayofweek < 6]              # Mon-Sat, Saturday is a half shift
records = []
job = 24000
for d in workdays:
    controlled = d >= CONTROL_START
    base = 6 + 3 * (d - START).days / 550        # volume grows over time
    n = rng.poisson(base * (0.5 if d.dayofweek == 5 else 1.0))
    for _ in range(n):
        job += int(rng.integers(0, 2))
        mat = dMaterial.iloc[rng.choice(len(dMaterial), p=mix)]
        machine = rng.choice(["L1", "L2", "L3"], p=[0.42, 0.40, 0.18])

        # dimensions in mm: many small offcuts, few big ones
        width = int(np.clip(rng.lognormal(np.log(380), 0.55), 120, 1500) // 10 * 10)
        length = int(np.clip(rng.lognormal(np.log(700), 0.55), 150, 3000) // 10 * 10)
        area = width * length / 1e6
        weight = area * mat.thickness_mm / 1000 * mat.density_kg_m3
        value = weight * mat.cost_brl_kg

        # without control, ~35% of remnants are dropped on the floor with no address
        on_floor = rng.random() < (0.08 if controlled else 0.35)
        if on_floor:
            loc = f"FLOOR-{int(rng.integers(1, 5)):02d}"
        else:
            loc = f"R{rng.choice(list('ABCD'))}-{int(rng.integers(1, 6)):02d}"

        # --- reuse: bigger pieces and carbon steel are easier to reuse; with control,
        #     planners can find remnants in the system and nest new jobs on them
        p_reuse = 0.15 + 0.25 * min(area / 0.8, 1) + (0.05 if "Carbon" in mat.material else 0)
        if controlled:
            p_reuse += 0.30
        elif on_floor:
            p_reuse *= 0.5                                  # nobody finds what is on the floor
        reuse_date = pd.NaT
        if rng.random() < min(p_reuse, 0.9):
            reuse_date = d + pd.Timedelta(days=int(rng.gamma(2.0, 15 if controlled else 40)))

        # --- scrap
        scrap_date = pd.NaT
        if area < 0.06 and rng.random() < 0.7:            # too small: straight to the scrap bin
            scrap_date = d + pd.Timedelta(days=int(rng.integers(0, 10)))
        elif controlled:                                   # policy: unused after 120 days -> scrap
            if rng.random() < 0.85:
                scrap_date = d + pd.Timedelta(days=120 + int(rng.integers(0, 15)))
        else:
            # before control: quarterly cleanup campaigns pick up old pieces at random
            for q_end in pd.date_range(d + pd.Timedelta(days=90), CONTROL_START, freq="QE"):
                if rng.random() < 0.45:
                    scrap_date = q_end
                    break
            # go-live: the untraceable floor pile and very old stock are purged
            if pd.isna(scrap_date):
                purge = CONTROL_START + pd.Timedelta(days=int(rng.integers(0, 10)))
                if (on_floor and rng.random() < 0.9) or ((CONTROL_START - d).days > 180 and rng.random() < 0.5):
                    scrap_date = purge
                elif rng.random() < 0.85:                   # what is left follows the new policy
                    scrap_date = max(d + pd.Timedelta(days=120), purge) + pd.Timedelta(days=int(rng.integers(0, 15)))

        # whatever happens first (and before the snapshot) wins
        status, disposal, reuse_job = "Available", pd.NaT, None
        events = [(t, s) for t, s in [(reuse_date, "Reused"), (scrap_date, "Scrapped")]
                  if pd.notna(t) and t <= SNAPSHOT]
        if events:
            disposal, status = min(events)
            if status == "Reused":
                reuse_job = f"JOB-{job + int(rng.integers(5, 400))}"

        records.append(dict(
            remnant_id=f"RM{len(records) + 1:06d}",
            generated_date=d.normalize(),
            source_job=f"JOB-{job}",
            machine_id=machine,
            material_id=mat.material_id,
            width_mm=width,
            length_mm=length,
            area_m2=round(area, 4),
            weight_kg=round(weight, 2),
            value_brl=round(value, 2),
            location_id=loc,
            status=status,
            disposal_date=disposal,
            reuse_job=reuse_job,
        ))
fRemnants = pd.DataFrame(records)

# ---------------------------------------------------------------- dCalendar
cal = pd.DataFrame({"date": pd.date_range(START, SNAPSHOT, freq="D")})
cal["year"] = cal.date.dt.year
cal["month_number"] = cal.date.dt.month
cal["year_month_number"] = cal.year * 100 + cal.month_number
cal["month_label"] = cal.date.dt.strftime("%b %Y")
cal["quarter"] = "Q" + cal.date.dt.quarter.astype(str) + " " + cal.year.astype(str)
cal["period"] = np.where(cal.date >= CONTROL_START, "After control", "Before control")

# ---------------------------------------------------------------- write
OUT.parent.mkdir(parents=True, exist_ok=True)
with pd.ExcelWriter(OUT, engine="openpyxl", datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as w:
    fRemnants.to_excel(w, sheet_name="fRemnants", index=False)
    dMaterial.to_excel(w, sheet_name="dMaterial", index=False)
    dMachine.to_excel(w, sheet_name="dMachine", index=False)
    dLocation.to_excel(w, sheet_name="dLocation", index=False)
    cal.to_excel(w, sheet_name="dCalendar", index=False)

print(f"{len(fRemnants):,} remnants written to {OUT}")
