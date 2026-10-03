// Independent JavaScript implementation of canonical-v1. No network or application code.
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const fixtureDir = path.join(root,'tests/fixtures/contracts/T00/rc3');
const vector = JSON.parse(fs.readFileSync(path.join(fixtureDir,'release-vector.json'),'utf8'));
function canonical(value) {
  if (value === null || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) throw new Error('INTEGER_REQUIRED');
    return JSON.stringify(value);
  }
  if (typeof value === 'string') {
    for (let i = 0; i < value.length; i++) {
      const c = value.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff) {
        const next = value.charCodeAt(++i);
        if (!(next >= 0xdc00 && next <= 0xdfff)) throw new Error('SURROGATE');
      } else if (c >= 0xdc00 && c <= 0xdfff) throw new Error('SURROGATE');
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort();
    if (keys.some(k => /[^\x00-\x7f]/.test(k))) throw new Error('ASCII_KEY_REQUIRED');
    return '{' + keys.map(k => JSON.stringify(k)+':'+canonical(value[k])).join(',') + '}';
  }
  throw new Error('UNSUPPORTED_TYPE');
}
const hash = crypto.createHash('sha256').update(canonical(vector.projection),'utf8').digest('hex');
if (hash !== vector.expectedReleaseHash) throw new Error('HASH_MISMATCH');
const unicode = canonical({z:'😀',a:'中\n文',n:1});
if (unicode !== '{"a":"中\\n文","n":1,"z":"😀"}') throw new Error('UNICODE_MISMATCH');
const anchors = JSON.parse(fs.readFileSync(path.join(fixtureDir,'anchor-vectors.json'),'utf8'));
const hashes = anchors.vectors.map(v => {
  const actual = crypto.createHash('sha256').update(canonical(v.projection),'utf8').digest('hex');
  if (actual !== v.expectedReleaseHash) throw new Error('ANCHOR_HASH_MISMATCH: '+v.name);
  return {name:v.name,releaseHash:actual};
});
if (new Set(hashes.map(v => v.releaseHash)).size !== hashes.length) throw new Error('ANCHOR_CHANGE_NOT_PROTECTED');
console.log(JSON.stringify({mode:'OFFLINE_JS_CANONICAL_ONLY',releaseHash:hash,anchorVectors:hashes,matchesPython:true,
  limitation:'Validates supplied Python projections; not a JavaScript Candidate projection implementation.'}));
