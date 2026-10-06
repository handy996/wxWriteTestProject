"""Session cookie name consistency across contract, config, code and tests (rc.3 EDITORIAL_SESSION).

Zero third-party dependencies. The frozen OpenAPI is JSON-syntax YAML so json.loads reads it
directly; the additive paged-Diff document is plain block YAML, so it is read with a small
indentation scanner over the two blocks we care about (`security` and `securitySchemes`) instead
of pulling in pyyaml. Closes T07-R04: both contracts declared EDITORIAL_SESSION while the server
set no cookie name, so runtime silently issued the container default JSESSIONID and any client
generated from the contract would have been rejected with 401 on every route.

Negative controls mutate the loaded sources **in memory only** — the approved rc.3 files are never
written to, not even temporarily.

Usage: python tests/engineering/T03/check_session_cookie.py [--output evidence.json]
Exit 0 when every source agrees; exit 1 with the mismatch printed.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    "frozenContract": ROOT / "docs/api/openapi.yaml",
    "additiveContract": ROOT / "docs/api/diff-pages-v1.1.openapi.yaml",
    "config": ROOT / "backend/src/main/resources/application.yml",
    "configProd": ROOT / "backend/src/main/resources/application-prod.yml",
    "code": ROOT / "backend/src/main/java/com/example/editorial/identity/T03Configuration.java",
}
FORBIDDEN = "JSESSIONID"


def read_sources():
    return {key: path.read_text(encoding="utf-8", errors="replace") for key, path in SOURCES.items()}


def contract_scheme_json(text, label):
    document = json.loads(text)
    schemes = document.get("components", {}).get("securitySchemes", {})
    root = document.get("security") or []
    if len(root) != 1 or len(root[0]) != 1:
        raise AssertionError(f"{label}: root security is not one single-scheme requirement: {root!r}")
    key = next(iter(root[0]))
    if key not in schemes:
        raise AssertionError(f"{label}: root security references undeclared scheme {key!r}")
    return key, schemes[key]


def _block_indent(lines, start):
    for index in range(start, len(lines)):
        line = lines[index].split("#")[0].rstrip()
        if line.strip():
            return len(line) - len(line.lstrip())
    return None


def contract_scheme_yaml(text, label):
    """(schemeKey, {type,in,name,...}) read from a block-YAML OpenAPI document."""
    lines = text.splitlines()
    root = None
    schemes = {}
    for index, raw in enumerate(lines):
        stripped = raw.split("#")[0].rstrip()
        if stripped == "security:":
            indent = _block_indent(lines, index + 1)
            items = []
            for follower in lines[index + 1:]:
                body = follower.split("#")[0].rstrip()
                if not body.strip():
                    continue
                if len(body) - len(body.lstrip()) < indent:
                    break
                match = re.match(r"\s*-\s+(\w+):\s*(.*)$", body)
                if match:
                    items.append({match.group(1): json.loads(match.group(2).replace("'", '"') or "null")})
            root = items
        elif stripped == "  securitySchemes:":
            key = None
            for follower in lines[index + 1:]:
                body = follower.split("#")[0].rstrip()
                if not body.strip():
                    continue
                indent = len(body) - len(body.lstrip())
                if indent <= 2:
                    break
                if indent == 4 and body.endswith(":"):
                    key = body.strip()[:-1]
                    schemes[key] = {}
                elif key and indent == 6:
                    match = re.match(r"\s*(\w+):\s*(.+)$", body)
                    if match:
                        schemes[key][match.group(1)] = match.group(2).strip().strip("'\"")
    if not root or len(root) != 1 or len(root[0]) != 1:
        raise AssertionError(f"{label}: root security is not one single-scheme requirement: {root!r}")
    name = next(iter(root[0]))
    if name not in schemes:
        raise AssertionError(f"{label}: root security references undeclared scheme {name!r}")
    return name, schemes[name]


def config_cookie_name(text):
    """Cookie name set under server.servlet.session.cookie, or None when absent."""
    block = None
    for line in text.splitlines():
        stripped = line.split("#")[0].rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        if stripped.strip() == "cookie:":
            block = indent
            continue
        if block is None:
            continue
        if indent <= block:
            block = None
            continue
        match = re.match(r"\s*name:\s*(\S+)\s*$", stripped)
        if match:
            return match.group(1)
    return None


def code_constant(text):
    match = re.search(r'SESSION_COOKIE_NAME\s*=\s*"([^"]+)"', text)
    if not match:
        raise AssertionError("code: SESSION_COOKIE_NAME constant is missing")
    return match.group(1)


def evaluate(sources):
    """Every declaration of the session cookie name must agree."""
    key, frozen_scheme = contract_scheme_json(sources["frozenContract"], "frozenContract")
    if frozen_scheme.get("type") != "apiKey" or frozen_scheme.get("in") != "cookie":
        raise AssertionError(f"frozenContract: scheme {key!r} must be apiKey/cookie, got {frozen_scheme!r}")
    cookie = frozen_scheme["name"]
    additive_key, additive_scheme = contract_scheme_yaml(sources["additiveContract"], "additiveContract")
    if additive_key != key or additive_scheme != frozen_scheme:
        raise AssertionError(f"additiveContract: {additive_key}={additive_scheme!r} must equal frozen {key}={frozen_scheme!r}")
    configured = config_cookie_name(sources["config"])
    if configured is None:
        raise AssertionError("config: application.yml sets no server.servlet.session.cookie.name; runtime would issue the container default")
    if configured != cookie:
        raise AssertionError(f"config: cookie name {configured!r} != contract {cookie!r}")
    prod = config_cookie_name(sources["configProd"])
    if prod not in (None, cookie):
        raise AssertionError(f"configProd: profile overrides the cookie name with {prod!r}")
    constant = code_constant(sources["code"])
    if constant != cookie:
        raise AssertionError(f"code: constant {constant!r} != contract {cookie!r}")
    return {"schemeKey": key, "frozenScheme": frozen_scheme, "additiveScheme": additive_scheme,
            "configuredCookieName": configured, "prodOverride": prod, "javaConstant": constant}


def negative_control(sources):
    """Prove the guard bites: each weakening, applied in memory, must be rejected."""
    def mutate(label):
        copy = dict(sources)
        if label == "config-drops-cookie-name":
            copy["config"] = re.sub(r"[ \t]*name: EDITORIAL_SESSION\r?\n", "", sources["config"], count=1)
        elif label == "config-changes-cookie-name":
            copy["config"] = sources["config"].replace("name: EDITORIAL_SESSION", "name: " + FORBIDDEN, 1)
        elif label == "contract-renames-cookie":
            copy["frozenContract"] = sources["frozenContract"].replace('"EDITORIAL_SESSION"', '"OTHER_SESSION"', 1)
        elif label == "additive-drops-scheme":
            copy["additiveContract"] = re.sub(r"  securitySchemes:\n(?:    .*\n|      .*\n)+", "", sources["additiveContract"], count=1)
        elif label == "additive-scheme-extra-key":
            copy["additiveContract"] = sources["additiveContract"].replace("      name: EDITORIAL_SESSION",
                                                                           "      name: EDITORIAL_SESSION\n      description: extra", 1)
        elif label == "code-constant-drifts":
            copy["code"] = sources["code"].replace('SESSION_COOKIE_NAME="EDITORIAL_SESSION"', 'SESSION_COOKIE_NAME="' + FORBIDDEN + '"', 1)
        else:
            raise AssertionError(f"unknown mutation {label}")
        return copy

    labels = ("config-drops-cookie-name", "config-changes-cookie-name", "contract-renames-cookie",
              "additive-drops-scheme", "additive-scheme-extra-key", "code-constant-drifts")
    rejected = []
    for label in labels:
        mutated = mutate(label)
        if mutated == sources:
            raise AssertionError(f"negative control {label} changed nothing; it proves nothing")
        try:
            evaluate(mutated)
        except (AssertionError, KeyError, json.JSONDecodeError):
            rejected.append(label)
        else:
            raise AssertionError(f"negative control {label} was accepted; the guard is ineffective")
    evaluate(sources)  # pristine sources must still pass, so controls cannot "pass" by breaking everything
    return sorted(rejected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("output already exists; keep prior evidence")
    sources = read_sources()
    agreement = evaluate(sources)
    rejected = negative_control(sources)
    drift = [str(SOURCES[key].relative_to(ROOT)).replace("\\", "/") for key, text in sources.items() if FORBIDDEN in text]
    if drift:
        raise AssertionError(f"container default {FORBIDDEN} reappears in: {drift}")
    result = {"agreement": agreement, "forbiddenDefault": FORBIDDEN, "forbiddenDefaultInCheckedSources": drift,
              "negativeControlsRejected": rejected,
              "sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in SOURCES.values()},
              "verdict": "PASS"}
    print(json.dumps(result, ensure_ascii=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
