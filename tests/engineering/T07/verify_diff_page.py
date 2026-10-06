"""Validate the additive DiffPage response and OpenAPI without touching T00 rc.3."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import openapi_spec_validator
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "docs/schemas/diff-page-v1.1.schema.json"
OPENAPI = ROOT / "docs/api/diff-pages-v1.1.openapi.yaml"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; keep prior evidence")
    sample = args.sample.resolve(strict=True)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    document = json.loads(sample.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(document)
    spec = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    openapi_spec_validator.validate_spec(spec)
    inline = spec["components"]["schemas"]["DiffPage"]
    assert set(inline["required"]) == set(schema["required"])
    assert set(inline["properties"]) == set(schema["properties"])
    subprocess.run([sys.executable, str(ROOT / "tests/engineering/T02/check_contracts.py")],
                   cwd=ROOT, check=True)
    evidence = {
        "jsonSchemaVersion": version("jsonschema"),
        "schema": {"path": str(SCHEMA.relative_to(ROOT)), "sha256": hashlib.sha256(SCHEMA.read_bytes()).hexdigest()},
        "openapi": {"path": str(OPENAPI.relative_to(ROOT)), "sha256": hashlib.sha256(OPENAPI.read_bytes()).hexdigest()},
        "sample": {"path": str(sample.relative_to(ROOT)), "sha256": hashlib.sha256(sample.read_bytes()).hexdigest()},
        "sampleTotalBlocks": document["totalBlocks"],
        "samplePageSize": len(document["blocks"]),
        "approvedT00Hashes": 27,
        "result": "PASS"
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("DiffPage schema, OpenAPI and T00 rc.3 checks passed")


if __name__ == "__main__":
    main()
