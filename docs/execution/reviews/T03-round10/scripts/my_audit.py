"""Reviewer's own load-bearing probes, run through the implementer's harness unchanged.

Three stubs the shipped 54-stub roster does not contain, chosen to test one specific claim:
"54 桩，无人看守 0 条". Each stub is a pure loosening (it removes a conclusion, never adds one).
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
HARNESS = ROOT / "tests/engineering/T03/.work/load_bearing.py"

spec = importlib.util.spec_from_file_location("lb", str(HARNESS))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

module.OUT = ROOT / "tests/engineering/T03/.work/r10rev-01/reviewer-audit.json"
module.BUDGET = 900.0
module.DIAGNOSTIC = ()
module.STUBS = [
    # (1) recite a plausible certificate instead of measuring: keeps every demanded field, deletes the measurement.
    ("reviewer-tokenizer-recited", "the projections are actually measured (numbers recited, nothing measured)",
     "def tokenizer_certificate(sources):", None,
     '    return {"sources": [], "corpusFiles": 600, "divergences": 0, "note": "recited, not measured"}'),
    # (2) drop the shell-word / forbidden-executable scan inside argv_check.
    ("reviewer-argv-shell-scan", "no shell word or non-suite executable may appear in the recorded argv",
     "    for part in argv:", "    for part in []:", None),
    # (3) drop the demand that the self-measurement reports its numbers.
    ("reviewer-must-report-numbers", "the tokenizer self-measurement has to report non-empty numbers",
     '    if unfed or not tokenizer["corpusFiles"]:', "    if False:", None),
]
print("harness stubs replaced with reviewer set:", [s[0] for s in module.STUBS], flush=True)
sys.exit(module.main())
