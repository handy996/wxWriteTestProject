"""Validate the additive DiffPage response, OpenAPI and session authentication without touching T00 rc.3."""
import argparse
import copy
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
FROZEN = ROOT / "docs/api/openapi.yaml"
METHODS = ("get", "put", "post", "patch", "delete", "head", "options", "trace")


def sha(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def session_authentication(spec, frozen):
    """Resolve each operation's effective security (operation first, then root) and reject gaps."""
    if len(frozen["security"]) != 1 or len(frozen["security"][0]) != 1:
        raise AssertionError("frozen contract security is not a single scheme requirement")
    name = next(iter(frozen["security"][0]))
    expected = frozen["components"]["securitySchemes"][name]
    declared = spec.get("components", {}).get("securitySchemes", {})
    root = spec.get("security")
    operations = []
    for route, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            effective = operation.get("security", root)
            problems = []
            if effective != frozen["security"]:
                problems.append(f"effective security {effective!r} != frozen contract {frozen['security']!r}")
            for requirement in effective or []:
                for referenced in requirement:
                    if declared.get(referenced) != expected:
                        problems.append(f"scheme '{referenced}' is {declared.get(referenced)!r}, expected {expected!r}")
            operations.append({
                "route": route,
                "method": method.upper(),
                "declaredAt": "operation" if "security" in operation else ("root" if root is not None else "absent"),
                "effectiveSecurity": effective,
                "scheme": declared.get(name),
                "problems": problems,
            })
    if not operations:
        raise AssertionError("no operations found to authenticate")
    gaps = [entry for entry in operations if entry["problems"]]
    if gaps:
        raise AssertionError("session authentication contract not declared: " + json.dumps(gaps, ensure_ascii=False))
    return {"schemeName": name, "frozenSecurity": frozen["security"], "frozenScheme": expected, "operations": operations}


def negative_control(spec, frozen):
    """A guard that cannot fail proves nothing: every weakening must be rejected."""
    def drop_root(document):
        document.pop("security", None)

    def drop_scheme(document):
        document["components"]["securitySchemes"].pop("session", None)

    def wrong_location(document):
        document["components"]["securitySchemes"]["session"]["in"] = "header"

    def anonymous(document):
        document["security"] = []

    rejected = []
    for label, mutate in {"drop-root-security": drop_root, "drop-session-scheme": drop_scheme,
                          "scheme-in-header": wrong_location, "anonymous-security-list": anonymous}.items():
        candidate = copy.deepcopy(spec)
        mutate(candidate)
        try:
            session_authentication(candidate, frozen)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError(f"negative control {label} was accepted; the authentication guard is ineffective")
    return sorted(rejected)


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
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    authentication = session_authentication(spec, frozen)
    rejected = negative_control(spec, frozen)
    subprocess.run([sys.executable, str(ROOT / "tests/engineering/T02/check_contracts.py")],
                   cwd=ROOT, check=True)
    evidence = {
        "jsonSchemaVersion": version("jsonschema"),
        "schema": sha(SCHEMA),
        "openapi": sha(OPENAPI),
        "frozenOpenapi": sha(FROZEN),
        "sample": sha(sample),
        "sampleTotalBlocks": document["totalBlocks"],
        "samplePageSize": len(document["blocks"]),
        "approvedT00Hashes": 27,
        "authentication": authentication,
        "authenticationNegativeControlsRejected": rejected,
        "result": "PASS"
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("DiffPage schema, OpenAPI structure, session authentication (with negative controls) "
          "and T00 rc.3 hashes passed")


if __name__ == "__main__":
    main()
