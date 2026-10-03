"""Offline evaluation of adjudicated matches; no model/network calls.

CLI: --input BUNDLE --output REPORT. Exit 0 = calculation succeeded, NOT acceptance.
Exit 2 = incomplete/invalid evaluation evidence. --demo is explicitly synthetic.
"""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/execution/contracts'))
from reference import digest

RUBRIC_VERSION='editorial-quality-v2'
# The SRS five equally weighted editorial dimensions. Analyzer scoring is separate.
DIMENSIONS=['THESIS','STRUCTURE','INFORMATION_DENSITY','TITLE_CONSISTENCY','MOBILE_READABILITY']


def require(condition,message):
    if not condition:
        raise ValueError(message)


def reviewed(record,demo=False):
    if demo:
        return
    require(record.get('status')=='ADJUDICATED','UNREVIEWED_GOLD')
    a=record.get('reviewA',{});b=record.get('reviewB',{})
    require(a.get('reviewerId') and b.get('reviewerId') and a['reviewerId']!=b['reviewerId'],'INDEPENDENT_REVIEWERS_REQUIRED')
    require(all(r.get('evidenceRef') and r.get('reviewedAt') and r.get('decision') for r in [a,b]),'ANNOTATION_EVIDENCE_REQUIRED')
    require(record.get('adjudicator') and record.get('adjudicationEvidence'),'ADJUDICATION_EVIDENCE_REQUIRED')


