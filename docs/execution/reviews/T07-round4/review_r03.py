"""Fourth-round independent verification of T07-R03 (session authentication in the additive DiffPage contract).

Written from scratch for this review. It does NOT import or reuse any function from
tests/engineering/T07/verify_diff_page.py; the guard and the negative controls below are
this reviewer's own implementation. Output is compact JSON on stdout only (the round-4
sandbox forbids child processes from writing under docs/).

Effective-security semantics: operation-level declaration first, otherwise root — the
same resolution used by round-3 check_review.py lines 44-49.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests" / "engineering" / "integration" / ".work" / "schema-deps"))
import yaml  # noqa: E402

ADDITIONAL = ROOT / "docs/api/diff-pages-v1.1.openapi.yaml"
FROZEN = ROOT / "docs/api/openapi.yaml"
SCHEMA_RC3 = ROOT / "docs/schemas/editorial.schema.json"
APPROVAL = ROOT / "docs/execution/reviews/T00-rc3-approval.json"
HTTP_TEST = ROOT / "docs/execution/reviews/T07-round3/ReviewDiffHttpTest.java"
R3_FINAL = ROOT / "docs/execution/reviews/T07-round3/evidence/final.json"
METHODS = ("get", "put", "post", "patch", "delete", "head", "options", "trace")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operations(doc):
    for route, item in doc.get("paths", {}).items():
        for method, op in item.items():
            if method in METHODS and isinstance(op, dict):
                yield route, method, op


def effective_security(doc, op):
    """Operation first, else root (round-3 semantics)."""
    return op.get("security", doc.get("security"))


def guard(doc, frozen):
    """Independent authentication-contract guard. Returns a list of problems; empty means pass.

    Asserts, for every operation: effective security == frozen root security (dict equality),
    and every referenced scheme is FULLY dict-equal to the frozen definition — an extra key,
    a missing key, or a changed type/in/name all fail.
    """
    problems = []
    frozen_security = frozen.get("security")
    if not isinstance(frozen_security, list) or len(frozen_security) != 1 or not isinstance(frozen_security[0], dict) or len(frozen_security[0]) != 1:
        return ["frozen root security is not exactly one single-scheme requirement"]
    frozen_schemes = frozen.get("components", {}).get("securitySchemes", {})
    ops = list(operations(doc))
    if not ops:
        problems.append("additive spec declares no operations")
    for route, method, op in ops:
        eff = effective_security(doc, op)
        if eff != frozen_security:
            problems.append(f"{route} {method.upper()}: effective security {eff!r} != frozen {frozen_security!r}")
        declared = doc.get("components", {}).get("securitySchemes", {})
        for req in (eff or []):
            if not isinstance(req, dict) or len(req) != 1:
                problems.append(f"{route} {method.upper()}: malformed security requirement {req!r}")
                continue
            name = next(iter(req))
            actual, expected = declared.get(name), frozen_schemes.get(name)
            if expected is None:
                problems.append(f"frozen contract itself lacks scheme '{name}'")
            elif actual != expected:
                problems.append(f"{route} {method.upper()}: scheme '{name}' is {actual!r}, must be dict-equal to frozen {expected!r}")
            else:
                for key in ("type", "in", "name"):
                    if actual.get(key) != expected[key]:
                        problems.append(f"{route} {method.upper()}: scheme '{name}'.{key} mismatch")
    return problems


def main():
    result = {"verdict": "PASS", "failures": []}

    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    spec = yaml.safe_load(ADDITIONAL.read_text(encoding="utf-8"))

    # Structure sanity: the fix must not have broken the OpenAPI document.
    try:
        import openapi_spec_validator
        openapi_spec_validator.validate_spec(spec)
        result["openapiStructureValid"] = True
    except Exception as error:  # noqa: BLE001
        result["openapiStructureValid"] = False
        result["failures"].append(f"openapi structure: {error}")

    # Item 1: effective security + dict-exact scheme equality on the real document.
    problems = guard(spec, frozen)
    root = spec.get("security")
    observations = []
    for route, method, op in operations(spec):
        declared = op.get("security", None)
        observations.append({
            "route": route,
            "method": method.upper(),
            "declaredAt": "operation" if "security" in op else ("root" if root is not None else "absent"),
            "effectiveSecurity": effective_security(spec, op),
            "operationLevelSecurity": declared,
        })
    result["authentication"] = {
        "frozenSecurity": frozen.get("security"),
        "frozenSessionScheme": frozen.get("components", {}).get("securitySchemes", {}).get("session"),
        "additiveRootSecurity": root,
        "additiveSessionScheme": spec.get("components", {}).get("securitySchemes", {}).get("session"),
        "operations": observations,
        "problems": problems,
    }
    if problems:
        result["failures"].append("guard on delivered document: " + "; ".join(problems))

    # Item 3: negative controls. Every weakening applied IN MEMORY to a deep copy must be rejected.
    def drop_root(doc):
        doc.pop("security", None)

    def drop_scheme(doc):
        doc["components"]["securitySchemes"].pop("session", None)

    def in_header(doc):
        doc["components"]["securitySchemes"]["session"]["in"] = "header"

    def anonymous(doc):
        doc["security"] = []

    def extra_key(doc):
        doc["components"]["securitySchemes"]["session"]["description"] = "extra"

    def operation_override_empty(doc):
        doc["paths"]["/api/v1/articles/{id}/diff/pages"]["get"]["security"] = []

    controls = {}
    for label, mutate in {
        "drop-root-security": drop_root,
        "drop-session-scheme": drop_scheme,
        "scheme-in-header": in_header,
        "anonymous-security-list": anonymous,
        "scheme-extra-key": extra_key,
        "operation-level-empty-override": operation_override_empty,
    }.items():
        candidate = copy.deepcopy(spec)
        mutate(candidate)
        rejected_problems = guard(candidate, frozen)
        controls[label] = {"rejected": bool(rejected_problems), "firstProblem": rejected_problems[0] if rejected_problems else None}
        if not rejected_problems:
            result["failures"].append(f"negative control ACCEPTED: {label} — guard is ineffective")
    result["negativeControls"] = controls

    # Item 4: independent hash cross-check against the T00 rc.3 approval record.
    hashes = {
        "docs/api/openapi.yaml": sha(FROZEN),
        "docs/schemas/editorial.schema.json": sha(SCHEMA_RC3),
        "docs/api/diff-pages-v1.1.openapi.yaml": sha(ADDITIONAL),
        "tests/engineering/T07/verify_diff_page.py": sha(ROOT / "tests/engineering/T07/verify_diff_page.py"),
        "docs/execution/reviews/T07-round3/ReviewDiffHttpTest.java": sha(HTTP_TEST),
    }
    result["sha256"] = hashes
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    recorded = {entry["path"]: entry["sha256"] for entry in approval["files"]}
    crosscheck = {}
    for path in ("docs/api/openapi.yaml", "docs/schemas/editorial.schema.json"):
        match = recorded.get(path) == hashes[path]
        crosscheck[path] = {"approvalRecorded": recorded.get(path), "recomputed": hashes[path], "match": match}
        if not match:
            result["failures"].append(f"frozen bytes changed: {path}")
    crosscheck["docs/api/diff-pages-v1.1.openapi.yaml"] = {
        "inApprovalManifest": "docs/api/diff-pages-v1.1.openapi.yaml" in recorded,
        "note": "additive v1.1 file is outside the T00 rc.3 approved set by design",
    }
    if crosscheck["docs/api/diff-pages-v1.1.openapi.yaml"]["inApprovalManifest"]:
        result["failures"].append("additive contract unexpectedly listed in rc.3 approval")
    result["frozenCrosscheck"] = crosscheck

    # Item 6 support: the round-3 HTTP test bytes must still equal the copy that was executed.
    final = json.loads(R3_FINAL.read_text(encoding="utf-8"))
    executed = [e for e in final.get("executedInputs", [])
                if isinstance(e, dict) and str(e.get("path", "")).replace("\\", "/").endswith("ReviewDiffHttpTest.java")]
    if executed:
        match = executed[0]["sha256"] == hashes["docs/execution/reviews/T07-round3/ReviewDiffHttpTest.java"]
        result["round3HttpTest"] = {"executedCopySha": executed[0]["sha256"], "worktreeSha": hashes["docs/execution/reviews/T07-round3/ReviewDiffHttpTest.java"], "match": match}
        if not match:
            result["failures"].append("ReviewDiffHttpTest.java differs from the round-3 executed copy")
    else:
        result["round3HttpTest"] = {"error": "executed copy fingerprint not found in round-3 final.json"}

    result["verdict"] = "PASS" if not result["failures"] else "FAIL"
    print(json.dumps(result, ensure_ascii=False, default=str))
    raise SystemExit(bool(result["failures"]))


if __name__ == "__main__":
    main()
