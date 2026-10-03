import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'docs/execution/contracts'))
from reference import canonical, digest, parse_json, text_hash, validate_ast, validate_span, approval_guard, commit_guard, budget_can_reserve, safe_address, topological, version_hash, manifest_hash, release_hash

SCHEMA = json.loads((ROOT/'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))
API = json.loads((ROOT/'docs/api/openapi.yaml').read_text(encoding='utf-8'))
UID = '00000000-0000-4000-8000-000000000001'


def sample(s):
    if '$ref' in s:
        return sample(SCHEMA['$defs'][s['$ref'].split('/')[-1]])
    if 'const' in s:
        return s['const']
    if 'enum' in s:
        return s['enum'][0]
    if 'anyOf' in s:
        return sample(s['anyOf'][0])
    typ = s.get('type')
    if typ == 'object':
        keys = s.get('required', [])[:]
        if s.get('minProperties') and not keys:
            keys = [next(iter(s['properties']))]
        if 'oneOf' in s:
            keys += s['oneOf'][0]['required']
        return {k: sample(s['properties'][k]) for k in keys}
    if typ == 'array':
        return [sample(s['items']) for _ in range(s.get('minItems', 0))]
    if typ == 'integer':
        return s.get('minimum', 0)
    if typ == 'boolean':
        return False
    if typ == 'null':
        return None
    if typ == 'string':
        if s.get('format') == 'uuid':
            return UID
        if s.get('format') == 'date-time':
            return '2026-10-02T12:00:00Z'
        if s.get('format') == 'date':
            return '2026-10-02'
        if s.get('format') == 'uri':
            return 'https://example.invalid/fixture'
        p = s.get('pattern', '')
        if '[a-f0-9]' in p:
            return 'a' * 64
        if '{6}' in p:
            return '0.000000'
        if '{3}' in p:
            return '0.500'
        return 'x' * max(1, s.get('minLength', 1))
    raise ValueError(s)


def validator(name):
    return Draft202012Validator({'$defs':SCHEMA['$defs'], '$ref':'#/$defs/'+name}, format_checker=FormatChecker())


class Contracts(unittest.TestCase):
    def test_standard_openapi_and_schema_validators(self):
        validate_spec(API)
        Draft202012Validator.check_schema(SCHEMA)

    def test_every_schema_has_positive_and_negative_structural_example(self):
        examples = []
        for name, schema in SCHEMA['$defs'].items():
            with self.subTest(schema=name):
                good = sample(schema)
                validator(name).validate(good)
                bad = copy.deepcopy(good)
                bad['__unexpected__'] = 'must reject'
                self.assertFalse(validator(name).is_valid(bad))
                examples.append({'schema':name,'positive':good,'negative':bad,'negativeReason':'additionalProperties'})
        # Store repeatable wire samples; structural, not claimed business-success examples.
        out = ROOT/'tests/fixtures/contracts/T00/rc3/structural-examples.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

    def test_api_inventory_exactly_covers_srs_plus_requested_deletion(self):
        srs = (ROOT/'docs/AI-Editorial-Agent-SRS-v1.0.md').read_text(encoding='utf-8')
        expected = set(re.findall(r'^\| (GET|POST|PATCH|PUT|DELETE) (/[^ ]+) \|',srs,re.M))
        actual = {(m.upper(),p) for p,methods in API['paths'].items() for m in methods}
        self.assertEqual(actual-expected,{('GET','/articles/{id}/deletion-impact'),('POST','/articles/{id}/deletion')})
        self.assertFalse(expected-actual)
        opids = [v['operationId'] for methods in API['paths'].values() for v in methods.values()]
        self.assertEqual(len(opids),len(set(opids)))

    def test_no_client_actor_status_or_model_approval(self):
        for path, methods in API['paths'].items():
            for method, operation in methods.items():
                if method == 'get' or path == '/auth/login':
                    continue
                self.assertEqual(operation['x-actor'],'OWNER')
                headers = {p['name'] for p in operation['parameters'] if p['in']=='header' and p['required']}
                self.assertTrue({'X-CSRF-Token','Idempotency-Key','X-Request-Hash'} <= headers)
                body = operation.get('requestBody')
                if body:
                    name = body['content']['application/json']['schema']['$ref'].split('/')[-1]
                    props = SCHEMA['$defs'][name]['properties']
                    self.assertFalse({'actorId','ownerId','approvedBy','status','licenseVerified'} & set(props))
        for route in ['/articles/{id}/approve','/articles/{id}/reject','/articles/{id}/versions','/articles/{id}/restore','/image-slots/{id}/selection']:
            method = 'put' if route.endswith('selection') else 'post'
            self.assertTrue(any(p['name']=='If-Match' and p['required'] for p in API['paths'][route][method]['parameters']))

    def test_baseline_hashes_and_ownership_dag(self):
        baseline=json.loads((ROOT/'docs/execution/contracts/baseline.json').read_text())
        for name,value in baseline['sourceHashes'].items():
            self.assertEqual(hashlib.sha256((ROOT/'docs'/name).read_bytes()).hexdigest(),value)
        registry=json.loads((ROOT/'docs/execution/contracts/tables.json').read_text(encoding='utf-8'))
        self.assertEqual(len(registry['tables']),38)
        graph={t['name']:t['prerequisites'] for t in registry['tables']}
        self.assertEqual(len(topological(graph)),38)
        full=copy.deepcopy(graph)
        for edge in registry['deferredForeignKeys']:
            full[edge['from']].append(edge['to'])
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_CYCLE'):
            topological(full)
        modules=json.loads((ROOT/'docs/execution/contracts/module-dependencies.json').read_text())
        self.assertEqual(len(topological(modules['compileDependencies'])),17)

    def test_unicode_and_canonical_vectors(self):
        self.assertEqual(canonical({'z':'😀','a':'中\n文','n':1}),'{"a":"中\\n文","n":1,"z":"😀"}'.encode())
        self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}))
        self.assertNotEqual(digest({'a':['x','y']}),digest({'a':['y','x']}))
        self.assertNotEqual(digest('é'),digest('e\u0301'))
        for value in [1.2,float('nan'),2**54,{'中文':1},'\ud800']:
            with self.assertRaises((ValueError,UnicodeError)):
                canonical(value)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_KEY'):
            parse_json('{"a":1,"a":2}')

    def test_codepoint_span_and_business_reference_failures(self):
        txt='甲😀乙'
        span={'blockId':'b1','start':1,'end':2,'quote':'😀','blockHash':text_hash(txt)}
        validate_span(span,{'b1':txt})
        for updates in [{'end':3},{'blockHash':'a'*64},{'blockId':'missing'},{'start':-1}]:
            with self.assertRaises(ValueError):
                validate_span(dict(span,**updates),{'b1':txt})
        block={'sectionId':'s1','blockId':'b1','blockType':'paragraph','text':txt,'marks':[],'claimRefs':[],'level':None,'items':[],'slotId':None}
        ast={'schemaVersion':'1.0.0-rc.3','blocks':[block]}
        validator('ContentAst').validate(ast)
        self.assertEqual(validate_ast(ast),txt)
        for changed in [dict(block,claimRefs=[UID]),dict(block,text='<script>x</script>'),dict(block,blockId='title'),dict(block,level=2)]:
            with self.assertRaises(ValueError):
                validate_ast(dict(ast,blocks=[changed]))

    def test_selection_exclusive_and_license_nullable(self):
        good=sample(SCHEMA['$defs']['SelectImageRequest'])
        validator('SelectImageRequest').validate(good)
        self.assertFalse(validator('SelectImageRequest').is_valid(dict(good,assetId=UID)))
        good.pop('candidateId')
        self.assertFalse(validator('SelectImageRequest').is_valid(good))
        license_option=sample(SCHEMA['$defs']['LicenseOption'])
        license_option['commercialUseAllowed']=None
        validator('LicenseOption').validate(license_option)

    def test_release_hash_covers_evidence_variant_and_excludes_mutable_flags(self):
        from test_review_regressions import candidate_example
        candidate=candidate_example()
        original=release_hash(candidate)
        mutable=copy.deepcopy(candidate);mutable['stale']=True;mutable['selections'][0]['active']=False
        self.assertEqual(original,release_hash(mutable))
        for key in ['selections','variants','licenses','sourceSnapshots','policyRefs']:
            changed=copy.deepcopy(candidate);changed[key][0]['hash']='f'*64
            self.assertNotEqual(original,release_hash(changed))
        version={'schemaVersion':'1.0.0-rc.3','title':'标题','subtitle':None,'contentAst':{'blocks':[]}}
        self.assertNotEqual(version_hash(version),version_hash(dict(version,subtitle='副标题')))
        mf={'items':[],'noticeCompact':'','noticeFull':'','policyVersionId':UID}
        self.assertNotEqual(manifest_hash(mf),manifest_hash(dict(mf,noticeFull='署名')))
        vector={'canonical':'canonical-v1','candidate':candidate,'expectedReleaseHash':original,
            'version':version,'expectedVersionHash':version_hash(version),'manifest':mf,'expectedManifestHash':manifest_hash(mf)}
        path=ROOT/'tests/fixtures/contracts/T00/rc3/hash-vectors.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(vector,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

    def test_approval_fencing_budget_and_safe_fetch_oracles(self):
        qa={'blockers':0,'unresolvedWarnings':0,'pendingRequiredTasks':0,'allExecuted':True,'fresh':True}
        args=['OWNER','HUMAN_REVIEW','"job-1"','"job-1"','h','h',qa]
        self.assertEqual(approval_guard(*args),'ALLOW')
        self.assertEqual(approval_guard('SYSTEM_WORKER',*args[1:]),'APPROVAL_FORBIDDEN')
        self.assertEqual(approval_guard(*args[:2],None,*args[3:]),'PRECONDITION_REQUIRED')
        self.assertEqual(approval_guard(*args[:2],'"job-0"',*args[3:]),'PRECONDITION_FAILED')
        for field in qa:
            bad=dict(qa); bad[field]=False if isinstance(qa[field],bool) else 1
            self.assertEqual(approval_guard(*args[:-1],bad),'QA_BLOCKED')
        self.assertEqual(commit_guard(1,2,'v1','v1'),'HISTORY_ONLY')
        self.assertEqual(commit_guard(1,1,'v1','v2'),'HISTORY_ONLY')
        self.assertEqual(commit_guard(1,1,'v1','v1',True),'CANCELLED_KEEP_COST')
        self.assertTrue(budget_can_reserve('4.000000','0.500000','0.500000','5.000000'))
        self.assertFalse(budget_can_reserve('4.000000','0.500000','0.500001','5.000000'))
        for address in ['127.0.0.1','10.0.0.1','169.254.169.254','::1','fc00::1','::ffff:127.0.0.1']:
            self.assertFalse(safe_address('https://example.invalid',[address]))
        self.assertFalse(safe_address('http://example.invalid',['8.8.8.8']))
        self.assertFalse(safe_address('https://example.invalid',['8.8.8.8','127.0.0.1']))


if __name__=='__main__':
    unittest.main()
