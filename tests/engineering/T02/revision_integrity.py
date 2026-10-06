"""Bind R01/B01 source/evidence to the delivery without rewriting old evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'b115a4022375675c7cbff536b239508db8f3f4e1'
original = 'backend/src/main/resources/db/migration/R__t02_schema_permissions.sql'
assert (ROOT / original).read_bytes() == subprocess.check_output(['git', 'show', BASELINE + ':' + original], cwd=ROOT)
jar = ROOT / 'backend/target/editorial-0.1.0-SNAPSHOT.jar'
with zipfile.ZipFile(jar) as archive:
    for script in ('R__t02_schema_permissions.sql', 'R__t02_function_permissions.sql',
                   'beforeMigrate__t02_function_defaults.sql'):
        resource = 'db/migration/' + script
        assert archive.read('BOOT-INF/classes/' + resource) == (ROOT / 'backend/src/main/resources' / resource).read_bytes()
    assert not any('V1__t02_function_order_probe.sql' in name for name in archive.namelist())

names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
excluded = {'tests/engineering/T02/evidence/r01-integrity.json', 'tests/engineering/T02/evidence/r01-integrity-run.json'}
paths = sorted(name for name in set(names) if name not in excluded and (
    name.startswith(('backend/', 'frontend/', 'infra/', '.github/', 'tests/engineering/T02/')) or
    name in ('README.md', 'docs/execution/reports/T02.md')))


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


result = {'reviewedCommit': BASELINE, 'contractVersion': '1.0.0-rc.3',
          'originalMigrationUnchanged': True, 'packagedMigrationBytesMatch': True,
          'testVersionedMigrationNotPackaged': True,
          'jarSha256': sha256(jar), 'files': {name: sha256(ROOT / name) for name in paths}}
(ROOT / 'tests/engineering/T02/evidence/r01-integrity.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(f'{len(paths)} delivery fingerprints; original migration unchanged; packaged SQL matches; test V1 absent')
