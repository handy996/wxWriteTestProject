"""Offline contract oracle, not production business or integration code."""
import hashlib
import ipaddress
import json
import re
from decimal import Decimal
from urllib.parse import urlparse


def canonical(value):
    def check(v):
        if v is None or isinstance(v, bool):
            return
        if isinstance(v, int):
            if abs(v) > 9007199254740991:
                raise ValueError('INTEGER_OUT_OF_RANGE')
        elif isinstance(v, str):
            v.encode('utf-8', errors='strict')
        elif isinstance(v, list):
            for x in v:
                check(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                if not isinstance(k, str) or not k.isascii():
                    raise ValueError('NON_ASCII_KEY')
                check(x)
        else:
            raise ValueError('FLOAT_OR_UNSUPPORTED_TYPE')
    check(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def version_hash(version):
    return digest({k:version[k] for k in ['schemaVersion','title','subtitle','contentAst']})


def manifest_hash(manifest):
    return digest({k:manifest[k] for k in ['items','noticeCompact','noticeFull','policyVersionId']})


def release_hash(candidate):
    # Explicit whitelist: mutating audit timestamps, stale or active cannot change historical content.
    body={k:candidate[k] for k in ['schemaVersion','version','manifest','factSetHash','skillRulesHash']}
    for name in ['selections','variants','licenses','sourceSnapshots','verifications','policies']:
        refs=candidate[name]
        if len({r['id'] for r in refs})!=len(refs):
            raise ValueError('DUPLICATE_RELEASE_REFERENCE')
        body[name]=sorted([{'id':r['id'],'hash':r['hash']} for r in refs],key=lambda r:r['id'])
    # Version/manifest refs also exclude API projection fields.
    for name in ['version','manifest']:
        body[name]={k:candidate[name][k] for k in ['id','hash']}
    return digest(body)


def parse_json(value):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('DUPLICATE_KEY')
            result[k] = v
        return result
    return json.loads(value, object_pairs_hook=pairs)


def validate_ast(ast, known_claim_ids=()):
    blocks = ast['blocks']
    ids = [b['blockId'] for b in blocks]
    if len(ids) != len(set(ids)) or {'title', 'subtitle'} & set(ids):
        raise ValueError('INVALID_BLOCK_ID')
    for block in blocks:
        text = block['text']
        text.encode('utf-8', errors='strict')
        if re.search(r'<\s*/?\s*[a-zA-Z][^>]*>', text):
            raise ValueError('HTML_NOT_ALLOWED')
        kind = block['blockType']
        if kind == 'list':
            if not block['items'] or text != '\n'.join(block['items']):
                raise ValueError('LIST_TEXT_MISMATCH')
        elif block['items']:
            raise ValueError('UNEXPECTED_LIST_ITEMS')
        if (kind == 'heading') != (block['level'] is not None):
            raise ValueError('HEADING_LEVEL')
        if (kind == 'imagePlaceholder') != (block['slotId'] is not None) or (kind == 'imagePlaceholder' and text):
            raise ValueError('IMAGE_PLACEHOLDER')
        for mark in block['marks']:
            if not 0 <= mark['start'] < mark['end'] <= len(text):
                raise ValueError('MARK_RANGE')
            if mark['type'] == 'link' and (not mark['href'] or urlparse(mark['href']).scheme != 'https'):
                raise ValueError('LINK_PROTOCOL')
            if mark['type'] != 'link' and mark['href'] is not None:
                raise ValueError('UNEXPECTED_LINK')
        if not set(block['claimRefs']) <= set(known_claim_ids):
            raise ValueError('UNKNOWN_CLAIM_REFERENCE')
    return '\n'.join(b['text'] for b in blocks)


def validate_span(span, text_by_block):
    text = text_by_block.get(span['blockId'])
    if text is None or not 0 <= span['start'] < span['end'] <= len(text):
        raise ValueError('SPAN_RANGE')
    if text[span['start']:span['end']] != span['quote'] or text_hash(text) != span['blockHash']:
        raise ValueError('SPAN_MISMATCH')


def license_decision(case):
    # A simplified offline policy oracle; no external license claims.
    if case['verificationStatus'] != 'VERIFIED' or not case['evidencePresent']:
        return 'BLOCKED'
    p = case['permission']
    if any(p.get(k) is None for k in ['commercialUseAllowed','modificationAllowed','attributionRequired','shareAlikeRequired','publicDomain']):
        return 'BLOCKED'
    if not p['commercialUseAllowed'] or not p['modificationAllowed']:
        return 'BLOCKED'
    if p['attributionRequired'] and not case['authorPresent']:
        return 'BLOCKED'
    if case['otherRightsStatus'] == 'BLOCKED':
        return 'BLOCKED'
    if case['otherRightsStatus'] == 'REVIEW_REQUIRED' or (p['shareAlikeRequired'] and not case['saObligationsSatisfied']):
        return 'REQUIRES_REVIEW'
    if not case['obligationsSatisfied']:
        return 'BLOCKED'
    return 'ALLOW'


def approval_guard(actor, state, etag, current_etag, candidate_hash, head_hash, qa):
    if actor != 'OWNER':
        return 'APPROVAL_FORBIDDEN'
    if etag is None:
        return 'PRECONDITION_REQUIRED'
    if etag != current_etag:
        return 'PRECONDITION_FAILED'
    if state != 'HUMAN_REVIEW' or candidate_hash != head_hash:
        return 'STATE_CONFLICT'
    if qa['blockers'] or qa['unresolvedWarnings'] or qa['pendingRequiredTasks'] or not qa['allExecuted'] or not qa['fresh']:
        return 'QA_BLOCKED'
    return 'ALLOW'


def commit_guard(fence, current_fence, base_version, head_version, cancelled=False):
    if cancelled:
        return 'CANCELLED_KEEP_COST'
    if fence != current_fence or base_version != head_version:
        return 'HISTORY_ONLY'
    return 'COMMIT'


def budget_can_reserve(spent, reserved, estimate, limit):
    # Pure arithmetic only; not an implementation or proof of atomic DB reservation.
    values = [Decimal(v) for v in (spent, reserved, estimate, limit)]
    if any(not v.is_finite() or v < 0 for v in values):
        raise ValueError('INVALID_MONEY')
    return sum(values[:3]) <= values[3]


def safe_address(url, resolved_addresses):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or not parsed.hostname or not resolved_addresses:
        return False
    try:
        return all(ipaddress.ip_address(a).is_global for a in resolved_addresses)
    except ValueError:
        return False


def topological(graph):
    remaining = {k: set(v) for k,v in graph.items()}
    if set().union(*remaining.values()) - set(remaining):
        raise ValueError('UNKNOWN_NODE')
    result = []
    while remaining:
        ready = sorted(k for k,v in remaining.items() if not v)
        if not ready:
            raise ValueError('DEPENDENCY_CYCLE')
        for k in ready:
            result.append(k)
            del remaining[k]
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return result
