"""
Build the Power BI Project (.pbip) for the remnant inventory dashboard from code.

- Semantic model in TMDL (tables, Power Query, relationships, calculated columns, DAX measures)
- Report in PBIR (one JSON per page and per visual) + a custom theme

Everything is regenerated from scratch on each run, so the output folder is safe to delete.
Usage:  python scripts/build_pbip.py
Then open powerbi/RemnantInventory.pbip in Power BI Desktop and set the DataFolder parameter.
"""
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi"
NAME = "RemnantInventory"
SM = OUT / f"{NAME}.SemanticModel"
RP = OUT / f"{NAME}.Report"
DEFAULT_DATA_FOLDER = "C:\\laser-remnant-inventory\\data\\"

NS = uuid.UUID("6b1f3c1e-4c2a-4f7e-9a51-0c3d2e7f8a90")


def guid(key: str) -> str:
    """Deterministic GUID so regenerating does not create noisy git diffs."""
    return str(uuid.uuid5(NS, key))


def vid(key: str) -> str:
    return uuid.uuid5(NS, "visual:" + key).hex[:20]


def write(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(content, str):
        content = json.dumps(content, indent=2, ensure_ascii=False)
    path.write_text(content + ("\n" if not content.endswith("\n") else ""), encoding="utf-8")


SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
S_VISUAL = f"{SCHEMA}/item/report/definition/visualContainer/2.4.0/schema.json"
S_PAGE = f"{SCHEMA}/item/report/definition/page/2.0.0/schema.json"

# Palette (laser orange + graphite, semantic colors for reused / scrapped / in stock)
GRAPHITE = "#1F2A36"
ORANGE = "#E8692C"
TEAL = "#2A9D8F"      # reused
RED = "#C8553D"       # scrapped
GRAY = "#8D99AE"      # still in stock
BG = "#F3F4F6"
LINE = "#DDE2E8"

# =====================================================================================
# SEMANTIC MODEL (TMDL)
# =====================================================================================
T = "\t"

# table -> list of (column, M type, TMDL dataType, summarizeBy, formatString)
COLUMNS = {
    "fRemnants": [
        ("remnant_id", "type text", "string", "none", None),
        ("generated_date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("source_job", "type text", "string", "none", None),
        ("machine_id", "type text", "string", "none", None),
        ("material_id", "type text", "string", "none", None),
        ("width_mm", "Int64.Type", "int64", "none", "0"),
        ("length_mm", "Int64.Type", "int64", "none", "0"),
        ("area_m2", "type number", "double", "sum", "#,0.000"),
        ("weight_kg", "type number", "double", "sum", "#,0.0"),
        ("value_brl", "type number", "double", "sum", "#,0.00"),
        ("location_id", "type text", "string", "none", None),
        ("status", "type text", "string", "none", None),
        ("disposal_date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("reuse_job", "type text", "string", "none", None),
    ],
    "dMaterial": [
        ("material_id", "type text", "string", "none", None),
        ("material", "type text", "string", "none", None),
        ("thickness_mm", "type number", "double", "none", "0.00"),
        ("material_description", "type text", "string", "none", None),
        ("density_kg_m3", "Int64.Type", "int64", "none", "0"),
        ("cost_brl_kg", "type number", "double", "none", "#,0.00"),
        ("scrap_price_brl_kg", "type number", "double", "none", "#,0.00"),
    ],
    "dMachine": [
        ("machine_id", "type text", "string", "none", None),
        ("machine", "type text", "string", "none", None),
        ("bed_size", "type text", "string", "none", None),
    ],
    "dLocation": [
        ("location_id", "type text", "string", "none", None),
        ("area", "type text", "string", "none", None),
        ("aisle", "type text", "string", "none", None),
        ("level", "Int64.Type", "int64", "none", "0"),
        ("is_addressed", "Int64.Type", "int64", "none", "0"),
    ],
    "dCalendar": [
        ("date", "type date", "dateTime", "none", "yyyy-mm-dd"),
        ("year", "Int64.Type", "int64", "none", "0"),
        ("month_number", "Int64.Type", "int64", "none", "0"),
        ("year_month_number", "Int64.Type", "int64", "none", "0"),
        ("month_label", "type text", "string", "none", None),
        ("quarter", "type text", "string", "none", None),
        ("period", "type text", "string", "none", None),
    ],
}
SORT_BY = {("dCalendar", "month_label"): "year_month_number"}

CALC_COLUMNS = {
    "fRemnants": [
        ("age_days", "int64", "0", None, [
            "-- days in stock until today (available) or until it left (reused / scrapped)",
            "VAR snapshot = MAX ( dCalendar[date] )",
            "VAR end_date = IF ( fRemnants[status] = \"Available\", snapshot, fRemnants[disposal_date] )",
            "RETURN INT ( end_date - fRemnants[generated_date] )",
        ]),
        ("age_bucket", "string", None, "age_bucket_order", [
            "SWITCH (",
            "    TRUE (),",
            "    fRemnants[age_days] <= 30, \"0-30 days\",",
            "    fRemnants[age_days] <= 90, \"31-90 days\",",
            "    fRemnants[age_days] <= 180, \"91-180 days\",",
            "    \"180+ days\"",
            ")",
        ]),
        ("age_bucket_order", "int64", "0", None, [
            "SWITCH (",
            "    TRUE (),",
            "    fRemnants[age_days] <= 30, 1,",
            "    fRemnants[age_days] <= 90, 2,",
            "    fRemnants[age_days] <= 180, 3,",
            "    4",
            ")",
        ]),
    ]
}

# (name, folder, format, DAX lines)
MEASURES = [
    ("Remnants Generated", "1 Volume", "#,0", ["COUNTROWS ( fRemnants )"]),
    ("Remnants in Stock", "2 Stock", "#,0",
     ["CALCULATE ( COUNTROWS ( fRemnants ), fRemnants[status] = \"Available\" )"]),
    ("Stock Area (m²)", "2 Stock", "#,0.0",
     ["CALCULATE ( SUM ( fRemnants[area_m2] ), fRemnants[status] = \"Available\" )"]),
    ("Stock Weight (kg)", "2 Stock", "#,0",
     ["CALCULATE ( SUM ( fRemnants[weight_kg] ), fRemnants[status] = \"Available\" )"]),
    ("Stock Value (BRL)", "2 Stock", "#,0",
     ["CALCULATE ( SUM ( fRemnants[value_brl] ), fRemnants[status] = \"Available\" )"]),
    ("Avg Stock Age (days)", "2 Stock", "#,0",
     ["CALCULATE ( AVERAGE ( fRemnants[age_days] ), fRemnants[status] = \"Available\" )"]),
    ("Stock on Floor %", "2 Stock", "0.0%", [
        "DIVIDE (",
        "    CALCULATE ( [Remnants in Stock], dLocation[is_addressed] = 0 ),",
        "    [Remnants in Stock]",
        ")",
    ]),
    ("Reused Count", "3 Outcome", "#,0",
     ["CALCULATE ( COUNTROWS ( fRemnants ), fRemnants[status] = \"Reused\" )"]),
    ("Scrapped Count", "3 Outcome", "#,0",
     ["CALCULATE ( COUNTROWS ( fRemnants ), fRemnants[status] = \"Scrapped\" )"]),
    ("Reuse Rate %", "3 Outcome", "0.0%", [
        "-- share of remnants that already left the stock and were reused (not scrapped)",
        "DIVIDE ( [Reused Count], [Reused Count] + [Scrapped Count] )",
    ]),
    ("Avg Days to Reuse", "3 Outcome", "#,0",
     ["CALCULATE ( AVERAGE ( fRemnants[age_days] ), fRemnants[status] = \"Reused\" )"]),
    ("Scrapped Weight (kg)", "3 Outcome", "#,0",
     ["CALCULATE ( SUM ( fRemnants[weight_kg] ), fRemnants[status] = \"Scrapped\" )"]),
    ("Value Lost to Scrap (BRL)", "3 Outcome", "#,0", [
        "-- material cost of scrapped remnants minus what the scrap buyer pays",
        "SUMX (",
        "    FILTER ( fRemnants, fRemnants[status] = \"Scrapped\" ),",
        "    fRemnants[value_brl] - fRemnants[weight_kg] * RELATED ( dMaterial[scrap_price_brl_kg] )",
        ")",
    ]),
    ("Scrapped Weight by Disposal Date (kg)", "4 By disposal date", "#,0", [
        "-- uses the inactive relationship to look at WHEN remnants were scrapped",
        "CALCULATE (",
        "    [Scrapped Weight (kg)],",
        "    USERELATIONSHIP ( fRemnants[disposal_date], dCalendar[date] )",
        ")",
    ]),
    ("Reused Weight by Disposal Date (kg)", "4 By disposal date", "#,0", [
        "CALCULATE (",
        "    CALCULATE ( SUM ( fRemnants[weight_kg] ), fRemnants[status] = \"Reused\" ),",
        "    USERELATIONSHIP ( fRemnants[disposal_date], dCalendar[date] )",
        ")",
    ]),
]

# (from table, from col, to table, to col, active)
RELATIONSHIPS = [
    ("fRemnants", "material_id", "dMaterial", "material_id", True),
    ("fRemnants", "machine_id", "dMachine", "machine_id", True),
    ("fRemnants", "location_id", "dLocation", "location_id", True),
    ("fRemnants", "generated_date", "dCalendar", "date", True),
    ("fRemnants", "disposal_date", "dCalendar", "date", False),
]


def tmdl_name(n: str) -> str:
    return n if n.replace("_", "").isalnum() else "'" + n.replace("'", "''") + "'"


def m_query(table: str) -> list[str]:
    types = ", ".join(f'{{"{c}", {mt}}}' for c, mt, *_ in COLUMNS[table])
    return [
        "let",
        f'    Source = Excel.Workbook(File.Contents(DataFolder & "remnant_inventory.xlsx"), null, true),',
        f'    Sheet = Source{{[Item="{table}",Kind="Sheet"]}}[Data],',
        "    Promoted = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),",
        f"    Typed = Table.TransformColumnTypes(Promoted, {{{types}}})",
        "in",
        "    Typed",
    ]


def table_tmdl(table: str) -> str:
    L = [f"table {table}", f"{T}lineageTag: {guid('table:' + table)}"]
    if table == "dCalendar":
        L.append(f"{T}dataCategory: Time")
    L.append("")
    if table == "fRemnants":
        for name, folder, fmt, dax in MEASURES:
            if len(dax) == 1:
                L.append(f"{T}measure {tmdl_name(name)} = {dax[0]}")
            else:
                L.append(f"{T}measure {tmdl_name(name)} =")
                L += [f"{T*3}{x}" for x in dax]
            L += [f"{T*2}formatString: {fmt}", f"{T*2}displayFolder: {folder}",
                  f"{T*2}lineageTag: {guid('measure:' + name)}", ""]
    for col, _mt, dt, summ, fmt in COLUMNS[table]:
        L.append(f"{T}column {tmdl_name(col)}")
        L.append(f"{T*2}dataType: {dt}")
        if fmt:
            L.append(f"{T*2}formatString: {fmt}")
        if table == "dCalendar" and col == "date":
            L.append(f"{T*2}isKey")
        L.append(f"{T*2}lineageTag: {guid(f'col:{table}.{col}')}")
        L.append(f"{T*2}summarizeBy: {summ}")
        L.append(f"{T*2}sourceColumn: {col}")
        if (table, col) in SORT_BY:
            L.append(f"{T*2}sortByColumn: {SORT_BY[(table, col)]}")
        L += ["", f"{T*2}annotation SummarizationSetBy = Automatic", ""]
    for col, dt, fmt, sort_by, dax in CALC_COLUMNS.get(table, []):
        L.append(f"{T}column {tmdl_name(col)} =")
        L += [f"{T*3}{x}" for x in dax]
        L.append(f"{T*2}dataType: {dt}")
        if fmt:
            L.append(f"{T*2}formatString: {fmt}")
        L.append(f"{T*2}lineageTag: {guid(f'col:{table}.{col}')}")
        L.append(f"{T*2}summarizeBy: none")
        if sort_by:
            L.append(f"{T*2}sortByColumn: {sort_by}")
        L += ["", f"{T*2}annotation SummarizationSetBy = Automatic", ""]
    L.append(f"{T}partition {table} = m")
    L.append(f"{T*2}mode: import")
    L.append(f"{T*2}source =")
    L += [f"{T*4}{x}" for x in m_query(table)]
    L += ["", f"{T}annotation PBI_ResultType = Table", ""]
    return "\n".join(L)


def build_semantic_model():
    write(SM / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {},
    })
    write(SM / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    order = ["DataFolder"] + list(COLUMNS)
    model = [
        "model Model",
        f"{T}culture: en-US",
        f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{T}sourceQueryCulture: en-US",
        f"{T}dataAccessOptions",
        f"{T*2}legacyRedirects",
        f"{T*2}returnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(order)}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
    ] + [f"ref table {t}" for t in COLUMNS]
    write(SM / "definition" / "model.tmdl", "\n".join(model))
    write(SM / "definition" / "expressions.tmdl", "\n".join([
        f'expression DataFolder = "{DEFAULT_DATA_FOLDER}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"{T}lineageTag: {guid('expr:DataFolder')}",
        "",
        f"{T}annotation PBI_ResultType = Text",
        "",
    ]))
    for t in COLUMNS:
        write(SM / "definition" / "tables" / f"{t}.tmdl", table_tmdl(t))
    rel = []
    for ft, fc, tt, tc, active in RELATIONSHIPS:
        rel.append(f"relationship {guid(f'rel:{ft}.{fc}-{tt}.{tc}')}")
        if not active:
            rel.append(f"{T}isActive: false")
        if tt == "dCalendar":
            rel.append(f"{T}joinOnDateBehavior: datePartOnly")
        rel += [f"{T}fromColumn: {ft}.{fc}", f"{T}toColumn: {tt}.{tc}", ""]
    write(SM / "definition" / "relationships.tmdl", "\n".join(rel))


# =====================================================================================
# REPORT (PBIR)
# =====================================================================================
def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def color(hex_):
    return {"solid": {"color": lit(hex_)}}


def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(prop, entity="fRemnants"):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(field, active=False):
    kind = "Measure" if "Measure" in field else "Column"
    ent = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if active:
        p["active"] = True
    return p


# Table headers: readable names instead of column names like week_label
COLUMN_LABELS = {
    "week_label": "Week", "material_description": "Material", "remnant_id": "Remnant",
    "operation_id": "Operation", "location_id": "Location", "generated_date": "Cut on",
    "supplier_type": "Type", "promised_lead_time_days": "Lead time (days)",
}
UNIT_SUFFIXES = {"_mm": " (mm)", "_m2": " (m²)", "_brl": " (BRL)", "_days": " (days)",
                 "_kg": " (kg)", "_hours": " (h)"}


def column_label(prop):
    if prop in COLUMN_LABELS:
        return COLUMN_LABELS[prop]
    unit = next((u for s, u in UNIT_SUFFIXES.items() if prop.endswith(s)), "")
    base = prop[: -len(next(s for s in UNIT_SUFFIXES if prop.endswith(s)))] if unit else prop
    return base.replace("_", " ").capitalize() + unit


def table_projection(field):
    p = proj(field)
    if "Column" in field:
        p["displayName"] = column_label(field["Column"]["Property"])
    return p


# Room for long category names on bar charts ("Welding / boilermaking"):
# the axis may take up to 45% of the visual width instead of the default 25%.
WIDE_CATEGORY_AXIS = [{"properties": {"maxMarginFactor": {"expr": {"Literal": {"Value": "45L"}}}}}]


def container_objects(title=None, background=True):
    o = {}
    if title:
        o["title"] = [{"properties": {
            "show": lit(True), "text": lit(title), "fontColor": color(GRAPHITE),
            "fontSize": lit(12), "bold": lit(True)}}]
    else:
        o["title"] = [{"properties": {"show": lit(False)}}]
    if background:
        o["background"] = [{"properties": {"show": lit(True), "color": color("#FFFFFF"),
                                           "transparency": lit(0)}}]
        o["border"] = [{"properties": {"show": lit(True), "color": color(LINE), "radius": lit(8)}}]
        o["dropShadow"] = [{"properties": {"show": lit(True), "preset": lit("BottomRight"),
                                           "transparency": lit(85)}}]
    return o


class Page:
    def __init__(self, name, display):
        self.name, self.display, self.visuals = name, display, []

    def add(self, key, x, y, w, h, visual, filters=None):
        v = {"$schema": S_VISUAL, "name": vid(self.name + key),
             "position": {"x": x, "y": y, "z": len(self.visuals) * 1000,
                          "height": h, "width": w, "tabOrder": len(self.visuals) * 1000},
             "visual": visual}
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)


def textbox(runs_by_paragraph, fill=None):
    paragraphs = [{"textRuns": [{"value": text, "textStyle": style} for text, style in runs]}
                  for runs in runs_by_paragraph]
    vco = {"title": [{"properties": {"show": lit(False)}}]}
    if fill:
        vco["background"] = [{"properties": {"show": lit(True), "color": color(fill),
                                             "transparency": lit(0)}}]
    else:
        vco["background"] = [{"properties": {"show": lit(False)}}]
    return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
            "visualContainerObjects": vco, "drillFilterOtherVisuals": True}


def card(measure):
    return {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [proj(meas(measure))]}}},
        "objects": {
            "labels": [{"properties": {"color": color(GRAPHITE), "fontSize": lit(26)}}],
            "categoryLabels": [{"properties": {"show": lit(True), "color": color("#5B6573"),
                                               "fontSize": lit(10)}}],
        },
        "visualContainerObjects": container_objects(None),
        "drillFilterOtherVisuals": True,
    }


