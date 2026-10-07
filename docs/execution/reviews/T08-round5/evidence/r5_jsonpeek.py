"""Reader helper: print selected keys of a JSON artefact (reviewer's own tooling, no repo writes)."""
import json
import sys

path, keys = sys.argv[1], sys.argv[2:]
data = json.load(open(path, encoding='utf-8'))
if not keys:
    print(json.dumps(data, ensure_ascii=False, indent=1)[:4000])
    sys.exit(0)
for key in keys:
    cur = data
    for part in key.split('.'):
        cur = cur[part] if part else cur
    text = json.dumps(cur, ensure_ascii=False)
    print(f'--- {key} ---')
    print(text if len(text) <= 3000 else text[:3000] + ' …[truncated]')
