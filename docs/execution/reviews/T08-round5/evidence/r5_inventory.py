"""Round-5 reviewer: the pre-fix half of the byte-fidelity check, and the gate-count / reversal inventory.

Two independent tallies:

1. `git add --renormalize` repaired HEAD without rewriting history, so the same recorded files must STILL differ
   from their bytes at `fb62212` (the last pre-fix commit). Whole-class comparison: every tracked recorded file
   that also exists at `fb62212`, disk sha256 vs that commit's blob sha256. Expected: many divergences (history
   keeps the normalized blobs). A reviewer who reads "130 files were wrong" as "130 files are wrong at HEAD"
   would be wrong — this separates the two claims.
2. The 66-entry reverse-control inventory: distinct (file, old, new) rewrite triples, duplicate labels, and how
   many entries name each gate — the "44 → 66 without double counting" question. Plus the CHECKS list: which two
   gates are new, and whether they share any assertion with the pre-existing 14 (the "14 → 16 = two real
   watchers, not one gate split in half" question).
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
        raise SystemExit('git %s exit=%d %r' % (' '.join(args), proc.returncode, proc.stderr[:200]))
    return proc.stdout


out = {}

recorded = [p for p in git(['ls-files', '--', 'tests/engineering']).decode('utf-8').splitlines()
            if ('/evidence/' in p or '-test-results/' in p or p.startswith('tests/engineering/output/'))
            and (REPO / p).is_file()]
pre_names = set(git(['ls-tree', '-r', '--name-only', 'fb62212', 'tests/engineering']).decode('utf-8').splitlines())
compared, divergent, matched = 0, [], []
for path in recorded:
    if path not in pre_names:
        continue
    disk = hashlib.sha256((REPO / path).read_bytes()).hexdigest()
    pre = hashlib.sha256(git(['cat-file', 'blob', 'fb62212:' + path])).hexdigest()
    head = hashlib.sha256(git(['cat-file', 'blob', 'HEAD:' + path])).hexdigest()
    compared += 1
    (divergent if disk != pre else matched).append({'path': path, 'disk': disk, 'pre': pre, 'head': head,
                                                   'headMatchesDisk': disk == head})
out['preFixCompared'] = compared
out['preFixDivergent'] = len(divergent)
out['preFixIdentical'] = len(matched)
out['preFixDivergentButHeadFixed'] = sum(1 for d in divergent if d['headMatchesDisk'])
out['preFixDivergentExamples'] = divergent[:4]
out['preFixIdenticalExamples'] = [m['path'] for m in matched[:4]]
# Sizes, because the commit message cites 318 vs 313 bytes for a dumpstream.
one = next((d for d in divergent if d['path'].endswith('.dumpstream')), None)
out['dumpstreamShape'] = None
if one:
    raw = (REPO / one['path']).read_bytes()
    blob = git(['cat-file', 'blob', 'fb62212:' + one['path']])
    out['dumpstreamShape'] = {'path': one['path'], 'diskBytes': len(raw), 'preBytes': len(blob),
                              'diskCrlf': b'\r\n' in raw, 'preCrlf': b'\r\n' in blob}

sys.path.insert(0, str(REPO / 'tests/engineering/T08'))
import verify  # noqa: E402

out['gateCount'] = len(verify.CHECKS)
out['gateNames'] = [c.__name__ for c in verify.CHECKS]
rev = verify.reversals()
out['reversalCount'] = len(rev)
triples = []
for spec in rev:
    edits = spec.get('edits') or [(spec.get('old', ''), spec.get('new', ''))]
    for old, new in edits:
        triples.append((str(spec['path']), old, new))
out['distinctTriples'] = len(set(triples))
out['duplicateTriples'] = [t[1][:60] for t, n in Counter(triples).items() if n > 1]
out['duplicateLabels'] = [k for k, n in Counter(s['name'] for s in rev).items() if n > 1]
out['reversalsPerGate'] = dict(Counter(g for s in rev for g in s['red']))
out['benignCount'] = len(verify.benign_probes())
out['benignLabels'] = [b['name'] for b in verify.benign_probes()]
# Which gates the 22 entries added since round 4 name (the entries that mention round-4 finding ids).
newish = [s['name'] for s in rev if 'R4' in s['name'] or 'round-4' in s['name']]
out['entriesNamingRound4'] = len(newish)
out['entriesNamingRound4List'] = newish
print(json.dumps(out, ensure_ascii=False, indent=2))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
