"""Round-5 reviewer: independent census of recorded-evidence byte fidelity at HEAD, plus the test-name ledger.

Two questions, both answered by bytes rather than by the commit message:

1. e4f0f3c claims the blanket ``/tests/engineering/** text eol=lf`` rule rewrote 130 tracked files (recorded
   Surefire / dumpstream output written with CRLF on this host) and that four ``-text`` rules plus
   ``git add --renormalize`` fixed it "in the index only". Checked three ways here:
     - every tracked file under an ``evidence/`` or ``*-test-results/`` directory: disk sha256 == HEAD blob
       sha256? (a reviewer recomputing a recorded digest after a fresh checkout must get the same number)
     - the same files against the PRE-FIX commit fb62212: expected to DIFFER (history still carries the
       normalized blobs; the message says so, and if it had claimed otherwise that would be over-wide);
     - the rule's reach: does ``-text`` cover any authored ``.py``/``.java`` source it should not exempt?
   A second pass lists any tracked file under tests/engineering that still diverges, so "zero still divergent"
   is checked and not copied.
2. The case ledger: 57 to 65 (unit 22 to 28, live 35 to 37), zero deletions, zero silent renames — compared by
   method-name set between fb62212 and HEAD.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"E:/project/codex/wxAgent")
PY = sys.executable


def git(*args, stdin_data=None):
    proc = subprocess.run(['git', '-C', str(REPO), *args], input=stdin_data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SystemExit(f'git {" ".join(args)} exit={proc.returncode}: {proc.stderr[:300]!r}')
    return proc.stdout


def ls_files(pathspecs):
    out = git('ls-files', '-s', '--', *pathspecs)
    rows = []
    for line in out.decode('utf-8', errors='replace').splitlines():
        meta, path = line.split('\t', 1)
        mode, oid, stage = meta.split()
        rows.append((path, oid))
    return rows


def blob_hashes(commit, paths):
    """sha256 of each blob as that commit stores it (raw bytes, no filter)."""
    rows = git('ls-tree', '-r', '--name-only', commit, '--', *paths).decode('utf-8').splitlines()
    wanted = set(paths)
    oids = {}
    listing = git('ls-tree', '-r', commit, '--', *paths)
    for line in listing.decode('utf-8', errors='replace').splitlines():
        meta, rest = line.split('\t', 1)
        mode, kind, oid = meta.split()
        oids[rest] = oid
    batch = git('cat-file', '--batch', stdin_data=('\n'.join(oids.values())).encode())
    blobs, index = {}, 0
    lines = batch.split(b'\n')
    pos = 0
    names = list(oids.items())
    for name, oid in names:
        header = lines[pos].decode(errors='replace')
        assert header.split(' ')[0] == oid or header.split(' ')[1] == oid, (header, oid)
        size = int(header.split(' ')[2])
        pos += 1
        payload = b'\n'.join(lines[pos:pos + size])
        # cat-file writes exactly `size` bytes then a newline; rebuild by offset to be safe.
        start = sum(len(lines[p]) + 1 for p in range(1, pos))
        pos += size
        blobs[name] = hashlib.sha256(batch[batch.index(b'\n', 0) + 1:][:0] or b'').hexdigest() if False else None
    # Simpler and exact: ask git for each blob individually (a few hundred calls at most).
    blobs = {}
    for name, oid in names:
        blobs[name] = hashlib.sha256(git('cat-file', 'blob', oid)).hexdigest()
    return blobs


def main():
    result = {}
    evidence_specs = ['tests/engineering/**/evidence/**', 'tests/engineering/**/*-test-results/**',
                      'tests/engineering/output/**']
    rows = ls_files(evidence_specs)
    result['recordedFilesTracked'] = len(rows)
    oids = dict(rows)
    mismatches, samples = [], []
    for path, oid in sorted(oids.items()):
        disk = REPO / path
        if not disk.is_file():
            mismatches.append({'path': path, 'why': 'missing on disk'})
            continue
        disk_sha = hashlib.sha256(disk.read_bytes()).hexdigest()
        head_sha = hashlib.sha256(git('cat-file', 'blob', oid)).hexdigest()
        if disk_sha != head_sha:
            mismatches.append({'path': path, 'disk': disk_sha, 'head': head_sha})
    result['headDiskVsBlobMismatches'] = mismatches
    result['headMismatchCount'] = len(mismatches)

    # The same files against the pre-fix commit: divergence is EXPECTED there (history keeps normalized blobs).
    pre = 'fb62212'
    pre_paths = sorted(oids)[:400]
    sample_paths = [p for p in sorted(oids) if p.endswith(('.dumpstream', '.txt'))][:300]
    pre_rows = git('ls-tree', '-r', pre, '--', *evidence_specs).decode('utf-8', errors='replace').splitlines()
    pre_oids = {}
    for line in pre_rows:
        meta, rest = line.split('\t', 1)
        mode, kind, oid = meta.split()
        pre_oids[rest] = oid
    compared, differ_at_pre, missing_at_pre = 0, [], 0
    for path in sample_paths:
        if path not in pre_oids:
            missing_at_pre += 1
            continue
        disk_sha = hashlib.sha256((REPO / path).read_bytes()).hexdigest()
        pre_sha = hashlib.sha256(git('cat-file', 'blob', pre_oids[path])).hexdigest()
        compared += 1
        if disk_sha != pre_sha:
            differ_at_pre.append({'path': path, 'disk': disk_sha, 'pre': pre_sha})
    result['preFixSampled'] = compared
    result['preFixMissingAtPath'] = missing_at_pre
    result['preFixDivergent'] = len(differ_at_pre)
    result['preFixDivergentExamples'] = differ_at_pre[:3]
    result['preFixMatchedExamples'] = [p for p in sample_paths if p not in
                                       {d['path'] for d in differ_at_pre}][:3]

    # Does any tracked file under tests/engineering still diverge (the "zero still divergent" claim)?
    all_rows = ls_files(['tests/engineering'])
    still = []
    crlf_authored = []
    for path, oid in all_rows:
        disk = REPO / path
        if not disk.is_file():
            continue
        raw = disk.read_bytes()
        if b'\r\n' in raw and path.endswith(('.py', '.java', '.sql', '.md', '.yml', '.yaml')):
            crlf_authored.append(path)
        if hashlib.sha256(raw).hexdigest() != hashlib.sha256(git('cat-file', 'blob', oid)).hexdigest():
            still.append(path)
    result['trackedUnderTestsEngineering'] = len(all_rows)
    result['stillDivergentAtHead'] = still
    result['authoredSourcesStillCrlfOnDisk'] = crlf_authored

    # Rule reach: which attributes actually apply to representative paths?
    probe = ['tests/engineering/T08/verify.py', 'tests/engineering/T08/run_pg.py',
             'tests/engineering/T08/evidence/r4-integration-main.json',
             'tests/engineering/T08/evidence/r4fix-65-test-results/2026-10-08T04-38-13_085.dumpstream',
             'tests/engineering/T07/check_delivery.py' if (REPO / 'tests/engineering/T07').is_dir() else
             'tests/engineering/T02/check_contracts.py',
             'docs/execution/reviews/T08-round5/review.md', 'backend/src/main/java/com/example/editorial/cost/BudgetService.java']
    checked = git('check-attr', 'text', 'eol', '--stdin', stdin_data='\n'.join(probe).encode())
    result['attributeReach'] = checked.decode('utf-8').splitlines()

    # Case ledger across the two commits.
    def methods(commit, path):
        raw = git('show', f'{commit}:{path}')
        return sorted(set(re.findall(r'\n    \x40Test[\s\S]{0,400}?\n    (?:public )?(?:static )?void ([A-Za-z0-9_]+)\(',
                                      raw.decode('utf-8', errors='replace'))))
    unit_now, unit_then = methods('HEAD', 'backend/src/test/java/com/example/editorial/cost/CostPricingTest.java'), \
        methods('fb62212', 'backend/src/test/java/com/example/editorial/cost/CostPricingTest.java')
    live_now, live_then = methods('HEAD', 'backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java'), \
        methods('fb62212', 'backend/src/test/java/com/example/editorial/cost/T08PostgresTest.java')
    result['caseLedger'] = {'unit': {'then': len(unit_then), 'now': len(unit_now),
                                     'removed': sorted(set(unit_then) - set(unit_now)),
                                     'added': sorted(set(unit_now) - set(unit_then))},
                            'live': {'then': len(live_then), 'now': len(live_now),
                                     'removed': sorted(set(live_then) - set(live_now)),
                                     'added': sorted(set(live_now) - set(live_then))}}
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


main()
