"""Round-10 reviewer metrics: report text metrics + evidence byte-fidelity against HEAD."""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
PY = sys.executable


def sh(args):
    p = subprocess.run(args, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout


def blob_bytes(revpath):
    p = subprocess.run(["git", "cat-file", "blob", revpath], cwd=str(ROOT), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    return p.returncode, p.stdout


print("== report text metrics ==")
raw = (ROOT / "docs/execution/reports/T03-Revision-R10.md").read_bytes()
text = raw.decode("utf-8")
print("bytes", len(raw))
print("splitlines", len(text.splitlines()))
print("count_nl_plus1", text.count("\n") + 1)
print("BOM", raw[:3] == b"\xef\xbb\xbf")
print("CRLF", b"\r\n" in raw)
pats = {"TODO": r"TODO", "TBD": r"TBD", "placeholder-cn": r"待填|占位|待定", "angle": r"<[A-Za-z_ ]+>",
        "XXX": r"XXX", "FIXME": r"FIXME", "lorem": r"lorem"}
for name, pat in pats.items():
    hits = re.findall(pat, text)
    print("placeholder", name, len(hits), hits[:4])

print()
print("== evidence fidelity: disk vs HEAD blob ==")
files = []
for i in range(1, 11):
    files.append("tests/engineering/T03/evidence/session-cookie-r%02d.json" % i)
files += ["tests/engineering/T03/evidence/guard-test-binding.json",
          "tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml",
          "tests/engineering/T03/evidence/T03SessionCookieGuardTest.txt",
          "tests/engineering/T03/evidence/config-census.txt",
          "tests/engineering/T03/check_session_cookie.py",
          "backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java",
          "backend/src/main/java/com/example/editorial/identity/T03Configuration.java"]
for f in files:
    disk = ROOT / f
    if not disk.exists():
        print("%-72s ABSENT-on-disk" % f)
        continue
    dbytes = disk.read_bytes()
    code, bb = blob_bytes("HEAD:" + f)
    hb = hashlib.sha256(dbytes).hexdigest()
    if code == 0:
        hg = hashlib.sha256(bb).hexdigest()
        same = (dbytes == bb)
        print("%-72s disk=%7d %s | head=%7d %s | equal=%s" % (f, len(dbytes), hb[:12], len(bb), hg[:12], same))
    else:
        print("%-72s disk=%7d %s | NOT-IN-HEAD" % (f, len(dbytes), hb[:12]))

print()
print("== r-prefix facts the task stated ==")
for n, want in (("r08", "6EB8EF60"), ("r09", "F18C88EF"), ("r04", "0"), ("r05", "0"), ("r06", "0"), ("r07", "0"),
                ("r10", "8F1E9CFA1734")):
    p = ROOT / ("tests/engineering/T03/evidence/session-cookie-%s.json" % n)
    if not p.exists():
        print(n, "ABSENT")
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest().upper()
    print(n, len(p.read_bytes()), h[:16], "prefix-matches-task:", (h.startswith(want) if want != "0" else "n/a"))
