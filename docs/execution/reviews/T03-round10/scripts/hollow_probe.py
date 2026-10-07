"""Reviewer's own F-04 / F-10 probe: splice the hollowed guard test into the gate in memory and judge.

Nothing on disk is modified; sources are read, mutated in a dict, re-hashed, and evaluated.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
GATE = ROOT / "tests/engineering/T03/check_session_cookie.py"
HOLLOW = ROOT / "tests/engineering/T03/.work/hollowed-guard-test.java"

spec = importlib.util.spec_from_file_location("t03_gate", str(GATE))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

base = g.read_sources()
hollow = HOLLOW.read_text(encoding="utf-8")
print("hollow file bytes", len(HOLLOW.read_bytes()), "live guardTest bytes", len(base["guardTest"]))
print("live @Test count", base["guardTest"].count("@Test"), "hollow @Test count", hollow.count("@Test"))
print("live assert count", base["guardTest"].count("assert"), "hollow assert count", hollow.count("assert"))

cases = []
cases.append(("hollowed bodies (F-04)", {"guardTest": hollow}))
cases.append(("drop assembly cases only", {"guardTest": "\n".join(
    l for l in base["guardTest"].splitlines() if "assembledIdentitySecurity" not in l)}))
cases.append(("guard call replaced by a string recital", {"code": base["code"].replace(
    "        verifySessionCookieContract(env);", '        String recital = "verifySessionCookieContract(env);', 1)}))

for label, patch in cases:
    mutated = dict(base)
    mutated.update(patch)
    try:
        mutated = g.rehash_record(mutated)
    except Exception as failure:
        print("\n[%s] rehash failed: %s" % (label, failure))
        continue
    try:
        g.evaluate(mutated)
        print("\n[%s] ACCEPTED  <-- no gate noticed this" % label)
    except g.Rejected as rejection:
        print("\n[%s] REJECTED: %s" % (label, str(rejection)[:230]))
    except AssertionError as failure:
        print("\n[%s] control-style assertion failure: %s" % (label, str(failure)[:200]))
    except Exception as failure:
        print("\n[%s] crashed %s: %s" % (label, type(failure).__name__, str(failure)[:200]))

print()
print("NEGATIVE_CONTROLS", len(g.NEGATIVE_CONTROLS), "BENIGN_PROBES", len(g.BENIGN_PROBES))
names = [c[0] for c in g.NEGATIVE_CONTROLS]
print("hollow-ish controls:", [n for n in names if "hollow" in n or "prose" in n or "role" in n])
print("benign halves for else/try/switch:", [p[0] for p in g.BENIGN_PROBES if any(
    k in p[0] for k in ("else", "finally", "switch", "try"))])
