"""Read-only contract, source fingerprint and persisted regression-result verification."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
name = sys.argv[1] if len(sys.argv) > 1 else 'revision-v1-final'
if Path(name).name != name:
    raise ValueError('evidence name must be a filename stem')
run = json.loads((HERE / 'evidence' / (name + '.json')).read_text(encoding='utf-8'))
assert run['exitCode'] == 0
contract = subprocess.run([sys.executable, str(ROOT / 'tests/engineering/T02/check_contracts.py')],
                          cwd=ROOT, capture_output=True, text=True, check=True)
assert (ROOT / 'docs/schemas/editorial.schema.json').read_bytes() == (ROOT / 'backend/src/main/resources/skills/editorial.schema.json').read_bytes()
suites = []
for path in sorted((HERE / 'evidence' / (name + '-test-results')).glob('TEST-*.xml')):
    suite = ET.parse(path).getroot()
    row = {key: int(suite.get(key)) for key in ('tests', 'failures', 'errors', 'skipped')}
    row.update(name=suite.get('name'), cases=[case.get('name') for case in suite.findall('testcase')])
    assert row['failures'] == row['errors'] == row['skipped'] == 0, row
    suites.append(row)
assert len(suites) == 8
assert sum(case.startswith('review') for suite in suites for case in suite['cases']) == 6
paths = []
for folder in ['backend/src/main/java/com/example/editorial/editorial/skill',
               'backend/src/main/java/com/example/editorial/settings/policy',
               'backend/src/main/resources/prompts', 'backend/src/main/resources/skills',
               'backend/src/test/java/com/example/editorial/editorial/skill',
               'backend/src/test/java/com/example/editorial/settings/policy']:
    paths.extend(path for path in (ROOT / folder).rglob('*') if path.is_file())
paths.extend([HERE / 'migration-draft.sql', HERE / 'integration.py'])
fingerprints = [{'path': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(paths)]
result = {'contractCheck': contract.stdout.strip(), 'runtimeSchemaMatchesApproved': True,
          'tests': sum(suite['tests'] for suite in suites), 'failures': 0, 'errors': 0, 'skipped': 0,
          'suites': suites, 'sourceFingerprints': fingerprints}
(HERE / 'evidence' / (name + '-checks.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ('suites', 'sourceFingerprints')}, ensure_ascii=False))
