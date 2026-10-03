"""R02-A: frozen location coverage, historical projection and rejection paths."""
import copy
import json
import unittest
from test_contracts import ROOT, SCHEMA, API, sample, validator
from test_review_regressions import candidate_example, uid
from reference import (digest, version_hash, manifest_hash, release_hash, release_hash_input,
    freeze_slot_anchors, render_frozen_positions)


def freeze_inputs():
    c=candidate_example()
    version=sample(SCHEMA['$defs']['ArticleVersion'])
    version['meta'].update(id=c['version']['id'],articleId=c['meta']['articleId'],
        versionId=c['version']['id'],ownerId=c['meta']['ownerId'])
    block={'sectionId':'section-1','blockId':'block-A','blockType':'paragraph','text':'第一段😀。',
        'marks':[],'claimRefs':[],'level':None,'items':[],'slotId':None}
    version['contentAst']['blocks']=[block,dict(block,blockId='block-B',text='第二段。')]
    version['meta']['contentHash']=version_hash(dict(version,schemaVersion=version['meta']['schemaVersion']))
    c['version']['hash']=version['meta']['contentHash']
    c['rightsSnapshot']['contentHash']=c['version']['hash']
    c['rightsSnapshot']['hash']=digest({k:v for k,v in c['rightsSnapshot'].items() if k!='hash'})
    second={'slotId':uid(170),'selectionId':uid(150),'assetId':uid(160),'variantId':uid(151),'licenseMetadataId':uid(152)}
    c['selectionBindings'].append(second)
    for name,key in [('selections','selectionId'),('variants','variantId'),('licenses','licenseMetadataId')]:
        c[name].append(dict(c[name][0],id=second[key],hash=digest(name+'-2')))
    manifest=sample(SCHEMA['$defs']['Manifest'])
    manifest['meta'].update(id=c['manifest']['id'],articleId=c['meta']['articleId'],
        versionId=c['version']['id'],ownerId=c['meta']['ownerId'])
    manifest['items']=[];slots=[]
    for i,binding in enumerate(c['selectionBindings']):
        item=sample(SCHEMA['$defs']['ManifestItem']);item.update(binding,displayOrder=i+1,caption='同一图注')
        manifest['items'].append(item)
        slot=sample(SCHEMA['$defs']['ImageSlot'])
        slot['meta'].update(id=binding['slotId'],articleId=c['meta']['articleId'],
            versionId=c['version']['id'],ownerId=c['meta']['ownerId'])
        slot.update(sectionId='section-1',anchorBlockId='block-A',anchorSide='AFTER',position=i,planHash=digest('plan'))
        slots.append(slot)
    manifest['meta']['contentHash']=manifest_hash(manifest)
    c['manifest']['hash']=manifest['meta']['contentHash']
    return c,version,manifest,slots