def slicer(field, title):
    return {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [proj(field, active=True)]}}},
        "objects": {"data": [{"properties": {"mode": lit("Dropdown")}}],
                    "header": [{"properties": {"show": lit(True), "text": lit(title),
                                               "fontColor": color(GRAPHITE)}}]},
        "visualContainerObjects": container_objects(None),
        "drillFilterOtherVisuals": True,
    }


def chart(vtype, category, values, title, sort=None, sort_dir="Descending", colors=None,
          series_colors=None, labels=True, label_format=None):
    vals = values if isinstance(values, list) else [values]
    q = {"queryState": {"Category": {"projections": [proj(category, active=True)]},
                        "Y": {"projections": [proj(v) for v in vals]}}}
    if sort is not None:
        q["sortDefinition"] = {"sort": [{"field": sort, "direction": sort_dir}], "isDefaultSort": True}
    objects = {}
    if labels:
        lp = {"show": lit(True), "color": color(GRAPHITE)}
        if label_format:
            lp["labelDisplayUnits"] = lit(label_format)
        objects["labels"] = [{"properties": lp}]
    if colors:
        objects["dataPoint"] = [{"properties": {"fill": color(colors)}}]
    if series_colors:
        objects["dataPoint"] = [
            {"properties": {"fill": color(c)},
             "selector": {"metadata": proj(m)["queryRef"]}} for m, c in series_colors]
    if len(vals) > 1:
        objects["legend"] = [{"properties": {"show": lit(True), "position": lit("Top")}}]
    if vtype == "clusteredBarChart":
        objects["categoryAxis"] = WIDE_CATEGORY_AXIS
    objects["valueAxis"] = [{"properties": {"show": lit(False)}}] if vtype.endswith("BarChart") else \
        [{"properties": {"gridlineShow": lit(False)}}]
    return {"visualType": vtype, "query": q, "objects": objects,
            "visualContainerObjects": container_objects(title), "drillFilterOtherVisuals": True}


