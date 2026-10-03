"""Adapt the six independent rc1 review counterexamples to the explicit rc2 wire migration.
Does not modify review artifacts. Exit 0 means all six corrected expectations hold.
"""
import copy
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'docs/evaluation'))
from test_contracts import SCHEMA,sample,validator
from test_review_regressions import candidate_example
from reference import release_hash,release_hash_input
from evaluate import demo_bundle,evaluate,DIMENSIONS


def main():
    findings={}
    example=sample(SCHEMA['$defs']['CreateArticleRequest'])
    findings['R01']={v:validator('CreateArticleRequest').is_valid(dict(example,rightsBasis=v))
        for v in ['OWNED','AUTHORIZED','REFERENCE_ONLY','UNKNOWN','LICENSED','PERMISSION']}
    c=candidate_example()
    findings['R02']={'candidateValid':validator('ReleaseCandidate').is_valid(c),
        'projectionValid':validator('ReleaseHashInput').is_valid(release_hash_input(c)),
        'hashMatches':release_hash(c)==c['releaseHash']}
    analysis=sample(SCHEMA['$defs']['AnalysisOutput']);claim=sample(SCHEMA['$defs']['ClaimDraft'])
    claim['localKey']='claim-local-1';analysis['factClaims']=[claim]
    analysis['recommendedTitles'][0]['supportedClaimLocalKeys']=[claim['localKey']]
    findings['R03']={'localReferenceValid':validator('AnalysisOutput').is_valid(analysis)}
    first=sample(SCHEMA['$defs']['CreateSkillVersionRequest']);first.pop('baseVersionId',None)
    findings['R04']={'firstWithoutBaseValid':validator('CreateSkillVersionRequest').is_valid(first),
        'switchValid':validator('PatchArticleRequest').is_valid({'skillVersionId':'00000000-0000-4000-8000-000000000001'})}
    obj=sample(SCHEMA['$defs']['ObjectRef']);obj.update(size=21*1024*1024,mime='application/zip')
    findings['R05']={'zip21MiBValid':validator('ObjectRef').is_valid(obj),
        'image21MiBRejected':not validator('ImageObjectRef').is_valid(dict(obj,mime='image/png'))}
    bundle=demo_bundle()
    for i,run in enumerate(bundle['runs']):
        run['predictions']=[{'id':f'{i}-{g["id"]}','articleId':g['articleId'],'importance':g['importance'],
            'matchedGoldId':g['id'],'verificationStatus':g['decision']} for g in bundle['gold']]
        for score in run['editorialScores']:score['scores']={d:4 if d=='THESIS' else 1 for d in DIMENSIONS}
    result=evaluate(bundle,True)
    findings['R06']={'editorialMean':result['runs'][0]['editorialMean'],
        'analyzerPassesIndependently':result['runs'][0]['gates']['analyzer'],'allRunThresholdsMet':result['allRunThresholdsMet']}
    ok=(findings['R01']==dict(OWNED=True,AUTHORIZED=True,REFERENCE_ONLY=True,UNKNOWN=True,LICENSED=False,PERMISSION=False)
        and all(all(v.values()) for k,v in findings.items() if k not in ['R01','R06'])
        and findings['R06']['editorialMean']==1.6 and findings['R06']['analyzerPassesIndependently'] and not findings['R06']['allRunThresholdsMet'])
    output={'contractVersion':'1.0.0-rc.2','mode':'OFFLINE_REVISION_PROBE','correctedExpectationsMet':ok,'findings':findings,
        'note':'Review script retained unchanged; request wire format/local-key fields and fixture paths migrated explicitly. No production acceptance.'}
    path=ROOT/'docs/execution/reports/T00-T01-rc2-probe.json'
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 0 if ok else 1


if __name__=='__main__':sys.exit(main())