def metric_run(gold,run,article_ids,demo=False):
    gold_by_id={g['id']:g for g in gold}
    require(len(gold_by_id)==len(gold),'DUPLICATE_GOLD_ID')
    major={g['id'] for g in gold if g['importance'] in ('CRITICAL','MAJOR')}
    require(major,'EMPTY_MAJOR_GOLD')
    seen=set();matched=set();false_positives=[];false_supported=[];unknown_support=[]
    for p in run['predictions']:
        require(p['id'] not in seen,'DUPLICATE_PREDICTION_ID');seen.add(p['id'])
        require(p['articleId'] in article_ids,'UNKNOWN_ARTICLE')
        require(p.get('verificationStatus') in ('UNVERIFIED','SUPPORTED','PARTIAL','CONTRADICTED','UNVERIFIABLE','REQUIRES_REVIEW','STALE'),'INVALID_PREDICTION_STATUS')
        require(p.get('importance') in ('CRITICAL','MAJOR','MINOR'),'INVALID_PREDICTION_IMPORTANCE')
        if not demo:
            require(p.get('matchReviewStatus')=='REVIEWED' and p.get('matchReviewer') and p.get('matchEvidence'),'UNREVIEWED_MATCH')
        gid=p.get('matchedGoldId')
        if gid is not None:
            require(gid in gold_by_id,'UNKNOWN_GOLD_REFERENCE')
            require(gold_by_id[gid]['articleId']==p['articleId'],'CROSS_ARTICLE_MATCH')
        if p['importance'] in ('CRITICAL','MAJOR'):
            if gid in major and gid not in matched:
                matched.add(gid)
            else:
                false_positives.append(p['id'])
        if p['verificationStatus']=='SUPPORTED':
            if gid is None:
                unknown_support.append(p['id'])
            elif gold_by_id[gid]['decision'] in ('CONTRADICTED','UNVERIFIABLE','PARTIAL','REQUIRES_REVIEW'):
                false_supported.append({'predictionId':p['id'],'goldId':gid,'articleId':p['articleId'],'goldDecision':gold_by_id[gid]['decision']})
    predicted_major=sum(p['importance'] in ('CRITICAL','MAJOR') for p in run['predictions'])
    recall=len(matched)/len(major)
    precision=len(matched)/predicted_major if predicted_major else 0.0
    critical_misses=[{'goldId':g['id'],'articleId':g['articleId'],'text':g['text'],'requiredAction':'逐例分析原因、修复、同冻结集重测'} for g in gold if g['importance']=='CRITICAL' and g['id'] not in matched]
    quality=run['editorialScores']
    require(len(quality)==len(article_ids) and {q['articleId'] for q in quality}==set(article_ids),'INCOMPLETE_EDITORIAL_SCORES')
    for q in quality:
        require(set(q['scores'])==set(DIMENSIONS),'MISSING_RUBRIC_DIMENSION')
        require(all(type(v) is int and 1<=v<=5 for v in q['scores'].values()),'INVALID_RUBRIC_SCORE')
        require(type(q.get('keyThesisReversed')) is bool,'MISSING_THESIS_REVERSAL_EVIDENCE')
        if not demo:
            require(q.get('reviewerId') and q.get('evidenceRef') and q.get('status')=='REVIEWED','UNREVIEWED_EDITORIAL_SCORE')
            require(set(q.get('dimensionEvidence',{}))==set(DIMENSIONS) and all(q['dimensionEvidence'].values()),'MISSING_DIMENSION_EVIDENCE')
            require(q.get('thesisReversalEvidence'),'MISSING_THESIS_REVERSAL_EVIDENCE')
    analyzer=run.get('analyzerScores',[])
    require(len(analyzer)==len(article_ids) and {q['articleId'] for q in analyzer}==set(article_ids),'INCOMPLETE_ANALYZER_SCORES')
    for q in analyzer:
        require(type(q.get('coreThesisScore')) is int and 1<=q['coreThesisScore']<=5,'INVALID_ANALYZER_SCORE')
        if not demo:
            require(q.get('reviewerId') and q.get('evidenceRef') and q.get('status')=='REVIEWED','UNREVIEWED_ANALYZER_SCORE')
    thesis_rate=sum(q['coreThesisScore']>=4 for q in analyzer)/len(article_ids)
    editorial_mean=Decimal(sum(sum(q['scores'].values()) for q in quality))/Decimal(len(article_ids)*len(DIMENSIONS))
    reversed_articles=[q['articleId'] for q in quality if q['keyThesisReversed']]
    costs=run['costs']
    require(len(costs)==len(article_ids) and {c['articleId'] for c in costs}==set(article_ids),'INCOMPLETE_COST_ROWS')
    actual=Decimal('0');estimated=Decimal('0');reserved=Decimal('0');unknown=[]
    by_article={a:Decimal('0') for a in article_ids}; ledger_keys=set()
    for c in costs:
        for entry in c['entries']:
            key=entry['idempotencyKey'];require(key not in ledger_keys,'DUPLICATE_COST_ENTRY');ledger_keys.add(key)
            require(entry['currency']=='USD','MIXED_OR_UNSUPPORTED_CURRENCY')
            require(entry['kind'] in ('ACTUAL','ESTIMATED','UNKNOWN'),'INVALID_COST_KIND')
            require(isinstance(entry['amount'],str),'COST_MUST_BE_DECIMAL_STRING')
            try:
                amount=Decimal(entry['amount'])
            except InvalidOperation as exc:
                raise ValueError('INVALID_COST_AMOUNT') from exc
            require(amount.is_finite() and amount>=0 and amount.as_tuple().exponent>=-6,'INVALID_COST_AMOUNT')
            require(entry.get('pricingVersion'),'MISSING_PRICING_VERSION')
            if entry['kind']=='ACTUAL':
                actual+=amount;by_article[c['articleId']]+=amount
            elif entry['kind']=='ESTIMATED':
                estimated+=amount
            else:
                reserved+=amount;unknown.append({'articleId':c['articleId'],'entry':key})
    require(costs and all(c['entries'] for c in costs),'MISSING_COST_EVIDENCE')
    gates={'facts':recall>=.95 and precision>=.90 and not critical_misses and not false_supported and not unknown_support,
        'analyzer':thesis_rate>=.90,'editorial':editorial_mean>=4 and not reversed_articles,
        'cost':not unknown and not estimated}
    return {'runId':run['id'],'recall':recall,'precision':precision,'truePositiveCount':len(matched),'goldMajorCount':len(major),
        'predictedMajorCount':predicted_major,'falsePositiveIds':false_positives,'criticalMisses':critical_misses,
        'falseSupportedCount':len(false_supported),'falseSupportedCases':false_supported,'supportedWithoutGoldMatch':unknown_support,
        'rubricVersion':RUBRIC_VERSION,'analyzerThesisAtLeast4Rate':thesis_rate,
        'editorialMean':float(editorial_mean),'keyThesisReversedArticleIds':reversed_articles,
        'rubricMean':{d:statistics.mean(q['scores'][d] for q in quality) for d in DIMENSIONS},'gates':gates,
        'cost':{'currency':'USD','actual':f'{actual:.6f}','estimated':f'{estimated:.6f}','unknownReserved':f'{reserved:.6f}',
            'unknownEntries':unknown,'actualByArticle':{k:f'{v:.6f}' for k,v in by_article.items()}},
        'thresholdsMet':all(gates.values())}


