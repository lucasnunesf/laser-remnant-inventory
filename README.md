# Laser Remnant Inventory · Power BI

Power BI dashboard that tracks **sheet-metal remnants** (offcuts left on the sheet after laser cutting) in a metal fabrication shop: what is in stock, how old it is, where it is stored, and how much of it is reused instead of being sold as scrap.

The use case is based on **AC Metais**, a Brazilian laser-cutting and metal fabrication company. **All data is synthetic**, generated in Python.

> 📸 *Screenshots: `docs/images/` (add after opening the report in Power BI Desktop)*

## The problem

Every sheet nested on a laser machine leaves a remnant. Without control:

- remnants pile up on the shop floor with no address, so nobody knows what is in stock;
- planners buy new sheets even when a usable remnant exists;
- old pieces end up sold as scrap for a fraction of their cost.

In the scenario, a **remnant control process** goes live in **March 2026**: every remnant gets an ID, dimensions and a rack address, and pieces unused for 120 days follow a scrap policy. The dashboard shows the stock today and the before/after effect.

## Key results (synthetic data)

| | Before control | After control |
|---|---|---|
| Reuse rate (reused ÷ reused + scrapped) | 20.5% | 74.1% |
| Avg days until a remnant is reused | 65 | 28 |
| Value lost to scrap (BRL) | 105k (10 months) | 22k (8 months) |

Stock on 31 Oct 2026: 586 remnants · 197 m² · BRL 63k · avg age 104 days.

## Dashboard

**Page 1 · Stock today** — *What is sitting on our racks, how old is it, and where is it?*
KPI cards (remnants, m², BRL, average age) · stock value by material · aging buckets · area by rack · list of available remnants, oldest first (what to use next).

**Page 2 · Reuse vs scrap** — *Are we reusing remnants or selling them as scrap? Did the control process help?*
KPI cards (reuse rate, scrapped kg, value lost, days to reuse) · outcome of each month's remnants (100% stacked) · reused vs scrapped kg by the month they left the stock · reuse rate by material · loss by material and thickness.

## Data model

Star schema, single-direction filters, imported from one Excel file.

```
                 dMaterial            dMachine
                     │ 1                  │ 1
                     │                    │
 dCalendar 1 ──── * fRemnants * ──────────┘
   (date)  ┄┄┄┄┄┄ *  (disposal_date, inactive)
                     │ *
                     │ 1
                 dLocation
```

| Table | Grain | Rows |
|---|---|---|
| `fRemnants` | one remnant | 3,259 |
| `dMaterial` | material + thickness | 26 |
| `dMachine` | laser machine | 3 |
| `dLocation` | rack address or floor area | 24 |
| `dCalendar` | day | 549 |

Highlights:

- **Two relationships to the calendar.** `generated_date` is active (when the remnant was created); `disposal_date` is inactive and activated with `USERELATIONSHIP` to show *when* material left the stock.
- **Calculated columns** for age in days and aging buckets (with a sort column).
- **15 DAX measures** in display folders (stock, outcome, by disposal date), e.g. value lost to scrap = material cost − scrap sale price:

```DAX
Value Lost to Scrap (BRL) =
SUMX (
    FILTER ( fRemnants, fRemnants[status] = "Scrapped" ),
    fRemnants[value_brl] - fRemnants[weight_kg] * RELATED ( dMaterial[scrap_price_brl_kg] )
)
```

## Report as code

The report is a **Power BI Project (.pbip)**, built entirely by a Python script:

- semantic model in **TMDL** (tables, Power Query M, relationships, calculated columns, measures);
- report in **PBIR**: one JSON per page and per visual (position, visual type, fields by role, sorting, visual filters, colors), plus a custom theme;
- every JSON file is validated against Microsoft's official schemas (`scripts/validate_pbir.py`);
- GUIDs are deterministic, so rebuilding does not create noisy git diffs.

## Repository

```
data/remnant_inventory.xlsx      synthetic data (5 sheets)
scripts/generate_data.py         data generator (seeded, reproducible)
scripts/build_pbip.py            builds the semantic model (TMDL) and report (PBIR)
scripts/validate_pbir.py         schema validation of the report JSON files
powerbi/RemnantInventory.pbip    open this in Power BI Desktop
docs/                            case study and screenshots
```

## How to run

```bash
pip install -r requirements.txt
python scripts/generate_data.py     # -> data/remnant_inventory.xlsx
python scripts/build_pbip.py        # -> powerbi/RemnantInventory.pbip
```

1. Open `powerbi/RemnantInventory.pbip` in Power BI Desktop (Windows).
2. *Transform data → Edit parameters →* set **DataFolder** to the full path of the `data` folder, ending with `\`.
3. *Refresh.*

Optional schema check:

```bash
git clone --depth 1 https://github.com/microsoft/json-schemas.git
pip install jsonschema
python scripts/validate_pbir.py json-schemas
```

## Tools

Python (pandas, NumPy) · Excel · Power BI Desktop · Power Query (M) · DAX · TMDL · PBIR

## Author

[lucasnunesf](https://github.com/lucasnunesf)
