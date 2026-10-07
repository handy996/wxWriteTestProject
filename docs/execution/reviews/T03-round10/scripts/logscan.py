import hashlib
import re
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
LOGS = ROOT / "docs/execution/reviews/T03-round10/logs"
for name in ("recorder-run.log", "gate-r10c-after-recorder.log", "foreign-0658/recorder-run2.log"):
    p = LOGS / name
    if not p.exists():
        print("==", name, "ABSENT")
        continue
    b = p.read_bytes()
    t = b.decode("utf-8", "replace")
    print("==", name, len(b), hashlib.sha256(b).hexdigest()[:12], "mtime",
          re.sub(r"\s", "T", str(__import__("time").strftime("%H:%M:%S", __import__("time").localtime(p.stat().st_mtime)))))
    for pat in ("recorder exit", "Tests run: 15, Failures", "not clean", "expected artefact", '"exitCode"',
                "contractNameBinds", "BUILD FAILURE", "BUILD SUCCESS", "REFUSE", "refusing"):
        hits = [m.start() for m in re.finditer(re.escape(pat), t)]
        if hits:
            print("   %-24s %d hits at %s" % (pat, len(hits), hits[:6]))
    print("   first 3 lines:", " /// ".join(t.splitlines()[:3])[:220])
    print("   last 3 lines:", " /// ".join(t.splitlines()[-3:])[:220])
