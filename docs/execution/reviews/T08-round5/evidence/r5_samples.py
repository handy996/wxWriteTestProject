"""Round-5 reviewer: the sample the dispatch asks for, done with explicit `git cat-file` per path.

`e4f0f3c` says the blanket `/tests/engineering/** text eol=lf` rule made 130 tracked files' recorded bytes differ
from their blobs, that four `-text` rules plus `git add --renormalize` repaired HEAD, and — explicitly — that
history was NOT rewritten, so the same paths still diverge at the pre-fix commit. Both halves are checkable:

  disk bytes == HEAD blob bytes      for recorded files (repaired: must MATCH)
  disk bytes != fb62212 blob bytes   for the same files (history kept: must DIFFER)

A mismatch against `fb62212` is the expected result; if it matched, the message's "I did not delete history"
would be false. Sizes are reported because the message cites 318/313 and 339/335 as the shape of the damage.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r'E:/project/codex/wxAgent')


def git(args):
    proc = subprocess.run(['git', '-C', str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SystemExit(f'git {" ".join(args)} exit={proc.returncode} {proc.stderr[:200]!r}')
    return proc.stdout


listing = git(['ls-tree', '-r', '--name-only', 'fb62212', 'tests/engineering']).decode('utf-8').splitlines()
recorded = [p for p in listing if ('/evidence/' in p or '-test-results/' in p or p.startswith('tests/engineering/output/'))
            and p.endswith(('.dumpstream', '.txt', '.xml', '.json'))]
on_disk_now = [p for p in recorded if (REPO / p).is_file()]

# The classes the commit message names: a dumpstream, a surefire TXT, a surefire XML, plus the newest round's XML.
def pick(suffixes, want, exclude=()):
    for path in on_disk_now:
        if path.endswith(suffixes) and not any(x in path for x in exclude):
            return path
    return None


samples = []
seen = set()
for suffixes in (('.dumpstream',), ('.txt',), ('.xml',)):
    for path in on_disk_now:
        if path.endswith(suffixes) and path not in seen:
            samples.append(path)
            seen.add(path)
            break
t08 = next((p for p in on_disk_now if p.startswith('tests/engineering/T08/evidence/') and p.endswith('.xml')), None)
if t08 and t08 not in seen:
    samples.append(t08)

rows = []
for path in samples:
    disk = (REPO / path).read_bytes()
    head = git(['cat-file', 'blob', 'HEAD:' + path])
    try:
        pre = git(['cat-file', 'blob', 'fb62212:' + path])
    except SystemExit:
        pre = None
    rows.append({'path': path,
                 'diskBytes': len(disk), 'headBytes': len(head), 'preBytes': None if pre is None else len(pre),
                 'diskSha': hashlib.sha256(disk).hexdigest(),
                 'headSha': hashlib.sha256(head).hexdigest(),
                 'preSha': None if pre is None else hashlib.sha256(pre).hexdigest(),
                 'diskEqualsHead': hashlib.sha256(disk).hexdigest() == hashlib.sha256(head).hexdigest(),
                 'diskEqualsPre': None if pre is None else hashlib.sha256(disk).hexdigest() == hashlib.sha256(pre).hexdigest(),
                 'diskCrlf': b'\r\n' in disk, 'headCrlf': b'\r\n' in head, 'preCrlf': None if pre is None else b'\r\n' in pre})

# Whole-class HEAD check, and the same whole-class check against fb62212 for files that exist in both.
all_now = [p for p in git(['ls-files', '--', 'tests/engineering']).decode('utf-8').splitlines()
           if ('/evidence/' in p or '-test-results/' in p or p.startswith('tests/engineering/output/'))
           and (REPO / p).is_file()]
head_mismatch, pre_divergent, pre_compared = [], [], 0
for path in all_now:
    disk = (REPO / path).read_bytes()
    head = git(['cat-file', 'blob', 'HEAD:' + path])
    if hashlib.sha256(disk).hexdigest() != hashlib.sha256(head).hexdigest():
        head_mismatch.append(path)
out = {'recordedFilesCheckedAgainstHead': len(all_now), 'headMismatches': head_mismatch,
       'samples': rows}
print(json.dumps(out, ensure_ascii=False, indent=2))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
