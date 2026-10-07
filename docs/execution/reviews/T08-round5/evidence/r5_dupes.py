"""Round-5 reviewer: chase the two loose ends the inventory turned up.

1. The 66-entry reversal inventory produced 68 distinct (file, old, new) triples and exactly ONE repeated triple.
   Print the two entries that carry it, in full, so "duplicate counting" can be judged rather than assumed: if one
   weakening appears twice under two labels, 66 overstates the coverage.
2. Reconcile the commit message's "130 mismatched files" with my own sweep, file by file: which recorded files
   carry CRLF on disk, which of them existed at `fb62212`, which diverged there, and which are new since.
"""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(r'E:/project/codex/wxAgent')


def git(args):
    proc = subprocess.run(['git', '-C', str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SystemExit('git %s exit=%d %r' % (' '.join(args[:4]), proc.returncode, proc.stderr[:200]))
    return proc.stdout


sys.path.insert(0, str(REPO / 'tests/engineering/T08'))
import verify  # noqa: E402

out = {}
rev = verify.reversals()
triples = {}
for spec in rev:
    edits = spec.get('edits') or [(spec.get('old', ''), spec.get('new', ''))]
    for old, new in edits:
        triples.setdefault((str(spec['path']), old, new), []).append(spec['name'])
dupes = {k: v for k, v in triples.items() if len(v) > 1}
out['duplicateTriples'] = [{'file': Path(k[0]).name, 'old': k[1][:400], 'new': k[2][:400], 'entries': v}
                           for k, v in dupes.items()]
out['entriesTotal'] = len(rev)
out['triplesTotal'] = sum(len(e.get('edits') or [1]) for e in rev)
out['multiEditEntries'] = [{'name': s['name'], 'edits': len(s['edits'])} for s in rev if s.get('edits')]

# Evidence-fidelity reconciliation.
recorded = [p for p in git(['ls-files', '--', 'tests/engineering']).decode('utf-8').splitlines()
            if ('/evidence/' in p or '-test-results/' in p or p.startswith('tests/engineering/output/'))]
pre_names = set(git(['ls-tree', '-r', '--name-only', 'fb62212', 'tests/engineering']).decode('utf-8').splitlines())
head_names = set(git(['ls-tree', '-r', '--name-only', 'HEAD', 'tests/engineering']).decode('utf-8').splitlines())
crlf, diverge_pre, new_since_pre, missing = [], [], [], []
for path in recorded:
    disk = REPO / path
    if not disk.is_file():
        missing.append(path)
        continue
    raw = disk.read_bytes()
    head_sha = hashlib.sha256(git(['cat-file', 'blob', 'HEAD:' + path])).hexdigest()
    if b'\r\n' in raw:
        crlf.append(path)
    if path not in pre_names:
        new_since_pre.append(path)
        continue
    pre_sha = hashlib.sha256(git(['cat-file', 'blob', 'fb62212:' + path])).hexdigest()
    if pre_sha != hashlib.sha256(raw).hexdigest():
        diverge_pre.append({'path': path, 'headFixed': head_sha == hashlib.sha256(raw).hexdigest()})
out['recordedTracked'] = len(recorded)
out['recordedCrlfOnDisk'] = len(crlf)
out['recordedCrlfAddedSincePreFix'] = [p for p in crlf if p in set(new_since_pre)]
out['divergentAtPreFix'] = len(diverge_pre)
out['divergentAtPreFixAllFixedAtHead'] = all(d['headFixed'] for d in diverge_pre)
out['notPresentAtPreFix'] = len(new_since_pre)
out['missingOnDisk'] = missing
# And: of the CRLF-bearing files, how many did the pre-fix commit store normalized (the damage set)?
crlf_set = set(crlf)
out['crlfAndDivergentAtPre'] = sum(1 for d in diverge_pre if d['path'] in crlf_set)
print(json.dumps(out, ensure_ascii=False, indent=2))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
