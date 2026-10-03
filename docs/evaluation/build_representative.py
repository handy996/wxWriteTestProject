"""Create a NEW dataset; never regenerates or overwrites rc1 fixtures/annotations."""
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/execution/contracts'))
from reference import digest,text_hash
from representative_cases import CASES,CATEGORY_CONTEXT
DATA=Path('tests/fixtures/representative-v1')
ANNOTATIONS=Path('docs/evaluation/representative-v1/annotations')


def put(path,body):
    path=ROOT/path;path.parent.mkdir(parents=True,exist_ok=True)
    raw=body.encode('utf-8')
    if path.exists() and path.read_bytes()!=raw:
        raise ValueError(f'REFUSE_OVERWRITE_EXISTING_DATASET: {path}; create a new version')
    if not path.exists():path.write_bytes(raw)


def js(path,value):put(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    articles=[];claims=[];category_numbers={}
    for category,title,thesis,lead,facts,contradicted,unsupported,correction,closing in CASES:
        category_numbers[category]=category_numbers.get(category,0)+1
        aid=f'{category.lower()}-{category_numbers[category]:02}'
        bodies=[fact+CATEGORY_CONTEXT[category][i] for i,fact in enumerate(facts+[contradicted,unsupported])]
        article=f'# {title}：{thesis}\n\n虚构测试材料；并非现实研究、政策、品牌或个人资料。含故意设置的待核/冲突命题，不能作为已核实内容。\n\n{lead}\n\n'+'\n\n'.join(bodies)+f'\n\n{closing}\n'
        path=DATA/'articles'/f'{aid}.md';put(path,article)
        sources=[]
        # Explicit provenance relationships, not three independent votes.
        for name,body,group,role in [
            ('primary','\n'.join(f'条目{i+1}：{f}' for i,f in enumerate(facts)),aid+'-origin','PRIMARY'),
            ('reprint','本页明确转录primary中的前四项，无独立测量或采访。\n'+'\n'.join(facts[:4]),aid+'-origin','REPRINT'),
            ('correction',correction,aid+'-correction','CORRECTION')]:
            source_path=DATA/'sources'/f'{aid}-{name}.md'
            source=f'# {title} / {name}\n\n合成原始材料，仅在本虚构情境内作为证据。不是现实官方文件或已授权第三方全文。\n\n{body}\n'
            put(source_path,source)
            sources.append({'id':aid+'-'+name,'path':source_path.as_posix(),'sha256':text_hash(source),
                'role':role,'independenceGroup':group,'captureMode':'FULL_ALLOWED_SYNTHETIC','rightsBasis':'TASK_AUTHORED_SYNTHETIC',
                'externalUrl':None,'realWorldAuthority':False})
        rows=[]
        for i,statement in enumerate(facts+[contradicted,unsupported]):
            cid=f'{aid}-c{i+1:02}';rows.append(cid)
            claims.append({'id':cid,'articleId':aid,'text':statement,'blockId':f'b{i+1:02}',
                'start':0,'end':len(statement),'quote':statement,'blockHash':text_hash(bodies[i]),
                'importance':'CRITICAL' if i in (0,8,9) else 'MAJOR','status':'UNREVIEWED',
                'suggestedDecision':'SUPPORTED' if i<8 else 'CONTRADICTED' if i==8 else 'UNVERIFIABLE',
                'suggestedEvidence':{'sourceId':aid+'-primary','locator':f'条目{i+1}'} if i<8 else {'sourceId':aid+'-correction','locator':'正文'},
                'suggestedDisposition':'KEEP' if i<8 else 'REMOVE','humanEvidence':None})
        articles.append({'id':aid,'category':category,'title':title,'thesisCandidate':thesis,'path':path.as_posix(),
            'sha256':text_hash(article),'codepointCount':sum(not c.isspace() and c!='#' for c in article),
            'rightsBasis':'TASK_AUTHORED_SYNTHETIC','status':'UNREVIEWED','claims':rows,'sources':sources,
            'blocks':[{'id':f'b{i+1:02}','text':b} for i,b in enumerate(bodies)]})
    js(DATA/'index.json',{'datasetVersion':'representative-v1.0.0-rc.1','contractVersion':'1.0.0-rc.2',
        'status':'REPRESENTATIVE_CANDIDATE_UNREVIEWED','humanGoldReady':False,'articles':articles,'claimCount':len(claims),
        'freezeHash':digest([{'id':a['id'],'hash':a['sha256'],'sources':a['sources']} for a in articles])})
    js(DATA/'claim-candidates.json',claims)
    fields=['claimId','articleId','claimText','importance','atomicClaimText','qualifiers','sourceIds','locator','decision','disposition','reviewerId','reviewedAt','evidenceRef','status']
    for role,seed in [('A',601),('B',602)]:
        buffer=io.StringIO(newline='');writer=csv.DictWriter(buffer,fieldnames=fields,lineterminator='\n');writer.writeheader()
        ordered=claims[:];random.Random(seed).shuffle(ordered)
        for c in ordered:writer.writerow({'claimId':c['id'],'articleId':c['articleId'],'claimText':c['text'],'status':'UNREVIEWED'})
        put(ANNOTATIONS/f'reviewer-{role}.csv',buffer.getvalue())
    js(ANNOTATIONS/'assignment.json',{'status':'UNASSIGNED','reviewerA':None,'reviewerB':None,'adjudicator':None,
        'independenceEvidence':None,'productRepresentativenessApproval':None,'rightsApproval':None,
        'requiredActions':['通读每篇并补漏，不仅勾选候选200条','A/B独立标注后保留原表','逐条复核分歧并保留理由和证据','确认五类素材代表性，必要时新版本加入获权真实材料']})
    files=[]
    for base in [DATA,ANNOTATIONS]:
        for p in sorted((ROOT/base).rglob('*')):
            if p.is_file() and p.name!='manifest.json':files.append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    js(DATA/'manifest.json',{'datasetVersion':'representative-v1.0.0-rc.1','files':files,'manifestHash':digest(files),'humanGoldReady':False})
    print(f'New representative candidate: {len(articles)} articles, {len(claims)} UNREVIEWED claims; old dataset untouched.')


if __name__=='__main__':main()
