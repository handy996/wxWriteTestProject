"""Bind R01/B01 source/evidence to the delivery without rewriting old evidence.

Round 3 review closed the scanner blind spot only by changing this generator's output shape:
fingerprints are records with `path` and `sha256` on separate lines (`digest_records`), so no
line ever pairs a key-like path (`.../secret_scan.py`) with a long hex token, which is what
Gitleaks' generic-api-key rule reports. Historical evidence stays immutable: writing to any frozen
record (the two r01 integrity files or the committed gitleaks-findings.json) is refused, and an
--out path outside the repository is rejected rather than raising a bare traceback.
"""
import argparse
from pathlib import Path
import json
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import digest_records

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'b115a4022375675c7cbff536b239508db8f3f4e1'
FROZEN = ('tests/engineering/T02/evidence/r01-integrity.json',
          'tests/engineering/T02/evidence/r01-integrity-run.json',
          'tests/engineering/T02/evidence/gitleaks-findings.json')
DEFAULT_OUT = 'tests/engineering/T02/evidence/r02-integrity.json'

original = 'backend/src/main/resources/db/migration/R__t02_schema_permissions.sql'
assert (ROOT / original).read_bytes() == subprocess.check_output(['git', 'show', BASELINE + ':' + original], cwd=ROOT)
jar = ROOT / 'backend/target/editorial-0.1.0-SNAPSHOT.jar'
with zipfile.ZipFile(jar) as archive:
    for script in ('R__t02_schema_permissions.sql', 'R__t02_function_permissions.sql',
                   'beforeMigrate__t02_function_defaults.sql'):
        resource = 'db/migration/' + script
        assert archive.read('BOOT-INF/classes/' + resource) == (ROOT / 'backend/src/main/resources' / resource).read_bytes()
    assert not any('V1__t02_function_order_probe.sql' in name for name in archive.namelist())

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--out', default=DEFAULT_OUT,
                    help='manifest path inside the repo (default %s); frozen evidence records and '
                         'paths outside the repository are refused' % DEFAULT_OUT)
args = parser.parse_args()
out = Path(args.out)
resolved = (out if out.is_absolute() else ROOT / out).resolve()
try:
    relative = resolved.relative_to(ROOT).as_posix()
except ValueError:
    raise SystemExit('--out must stay inside the repository; refusing to write outside it: '
                     + str(resolved))
if relative in FROZEN:
    raise SystemExit('refusing to rewrite frozen evidence record: ' + relative)

names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
excluded = {relative}
paths = sorted(name for name in set(names) if name not in excluded and (
    name.startswith(('backend/', 'frontend/', 'infra/', '.github/', 'tests/engineering/T02/')) or
    name in ('README.md', 'docs/execution/reports/T02.md',
             'docs/execution/reports/T02-Revision-R02.md')))

result = {'reviewedCommit': BASELINE, 'contractVersion': '1.0.0-rc.3',
          'originalMigrationUnchanged': True, 'packagedMigrationBytesMatch': True,
          'testVersionedMigrationNotPackaged': True,
          'jarSha256': digest_records.sha256_file(jar),
          'files': digest_records.records(paths, root=ROOT)}
digest_records.write(result, ROOT / relative)
print(f'{len(paths)} delivery fingerprints; original migration unchanged; packaged SQL matches; test V1 absent')