def table(columns, title, sort=None):
    q = {"queryState": {"Values": {"projections": [table_projection(c) for c in columns]}}}
    if sort is not None:
        q["sortDefinition"] = {"sort": [{"field": sort, "direction": "Descending"}], "isDefaultSort": True}
    return {"visualType": "tableEx", "query": q,
            "objects": {"columnHeaders": [{"properties": {"backColor": color(GRAPHITE),
                                                          "fontColor": color("#FFFFFF")}}],
                        "grid": [{"properties": {"gridHorizontalColor": color(LINE)}}]},
            "visualContainerObjects": container_objects(title), "drillFilterOtherVisuals": True}


def categorical_filter(entity, prop, value, name):
    return {
        "name": vid("filter:" + name),
        "field": col(entity, prop),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "f", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": prop}}],
                "Values": [[{"Literal": {"Value": f"'{value}'"}}]]}}}],
        },
        "howCreated": "User",
    }


def title_band(page, title, question):
    page.add("title", 0, 0, 1280, 64, textbox([
        [(title, {"fontWeight": "bold", "fontSize": "20pt", "color": "#FFFFFF"})],
        [(question, {"fontSize": "11pt", "color": "#F4B183"})],
    ], fill=GRAPHITE))
    page.add("footer", 900, 688, 372, 32, textbox([
        [("AC Metais · synthetic data · snapshot 31 Oct 2026",
          {"fontSize": "8pt", "color": "#7A8494"})]]))


