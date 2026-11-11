"""
Small reader for the Power BI Project files (TMDL + PBIR) used by the tests.

The Microsoft JSON schemas check that each file has the right shape, but they do not
check that a visual points to a column or measure that really exists in the model,
or that a DAX formula only uses existing names. This module does that cross-check.
"""
import json
import re
from pathlib import Path


def _name(raw):
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def read_model(model_dir):
    """Return {table: {"columns": set, "measures": {name: dax}, "calc": {name: dax}, "sort_by": {col: col}}}
    and the list of relationships (from_table, from_col, to_table, to_col, active)."""
    model_dir = Path(model_dir) / "definition"
    tables = {}
    for f in sorted((model_dir / "tables").glob("*.tmdl")):
        lines = f.read_text(encoding="utf-8").splitlines()
        table = _name(lines[0].split(" ", 1)[1])
        t = {"columns": set(), "measures": {}, "calc": {}, "sort_by": {}}
        current, kind, dax = None, None, []

        def close():
            if current and kind in ("measure", "calc"):
                t["measures" if kind == "measure" else "calc"][current] = "\n".join(dax).strip()

        for line in lines[1:]:
            m = re.match(r"^\t(measure|column) (.+?)(?: =(.*))?$", line)
            if m:
                close()
                kw, raw, expr = m.groups()
                current = _name(raw)
                if kw == "measure":
                    kind = "measure"
                else:
                    t["columns"].add(current)
                    kind = "calc" if expr is not None else "column"
                dax = [expr.strip()] if expr and expr.strip() else []
                continue
            if re.match(r"^\t\S", line):            # partition, annotation, etc.
                close()
                current, kind, dax = None, None, []
                continue
            if current and line.startswith("\t\t\t"):
                dax.append(line.strip())
            elif current and line.strip().startswith("sortByColumn:"):
                t["sort_by"][current] = _name(line.split(":", 1)[1])
        close()
        tables[table] = t

    rels = []
    text = (model_dir / "relationships.tmdl").read_text(encoding="utf-8")
    for block in text.split("relationship ")[1:]:
        fc = re.search(r"fromColumn: (\S+)\.(\S+)", block).groups()
        tc = re.search(r"toColumn: (\S+)\.(\S+)", block).groups()
        rels.append((fc[0], fc[1], tc[0], tc[1], "isActive: false" not in block))
    return tables, rels


def dax_references(dax):
    """Table[column] pairs and [Measure] names used in a DAX expression."""
    code = re.sub(r"--[^\n]*", "", dax)
    code = re.sub(r'"(?:[^"]|"")*"', '""', code)
    cols = set(re.findall(r"('?[A-Za-z_][\w ]*'?)\[([^\]]+)\]", code))
    cols = {(_name(t), c) for t, c in cols}
    measures = set(re.findall(r"(?<![\w'\]])\[([^\]]+)\]", code))
    return cols, measures


def _walk(node, aliases, out):
    if isinstance(node, dict):
        local = dict(aliases)
        for src in node.get("From", []) or []:
            if isinstance(src, dict) and "Name" in src and "Entity" in src:
                local[src["Name"]] = src["Entity"]
        for kind in ("Column", "Measure"):
            if kind in node and isinstance(node[kind], dict) and "Property" in node[kind]:
                ref = node[kind]["Expression"]["SourceRef"]
                entity = ref.get("Entity") or local.get(ref.get("Source"))
                out.append((kind, entity, node[kind]["Property"]))
        for v in node.values():
            _walk(v, local, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, aliases, out)


def visual_fields(report_dir):
    """Every (kind, table, name) a visual or filter in the report points to, per visual file."""
    result = {}
    for f in sorted(Path(report_dir).glob("definition/pages/*/visuals/*/visual.json")):
        out = []
        _walk(json.loads(f.read_text(encoding="utf-8")), {}, out)
        result[f] = out
    return result


def problems(project_dir, name):
    """List of human-readable problems found in a built Power BI project (empty = good)."""
    project_dir = Path(project_dir)
    tables, rels = read_model(project_dir / f"{name}.SemanticModel")
    all_measures = {m for t in tables.values() for m in t["measures"]}
    issues = []

    for table, t in tables.items():
        for col, target in t["sort_by"].items():
            if target not in t["columns"]:
                issues.append(f"{table}[{col}] sorted by missing column {target}")
        for label, dax in list(t["measures"].items()) + list(t["calc"].items()):
            cols, meas = dax_references(dax)
            for tb, c in cols:
                if tb not in tables or c not in tables[tb]["columns"]:
                    issues.append(f"{label}: unknown column {tb}[{c}]")
            for mname in meas:
                if mname not in all_measures and mname not in t["columns"]:
                    issues.append(f"{label}: unknown measure [{mname}]")

    for ft, fc, tt, tc, _ in rels:
        for tb, c in ((ft, fc), (tt, tc)):
            if tb not in tables or c not in tables[tb]["columns"]:
                issues.append(f"relationship uses missing column {tb}.{c}")

    for f, fields in visual_fields(project_dir / f"{name}.Report").items():
        for kind, tb, prop in fields:
            ok = tb in tables and (prop in tables[tb]["columns"] if kind == "Column"
                                   else prop in tables[tb]["measures"])
            if not ok:
                issues.append(f"{f.parent.name}: {kind} {tb}.{prop} not in model")
    return issues
