import hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
defs=json.loads((ROOT/'docs/schemas/editorial.schema.json').read_text(encoding='utf-8'))['$defs']
prompts=[]
for p in (ROOT/'backend/src/main/resources/prompts').glob('*.json'):
    v=json.loads(p.read_text(encoding='utf-8'))
    name=v['outputSchema']['$ref'].split('/')[-1]
    prompts.append({'path':str(p.relative_to(ROOT)), 'schema':name, 'existsInApprovedDefinitions':name in defs, 'required':defs.get(name,{}).get('required'), 'userTemplate':v['userTemplate']})
paths=['backend/src/main/java/com/example/editorial/editorial/skill/CursorCodec.java','backend/src/main/java/com/example/editorial/editorial/skill/SkillService.java','backend/src/main/java/com/example/editorial/editorial/skill/SkillConfigValidator.java','backend/src/main/java/com/example/editorial/settings/policy/PromptService.java','backend/src/main/java/com/example/editorial/settings/policy/PolicyService.java','tests/engineering/T05/migration-draft.sql','docs/execution/reports/T05.md']
needles=['return b64','MessageDigest.isEqual','statusJoin =','av.status','validateBindings','binding.hash','ORDER BY version DESC','CREATE FUNCTION','GRANT SELECT','T06','T11','修改路径']
lines=[]
for name in paths:
    for i,line in enumerate((ROOT/name).read_text(encoding='utf-8').splitlines(),1):
        if any(n in line for n in needles): lines.append({'path':name,'line':i,'text':line})
owned=[]
for p in (ROOT/'backend/src').rglob('*'):
    if p.is_file() and ('/editorial/skill/' in p.as_posix() or '/settings/policy/' in p.as_posix()): owned.append(p)
diff_matches=[{'path':str(p.relative_to(ROOT)),'line':i,'text':s} for p in owned for i,s in enumerate(p.read_text(encoding='utf-8').splitlines(),1) if 'diff' in s.lower() or '差异' in s]
schema_equal=hashlib.sha256((ROOT/'docs/schemas/editorial.schema.json').read_bytes()).digest()==hashlib.sha256((ROOT/'backend/src/main/resources/skills/editorial.schema.json').read_bytes()).digest()
data={'prompts':prompts,'lines':lines,'diffSearch':{'files':len(owned),'matches':diff_matches},'schemaCopyByteIdentical':schema_equal,'agentFiles':[str(p) for p in [ROOT/'AGENTS.md',ROOT.parent/'AGENTS.md',ROOT.parent.parent/'AGENTS.md',Path('E:/AGENTS.md')] if p.exists()]}
(HERE/'static-checks.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'lines':lines,'diffSearch':data['diffSearch'],'schemaCopyByteIdentical':schema_equal},ensure_ascii=False))
