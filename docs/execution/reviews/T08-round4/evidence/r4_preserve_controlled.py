"""T08 round-4 reviewer: preserve, then hand back.

`run_pg.py:389` hard-codes the evidence directory as its own `HERE/'evidence'`, so the pre-interruption
baseline run (`--evidence-name r4-main`) wrote its artefacts into the CONTROLLED directory
`tests/engineering/T08/evidence/` instead of the review directory. The dispatch says: state it, do not
delete controlled sources, hand it back. So this script copies the two entries byte-for-byte into the
review directory and proves the copies match by sha256 — it deletes nothing.
"""
import hashlib
import shutil
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
CONTROLLED = REPO / "tests/engineering/T08/evidence"
MINE = REPO / "docs/execution/reviews/T08-round4/evidence"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def copy_file(name: str) -> None:
    src, dst = CONTROLLED / name, MINE / name
    digest_src, digest_dst = sha256(src), sha256(dst)
    print("%s -> controlled=%s mine=%s match=%s" % (name, digest_src, digest_dst, digest_src == digest_dst))


single = "r4-main.json"
if not (MINE / single).exists():
    shutil.copy2(CONTROLLED / single, MINE / single)
copy_file(single)

tree = "r4-main-test-results"
if not (MINE / tree).exists():
    shutil.copytree(CONTROLLED / tree, MINE / tree)
rows = []
for path in sorted((CONTROLLED / tree).rglob("*")):
    if path.is_file():
        relative = path.relative_to(CONTROLLED)
        other = MINE / relative
        rows.append((relative.as_posix(), sha256(path), sha256(other) if other.exists() else "MISSING"))
print("%s files=%d all-match=%s" % (tree, len(rows), all(a == b for _, a, b in rows)))
for name, a, b in rows:
    print("   %-64s %s %s" % (name, a[:16], "OK" if a == b else "DIFF " + b[:16]))
