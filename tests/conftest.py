import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

SCHEMAS = Path(os.environ.get("PBI_SCHEMAS", ROOT / "json-schemas"))


def run(script, cwd):
    out = subprocess.run([sys.executable, str(Path("scripts") / script)], cwd=cwd,
                         capture_output=True, text=True, check=True)
    return out.stdout


@pytest.fixture(scope="session")
def fresh(tmp_path_factory):
    """Copy the scripts to an empty folder and run them like a user would."""
    work = tmp_path_factory.mktemp("project")
    shutil.copytree(ROOT / "scripts", work / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    logs = {"generate": run("generate_data.py", work), "build": run("build_pbip.py", work)}
    return work, logs


def load(xlsx):
    return pd.read_excel(xlsx, sheet_name=None)
