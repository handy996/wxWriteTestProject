"""Round-5 reviewer tally of the delivered reverse control and of the mutation inventory itself.

Why a script instead of reading the transcript: PowerShell 5.1's ``*>`` redirection writes UTF-16, so the
transcript needs decoding before counting. This reads the raw transcript the run produced AND re-enumerates
``verify.MUTATIONS`` / the benign probe list in-process, because "66" is a claim about a list, and the only way
to check a list for double counting is to look at the list: how many entries, on how many distinct files, with
how many distinct (file, old, new) triples. Two labels with the same triple is padding; two entries with the
same triple that are meant to be different are duplicates.
"""
import collections
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(r'E:/project/codex/wxAgent')
sys.path.insert(0, str(REPO / 'tests/engineering/T08'))
import verify  # noqa: E402

out = {}
entries = []
for group, pairs in verify.MUTATIONS.items():
    for old, new in pairs:
        entries.append({'group': group, 'file': str(pairs and old and new and ''), })
out['mutationGroups'] = len(verify.MUTATIONS)
out['mutationEntries'] = sum(len(v) for v in verify.MUTATIONS.values())

# Distinct rewrite triples across the whole inventory.
triples = []
for path, pairs in verify.MUTATIONS.items():
    for old, new in pairs:
        triples.append((str(path), old, new))
counter = collections.Counter(triples)
out['distinctTriples'] = len(counter)
out['duplicateTriples'] = {f'{p}:{o[:40]}': n for (p, o, n2), n in
                           ((k, k[2], v) for k, v in counter.items()) if v > 1}
# Same old-string rewritten twice within one file is only a duplicate if the replacement is identical.
same_old = collections.Counter((p, o) for (p, o, n) in triples)
out['sameOldTwice'] = {f'{p}|{o[:60]}': v for (p, o), v in same_old.items() if v > 1}
out['groupCounts'] = {str(p): len(v) for p, v in verify.MUTATIONS.items()}

# The reversals() inventory: labels, and how many entries assert a specific gate.
rev = verify.reversals()
out['reversalCount'] = len(rev)
labels = [r.get('label', '') for r in rev]
out['duplicateReversalLabels'] = [k for k, v in collections.Counter(labels).items() if v > 1]
out['reversalsByGate'] = dict(collections.Counter(str(r.get('gates')) for r in rev))
benign = verify.benign_probes()
out['benignCount'] = len(benign)
out['benignLabels'] = [b.get('label', '') for b in benign]

# Transcript counts, decoded from whatever the shell wrote.
tdir = Path(os.environ['TEMP']) / 't08r5'
for name in ('reverse-control.txt', 'verify-main.txt'):
    raw = (tdir / name).read_bytes()
    text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', errors='replace')
    if raw[:2] == b'\xff\xfe':
        text = raw.decode('utf-16-le', errors='replace').lstrip('\ufeff')
    rej = [l for l in text.splitlines() if '[REJECT]' in l]
    ben = [l for l in text.splitlines() if '[benign' in l]
    out[name] = {'rejectLines': len(rej), 'benignLines': len(ben),
                 'blind': [l for l in text.splitlines() if 'blind=' in l],
                 'footer': [l for l in text.splitlines() if 'reverse control:' in l],
                 'gatesLine': [l for l in text.splitlines() if 'static checks:' in l]}

print(json.dumps(out, ensure_ascii=False, indent=2))
