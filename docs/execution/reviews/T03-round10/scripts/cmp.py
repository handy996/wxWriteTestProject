"""Compare the shipped r10 gate evidence with my rerun r10b; same criteria or not."""
import hashlib
import json
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
EV = ROOT / "tests/engineering/T03/evidence"
a = json.loads((EV / "session-cookie-r10.json").read_bytes())
b = json.loads((EV / "session-cookie-r10b.json").read_bytes())


def shape(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(shape(v, prefix + k + "."))
        elif isinstance(v, list):
            out[prefix + k] = "list[%d]" % len(v)
        else:
            out[prefix + k] = v
    return out


print("top-level keys r10:", sorted(a))
print("top-level keys r10b:", sorted(b))
fa, fb = shape(a), shape(b)
diff = []
for k in sorted(set(fa) | set(fb)):
    if fa.get(k) != fb.get(k):
        diff.append((k, fa.get(k), fb.get(k)))
print("flat-field count r10=%d r10b=%d" % (len(fa), len(fb)))
print("DIFFERING FIELDS:", len(diff))
for k, x, y in diff[:40]:
    print("  ", k, "|", str(x)[:70], "|", str(y)[:70])
print()
print("summary r10 :", json.dumps(a.get("summary", a.get("verdict")), ensure_ascii=False)[:400])
print("summary r10b:", json.dumps(b.get("summary", b.get("verdict")), ensure_ascii=False)[:400])
for key in ("inputs", "inputSha256", "hashes"):
    if key in a:
        ia, ib = a[key], b.get(key, {})
        same = [k for k in set(ia) | set(ib) if ia.get(k) != ib.get(k)] if isinstance(ia, dict) else None
        print(key, "count", len(ia), "differing", same)
