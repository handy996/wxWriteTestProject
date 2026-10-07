#!/usr/bin/env python3
"""Independent reviewer gate runner for T08 round 1.

Runs the three mandated reproduction commands, records argv / exit code / counts / failure summary only
(no log bodies), and merges the result into evidence/checks.json. Writes nothing outside its own directory.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE = HERE / "evidence" / "checks.json"

GATES = [
    ("t08_pg_suite", [sys.executable, "tests/engineering/T08/run_pg.py",
                      "--evidence-name", "t08-r1-reviewer1"],
     {"expectExit": 0, "expectTotals": {"tests": 40, "failures": 0, "skipped": 0}}),
    ("t08_static_verify", [sys.executable, "tests/engineering/T08/verify.py"],
     {"expectExit": 0, "expectLine": r"T08 static checks: (\d+)/(\d+) passed"}),
    ("t02_contract_hashes", [sys.executable, "tests/engineering/T02/check_contracts.py"],
     {"expectExit": 0, "expectLine": r"(\d+) hashes verified"}),
]


def summary(text: str, limit: int = 400) -> str:
    """Keep counts, exit codes and the shortest failure hint - never a whole-file or full-log snapshot."""
    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    tail = " | ".join(lines[-6:])
    return tail[-limit:]


def run(name: str, argv: list[str], rules: dict) -> dict:
    started = time.time()
    proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out, err = proc.stdout or "", proc.stderr or ""
    record = {"argv": argv, "exitCode": proc.returncode, "seconds": round(time.time() - started, 1),
              "expectExit": rules["expectExit"], "stdoutTail": summary(out), "stderrTail": summary(err)}
    match = re.search(rules.get("expectLine", r"$^"), out)
    if match:
        record["counts"] = list(match.groups())
    if "expectTotals" in rules:
        evidence = ROOT / "tests/engineering/T08/evidence" / (argv[-1] + ".json")
        if evidence.is_file():
            data = json.loads(evidence.read_text(encoding="utf-8"))
            record["totals"] = data.get("totals")
            record["mode"] = data.get("mode")
            record["costTriggers"] = data.get("costTriggers")
            record["suites"] = [{"suite": s["suite"], "tests": s["tests"], "failures": s["failures"],
                                 "errors": s["errors"], "skipped": s["skipped"]} for s in data.get("suites", [])]
            record["clusterStopped"] = data.get("clusterStopped")
        else:
            record["totals"] = None
            record["evidenceWritten"] = False
        record["reproduced"] = record.get("totals") == rules["expectTotals"] and proc.returncode == 0
    failure = re.search(r"^(.*(?:Error|Exception|Traceback).*)$", err or out, re.M)
    if failure and proc.returncode != 0:
        record["failureSummary"] = failure.group(1).strip()[:200]
    record["asClaimed"] = proc.returncode == rules["expectExit"]
    return record


def main() -> int:
    worktree = subprocess.run(["git", "status", "--porcelain=v1"], cwd=str(ROOT), capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout.splitlines()
    dirty = [line for line in worktree if not line.startswith("?? ")]
    untracked = [line for line in worktree if line.startswith("?? ")]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()
    payload = {"task": "T08 round-1 independent review - gate reproduction",
               "reviewer": "independent-review-agent-1", "head": head,
               "modifiedTrackedFiles": dirty, "untrackedFiles": untracked,
               "note": "reviewer never stages, commits, pushes or edits a tracked file",
               "gates": {}}
    for name, argv, rules in GATES:
        payload["gates"][name] = run(name, argv, rules)
        print(f"{name}: exit={payload['gates'][name]['exitCode']} "
              f"counts={payload['gates'][name].get('counts')} "
              f"totals={payload['gates'][name].get('totals')} "
              f"reproduced={payload['gates'][name].get('reproduced')}")
    EVIDENCE.parent.mkdir(exist_ok=True)
    merged = {}
    if EVIDENCE.is_file():
        merged = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    merged.update(payload)
    try:
        EVIDENCE.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("evidence:", EVIDENCE.relative_to(ROOT))
    except OSError as blocked:
        print(f"evidence write blocked ({type(blocked).__name__}); JSON follows on stdout")
        print("===JSON-BEGIN===")
        print(json.dumps(payload, ensure_ascii=False))
        print("===JSON-END===")
    blocked = [name for name, gate in payload["gates"].items() if not gate["asClaimed"]]
    print("gates not as claimed:", blocked or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
