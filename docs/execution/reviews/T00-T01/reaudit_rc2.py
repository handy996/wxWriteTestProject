"""Main-agent rc.2 review; read candidates, preserve rc.1, write review evidence only.
Exit zero means the review ran successfully, not G0 approval.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import uuid
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'docs/execution/contracts'))
sys.path.insert(0, str(ROOT / 'docs/evaluation'))
from reference import release_hash, release_hash_input, resolve_analysis
from evaluate import demo_bundle, evaluate, DIMENSIONS


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


schema = read('docs/schemas/editorial.schema.json')
examples = {x['schema']: x['positive'] for x in read('tests/fixtures/contracts/T00/rc2/structural-examples.json')}


def valid(name, value):
    return Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/' + name},
                               format_checker=FormatChecker()).is_valid(value)


out = {'contractVersion': '1.0.0-rc.2', 'mode': 'MAIN_AGENT_OFFLINE_REVIEW', 'regressions': {}}
create = read('tests/fixtures/contracts/T00/rc2/srs-create-request.json')
out['regressions']['R01'] = {b: valid('CreateArticleRequest', dict(create, rightsBasis=b))
    for b in ['OWNED', 'AUTHORIZED', 'REFERENCE_ONLY', 'UNKNOWN', 'LICENSED', 'PERMISSION']}
assert out['regressions']['R01'] == dict(OWNED=True, AUTHORIZED=True, REFERENCE_ONLY=True,
                                        UNKNOWN=True, LICENSED=False, PERMISSION=False)

vector = read('tests/fixtures/contracts/T00/rc2/release-vector.json')
c = vector['candidate']
projection = release_hash_input(c)
assert valid('ReleaseCandidate', c) and valid('ReleaseHashInput', projection)
assert release_hash(c) == vector['expectedReleaseHash']
out['regressions']['R02_wire_projection'] = 'PASS'

analysis = copy.deepcopy(examples['AnalysisOutput'])
analysis['factClaims'] = [dict(copy.deepcopy(examples['ClaimDraft']), localKey='audit-a'),
                         dict(copy.deepcopy(examples['ClaimDraft']), localKey='audit-b')]
for index, title in enumerate(analysis['recommendedTitles']):
    title['supportedClaimLocalKeys'] = ['audit-a' if index % 2 else 'audit-b']
ids = iter([str(uuid.UUID(int=501, version=4)), str(uuid.UUID(int=502, version=4))])
resolved, mapping = resolve_analysis(analysis, lambda: next(ids))
assert valid('AnalysisOutput', analysis) and valid('AnalysisResolvedOutput', resolved)
assert len(mapping) == 2
out['regressions']['R03'] = 'PASS'

skill = copy.deepcopy(examples['CreateSkillVersionRequest'])
skill.pop('baseVersionId', None)
assert valid('CreateSkillVersionRequest', skill)
assert valid('CreateSkillVersionRequest', dict(skill, baseVersionId=None))
assert valid('PatchArticleRequest', {'skillVersionId': create['skillVersionId']})
out['regressions']['R04'] = 'PASS'
obj = dict(examples['ObjectRef'], size=21 * 1024 * 1024, mime='application/zip')
assert valid('ObjectRef', obj) and not valid('ImageObjectRef', dict(obj, mime='image/png'))
out['regressions']['R05'] = 'PASS'

bundle = demo_bundle()
for index, run in enumerate(bundle['runs']):
    run['predictions'] = [dict(id=f'audit-{index}-{g["id"]}', articleId=g['articleId'],
        importance=g['importance'], matchedGoldId=g['id'], verificationStatus=g['decision']) for g in bundle['gold']]
baseline = evaluate(bundle, True)
assert baseline['allRunThresholdsMet']
quality = {}
bad = copy.deepcopy(bundle)
for run in bad['runs']:
    for score in run['editorialScores']:
        score['scores'] = {d: 4 if d == 'THESIS' else 1 for d in DIMENSIONS}
report = evaluate(bad, True)
assert not report['allRunThresholdsMet']
quality['lowMean'] = report['runs'][0]['editorialMean']
for name in ['below_four', 'reversal', 'analyzer_below_ninety']:
    bad = copy.deepcopy(bundle)
    for run in bad['runs']:
        if name == 'below_four':
            run['editorialScores'][0]['scores']['THESIS'] = 3
        elif name == 'reversal':
            run['editorialScores'][0]['keyThesisReversed'] = True
        else:
            for score in run['analyzerScores'][:3]:
                score['coreThesisScore'] = 3
    assert not evaluate(bad, True)['allRunThresholdsMet']
    quality[name] = 'REJECTED'
out['regressions']['R06'] = quality

# An anchor-only PATCH is legal. No frozen slot/anchor field exists in the
# selection binding, Manifest item, or candidate hash projection. Do not claim
# this is a production exploit; it is a missing contract input.
anchor_patch = {'anchor': {'blockId': 'audit-paragraph-2', 'side': 'BEFORE'}}
assert valid('PatchSlotRequest', anchor_patch)
with_anchor = copy.deepcopy(c)
with_anchor['slotAnchors'] = [{'slotId': str(uuid.UUID(int=601, version=4)),
    'anchorBlockId': 'audit-paragraph-2', 'anchorSide': 'BEFORE', 'position': 1}]
anchor_evidence = {
    'anchorOnlyPatchSchemaValid': valid('PatchSlotRequest', anchor_patch),
    'candidateWithFrozenAnchorsSchemaValid': valid('ReleaseCandidate', with_anchor),
    'hashProjectionFields': sorted(projection),
    'manifestItemFields': sorted(schema['$defs']['ManifestItem']['properties']),
    'frozenSelectionBindingFields': sorted(schema['$defs']['FrozenSelectionBinding']['properties']),
    'note': 'No typed frozen slot anchor or required AST rewrite contract; actual HTTP/DB behavior not executed.'}
assert not anchor_evidence['candidateWithFrozenAnchorsSchemaValid']
out['remainingFindings'] = {'R02_ANCHOR_SNAPSHOT': anchor_evidence}

out['manifests'] = {}
for path in ['docs/execution/contracts/candidate-manifest.json', 'tests/fixtures/freeze-manifest.json',
             'tests/fixtures/representative-v1/manifest.json']:
    manifest = read(path)
    mismatches = [r['path'] for r in manifest['files']
        if hashlib.sha256((ROOT / r['path']).read_bytes()).hexdigest() != r['sha256']]
    assert not mismatches
    out['manifests'][path] = {'files': len(manifest['files']), 'mismatches': mismatches}
out['humanAssignment'] = read('docs/evaluation/representative-v1/annotations/assignment.json')
path = Path(__file__).with_name('reaudit-rc2-results.json')
path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
