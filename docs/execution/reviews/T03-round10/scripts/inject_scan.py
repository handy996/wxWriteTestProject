import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
MINE = ROOT / "tests/engineering/integration/evidence/r10-review-round10-test-results/TEST-com.example.editorial.identity.T03PostgresTest.xml"
THEIRS = ROOT / "tests/engineering/integration/evidence/r10-wrong-cookie-inject-test-results/TEST-com.example.editorial.identity.T03PostgresTest.xml"

for tag, path in (("MINE", MINE), ("THEIRS", THEIRS)):
    raw = path.read_text(encoding="utf-8", errors="replace")
    suite = ET.fromstring(path.read_bytes())
    cases = list(suite.iter("testcase"))
    errs = [c for c in cases if c.find("error") is not None]
    print(tag, "bytes", len(raw), "attrs", [suite.get(k) for k in ("tests", "failures", "errors", "skipped")],
          "testcase elems", len(cases), "error elems", len(errs))
    for pat in ("T03_COOKIE", "verifySessionCookieContract", "Failed to load ApplicationContext",
                "failure threshold", "WRONGNAME", "session cookie name must equal", "EDITORIAL_SESSION"):
        print("   %-34s %d" % (pat, raw.count(pat)))
    if errs:
        msg = errs[0].find("error").get("message") or ""
        print("   first failing case:", errs[0].get("name"))
        print("   first message head:", re.sub(r"\s+", " ", msg)[:180])
        hits = re.findall(r"Caused by: [^\r\n]{0,160}", errs[0].find("error").text or "")
        for h in hits[:3]:
            print("   caused-by:", re.sub(r"\s+", " ", h))