def evaluate(bundle,demo=False):
    require(bundle.get('mode') in ('REAL','MOCK','SYNTHETIC_ORACLE'),'INVALID_MODE')
    require(demo==(bundle.get('mode')=='SYNTHETIC_ORACLE'),'DEMO_MODE_MISMATCH')
    if not demo:
        require(bundle.get('goldStatus')=='ADJUDICATED','UNREVIEWED_GOLD')
        require(bundle.get('independenceEvidence'),'INDEPENDENCE_EVIDENCE_REQUIRED')
    gold=bundle['gold'];articles=bundle['articleIds']
    require(len(articles)==20 and len(set(articles))==20,'EXPECTED_TWENTY_ARTICLES')
    require(len([g for g in gold if g['importance'] in ('CRITICAL','MAJOR')])>=200,'EXPECTED_200_MAJOR_CLAIMS')
    for g in gold:
        require(g['articleId'] in articles,'UNKNOWN_GOLD_ARTICLE')
        require(g['decision'] in ('SUPPORTED','PARTIAL','CONTRADICTED','UNVERIFIABLE','REQUIRES_REVIEW'),'INVALID_GOLD_DECISION')
        reviewed(g,demo)
    require(len(bundle['runs'])==3 and len({r['id'] for r in bundle['runs']})==3,'EXPECTED_THREE_DISTINCT_RUNS')
    fingerprints=['datasetHash','goldHash','model','promptHash','skillHash','policyHash','parametersHash']
    require(bundle.get('datasetHash') and bundle.get('goldHash')==digest(gold),'GOLD_HASH_MISMATCH')
    for r in bundle['runs']:
        require(all(r.get(k) for k in fingerprints),'MISSING_RUN_PROVENANCE')
        require(r['datasetHash']==bundle['datasetHash'] and r['goldHash']==bundle['goldHash'],'DATASET_HASH_MISMATCH')
        require(all(r[k]==bundle['runs'][0][k] for k in fingerprints),'INCOMPARABLE_RUNS')
        require(set(r['completedArticleIds'])==set(articles) and len(r['completedArticleIds'])==20,'INCOMPLETE_RUN')
    results=[metric_run(gold,r,articles,demo) for r in bundle['runs']]
    distributions={k:{'min':min(r[k] for r in results),'median':statistics.median(r[k] for r in results),'max':max(r[k] for r in results)}
        for k in ('recall','precision','falseSupportedCount','analyzerThesisAtLeast4Rate','editorialMean')}
    all_actual=[Decimal(v) for r in results for v in r['cost']['actualByArticle'].values()]
    all_actual.sort()
    costs={'actualTotal':f'{sum(all_actual):.6f}','perArticleMin':f'{min(all_actual):.6f}',
        'perArticleMedian':f'{statistics.median(all_actual):.6f}',
        'perArticleP95':f'{all_actual[(95*len(all_actual)+99)//100-1]:.6f}',
        'perArticleMax':f'{max(all_actual):.6f}','currency':'USD','note':'UNKNOWN and ESTIMATED reported separately; no token/reasoning-token double counting.'}
    return {'status':'SYNTHETIC_TOOL_DEMO' if demo else 'CALCULATED_AWAITING_MAIN_AGENT_REVIEW',
        'mode':bundle['mode'],'datasetHash':bundle['datasetHash'],'goldHash':bundle['goldHash'],
        'humanGoldVerifiedByThisTool':False,'acceptancePassed':False,
        'rubricVersion':RUBRIC_VERSION,'allRunThresholdsMet':all(r['thresholdsMet'] for r in results),
        'runs':results,'distributions':distributions,'threeRunCosts':costs,
        'limits':['Identity and annotation evidence must be checked by the main agent; nonempty fields alone do not authenticate humans.',
                  'Metrics describe the frozen set only. Mock and synthetic results are not real model quality evidence.',
                  'Actual paid-call ledger reconciliation and integration remain T08/T09/T36/T37 responsibilities.']}


