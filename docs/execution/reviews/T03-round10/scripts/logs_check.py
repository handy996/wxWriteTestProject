import hashlib
import re
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
LOGS = ROOT / "docs/execution/reviews/T03-round10/logs"
for name in ("full-verify-round10.log", "inject-r10-review-round10.log", "check-contracts.log",
             "gate-plain-run1.log", "gate-r10b.log", "gate-r10c-after-recorder.log",
             "recorder-run.log", "recorder-run2.log"):
    p = LOGS / name
    if not p.exists():
        print("ABSENT", name)
        continue
    b = p.read_bytes()
    t = b.decode("utf-8", "replace")
    print("%-34s %7d %s lines=%-5d BOM=%s CRLF=%s" % (name, len(b), hashlib.sha256(b).hexdigest()[:12],
                                                      len(t.splitlines()), b[:3] == b"\xef\xbb\xbf", b"\r\n" in b))
    print("     Running=%d Tests-run=%d BUILD-SUCCESS=%s FAILURE=%s 'Tests run: 305'=%s" % (
        len(re.findall(r"Running com\.example", t)), len(re.findall(r"Tests run:", t)),
        "BUILD SUCCESS" in t, "BUILD FAILURE" in t, "Tests run: 305" in t))

v = (LOGS / "full-verify-round10.log").read_text(encoding="utf-8", errors="replace")
print("\nverify log: classes listed =", sorted(set(re.findall(r"Running (com\.example[\w.]+)", v)))[:40].__len__())
print("errors=0 failures=0 line:", [l.strip() for l in v.splitlines() if "Tests run: 305" in l])
print("skipped-goal warning:", [l.strip() for l in v.splitlines() if "online mode" in l])
print("tail:", v.splitlines()[-4:])
