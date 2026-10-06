"""Read-only comparisons to previous review and author delivery manifests."""
import hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=json.loads((HERE/'before.json').read_text(encoding='utf-8'))
previous=json.loads((ROOT/'docs/execution/reviews/T04-round1/before.json').read_text(encoding='utf-8'))
old={item['path']:item['sha256'] for item in previous['files']}
new={item['path']:item['sha256'] for item in before['files']}
changes=[dict(path=p,previousSha256=old[p],currentSha256=new.get(p)) for p in sorted(old) if old[p]!=new.get(p)]
delivery=json.loads((ROOT/'tests/engineering/T04/revision1/integrity.json').read_text(encoding='utf-8'))['delivery']
failures=[item['path'] for item in delivery if digest(ROOT/item['path'])!=item['sha256']]
approval=json.loads((ROOT/'docs/execution/reviews/T00-rc3-approval.json').read_text(encoding='utf-8'))
expected=approval['files']+[dict(path=approval['manifestPath'],sha256=approval['manifestSha256'])]
baseline=json.loads((ROOT/'docs/execution/contracts/baseline.json').read_text(encoding='utf-8'))
expected += [dict(path='docs/'+p,sha256=h) for p,h in baseline['sourceHashes'].items()]
frozen=[v['path'] for v in expected if digest(ROOT/v['path'])!=v['sha256']]
out=dict(snapshotFiles=len(new),changedExistingSinceRound1=changes,
         newFilesSinceRound1=[p for p in sorted(new) if p not in old],
         authorDeliveryFingerprints=len(delivery),authorDeliveryMismatches=failures,
         approvedFingerprints=len(expected),approvedMismatches=frozen)
(HERE/'input-comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['changedExistingSinceRound1','newFilesSinceRound1']}))
print(json.dumps([v['path'] for v in changes]))
assert not failures and not frozen