def demo_bundle():
    index=json.loads((ROOT/'tests/fixtures/index.json').read_text(encoding='utf-8'))
    candidates=json.loads((ROOT/'tests/fixtures/claims/candidates.json').read_text(encoding='utf-8'))
    gold=[{'id':c['id'],'articleId':c['articleId'],'text':c['text'],'importance':c['importance'],'decision':c['proposedLabel'],'status':'SYNTHETIC_ORACLE'} for c in candidates]
    article_ids=[a['id'] for a in index['articles']]
    bundle={'mode':'SYNTHETIC_ORACLE','goldStatus':'NOT_HUMAN_GOLD','datasetHash':index['freezeHash'],
        'gold':gold,'goldHash':digest(gold),'articleIds':article_ids,'runs':[]}
    for number in range(1,4):
        predictions=[{'id':f'r{number}-{g["id"]}','articleId':g['articleId'],'importance':g['importance'],
            'matchedGoldId':g['id'],'verificationStatus':g['decision']} for g in gold]
        if number==2:
            predictions=predictions[1:]  # exercise explicit critical false-negative list
        if number==3:
            predictions[9]['verificationStatus']='SUPPORTED' # exercise incorrect support
            predictions.append(dict(predictions[0],id='duplicate-semantic-claim'))
        provenance={'datasetHash':bundle['datasetHash'],'goldHash':bundle['goldHash'],'model':'SYNTHETIC_NO_MODEL',
            'promptHash':digest('mock-prompt'),'skillHash':digest('mock-skill'),'policyHash':digest('mock-policy'),'parametersHash':digest({})}
        bundle['runs'].append(dict(provenance,id=f'synthetic-run-{number}',completedArticleIds=article_ids[:],
            predictions=predictions,editorialScores=[{'articleId':a,'scores':{d:4 for d in DIMENSIONS},'keyThesisReversed':False,'status':'SYNTHETIC'} for a in article_ids],
            analyzerScores=[{'articleId':a,'coreThesisScore':4,'status':'SYNTHETIC'} for a in article_ids],
            costs=[{'articleId':a,'entries':[{'idempotencyKey':f'r{number}-{a}','kind':'ACTUAL','amount':'0.000000','currency':'USD','pricingVersion':'MOCK_ZERO_NO_CALL'}]} for a in article_ids]))
    return bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--input',type=Path);group.add_argument('--demo',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        bundle=demo_bundle() if args.demo else json.loads(args.input.read_text(encoding='utf-8'))
        result=evaluate(bundle,args.demo);code=0
    except (ValueError,KeyError,TypeError) as exc:
        result={'status':'BLOCKED_INCOMPLETE_EVIDENCE','reason':str(exc),'acceptancePassed':False};code=2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'acceptancePassed':False,'output':str(args.output)},ensure_ascii=False))
    return code


if __name__=='__main__':
    sys.exit(main())
