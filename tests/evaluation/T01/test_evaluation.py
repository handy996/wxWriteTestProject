import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'docs/evaluation'))
sys.path.insert(0,str(ROOT/'docs/execution/contracts'))
from evaluate import demo_bundle,evaluate,metric_run
from reference import digest,license_decision,text_hash
import build_fixtures


class Evaluation(unittest.TestCase):
    def setUp(self):
        self.bundle=demo_bundle()

    def test_dataset_counts_lengths_sources_hashes_and_unreviewed(self):
        index=json.loads((ROOT/'tests/fixtures/index.json').read_text(encoding='utf-8'))
        self.assertEqual(len(index['articles']),20)
        for category in ['SCIENCE','HISTORY','POLICY','BRAND','NARRATIVE']:
            self.assertEqual(sum(a['category']==category for a in index['articles']),4)
        for a in index['articles']:
            self.assertTrue(1000<=a['codepointCount']<=5000)
            self.assertEqual(a['humanReviewStatus'],'UNREVIEWED')
            for p,h in [('path','sha256'),('sourcePath','sourceSha256')]:
                self.assertEqual(hashlib.sha256((ROOT/a[p]).read_bytes()).hexdigest(),a[h])
        claims=json.loads((ROOT/'tests/fixtures/claims/candidates.json').read_text(encoding='utf-8'))
        self.assertEqual(len(claims),200)
        by_article={a['id']:a for a in index['articles']}
        for c in claims:
            self.assertEqual(c['status'],'UNREVIEWED')
            block=next(b for b in by_article[c['articleId']]['blocks'] if b['id']==c['blockId'])
            self.assertEqual(block['text'][c['start']:c['end']],c['quote'])
            self.assertEqual(text_hash(block['text']),c['blockHash'])

    def test_blind_templates_are_not_fabricated_annotations(self):
        ids=[]
        for letter in ['A','B']:
            with (ROOT/f'docs/evaluation/annotations/reviewer-{letter}.csv').open(encoding='utf-8-sig') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),200)
            self.assertTrue(all(r['status']=='UNREVIEWED' and not r['decision'] and not r['reviewerId'] for r in rows))
            ids.append([r['claimId'] for r in rows])
        self.assertEqual(set(ids[0]),set(ids[1]));self.assertNotEqual(ids[0],ids[1])

    def test_demo_metrics_known_counts_and_no_acceptance(self):
        result=evaluate(self.bundle,True)
        self.assertEqual(result['runs'][0]['recall'],1)
        self.assertEqual(result['runs'][0]['precision'],1)
        self.assertEqual(result['runs'][1]['recall'],199/200)
        self.assertEqual(len(result['runs'][1]['criticalMisses']),1)
        self.assertEqual(result['runs'][2]['precision'],200/201)
        self.assertEqual(result['runs'][2]['falseSupportedCount'],1)
        self.assertFalse(result['allRunThresholdsMet'])
        self.assertFalse(result['acceptancePassed'])
        self.assertEqual(result['threeRunCosts']['actualTotal'],'0.000000')

    def test_unreviewed_and_fake_independent_humans_block(self):
        b=copy.deepcopy(self.bundle);b['mode']='REAL';b['goldStatus']='UNREVIEWED'
        with self.assertRaisesRegex(ValueError,'UNREVIEWED_GOLD'):
            evaluate(b)
        b['goldStatus']='ADJUDICATED';b['independenceEvidence']='example'
        b['gold'][0].update(status='ADJUDICATED',reviewA={'reviewerId':'same'},reviewB={'reviewerId':'same'})
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_REVIEWERS_REQUIRED'):
            evaluate(b)

    def test_matching_rejects_cross_article_unknown_and_duplicate_ids(self):
        for mutation,reason in [('cross','CROSS_ARTICLE_MATCH'),('unknown','UNKNOWN_GOLD_REFERENCE'),('duplicate','DUPLICATE_PREDICTION_ID')]:
            r=copy.deepcopy(self.bundle['runs'][0])
            if mutation=='cross':r['predictions'][0]['matchedGoldId']=self.bundle['gold'][10]['id']
            if mutation=='unknown':r['predictions'][0]['matchedGoldId']='missing'
            if mutation=='duplicate':r['predictions'][1]['id']=r['predictions'][0]['id']
            with self.assertRaisesRegex(ValueError,reason):
                metric_run(self.bundle['gold'],r,self.bundle['articleIds'],True)

    def test_empty_predictions_are_zero_precision_not_divide_by_zero(self):
        r=copy.deepcopy(self.bundle['runs'][0]);r['predictions']=[]
        result=metric_run(self.bundle['gold'],r,self.bundle['articleIds'],True)
        self.assertEqual(result['precision'],0);self.assertEqual(result['recall'],0)
        self.assertEqual(len(result['criticalMisses']),60)

    def test_unknown_and_estimated_cost_not_silently_free(self):
        r=copy.deepcopy(self.bundle['runs'][0])
        r['costs'][0]['entries'][0].update(kind='UNKNOWN',amount='0.300000')
        r['costs'][1]['entries'][0].update(kind='ESTIMATED',amount='0.200000')
        result=metric_run(self.bundle['gold'],r,self.bundle['articleIds'],True)
        self.assertEqual(result['cost']['actual'],'0.000000')
        self.assertEqual(result['cost']['unknownReserved'],'0.300000')
        self.assertEqual(result['cost']['estimated'],'0.200000');self.assertFalse(result['thresholdsMet'])
        r['costs'][0]['entries'][0]['amount']='NaN'
        with self.assertRaisesRegex(ValueError,'INVALID_COST_AMOUNT'):
            metric_run(self.bundle['gold'],r,self.bundle['articleIds'],True)

    def test_incomplete_or_changed_runs_rejected(self):
        for mutation,reason in [('missing','EXPECTED_THREE_DISTINCT_RUNS'),('model','INCOMPARABLE_RUNS'),('article','INCOMPLETE_RUN')]:
            b=copy.deepcopy(self.bundle)
            if mutation=='missing':b['runs'].pop()
            if mutation=='model':b['runs'][1]['model']='different'
            if mutation=='article':b['runs'][0]['completedArticleIds'].pop()
            with self.assertRaisesRegex(ValueError,reason):evaluate(b,True)

    def test_license_vectors_and_coverage_inventory(self):
        cases=json.loads((ROOT/'tests/fixtures/licenses/cases.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(cases),20)
        for case in cases:
            with self.subTest(case=case['id']):self.assertEqual(license_decision(case['input']),case['expected'])
        coverage=json.loads((ROOT/'docs/evaluation/ac-coverage.json').read_text(encoding='utf-8'))
        self.assertEqual({c['ac'] for c in coverage},{f'AC-{i:02}' for i in range(1,36)})
        self.assertTrue(all(c['businessTestStatus']=='NOT_EXECUTED' for c in coverage))

    def test_frozen_manifest_bytes_match(self):
        manifest=json.loads((ROOT/'tests/fixtures/freeze-manifest.json').read_text(encoding='utf-8'))
        self.assertFalse(manifest['humanGoldReady'])
        self.assertEqual(manifest['manifestHash'],digest(manifest['files']))
        for row in manifest['files']:
            content=(ROOT/row['path']).read_bytes()
            self.assertEqual(len(content),row['bytes'])
            self.assertEqual(hashlib.sha256(content).hexdigest(),row['sha256'])

    def test_regeneration_refuses_to_overwrite_human_work(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_root=Path(directory);folder=fake_root/'docs/evaluation/annotations';folder.mkdir(parents=True)
            (folder/'reviewer-A.csv').write_text('status,reviewerId,decision\nUNREVIEWED,person-a,\n',encoding='utf-8')
            with patch.object(build_fixtures,'ROOT',fake_root):
                with self.assertRaisesRegex(SystemExit,'REFUSE_OVERWRITE'):
                    build_fixtures.protect_annotations()

    def perfect_bundle(self):
        b=copy.deepcopy(self.bundle)
        for number,run in enumerate(b['runs']):
            run['predictions']=[{'id':f'{number}-{g["id"]}','articleId':g['articleId'],'importance':g['importance'],
                'matchedGoldId':g['id'],'verificationStatus':g['decision']} for g in b['gold']]
        return b

    def test_r06_low_editing_mean_cannot_pass(self):
        b=self.perfect_bundle()
        for run in b['runs']:
            for q in run['editorialScores']:
                q['scores']={d:4 if d=='THESIS' else 1 for d in q['scores']}
        result=evaluate(b,True)
        self.assertEqual(result['runs'][0]['editorialMean'],1.6)
        self.assertTrue(result['runs'][0]['gates']['analyzer'])
        self.assertFalse(result['runs'][0]['gates']['editorial'])
        self.assertFalse(result['allRunThresholdsMet'])

    def test_r06_average_four_and_analyzer_ninety_percent_boundaries(self):
        b=self.perfect_bundle()
        for run in b['runs']:
            for q in run['analyzerScores'][-2:]:q['coreThesisScore']=3
        good=evaluate(b,True)
        self.assertTrue(good['allRunThresholdsMet'])
        self.assertEqual(good['runs'][0]['editorialMean'],4.0)
        self.assertEqual(good['runs'][0]['analyzerThesisAtLeast4Rate'],.9)
        b['runs'][0]['editorialScores'][0]['scores']['INFORMATION_DENSITY']=3
        self.assertFalse(evaluate(b,True)['allRunThresholdsMet'])
        b=self.perfect_bundle()
        for q in b['runs'][0]['analyzerScores'][-3:]:q['coreThesisScore']=3
        self.assertFalse(evaluate(b,True)['allRunThresholdsMet'])

    def test_r06_reversal_and_missing_evidence_block(self):
        b=self.perfect_bundle();b['runs'][0]['editorialScores'][0]['keyThesisReversed']=True
        self.assertFalse(evaluate(b,True)['allRunThresholdsMet'])
        for mutation,reason in [('density','MISSING_RUBRIC_DIMENSION'),('analyzer','INCOMPLETE_ANALYZER_SCORES'),('reversal','MISSING_THESIS_REVERSAL_EVIDENCE')]:
            b=self.perfect_bundle()
            if mutation=='density':b['runs'][0]['editorialScores'][0]['scores'].pop('INFORMATION_DENSITY')
            elif mutation=='analyzer':b['runs'][0].pop('analyzerScores')
            else:b['runs'][0]['editorialScores'][0].pop('keyThesisReversed')
            with self.assertRaisesRegex(ValueError,reason):evaluate(b,True)

    def test_representative_dataset_is_separate_and_has_category_specific_material(self):
        root=ROOT/'tests/fixtures/representative-v1'
        index=json.loads((root/'index.json').read_text(encoding='utf-8'))
        self.assertFalse(index['humanGoldReady']);self.assertEqual(index['claimCount'],200)
        self.assertEqual(len(index['articles']),20)
        for category in ['SCIENCE','HISTORY','POLICY','BRAND','NARRATIVE']:
            rows=[a for a in index['articles'] if a['category']==category];self.assertEqual(len(rows),4)
            self.assertEqual(len({a['thesisCandidate'] for a in rows}),4)
        for a in index['articles']:
            self.assertTrue(1000<=a['codepointCount']<=5000)
            self.assertEqual(a['status'],'UNREVIEWED')
            self.assertEqual(a['sources'][0]['independenceGroup'],a['sources'][1]['independenceGroup'])
            self.assertNotEqual(a['sources'][0]['independenceGroup'],a['sources'][2]['independenceGroup'])
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        for record in manifest['files']:
            self.assertEqual(hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest(),record['sha256'])


if __name__=='__main__':unittest.main()
