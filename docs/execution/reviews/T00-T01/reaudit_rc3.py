"""Main-agent rc.3 scope review. Offline; writes review evidence only."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'docs/execution/contracts'))
from reference import freeze_slot_anchors, render_frozen_positions


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def independent_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


data = read('tests/fixtures/contracts/T00/rc3/anchor-vectors.json')
cases = {x['name']: x for x in data['vectors']}
version, manifest = data['version'], data['manifest']
checks = {}
for name, item in cases.items():
    assert independent_digest(item['projection']) == item['expectedReleaseHash']
    assert item['candidate']['releaseHash'] == item['expectedReleaseHash']
    actual = render_frozen_positions(item['candidate'], version)
    assert actual == item['positions']
    assert item['candidate']['version'] == cases['baseline']['candidate']['version']
    assert item['candidate']['manifest'] == cases['baseline']['candidate']['manifest']
    checks[name] = {'hash': item['expectedReleaseHash'], 'positionsVerified': True}
assert len({x['hash'] for x in checks.values()}) == 5

base = copy.deepcopy(cases['baseline']['candidate'])
blocks = {b['blockId']: b for b in version['contentAst']['blocks']}
slots = [{'meta': {'id': a['slotId'], 'articleId': base['meta']['articleId'],
                   'ownerId': base['meta']['ownerId'], 'versionId': a['versionId']},
          'sectionId': blocks[a['anchorBlockId']]['sectionId'],
          **{k: a[k] for k in ['anchorBlockId', 'anchorSide', 'position', 'planHash']}}
         for a in base['slotAnchors']]
frozen = freeze_slot_anchors(base, version, manifest, slots)
assert frozen == base
history = copy.deepcopy(render_frozen_positions(frozen, version))
slots[0].update(anchorBlockId='block-B', anchorSide='BEFORE')
moved = freeze_slot_anchors(base, version, manifest, slots)
assert moved['releaseHash'] != frozen['releaseHash']
slots.clear()
assert render_frozen_positions(frozen, version) == history

rejections = {}
for name in ['missing', 'duplicate', 'foreign_version', 'missing_block', 'wrong_owner']:
    bad = copy.deepcopy(base)
    if name == 'missing': bad['slotAnchors'].pop()
    if name == 'duplicate': bad['slotAnchors'].append(copy.deepcopy(bad['slotAnchors'][0]))
    if name == 'foreign_version': bad['slotAnchors'][0]['versionId'] = '00000000-0000-4000-8000-000000000999'
    if name == 'missing_block': bad['slotAnchors'][0]['anchorBlockId'] = 'not-in-version'
    body = copy.deepcopy(version)
    if name == 'wrong_owner': body['meta']['ownerId'] = '00000000-0000-4000-8000-000000000999'
    try:
        render_frozen_positions(bad, body)
    except ValueError as exc:
        rejections[name] = str(exc)
    else:
        raise AssertionError('Rejected case accepted: ' + name)

manifests = {}
for path in ['docs/execution/contracts/candidate-manifest.json', 'tests/fixtures/freeze-manifest.json',
             'tests/fixtures/representative-v1/manifest.json']:
    value = read(path)
    mismatches = [f['path'] for f in value['files']
        if hashlib.sha256((ROOT / f['path']).read_bytes()).hexdigest() != f['sha256']]
    assert not mismatches
    manifests[path] = {'fileCount': len(value['files']), 'mismatches': mismatches,
        'manifestSha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
assignment = read('docs/evaluation/representative-v1/annotations/assignment.json')
result = {'reviewDate': '2026-10-03', 'contractVersion': '1.0.0-rc.3',
    'mode': 'MAIN_AGENT_OFFLINE_REVIEW', 'R02_A': 'PASS', 'vectors': checks,
    'immutableHistoryAfterLiveSlotsRemoved': True, 'negativeCases': rejections,
    'manifests': manifests, 'humanAssignment': assignment,
    'limitations': ['Not an HTTP, database, storage, renderer or Provider integration test.',
                   'Human gold annotation and representativeness approval remain pending.']}
Path(__file__).with_name('reaudit-rc3-results.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
