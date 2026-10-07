"""Preserve the controlled artefacts as they currently stand (a third party rewrote them during my run).

Then re-run the recorder once, alone, and report before/after for that single run only.
"""
import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
KEEP = ROOT / "docs/execution/reviews/T03-round10/logs/foreign-0658"
PY = sys.executable
FILES = ["tests/engineering/T03/evidence/guard-test-binding.json",
         "tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml",
         "tests/engineering/T03/evidence/T03SessionCookieGuardTest.txt",
         "tests/engineering/T03/evidence/config-census.txt"]

KEEP.mkdir(parents=True, exist_ok=True)
print("== now:", time.strftime("%Y-%m-%d %H:%M:%S"))
for f in FILES:
    p = ROOT / f
    st = p.stat()
    b = p.read_bytes()
    print("%-62s %7d %s mtime=%s" % (f, len(b), hashlib.sha256(b).hexdigest()[:12],
                                     time.strftime("%H:%M:%S", time.localtime(st.st_mtime))))
    shutil.copyfile(p, KEEP / Path(f).name)
head = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), stdout=subprocess.PIPE)
print(head.stdout.decode("utf-8", "replace"))
proc = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe", "/FO", "TABLE"], stdout=subprocess.PIPE)
print(proc.stdout.decode("utf-8", "replace"))

print("== re-running recorder (alone) ==")
run = subprocess.run([PY, "tests/engineering/T03/record_guard_binding.py", "--jdk", ".tools/t02/jdk-21.0.12.1+1"],
                     cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = run.stdout
(KEEP.parent / "recorder-run2.log").write_bytes(out)
print("exit =", run.returncode, "bytes =", len(out), "sha =", hashlib.sha256(out).hexdigest()[:12])
text = out.decode("utf-8", "replace")
print(text[-2500:])
print("== after ==")
for f in FILES:
    p = ROOT / f
    b = p.read_bytes()
    print("%-62s %7d %s" % (f, len(b), hashlib.sha256(b).hexdigest()[:12]))
