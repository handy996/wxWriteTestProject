import hashlib, json, re, sys, pathlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = pathlib.Path('.')
srs = (ROOT/'docs/AI-Editorial-Agent-SRS-v1.0.md').read_text(encoding='utf-8').splitlines()
def show(n, label):
    line = srs[n-1]
    print(f'SRS line {n} ({label}) len={len(line)}')
    print('   ascii-safe excerpt:', re.sub(r'[^\x20-\x7e]', '?', line)[:200])
for n, label in [(1099, 'daily budget example'), (1103, 'count ceilings'), (1143, 'alert >80%'), (1281, 'OQ-09')]:
    show(n, label)
# what the gate extracts, recomputed independently
line = srs[1102]
pats = {'search-queries-per-article': r'总检索 query 上限 ([0-9,]+)',
        'model-output-tokens-per-article': r'输出总 token 上限 ([0-9,]+)',
        'queries-per-claim': r'单 Claim query 上限 ([0-9,]+)',
        'auto-edit-loops-per-article': r'自动编辑循环 ([0-9,]+)',
        'image-units-per-slot': r'单 Slot 生图 ([0-9,]+) 次',
        'image-units-per-article': r'每篇生成 ([0-9,]+) 张'}
print('SRS 32.2 counts parsed by this reviewer:', {k: re.search(p, line).group(1) for k, p in pats.items()})
print('SRS daily example:', re.search(r'日预算示例\s*([0-9.]+)\s*USD', srs[1098]).group(1))
print('SRS alert percent:', re.search(r'预算\s*>\s*([0-9]+)%', srs[1142]).group(1))
print('OQ-09 line has 示例:', '示例' in srs[1280], '| OQ-09:', 'OQ-09' in srs[1280])
cfg = (ROOT/'backend/src/main/java/com/example/editorial/cost/BudgetPolicyConfig.java').read_text(encoding='utf-8')
print('code count() fallbacks:', re.findall(r'count\(env,\s*"([^"]+)",\s*([0-9_]+)\)', cfg))
print('code getProperty defaults:', re.findall(r'getProperty\("([^"]+)",\s*(?:Integer\.class,\s*)?"?([\w.]+)"?\)', cfg))
print('all numeric literals in BudgetPolicyConfig (excluding line numbers):',
      sorted({m for m in re.findall(r'(?<=[\s,(=])\d[\d_]*(?=[\s,);])', cfg)}))
yml = (ROOT/'backend/src/main/resources/application.yml').read_text(encoding='utf-8')
print('application.yml cost block:', re.sub(r'\s+', ' ', yml[yml.find('  cost:'):yml.find('  cost:')+200]))
# every ceiling-ish default anywhere in the cost main package
for p in sorted((ROOT/'backend/src/main/java/com/example/editorial/cost').glob('*.java')):
    txt = p.read_text(encoding='utf-8')
    hits = re.findall(r'getProperty\("[^"]+",\s*(?:[A-Za-z]+\.class,\s*)?[^)]{0,24}\)', txt)
    hits = [h for h in hits if re.search(r'\d', h)]
    if hits:
        print(f'  {p.name}: defaults-in-source {hits}')
print('v5/draft sha256:', [hashlib.sha256((ROOT/p).read_bytes()).hexdigest()[:16] for p in
      ['backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql',
       'tests/engineering/T08/migration-draft.sql']])
draft = (ROOT/'tests/engineering/T08/migration-draft.sql').read_bytes()
v5 = (ROOT/'backend/src/main/resources/db/migration/V5__cost_ledger_pricing.sql').read_bytes()
b = lambda x: b''.join(x.splitlines(keepends=True)[3:])
print('draft body sha256 == v5 body sha256:', hashlib.sha256(b(draft)).hexdigest() == hashlib.sha256(b(v5)).hexdigest(),
      'bodylen', len(b(draft)), len(b(v5)), 'CR count', b(draft).count(b'\r'), b(v5).count(b'\r'))
print('full-file equal:', draft == v5, 'draft first line:', re.sub(r'[^\x20-\x7e]','?',draft.splitlines()[0].decode()))
print('v5 first line:', re.sub(r'[^\x20-\x7e]','?',v5.splitlines()[0].decode()))
