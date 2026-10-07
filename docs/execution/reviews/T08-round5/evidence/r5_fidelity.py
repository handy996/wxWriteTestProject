"""Round-5 reviewer: independent census of recorded-evidence byte fidelity, plus the case ledger.

Two questions, answered by bytes rather than by the commit message.

1. `e4f0f3c` says the blanket `/tests/engineering/** text eol=lf` rule rewrote 130 tracked files (recorded
   Surefire / dumpstream output, which this Windows host writes with CRLF) and that four `-text` rules plus
   `git add --renormalize` fixed it "in the index only". Checked three ways here:
     - every tracked file under an `evidence/`, `*-test-results/` or `tests/engineering/output/` directory:
       disk sha256 == HEAD blob sha256? A reviewer who recomputes a recorded digest after a fresh checkout has
       to get the number the run produced.
     - the same class of files against the PRE-FIX commit `fb62212`: divergence is EXPECTED there (history keeps
       the normalized blobs — the message says so); if it did NOT diverge, the message's "I did not delete
       history" would be wrong in the other direction.
     - still-divergent sweep over everything tracked under `tests/engineering`, so "zero still divergent" is
       measured and not copied, plus the reach of the new rules via `git check-attr`.
2. The case ledger 57 → 65 (unit 22 → 28, live 35 → 37): compared by method-name SET between `fb62212` and HEAD,
   because a deletion or a silent rename is only visible as a set difference.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r'E:/project/codex/wxAgent')
RECORDED = ['tests/engineering/**/evidence/**', 'tests/engineering/**/*-test-results/**',
            'tests/engineering/output/**']


def git(*args, stdin_data=None):
    proc = subprocess.run(['git', '-C', str(REPO), *args], input=stdin_data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SystemExit('git %s exit=%d %r' % (' '.join(args), proc.returncode, proc.stderr[:300]))
    return proc.stdout


def ls_files(pathspecs):
    rows = []
    for line in git('ls-files', '-s', '--', *pathspecs).decode('utf-8', errors='replace').splitlines():
        meta, path = line.split('\t', 1)
        _mode, oid, _stage = meta.split()
        rows.append((path, oid))
    return rows


def sha(bytes_):
    return hashlib.sha256(bytes_).hexdigest()


def methods(commit, path):
    raw = git('show', '%s:%s' % (commit, path)).decode('utf-8', errors='replace')
    # A test method is an @Test annotation followed by its signature within the next few lines.
    return sorted(set(re.findall(r'@Test\b[\s\S]{0,400}?\n    (?:public )?(?:static )?void ([A-Za-z0-9_]+)\(',
                                 raw)))


result = {}

recorded = ls_files(RECORDED)
result['recordedTracked'] = len(recorded)
head_bad, head_disk_crlf = [], 0
for path, oid in recorded:
    disk = REPO / path
    if not disk.is_file():
        head_bad.append({'path': path, 'why': 'missing on disk'})
        continue
    raw = disk.read_bytes()
    if b'\r\n' in raw:
        head_disk_crlf += 1
    if sha(raw) != sha(git('cat-file', 'blob', oid)):
        head_bad.append({'path': path, 'disk': sha(raw), 'head': sha(git('cat-file', 'blob', oid))})
result['headMismatchCount'] = len(head_bad)
result['headMismatchExamples'] = head_bad[:10]
result['recordedWithCrlfOnDisk'] = head_disk_crlf

# The pre-fix commit: same class of files, expected to diverge from disk.
pre_rows = {}
for line in git('ls-tree', '-r', 'fb62212', '--', *RECORDED).decode('utf-8', errors='replace').splitlines():
    meta, rest = line.split('\t', 1)
    _mode, _kind, oid = meta.split()
    pre_rows[rest] = oid
sample = sorted(pre_rows)[:250]
diverged, matched, absent = [], [], []
for path in sample:
    disk = REPO / path
    if not disk.is_file():
        absent.append(path)
        continue
    d = sha(disk.read_bytes())
    p = sha(git('cat-file', 'blob', pre_rows[path]))
    (diverged if d != p else matched).append({'path': path, 'disk': d, 'pre': p})
result['preFixSampled'] = len(sample)
result['preFixDivergent'] = len(diverged)
result['preFixMatched'] = len(matched)
result['preFixMissingNow'] = len(absent)
result['preFixDivergentExamples'] = diverged[:3]
result['preFixMatchedExamples'] = matched[:3]

# Sweep: anything still divergent under tests/engineering at HEAD (the "zero still divergent" claim).
still, crlf_authored = [], []
for path, oid in ls_files(['tests/engineering']):
    disk = REPO / path
    if not disk.is_file():
        continue
    raw = disk.read_bytes()
    blob = sha(git('cat-file', 'blob', oid))
    if sha(raw) != blob:
        still.append(path)
    if b'\r\n' in raw and path.endswith(('.py', '.java', '.sql', '.md', '.yml', '.yaml')):
        crlf_authored.append(path)
result['trackedUnderTestsEngineering'] = len(ls_files(['tests/engineering']))
result['stillDivergentAtHead'] = still
result['authoredSourcesWithCrlfOnDisk'] = crlf_authored

probe = ['tests/engineering/T08/verify.py', 'tests/engineering/T08/run_pg.py',
         'tests/engineering/T08/evidence/r4-integration-main.json',
         'tests/engineering/T02/check_contracts.py',
         'docs/execution/reviews/T08-round5/review.md',
         'backend/src/main/java/com/example/editorial/cost/BudgetService.java']
result['attributeReach'] = git('check-attr', 'text', 'eol', '--stdin',
                               stdin_data='\n'.join(probe).encode()).decode('utf-8').splitlines()

unit_now, unit_then = methods('HEAD', 'backend/src/test/java/com/example/editorial/cost/CostPricingTest.java'), \
    methods('fb62212', 'backend/src/test/java/com/example/editorial/cost/CostPricingTest.java')
live_now, live_then = methods('HEAD', 'backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java'), \
    methods('fb62212', 'backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java')
result['caseLedger'] = {
    'unit': {'then': len(unit_then), 'now': len(unit_now),
             'removed': sorted(set(unit_then) - set(unit_now)),
             'added': sorted(set(unit_now) - set(unit_then))},
    'live': {'then': len(live_then), 'now': len(live_now),
             'removed': sorted(set(live_then) - set(live_now)),
             'added': sorted(set(live_now) - set(live_then))}}

print(json.dumps(result, ensure_ascii=False, indent=2))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                 newline='\n')
