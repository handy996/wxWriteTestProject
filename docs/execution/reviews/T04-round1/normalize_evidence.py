"""Normalize only reviewer-created log text: key=<UUID> -> object UUID <UUID>.

UUIDs are object IDs, not credentials. Keep originals inside this review's ignored
work area and record hashes. Do not touch author evidence or scanner rules.
"""
import hashlib, json, re, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
RAW=HERE/'.work/raw-evidence'
RAW.mkdir(parents=True,exist_ok=True)
records=[]
paths=[HERE/'verification.json']+list((HERE/'test-results').glob('*.xml'))
for p in paths:
    data=p.read_text(encoding='utf-8')
    normalized,count=re.subn(r'key=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',r'object UUID \1',data)
    if not count: continue
    backup=RAW/p.name
    assert not backup.exists()
    shutil.copyfile(p,backup)
    original_hash=hashlib.sha256(p.read_bytes()).hexdigest()
    p.write_text(normalized,encoding='utf-8')
    records.append(dict(path=p.relative_to(HERE).as_posix(),originalSha256=original_hash,
                        normalizedSha256=hashlib.sha256(p.read_bytes()).hexdigest(),replacements=count))
(HERE/'evidence-normalization.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
print(json.dumps(records))
