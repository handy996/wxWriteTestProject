"""Reviewer's recorder run: state before -> run -> state after -> gate still 0.

Writes nothing except the retained logs; the recorder itself rewrites the controlled artefacts by design.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
PY = sys.executable
LOGS = ROOT / "docs/execution/reviews/T03-round10/logs"
FILES = ["tests/engineering/T03/evidence/guard-test-binding.json",
         "tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml",
         "tests/engineering/T03/evidence/T03SessionCookieGuardTest.txt",
         "tests/engineering/T03/evidence/config-census.txt"]
TARGET = "backend/target/t03-config-census.txt"
REPORT = "backend/target/surefire-reports/com.example.editorial.identity.T03SessionCookieGuardTest.txt"


def stamp(tag):
    print("== " + tag + " ==")
    for f in FILES + [TARGET, REPORT]:
        p = ROOT / f
        if not p.exists():
            print("%-70s ABSENT" % f)
            continue
        b = p.read_bytes()
        print("%-70s %7d %s" % (f, len(b), hashlib.sha256(b).hexdigest()[:12]))
    st = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), stdout=subprocess.PIPE)
    print("git status:", st.stdout.decode("utf-8", "replace").strip().replace("\r\n", " | "))


stamp("BEFORE recorder")
proc = subprocess.run([PY, "tests/engineering/T03/record_guard_binding.py", "--jdk", ".tools/t02/jdk-21.0.12.1+1"],
                      cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = proc.stdout or b""
(LOGS / "recorder-run.log").write_bytes(out)
print("recorder exit =", proc.returncode, "logBytes =", len(out),
      "logSha =", hashlib.sha256(out).hexdigest()[:12])
print(out.decode("utf-8", "replace"))
stamp("AFTER recorder")

gate = subprocess.run([PY, "tests/engineering/T03/check_session_cookie.py", "--output",
                       "tests/engineering/T03/evidence/session-cookie-r10c.json"],
                      cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
gout = gate.stdout or b""
(LOGS / "gate-r10c-after-recorder.log").write_bytes(gout)
print("gate-after exit =", gate.returncode, "logBytes =", len(gout),
      "logSha =", hashlib.sha256(gout).hexdigest()[:12])
print(gout.decode("utf-8", "replace"))
sys.exit(0)
