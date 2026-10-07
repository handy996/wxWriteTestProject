"""Round-10 reviewer: decompose the 305/149 reading of the full offline verify, from the surefire XMLs."""
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
REPORTS = ROOT / "backend/target/surefire-reports"
log = ROOT / "docs/execution/reviews/T03-round10/logs/full-verify-round10.log"
raw = log.read_bytes()
print("log bytes", len(raw), "lines", len(raw.decode("utf-8", "replace").splitlines()))
print("log mtime", time.strftime("%H:%M:%S", time.localtime(log.stat().st_mtime)))
text = raw.decode("utf-8", "replace")
print("first line:", text.splitlines()[0][:120])
for pat in ("Apache Maven", "Tests run: 305", "BUILD SUCCESS", "Total time", "makeAggregateBom",
            "Results:"):
    print("contains", pat, ":", pat in text)

rows = []
total = Counter()
for xml in sorted(REPORTS.glob("TEST-*.xml")):
    suite = ET.parse(xml).getroot()
    counts = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
    total.update(counts)
    skips = [(c.get("name"), (c.find("skipped").get("message") or "") if c.find("skipped") is not None else "")
             for c in suite.iter("testcase") if c.find("skipped") is not None]
    rows.append((suite.get("name"), counts, skips))

print("\nexecuted totals from XMLs:", dict(total), " executed =", total["tests"] - total["skipped"])
print("\nper class (tests/failures/errors/skipped):")
for name, c, skips in rows:
    if c["skipped"]:
        print("  %-62s %3d/%d/%d/%3d" % (name, c["tests"], c["failures"], c["errors"], c["skipped"]))
print("\nper class with NO skips:")
for name, c, skips in rows:
    if not c["skipped"]:
        print("  %-62s %3d/%d/%d/%3d" % (name, c["tests"], c["failures"], c["errors"], c["skipped"]))
print("\nskipped messages (dedup):")
seen = Counter()
for name, c, skips in rows:
    for case, msg in skips:
        seen[re.sub(r"\s+", " ", msg)[:160]] += 1
for msg, n in seen.most_common(20):
    print("  %3d  %s" % (n, msg or "<empty message attribute>"))
print("\nguard test suite state:")
for name, c, skips in rows:
    if "T03SessionCookieGuardTest" in name:
        print("  ", name, c, "cases:", len([x for x in ET.parse(str(REPORTS / ("TEST-" + name + ".xml"))).getroot()
                                           .iter("testcase")]))
