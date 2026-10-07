"""Reviewer's field-level comparison of two gate evidence files (same criteria check)."""
import json
import sys
from pathlib import Path

ROOT = Path("E:/project/codex/wxAgent")
EV = ROOT / "tests/engineering/T03/evidence"
a_name, b_name = sys.argv[1], sys.argv[2]


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


a = json.loads((EV / ("session-cookie-%s.json" % a_name)).read_bytes())
b = json.loads((EV / ("session-cookie-%s.json" % b_name)).read_bytes())
fa, fb = shape(a), shape(b)
diff = [(k, fa.get(k), fb.get(k)) for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
print("%s vs %s: flat leaf fields %d / %d, differing %d" % (a_name, b_name, len(fa), len(fb), len(diff)))
for k, x, y in diff[:30]:
    print("   ", k, "|", str(x)[:70], "|", str(y)[:70])
print("verdict %s = %s | verdict %s = %s" % (a_name, a.get("verdict"), b_name, b.get("verdict")))
for key in ("summary", "controls", "probes"):
    if key in a:
        print(key, "A:", json.dumps(a[key], ensure_ascii=False)[:200])
        print(key, "B:", json.dumps(b.get(key), ensure_ascii=False)[:200])