class SlotAnchors(unittest.TestCase):
    def test_anchor_side_order_plan_hash_and_vectors(self):
        c,v,m,slots=freeze_inputs()
        validator('ArticleVersion').validate(v);validator('Manifest').validate(m)
        for s in slots:validator('ImageSlot').validate(s)
        cases={'baseline':slots}
        for name,update in [('moved',dict(anchorBlockId='block-B',anchorSide='BEFORE')),
                            ('side',dict(anchorSide='BEFORE')),('plan',dict(planHash=digest('new-plan')))]:
            changed=copy.deepcopy(slots);changed[0].update(update);cases[name]=changed
        reordered=copy.deepcopy(slots);reordered[0]['position']=1;reordered[1]['position']=0
        cases['order']=reordered
        vectors=[]
        for name,inputs in cases.items():
            frozen=freeze_slot_anchors(c,v,m,inputs)
            validator('ReleaseCandidate').validate(frozen)
            projection=release_hash_input(frozen);validator('ReleaseHashInput').validate(projection)
            vectors.append({'name':name,'candidate':frozen,'projection':projection,'expectedReleaseHash':frozen['releaseHash'],
                'positions':render_frozen_positions(frozen,v)})
            self.assertEqual(frozen['version'],c['version']);self.assertEqual(frozen['manifest'],c['manifest'])
            self.assertEqual(frozen['selectionBindings'],c['selectionBindings'])
        self.assertEqual(len({x['expectedReleaseHash'] for x in vectors}),len(cases))
        self.assertEqual(vectors[-1]['positions'][0]['slotId'],slots[1]['meta']['id'])
        out=ROOT/'tests/fixtures/contracts/T00/rc3/anchor-vectors.json'
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps({'mode':'OFFLINE_SYNTHETIC','version':v,'manifest':m,'vectors':vectors},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

    def test_history_uses_only_frozen_body_and_candidate(self):
        c,v,m,slots=freeze_inputs();original=copy.deepcopy(c)
        old=freeze_slot_anchors(c,v,m,slots);before=render_frozen_positions(old,v)
        slots[0].update(anchorBlockId='block-B',anchorSide='BEFORE')
        new=freeze_slot_anchors(c,v,m,slots)
        slots.clear()  # Historical rendering has no live slot input or lookup.
        self.assertEqual(render_frozen_positions(old,v),before)
        self.assertNotEqual(render_frozen_positions(new,v),before)
        self.assertNotEqual(old['releaseHash'],new['releaseHash'])
        self.assertEqual(c,original)
        corrupt=copy.deepcopy(old);corrupt['slotAnchors'][0]['position']=9
        with self.assertRaisesRegex(ValueError,'RELEASE_HASH_MISMATCH'):render_frozen_positions(corrupt,v)

    def test_freeze_rejects_missing_extra_duplicate_foreign_and_invalid_blocks(self):
        cases=[('block', 'SLOT_BLOCK',lambda s:s[0].update(anchorBlockId='missing')),
            ('section','SLOT_BLOCK',lambda s:s[0].update(sectionId='foreign')),
            ('version','SLOT_SCOPE',lambda s:s[0]['meta'].update(versionId=uid(999))),
            ('article','SLOT_SCOPE',lambda s:s[0]['meta'].update(articleId=uid(999))),
            ('owner','SLOT_SCOPE',lambda s:s[0]['meta'].update(ownerId=uid(999))),
            ('missing','SLOT_SNAPSHOT_COVERAGE',lambda s:s.pop()),
            ('extra','SLOT_SNAPSHOT_COVERAGE',lambda s:s.append(dict(s[0],meta=dict(s[0]['meta'],id=uid(999))))),
            ('duplicate','DUPLICATE_SLOT_SNAPSHOT',lambda s:s.append(copy.deepcopy(s[0]))),
            ('order-tie','AMBIGUOUS_SLOT_ORDER',lambda s:s[1].update(position=0)),
            ('negative','INVALID_SLOT_POSITION',lambda s:s[0].update(position=-1)),
            ('boolean','INVALID_SLOT_POSITION',lambda s:s[0].update(position=True)),
            ('side','INVALID_SLOT_POSITION',lambda s:s[0].update(anchorSide='MIDDLE'))]
        for name,error,mutate in cases:
            with self.subTest(name=name):
                c,v,m,s=freeze_inputs();mutate(s)
                with self.assertRaisesRegex(ValueError,error):freeze_slot_anchors(c,v,m,s)

    def test_frozen_anchor_and_manifest_exact_binding_coverage(self):
        c,v,m,s=freeze_inputs();frozen=freeze_slot_anchors(c,v,m,s)
        mutations=[lambda x:x['slotAnchors'].pop(),
            lambda x:x['slotAnchors'].append(copy.deepcopy(x['slotAnchors'][0])),
            lambda x:x['selectionBindings'].append(copy.deepcopy(x['selectionBindings'][0])),
            lambda x:x['slotAnchors'][0].update(selectionId=uid(999)),
            lambda x:x['slotAnchors'][0].update(versionId=uid(999))]
        for mutate in mutations:
            bad=copy.deepcopy(frozen);mutate(bad)
            with self.assertRaises(ValueError):release_hash(bad)
        m['items'].pop();m['meta']['contentHash']=manifest_hash(m);c['manifest']['hash']=manifest_hash(m)
        with self.assertRaisesRegex(ValueError,'MANIFEST_BINDING_MISMATCH'):freeze_slot_anchors(c,v,m,s)
        # Duplicates cannot pass by making both manifest and bindings equally wrong.
        c,v,m,s=freeze_inputs();c['selectionBindings'].append(copy.deepcopy(c['selectionBindings'][0]))
        m['items'].append(copy.deepcopy(m['items'][0]));m['meta']['contentHash']=manifest_hash(m);c['manifest']['hash']=manifest_hash(m)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SELECTION_BINDING'):freeze_slot_anchors(c,v,m,s)

    def test_body_hash_block_hash_and_version_fail_closed(self):
        c,v,m,s=freeze_inputs();frozen=freeze_slot_anchors(c,v,m,s)
        for update in [dict(id=uid(999)),dict(ownerId=uid(999)),dict(articleId=uid(999))]:
            bad=copy.deepcopy(v);bad['meta'].update(update)
            with self.assertRaisesRegex(ValueError,'VERSION_SCOPE'):render_frozen_positions(frozen,bad)
        bad=copy.deepcopy(v);bad['contentAst']['blocks'][0]['text']='被改写'
        with self.assertRaisesRegex(ValueError,'VERSION_CONTENT'):freeze_slot_anchors(c,bad,m,s)
        corrupt=copy.deepcopy(frozen);corrupt['slotAnchors'][0]['blockHash']='f'*64;corrupt['releaseHash']=release_hash(corrupt)
        with self.assertRaisesRegex(ValueError,'SLOT_BLOCK'):render_frozen_positions(corrupt,v)
        bad=copy.deepcopy(m);bad['items'][0]['caption']='被改写'
        with self.assertRaisesRegex(ValueError,'MANIFEST_CONTENT'):freeze_slot_anchors(c,v,bad,s)

    def test_unordered_sets_and_empty_selection(self):
        c,v,m,s=freeze_inputs();frozen=freeze_slot_anchors(c,v,m,s)
        reordered=copy.deepcopy(frozen)
        reordered['selectionBindings'].reverse();reordered['slotAnchors'].reverse()
        self.assertEqual(release_hash(frozen),release_hash(reordered))
        self.assertEqual(render_frozen_positions(frozen,v),render_frozen_positions(reordered,v))
        for key in ['selections','variants','licenses','selectionBindings']:c[key]=[]
        m['items']=[];m['meta']['contentHash']=manifest_hash(m);c['manifest']['hash']=manifest_hash(m)
        empty=freeze_slot_anchors(c,v,m,[]);validator('ReleaseCandidate').validate(empty)
        self.assertEqual(empty['slotAnchors'],[]);self.assertEqual(render_frozen_positions(empty,v),[])

    def test_patch_and_invalidation_contract(self):
        for patch in [dict(anchor={'blockId':'block-B','side':'BEFORE'}),dict(position=1)]:
            validator('PatchSlotRequest').validate(patch)
        self.assertFalse(validator('PatchSlotRequest').is_valid({'position':-1}))
        operation=API['paths']['/image-slots/{id}']['patch']
        self.assertTrue(any(p['name']=='If-Match' and p['required'] for p in operation['parameters']))
        events=SCHEMA['$defs']['DependencyEvent']['properties']['type']['enum']
        self.assertIn('SLOT_ANCHOR_CHANGED',events)
        registry=json.loads((ROOT/'docs/execution/contracts/invalidation.json').read_text(encoding='utf-8'))
        self.assertTrue({'QA','CANDIDATE','CURRENT_APPROVAL'}<=set(registry['SLOT_ANCHOR_CHANGED']))

    def test_placeholder_is_not_a_second_position_authority(self):
        c,v,m,s=freeze_inputs()
        placeholder=dict(v['contentAst']['blocks'][0],blockId='placeholder',blockType='imagePlaceholder',
            text='',slotId=s[0]['meta']['id'])
        v['contentAst']['blocks'].insert(0,placeholder)
        v['meta']['contentHash']=version_hash(dict(v,schemaVersion=v['meta']['schemaVersion']))
        c['version']['hash']=v['meta']['contentHash'];c['rightsSnapshot']['contentHash']=c['version']['hash']
        c['rightsSnapshot']['hash']=digest({k:value for k,value in c['rightsSnapshot'].items() if k!='hash'})
        frozen=freeze_slot_anchors(c,v,m,s)
        self.assertEqual(len(render_frozen_positions(frozen,v)),2)
        self.assertTrue(all(a['anchorBlockId']=='block-A' for a in render_frozen_positions(frozen,v)))
        s[0]['anchorBlockId']='placeholder'
        with self.assertRaisesRegex(ValueError,'SLOT_BLOCK_MISMATCH'):freeze_slot_anchors(c,v,m,s)


if __name__=='__main__':unittest.main()