def build_pages():
    W, G, X0 = 210, 12, 16
    cards_x = [X0 + i * (W + G) for i in range(4)]

    # ------------------------------------------------------------ page 1: stock today
    p1 = Page("stock_today", "Stock today")
    title_band(p1, "Laser remnant inventory · Stock today",
               "What is sitting on our racks, how old is it, and where is it?")
    for x, m in zip(cards_x, [
            "Remnants in Stock", "Stock Area (m²)",
            "Stock Value (BRL)", "Avg Stock Age (days)"]):
        p1.add("card " + m, x, 80, W, 92, card(m))
    p1.add("slicer material", 904, 80, 176, 92, slicer(col("dMaterial", "material"), "Material"))
    p1.add("slicer machine", 1092, 80, 172, 92, slicer(col("dMachine", "machine"), "Machine"))
    p1.add("bar value material", 16, 186, 404, 250, chart(
        "clusteredBarChart", col("dMaterial", "material"), meas("Stock Value (BRL)"),
        "Which materials hold the most money? (stock value, BRL)",
        sort=meas("Stock Value (BRL)"), colors=ORANGE))
    p1.add("col aging", 432, 186, 404, 250, chart(
        "clusteredColumnChart", col("fRemnants", "age_bucket"), meas("Remnants in Stock"),
        "How old is the stock? (remnants by age)",
        sort=col("fRemnants", "age_bucket"), sort_dir="Ascending", colors=GRAPHITE))
    p1.add("bar location", 848, 186, 416, 250, chart(
        "clusteredBarChart", col("dLocation", "aisle"), meas("Stock Area (m²)"),
        "Where is it stored? (stock area by rack, m²)",
        sort=meas("Stock Area (m²)"), colors=GRAY))
    p1.add("table oldest", 16, 448, 1248, 240, table(
        [col("fRemnants", "remnant_id"), col("dMaterial", "material_description"),
         col("fRemnants", "width_mm"), col("fRemnants", "length_mm"),
         col("fRemnants", "area_m2"), col("fRemnants", "value_brl"),
         col("fRemnants", "location_id"), col("fRemnants", "generated_date"),
         col("fRemnants", "age_days")],
        "Which remnants should be used first? (available remnants, oldest first)",
        sort=col("fRemnants", "age_days")),
        filters=[categorical_filter("fRemnants", "status", "Available", "p1 table available")])

    # ------------------------------------------------------------ page 2: reuse vs scrap
    p2 = Page("reuse_vs_scrap", "Reuse vs scrap")
    title_band(p2, "Laser remnant inventory · Reuse vs scrap",
               "Are we reusing remnants or selling them as scrap? Did the control process help?")
    for x, m in zip(cards_x, ["Reuse Rate %", "Scrapped Weight (kg)",
                              "Value Lost to Scrap (BRL)", "Avg Days to Reuse"]):
        p2.add("card " + m, x, 80, W, 92, card(m))
    p2.add("slicer period", 904, 80, 176, 92, slicer(col("dCalendar", "period"), "Period"))
    p2.add("slicer material", 1092, 80, 172, 92, slicer(col("dMaterial", "material"), "Material"))
    p2.add("stacked fate", 16, 186, 620, 250, chart(
        "hundredPercentStackedColumnChart", col("dCalendar", "month_label"),
        [meas("Reused Count"), meas("Scrapped Count"), meas("Remnants in Stock")],
        "What happened to the remnants generated each month?",
        sort=col("dCalendar", "month_label"), sort_dir="Ascending", labels=False,
        series_colors=[(meas("Reused Count"), TEAL), (meas("Scrapped Count"), RED),
                       (meas("Remnants in Stock"), GRAY)]))
    p2.add("col scrap timing", 648, 186, 616, 250, chart(
        "clusteredColumnChart", col("dCalendar", "month_label"),
        [meas("Reused Weight by Disposal Date (kg)"), meas("Scrapped Weight by Disposal Date (kg)")],
        "When does material leave the stock? (kg by month it left)",
        sort=col("dCalendar", "month_label"), sort_dir="Ascending", labels=False,
        series_colors=[(meas("Reused Weight by Disposal Date (kg)"), TEAL),
                       (meas("Scrapped Weight by Disposal Date (kg)"), RED)]))
    p2.add("bar reuse material", 16, 448, 404, 240, chart(
        "clusteredBarChart", col("dMaterial", "material"), meas("Reuse Rate %"),
        "Which materials do we reuse best? (reuse rate)",
        sort=meas("Reuse Rate %"), colors=TEAL))
    p2.add("table material", 432, 448, 832, 240, table(
        [col("dMaterial", "material_description"), meas("Remnants Generated"),
         meas("Reused Count"), meas("Scrapped Count"), meas("Reuse Rate %"),
         meas("Scrapped Weight (kg)"), meas("Value Lost to Scrap (BRL)")],
        "Where is the money lost? (by material and thickness)",
        sort=meas("Value Lost to Scrap (BRL)")))
    return [p1, p2]


