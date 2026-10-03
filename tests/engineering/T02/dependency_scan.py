"""Check the resolved Maven CycloneDX inventory against OSV's public advisory API.

Only package coordinates and versions are sent. Network/errors fail the check.
No suppressions: every advisory must be reviewed before this baseline passes.
"""
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
bom = json.loads((ROOT / 'backend/target/sbom/application.json').read_text(encoding='utf-8'))
components = [item for item in bom['components'] if item.get('group') and item.get('version')]
queries = [{'package': {'ecosystem': 'Maven', 'name': item['group'] + ':' + item['name']}, 'version': item['version']} for item in components]
request = urllib.request.Request('https://api.osv.dev/v1/querybatch',
                                 data=json.dumps({'queries': queries}).encode(),
                                 headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=60) as response:
    results = json.load(response)['results']
if len(results) != len(queries):
    raise ValueError('Incomplete OSV response')
findings = [{'package': query, 'advisories': result['vulns']} for query, result in zip(queries, results) if result.get('vulns')]
print(json.dumps({'source': 'https://api.osv.dev/v1/querybatch', 'packagesChecked': len(queries), 'findings': findings}, indent=2))
sys.exit(bool(findings))
