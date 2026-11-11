"""
Validate every PBIR / PBIP JSON file against Microsoft's published JSON schemas.

Needs a local clone of https://github.com/microsoft/json-schemas (only the fabric folder):
    git clone --depth 1 https://github.com/microsoft/json-schemas.git
Usage:  python scripts/validate_pbir.py <path-to-json-schemas-clone>
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1] / "powerbi"
SCHEMAS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("json-schemas")
PREFIX = "https://developer.microsoft.com/json-schemas/"


def retrieve(uri: str):
    path = SCHEMAS / uri.replace(PREFIX, "")
    return Resource.from_contents(json.loads(path.read_text(encoding="utf-8")))


registry = Registry(retrieve=retrieve)
errors = 0
files = [f for f in ROOT.rglob("*.json") if "StaticResources" not in f.parts] + \
        list(ROOT.rglob("*.pbip")) + list(ROOT.rglob("*.pbir")) + list(ROOT.rglob("*.pbism"))
for f in sorted(files):
    doc = json.loads(f.read_text(encoding="utf-8"))
    uri = doc.get("$schema")
    if not uri:
        continue
    schema = retrieve(uri).contents
    v = Draft7Validator(schema, registry=registry)
    errs = list(v.iter_errors(doc))
    for e in errs[:5]:
        print(f"{f.relative_to(ROOT)}: {'/'.join(map(str, e.absolute_path))}: {e.message[:200]}")
    errors += len(errs)
print(f"{len(files)} files checked, {errors} schema errors")
sys.exit(1 if errors else 0)
