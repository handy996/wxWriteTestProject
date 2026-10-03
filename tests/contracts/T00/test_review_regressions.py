"""Regression tests for review R01-R05 and the two additional design findings."""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid
from test_contracts import ROOT,SCHEMA,sample,validator,UID
from reference import (release_hash,release_hash_input,resolve_analysis,rights_export_eligible,
    next_skill_version,switch_skill,validate_model_routes,validate_image_size,validate_text_upload,
    restore_allowed,digest)


def uid(number):return str(uuid.UUID(int=number,version=4))


def candidate_example():
    c=sample(SCHEMA['$defs']['ReleaseCandidate'])
    article=uid(10);version=uid(20)
    c['meta'].update(articleId=article,ownerId=uid(30),versionId=version)
    def frozen(number,kind):
        return {'id':uid(number),'articleId':article,'versionId':version,'kind':kind,'hash':digest(kind),'stale':False}
    c['version']=frozen(20,'VERSION');c['manifest']=frozen(40,'MANIFEST')
    c['factSet'].update(articleId=article,versionId=version,claims=[frozen(41,'CLAIM')],verifications=[frozen(42,'VERIFICATION')])
    for n,name in enumerate(['selections','variants','licenses','sourceSnapshots'],50):c[name]=[frozen(n,name)]
    c['selectionBindings']=[{'slotId':uid(70),'selectionId':uid(50),'assetId':uid(60),'variantId':uid(51),'licenseMetadataId':uid(52)}]
    c['slotAnchors']=[{'slotId':uid(70),'selectionId':uid(50),'versionId':version,'anchorBlockId':'block-A',
        'blockHash':digest('block-A'),'anchorSide':'AFTER','position':0,'planHash':digest('plan')}]
    c['rightsSnapshot'].update(id=uid(80),articleId=article,versionId=version,contentHash=c['version']['hash'],basis='OWNED',notes='本稿原创测试材料',evidenceIds=[])
    c['rightsSnapshot']['hash']=digest({k:v for k,v in c['rightsSnapshot'].items() if k!='hash'})
    c['skillSnapshot'].update(id=uid(90),status='PUBLISHED')
    c['policyRefs']=[sample(SCHEMA['$defs']['PolicySnapshot'])]
    c['policyRefs'][0].update(id=uid(91),type='FACT')
    c['releaseHash']=release_hash(c)
    return c


