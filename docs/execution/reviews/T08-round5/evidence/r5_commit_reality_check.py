"""Round-5 reviewer: what did a commit ACTUALLY re-record?  (read-only: git cat-file only)

Usage: python r5_commit_reality_check.py [rev]     (default rev = e4f0f3c)

For every file `rev` changed, compare the parent blob with the new blob and classify:
  CR_RESTORED  - new == parent with the CRs put back, i.e. new.replace(b'\\r\\n', b'\\n') == parent
                 and parent itself carries no CR.  This is exactly a line-ending re-record: the
                 repair the commit message claims.
  CONTENT      - a difference line endings cannot explain.  If these are authored files, the commit
                 swept working-tree content in under a message that says it only restaged blobs.
  IDENTICAL    - blob unchanged (the path appears in the diff only as a mode/name change).
Also records whether each file's disk bytes equal the new blob right now.

First run of this script used the opposite predicate (parent -> new with CRs stripped) and reported
136/136 as unexplained; that was my bug, corrected here and re-measured.  Nothing else changed.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = r'E:/project/codex/wxAgent'


def git(*args):
    p = subprocess.run(['git', '-C', REPO, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise SystemExit('git failed: ' + p.stderr.decode('utf-8', 'replace')[:300])
    return p.stdout


def main(rev):
    names = [n for n in git('diff', '--name-only', rev + '~1', rev).decode('utf-8', 'replace').split('\n') if n.strip()]
    restored, content, identical = [], [], []
    for f in names:
        a = git('cat-file', 'blob', rev + '~1:' + f)
        b = git('cat-file', 'blob', rev + ':' + f)
        disk = Path(REPO, f).read_bytes() if Path(REPO, f).is_file() else None
        row = {'path': f, 'before': len(a), 'after': len(b), 'beforeCrlf': a.count(b'\r\n'),
               'afterCrlf': b.count(b'\r\n'), 'diskMatchesNewBlob': disk == b}
        if a == b:
            identical.append(row)
        elif a.count(b'\r') == 0 and b.replace(b'\r\n', b'\n') == a:
            restored.append(row)
        else:
            content.append(row)
    report = {'commit': rev, 'filesChanged': len(names),
              'crRestoredOnly': len(restored),
              'crRestoredDiskMatchesNow': sum(1 for r in restored if r['diskMatchesNewBlob']),
              'contentChangeNotLineEndings': len(content), 'blobIdentical': len(identical),
              'contentList': content,
              'crRestoredBuckets': sorted({'/'.join(r['path'].split('/')[:3]) for r in restored})}
    out = Path(REPO) / 'docs/execution/reviews/T08-round5/evidence/r5-e4f0f3c-actual-repair.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    summary = {k: v for k, v in report.items() if k not in ('contentList', 'crRestoredBuckets')}
    sys.stdout.write(summary.__repr__() + '\n')
    for row in content:
        sys.stdout.write('  CONTENT ' + repr(row) + '\n')
    sys.stdout.write('  cr buckets ' + repr(report['crRestoredBuckets']) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else 'e4f0f3c'))
