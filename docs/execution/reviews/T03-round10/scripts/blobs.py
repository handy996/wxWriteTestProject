import hashlib
import subprocess
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
FILES = ["tests/engineering/T03/check_session_cookie.py",
         "tests/engineering/T03/record_guard_binding.py",
         "tests/engineering/T03/evidence/T03SessionCookieGuardTest.txt",
         "tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml",
         "tests/engineering/T03/evidence/guard-test-binding.json",
         "backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java",
         "tests/engineering/T03/evidence/config-census.txt",
         "tests/engineering/T03/evidence/session-cookie-r10.json"]


def blob(rev, f):
    p = subprocess.run(["git", "rev-parse", "%s:%s" % (rev, f)], cwd=str(ROOT),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        return None
    sha = p.stdout.decode().strip()
    size = subprocess.run(["git", "cat-file", "-s", sha], cwd=str(ROOT), stdout=subprocess.PIPE)
    try:
        return sha[:12] + "/" + str(int(size.stdout.decode().strip()))
    except ValueError:
        return sha[:12]


print("%-72s %-14s %-14s %-14s %s" % ("file", "e4f0f3c", "11a3d7f", "HEAD(cc91998..)", "worktree"))
for f in FILES:
    a = blob("e4f0f3c", f)
    b = blob("11a3d7f", f)
    c = blob("HEAD", f)
    disk = ROOT / f
    d = hashlib.sha256(disk.read_bytes()).hexdigest()[:12] if disk.exists() else None
    wt = subprocess.run(["git", "hash-object", f], cwd=str(ROOT), stdout=subprocess.PIPE).stdout.decode().strip()[:12]
    print("%-72s %-14s %-14s %-14s disk=%s hash-object=%s" % (f, a, b, c, d, wt))

print()
print("worktree == 11a3d7f blob?", all(
    blob("11a3d7f", f).split("/")[0] == subprocess.run(["git", "hash-object", f], cwd=str(ROOT),
                                            stdout=subprocess.PIPE).stdout.decode().strip()[:12]
    for f in FILES if (ROOT / f).exists() and blob("11a3d7f", f)))

print()
print("== committed injection JSON internal name self-reference ==")
import json
j = json.loads((ROOT / "tests/engineering/integration/evidence/r10-wrong-cookie-inject.json").read_text(encoding="utf-8"))
for k in ("mode", "exitCode", "isolatedWork", "testResults", "samples", "injections"):
    print("  ", k, "=", j.get(k))
print("   commands =", len(j["commands"]), "executedInputs =", len(j["executedInputs"]))
print("   producedBy-ish keys:", [k for k in j if "roduc" in k or "wen" in k])
m = json.loads((ROOT / "tests/engineering/integration/evidence/r10-review-round10.json").read_text(encoding="utf-8"))
for k in ("isolatedWork", "testResults", "samples"):
    print("   MINE", k, "=", m.get(k))
import re
hits = re.findall(r"integration[-\w]*", json.dumps(j))
print("   'integration*' strings inside committed JSON:", sorted(set(hits))[:10])