class ReviewRegressions(unittest.TestCase):
    def test_r01_srs_create_request_and_rights_lifecycle(self):
        request={'original':{'format':'MARKDOWN','title':'待编辑文章','content':'可读原文。'*100},
            'skillVersionId':UID,'targetLength':3000,'rightsBasis':'OWNED','budget':{'limit':'5.000000','currency':'USD'}}
        c=candidate_example();rights=c['rightsSnapshot']
        for basis in ['OWNED','AUTHORIZED','REFERENCE_ONLY','UNKNOWN']:
            validator('CreateArticleRequest').validate(dict(request,rightsBasis=basis))
            effective=dict(rights,basis=basis,evidenceIds=[uid(99)])
            self.assertEqual(rights_export_eligible(effective,c['meta']['articleId'],c['version']['id'],c['version']['hash']),basis in ['OWNED','AUTHORIZED'])
        self.assertFalse(validator('CreateArticleRequest').is_valid(dict(request,rightsBasis='LICENSED')))
        self.assertFalse(rights_export_eligible(dict(rights,basis='AUTHORIZED'),c['meta']['articleId'],c['version']['id'],c['version']['hash']))
        supplied=dict(rights,basis='AUTHORIZED',evidenceIds=[uid(99)])
        self.assertTrue(rights_export_eligible(supplied,c['meta']['articleId'],c['version']['id'],c['version']['hash']))
        self.assertFalse(rights_export_eligible(supplied,c['meta']['articleId'],uid(98),c['version']['hash']))
        out=ROOT/'tests/fixtures/contracts/T00/rc3/srs-create-request.json';out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

    def test_r02_schema_candidate_projection_and_protected_inputs(self):
        c=candidate_example();validator('ReleaseCandidate').validate(c)
        projection=release_hash_input(c);validator('ReleaseHashInput').validate(projection)
        self.assertEqual(digest(projection),c['releaseHash'])
        mutations=[('version','hash'),('manifest','hash'),('factSet','hash'),('skillSnapshot','rulesHash'),('rightsSnapshot','hash')]
        for key,field in mutations:
            changed=copy.deepcopy(c);changed[key][field]='f'*64
            if key=='version':changed['rightsSnapshot']['contentHash']='f'*64
            self.assertNotEqual(release_hash(c),release_hash(changed))
        for key in ['claims','verifications']:
            changed=copy.deepcopy(c);changed['factSet'][key][0]['hash']='f'*64
            self.assertNotEqual(release_hash(c),release_hash(changed))
        cross=copy.deepcopy(c);cross['licenses'][0]['articleId']=uid(999)
        with self.assertRaisesRegex(ValueError,'CROSS_ARTICLE'):release_hash(cross)
        omitted=copy.deepcopy(c);omitted['variants']=[]
        with self.assertRaisesRegex(ValueError,'SELECTION_BINDING_COVERAGE'):release_hash(omitted)
        association=copy.deepcopy(c);association['selectionBindings'][0]['assetId']=uid(555)
        self.assertNotEqual(release_hash(c),release_hash(association))
        mutable=copy.deepcopy(c);mutable['meta'].update(stale=True,traceId=uid(11),createdAt='2026-10-03T00:00:00Z')
        mutable['selections'][0]['stale']=True
        self.assertEqual(release_hash(c),release_hash(mutable))
        vector={'candidate':c,'projection':projection,'canonicalVersion':'canonical-v1','expectedReleaseHash':release_hash(c)}
        out=ROOT/'tests/fixtures/contracts/T00/rc3/release-vector.json';out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(vector,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

    def test_r03_new_claim_references_resolve_once(self):
        output=sample(SCHEMA['$defs']['AnalysisOutput']);draft=sample(SCHEMA['$defs']['ClaimDraft'])
        output['factClaims']=[dict(draft,localKey='claim-a'),dict(draft,localKey='claim-b')]
        for i,t in enumerate(output['recommendedTitles']):t['supportedClaimLocalKeys']=['claim-a' if i%2 else 'claim-b']
        validator('AnalysisOutput').validate(output)
        allocated=iter([uid(111),uid(112)])
        resolved,mapping=resolve_analysis(output,lambda:next(allocated))
        validator('AnalysisResolvedOutput').validate(resolved)
        result=sample(SCHEMA['$defs']['AnalysisResult']);result.update(result=resolved,claimIdMap=mapping)
        validator('AnalysisResult').validate(result)
        self.assertEqual(resolved['recommendedTitles'][0]['supportedClaimIds'],[uid(112)])
        for kind in ['unknown','duplicate']:
            bad=copy.deepcopy(output)
            if kind=='unknown':bad['recommendedTitles'][0]['supportedClaimLocalKeys']=['not-here']
            else:bad['factClaims'][1]['localKey']='claim-a'
            with self.assertRaises(ValueError):resolve_analysis(bad,lambda:self.fail('Allocate only after refs validate'))

    def test_r04_first_version_copy_publish_and_switch_plan(self):
        request=sample(SCHEMA['$defs']['CreateSkillVersionRequest']);request.pop('baseVersionId',None)
        validator('CreateSkillVersionRequest').validate(request)
        validator('CreateSkillVersionRequest').validate(dict(request,baseVersionId=None))
        validator('PatchArticleRequest').validate({'skillVersionId':uid(22)})
        self.assertEqual(next_skill_version(uid(1),[]),'1.0.0')
        existing=[{'id':uid(21),'skillId':uid(1),'version':'1.0.0'}]
        self.assertEqual(next_skill_version(uid(1),existing,uid(21)),'1.0.1')
        for base in [None,uid(999)]:
            with self.assertRaises(ValueError):next_skill_version(uid(1),existing,base)
        snapshot=sample(SCHEMA['$defs']['SkillSnapshot']);snapshot.update(id=uid(22),status='PUBLISHED')
        old={'lockVersion':1,'generation':3,'fencingToken':4,'skillVersionId':uid(21),'status':'RUNNING'}
        changed=switch_skill(old,snapshot,1)
        self.assertEqual((changed['generation'],changed['fencingToken'],changed['skillVersionId']),(4,5,uid(22)))
        self.assertEqual(old['skillVersionId'],uid(21))
        with self.assertRaisesRegex(ValueError,'PRECONDITION_FAILED'):switch_skill(old,snapshot,0)
        with self.assertRaisesRegex(ValueError,'SKILL_NOT_PUBLISHED'):switch_skill(old,dict(snapshot,status='DRAFT'),1)

    def test_r05_limits_are_scoped(self):
        zip_ref=sample(SCHEMA['$defs']['ObjectRef']);zip_ref.update(size=21*1024*1024,mime='application/zip')
        validator('ObjectRef').validate(zip_ref)
        self.assertFalse(validator('ImageObjectRef').is_valid(dict(zip_ref,mime='image/png')))
        validator('ImageObjectRef').validate(dict(zip_ref,size=20971520,mime='image/png'))
        for size,pixels in [(20971521,100),(1,40000001)]:
            with self.assertRaisesRegex(ValueError,'IMAGE_LIMIT'):validate_image_size(size,pixels)
        validate_text_upload('a'*1048576)
        with self.assertRaisesRegex(ValueError,'UPLOAD_BYTE_LIMIT'):validate_text_upload('中'*349526)

    def test_routes_and_restore_fail_closed(self):
        route={'capability':'TEXT','model':'mock-text-v1','enabled':True,'maxOutputTokens':1024}
        value=sample(SCHEMA['$defs']['SetProviderRequest']);value['routes']=[route]
        validator('SetProviderRequest').validate(value);validate_model_routes(value['routes'])
        config=sample(SCHEMA['$defs']['ProviderConfig']);config['routes']=[route];validator('ProviderConfig').validate(config)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_CAPABILITY'):validate_model_routes([route,route])
        barrier={'backupCapturedAt':'2026-10-02T00:00:00Z','backupJournalSequence':1,'journalHeadSequence':3,
            'verifiedThroughSequence':3,'missingSequences':[],'unappliedDeletionIds':[],
            'externalJournalAvailable':True,'headSignatureVerified':True}
        validator('RestoreBarrier').validate(barrier);self.assertTrue(restore_allowed(barrier))
        for update in [dict(externalJournalAvailable=False),dict(headSignatureVerified=False),dict(verifiedThroughSequence=1),dict(missingSequences=[2]),dict(unappliedDeletionIds=[UID])]:
            self.assertFalse(restore_allowed(dict(barrier,**update)))


if __name__=='__main__':unittest.main()