THEME = {
    "name": "Remnant Inventory",
    "dataColors": [ORANGE, GRAPHITE, TEAL, RED, GRAY, "#F4B183", "#3D5A80", "#98C1D9"],
    "background": "#FFFFFF",
    "foreground": GRAPHITE,
    "tableAccent": ORANGE,
    "good": TEAL,
    "bad": RED,
    "neutral": GRAY,
    "textClasses": {
        "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#3A4452"},
        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": GRAPHITE},
        "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 26, "color": GRAPHITE},
    },
    "visualStyles": {
        "page": {"*": {"background": [{"color": {"solid": {"color": BG}}, "transparency": 0}]}},
    },
}


def build_report():
    pages = build_pages()
    write(RP / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    d = RP / "definition"
    write(d / "version.json", {"$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
                               "version": "2.0.0"})
    theme_file = "RemnantInventoryTheme.json"
    write(d / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {
            "name": theme_file,
            "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.0.0"},
            "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": theme_file, "path": theme_file, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
    })
    write(RP / "StaticResources" / "RegisteredResources" / theme_file, THEME)
    write(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        write(d / "pages" / p.name / "page.json", {
            "$schema": S_PAGE, "name": p.name, "displayName": p.display,
            "displayOption": "FitToPage", "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {"color": color(BG), "transparency": lit(0)}}]}})
        for v in p.visuals:
            write(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)
    return pages


def main():
    for p in (SM, RP):
        if p.exists():
            shutil.rmtree(p)
    build_semantic_model()
    pages = build_report()
    write(OUT / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    n = sum(len(p.visuals) for p in pages)
    print(f"Built {OUT / (NAME + '.pbip')}: {len(COLUMNS)} tables, {len(MEASURES)} measures, "
          f"{len(pages)} pages, {n} visuals")


if __name__ == "__main__":
    main()
