"""The Power BI Project: rebuilt files match the repository, and every name a visual
or a DAX formula uses exists in the model."""
import filecmp
import json
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, SCHEMAS
from pbip_check import dax_references, problems, read_model
from project import NAME


def _diff(a, b):
    cmp = filecmp.dircmp(a, b, ignore=[".pbi"])
    out = [str(a / x) for x in cmp.left_only + cmp.right_only + cmp.diff_files]
    for sub in cmp.common_dirs:
        out += _diff(a / sub, b / sub)
    return out


def test_build_is_reproducible(fresh):
    work, _ = fresh
    assert _diff(work / "powerbi", ROOT / "powerbi") == []


def test_every_reference_exists():
    assert problems(ROOT / "powerbi", NAME) == []


def test_checker_catches_a_broken_visual(tmp_path):
    copy = tmp_path / "powerbi"
    shutil.copytree(ROOT / "powerbi", copy)
    visual = next(copy.glob(f"{NAME}.Report/definition/pages/*/visuals/*/visual.json"))
    text = visual.read_text(encoding="utf-8").replace('"Property": "', '"Property": "Missing ', 1)
    visual.write_text(text, encoding="utf-8")
    assert any("not in model" in p for p in problems(copy, NAME))


def test_dax_reader():
    cols, meas = dax_references(
        'CALCULATE ( [Receipts], t[status] = "x [y]" ) -- [comment]\n+ \'d Cal\'[date]')
    assert cols == {("t", "status"), ("d Cal", "date")}
    assert meas == {"Receipts"}


def test_measures_live_in_display_folders():
    tables, _ = read_model(ROOT / "powerbi" / f"{NAME}.SemanticModel")
    measures = {m for t in tables.values() for m in t["measures"]}
    tmdl = "".join(p.read_text(encoding="utf-8") for p in
                   (ROOT / "powerbi" / f"{NAME}.SemanticModel" / "definition" / "tables").glob("*.tmdl"))
    assert tmdl.count("displayFolder:") >= len(measures)


def test_two_pages_and_all_json_valid():
    pages = json.loads((ROOT / "powerbi" / f"{NAME}.Report" / "definition" / "pages" / "pages.json")
                       .read_text(encoding="utf-8"))
    assert len(pages["pageOrder"]) == 2
    for f in (ROOT / "powerbi").rglob("*.json"):
        json.loads(f.read_text(encoding="utf-8"))


@pytest.mark.skipif(not SCHEMAS.exists(), reason="clone microsoft/json-schemas to run this check")
def test_report_matches_microsoft_schemas():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_pbir.py"), str(SCHEMAS)],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "0 schema errors" in out.stdout
