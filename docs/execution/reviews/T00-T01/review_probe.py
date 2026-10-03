"""Independent review probes. Synthetic data only; no generation or provider calls.

Exit 0 means probes ran, not that the reviewed contracts passed.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'docs/execution/contracts'))
sys.path.insert(0, str(ROOT / 'docs/evaluation'))
from reference import release_hash
from evaluate import demo_bundle, evaluate, DIMENSIONS

schema = json.loads((ROOT / 'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))
examples = {x['schema']: x['positive'] for x in json.loads(
    (ROOT / 'tests/fixtures/contracts/T00/structural-examples.json').read_text(encoding='utf-8'))}


def valid(name, value):
    return Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/' + name},
                               format_checker=FormatChecker()).is_valid(value)


results = {'mode': 'INDEPENDENT_OFFLINE_REVIEW', 'findings': {}}
rights = {}
for kind in ['OWNED', 'AUTHORIZED', 'REFERENCE_ONLY', 'UNKNOWN', 'LICENSED', 'PERMISSION']:
    value = copy.deepcopy(examples['CreateArticleRequest'])
    value['rightsBasis']['kind'] = kind
    rights[kind] = valid('CreateArticleRequest', value)
results['findings']['R01_original_rights'] = rights

candidate = copy.deepcopy(examples['ReleaseCandidate'])
try:
    hash_result = release_hash(candidate)
except (KeyError, ValueError) as exc:
    hash_result = type(exc).__name__ + ': ' + str(exc)
vector = json.loads((ROOT / 'tests/fixtures/contracts/T00/hash-vectors.json').read_text(encoding='utf-8'))
results['findings']['R02_release_hash'] = {
    'schemaCandidateValid': valid('ReleaseCandidate', candidate),
    'hashResult': hash_result,
    'oracleVectorValidAsCandidate': valid('ReleaseCandidate', vector['candidate'])}

analysis = copy.deepcopy(examples['AnalysisOutput'])
draft = copy.deepcopy(examples['ClaimDraft'])
draft['localKey'] = 'claim-local-1'
analysis['factClaims'] = [draft]
analysis['recommendedTitles'][0]['supportedClaimIds'] = [draft['localKey']]
results['findings']['R03_analyzer_local_reference'] = {
    'claimLocalKeyAccepted': valid('ClaimDraft', draft),
    'titleReferencingThatLocalKeyAccepted': valid('AnalysisOutput', analysis)}

create_skill = copy.deepcopy(examples['CreateSkillVersionRequest'])
create_skill.pop('baseVersionId')
patch_skill = {'skillVersionId': '00000000-0000-4000-8000-000000000001'}
results['findings']['R04_skill_lifecycle'] = {
    'firstVersionWithoutBaseAccepted': valid('CreateSkillVersionRequest', create_skill),
    'switchSkillPatchAccepted': valid('PatchArticleRequest', patch_skill)}

obj = copy.deepcopy(examples['ObjectRef'])
obj.update(size=21 * 1024 * 1024, mime='application/zip')
results['findings']['R05_export_object_size'] = {
    'zip21MiBAccepted': valid('ObjectRef', obj),
    'globalObjectSizeMax': schema['$defs']['ObjectRef']['properties']['size']['maximum']}

bundle = demo_bundle()
for index, run in enumerate(bundle['runs']):
    run['predictions'] = [dict(id=f'r{index}-{g["id"]}', articleId=g['articleId'],
        importance=g['importance'], matchedGoldId=g['id'], verificationStatus=g['decision']) for g in bundle['gold']]
    for score in run['editorialScores']:
        score['scores'] = {d: 4 if d == 'THESIS' else 1 for d in DIMENSIONS}
report = evaluate(bundle, demo=True)
results['findings']['R06_quality_gate'] = {
    'syntheticOnly': True,
    'allRunThresholdsMet': report['allRunThresholdsMet'],
    'rubricMean': report['runs'][0]['rubricMean'],
    'overallMean': sum(report['runs'][0]['rubricMean'].values()) / len(DIMENSIONS),
    'acceptancePassed': report['acceptancePassed']}

results['manifestChecks'] = {}
for path in ['docs/execution/contracts/candidate-manifest.json', 'tests/fixtures/freeze-manifest.json']:
    manifest = json.loads((ROOT / path).read_text(encoding='utf-8'))
    mismatches = [f['path'] for f in manifest['files']
                  if hashlib.sha256((ROOT / f['path']).read_bytes()).hexdigest() != f['sha256']]
    results['manifestChecks'][path] = {'fileCount': len(manifest['files']), 'mismatches': mismatches}

out = Path(__file__).with_name('review-probe-results.json')
out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
