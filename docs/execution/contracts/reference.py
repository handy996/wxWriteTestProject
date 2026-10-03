"""Offline contract oracle, not production business or integration code."""
import hashlib
import ipaddress
import json
import re
import copy
import uuid
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


def release_hash_input(candidate):
    """The ONLY projection from ReleaseCandidate to ReleaseHashInput. No DB/IO lookup."""
    meta=candidate['meta'];article=meta['articleId'];version=candidate['version']['id']
    if meta['versionId']!=version or candidate['factSet']['articleId']!=article or candidate['factSet']['versionId']!=version:
        raise ValueError('CANDIDATE_VERSION_MISMATCH')
    rights=candidate['rightsSnapshot']
    if rights['articleId']!=article or rights['versionId']!=version or rights['contentHash']!=candidate['version']['hash']:
        raise ValueError('RIGHTS_SNAPSHOT_MISMATCH')
    def refs(values,article_scoped=True):
        if len({r['id'] for r in values})!=len(values):
            raise ValueError('DUPLICATE_RELEASE_REFERENCE')
        if article_scoped and any(r['articleId']!=article for r in values):
            raise ValueError('CROSS_ARTICLE_REFERENCE')
        return sorted([{'id':r['id'],'hash':r['hash']} for r in values],key=lambda r:r['id'])
    result={'schemaVersion':meta['schemaVersion'],'articleId':article,'ownerId':meta['ownerId'],
        'version':refs([candidate['version']])[0],'manifest':refs([candidate['manifest']])[0],
        'factSetHash':candidate['factSet']['hash'],'skillVersionId':candidate['skillSnapshot']['id'],
        'skillRulesHash':candidate['skillSnapshot']['rulesHash'],'rights':{'id':rights['id'],'hash':rights['hash']}}
    for name in ['selections','variants','licenses','sourceSnapshots']:
        result[name]=refs(candidate[name])
    for name in ['claims','verifications']:
        result[name]=refs(candidate['factSet'][name])
    result['policies']=refs(candidate['policyRefs'],False)
    bindings=candidate['selectionBindings']
    if len({b['selectionId'] for b in bindings})!=len(bindings) or len({b['slotId'] for b in bindings})!=len(bindings):
        raise ValueError('DUPLICATE_SELECTION_BINDING')
    for key,name in [('selectionId','selections'),('variantId','variants'),('licenseMetadataId','licenses')]:
        if {b[key] for b in bindings}!={r['id'] for r in candidate[name]}:
            raise ValueError('SELECTION_BINDING_COVERAGE')
    result['selectionBindings']=sorted(copy.deepcopy(bindings),key=lambda b:b['selectionId'])
    validate_slot_anchor_coverage(candidate)
    result['slotAnchors']=sorted(copy.deepcopy(candidate['slotAnchors']),key=lambda a:a['slotId'])
    return result


def release_hash(candidate):
    return digest(release_hash_input(candidate))


def validate_slot_anchor_coverage(candidate):
    """Relational guard after DTO schema validation; no mutable slot lookup."""
    anchors=candidate['slotAnchors'];bindings=candidate['selectionBindings']
    for values in [anchors,bindings]:
        for key in ['slotId','selectionId']:
            if len({v[key] for v in values})!=len(values):
                raise ValueError('DUPLICATE_SLOT_BINDING')
    if {(a['slotId'],a['selectionId']) for a in anchors}!={(b['slotId'],b['selectionId']) for b in bindings}:
        raise ValueError('SLOT_ANCHOR_COVERAGE')
    boundaries=set()
    for a in anchors:
        if a['versionId']!=candidate['version']['id']:
            raise ValueError('SLOT_VERSION_MISMATCH')
        if a['anchorSide'] not in ('BEFORE','AFTER') or type(a['position']) is not int or a['position']<0:
            raise ValueError('INVALID_SLOT_POSITION')
        boundary=(a['anchorBlockId'],a['anchorSide'],a['position'])
        if boundary in boundaries:
            raise ValueError('AMBIGUOUS_SLOT_ORDER')
        boundaries.add(boundary)


def frozen_version_blocks(candidate, version):
    meta=version['meta'];cm=candidate['meta']
    if (meta['id']!=candidate['version']['id'] or meta['versionId']!=meta['id']
            or meta['articleId']!=cm['articleId'] or meta['ownerId']!=cm['ownerId']):
        raise ValueError('VERSION_SCOPE_MISMATCH')
    computed=version_hash(dict(version,schemaVersion=meta['schemaVersion']))
    if computed!=candidate['version']['hash'] or computed!=meta['contentHash']:
        raise ValueError('VERSION_CONTENT_MISMATCH')
    validate_ast(version['contentAst'],[c['id'] for c in candidate['factSet']['claims']])
    return {b['blockId']:b for b in version['contentAst']['blocks'] if b['blockType']!='imagePlaceholder'}


def freeze_slot_anchors(candidate, version, manifest, selected_slots):
    """Offline freeze plan. Caller validates DTOs and commits under job lock/ETag/fence.

    selected_slots must be the complete selected-slot set in that transaction.
    This does not implement licensing/QA/approval gates or persist an approval.
    """
    blocks=frozen_version_blocks(candidate,version);cm=candidate['meta'];mm=manifest['meta']
    if (mm['id']!=candidate['manifest']['id'] or mm['articleId']!=cm['articleId']
            or mm['ownerId']!=cm['ownerId'] or mm['versionId']!=candidate['version']['id']):
        raise ValueError('MANIFEST_SCOPE_MISMATCH')
    if manifest_hash(manifest)!=candidate['manifest']['hash'] or manifest_hash(manifest)!=mm['contentHash']:
        raise ValueError('MANIFEST_CONTENT_MISMATCH')
    bindings=candidate['selectionBindings']
    keys=['slotId','selectionId','assetId','variantId','licenseMetadataId']
    associations=lambda values: sorted([tuple(v[k] for k in keys) for v in values])
    if associations(manifest['items'])!=associations(bindings):
        raise ValueError('MANIFEST_BINDING_MISMATCH')
    if len({s['meta']['id'] for s in selected_slots})!=len(selected_slots):
        raise ValueError('DUPLICATE_SLOT_SNAPSHOT')
    if {s['meta']['id'] for s in selected_slots}!={b['slotId'] for b in bindings}:
        raise ValueError('SLOT_SNAPSHOT_COVERAGE')
    by_slot={b['slotId']:b for b in bindings};anchors=[]
    for slot in selected_slots:
        sm=slot['meta']
        if sm['articleId']!=cm['articleId'] or sm['ownerId']!=cm['ownerId'] or sm['versionId']!=candidate['version']['id']:
            raise ValueError('SLOT_SCOPE_MISMATCH')
        block=blocks.get(slot['anchorBlockId'])
        if block is None or block['sectionId']!=slot['sectionId']:
            raise ValueError('SLOT_BLOCK_MISMATCH')
        anchors.append({'slotId':sm['id'],'selectionId':by_slot[sm['id']]['selectionId'],
            'versionId':sm['versionId'],'anchorBlockId':block['blockId'],'blockHash':text_hash(block['text']),
            'anchorSide':slot['anchorSide'],'position':slot['position'],'planHash':slot['planHash']})
    frozen=copy.deepcopy(candidate);frozen['slotAnchors']=sorted(anchors,key=lambda a:a['slotId'])
    frozen['releaseHash']=release_hash(frozen)
    return frozen


def render_frozen_positions(candidate, version):
    """Historical positioning oracle: only immutable candidate and body, never live slots."""
    if candidate['releaseHash']!=release_hash(candidate):
        raise ValueError('RELEASE_HASH_MISMATCH')
    blocks=frozen_version_blocks(candidate,version)
    indices={key:i for i,key in enumerate(blocks)}
    for a in candidate['slotAnchors']:
        if a['anchorBlockId'] not in blocks or a['blockHash']!=text_hash(blocks[a['anchorBlockId']]['text']):
            raise ValueError('SLOT_BLOCK_MISMATCH')
    bindings={b['slotId']:b for b in candidate['selectionBindings']}
    ordered=sorted(candidate['slotAnchors'],key=lambda a:(indices[a['anchorBlockId']],0 if a['anchorSide']=='BEFORE' else 1,a['position']))
    return [dict(copy.deepcopy(a),assetId=bindings[a['slotId']]['assetId'],variantId=bindings[a['slotId']]['variantId']) for a in ordered]


def resolve_analysis(output, allocate_id):
    """Server-side ID allocation supplied by caller, never by the model. No persistence."""
    keys=[c['localKey'] for c in output['factClaims']]
    if len(keys)!=len(set(keys)):
        raise ValueError('DUPLICATE_CLAIM_LOCAL_KEY')
    for title in output['recommendedTitles']:
        if not set(title['supportedClaimLocalKeys'])<=set(keys):
            raise ValueError('UNKNOWN_CLAIM_LOCAL_KEY')
    mapping={k:str(uuid.UUID(str(allocate_id()))) for k in keys}
    if len(set(mapping.values()))!=len(mapping):
        raise ValueError('DUPLICATE_ALLOCATED_ID')
    resolved=copy.deepcopy(output)
    resolved['factClaims']=[{'id':mapping[c['localKey']],'draft':copy.deepcopy(c)} for c in output['factClaims']]
    for title in resolved['recommendedTitles']:
        title['supportedClaimIds']=[mapping[k] for k in title.pop('supportedClaimLocalKeys')]
    return resolved,[{'localKey':k,'claimId':v} for k,v in mapping.items()]


def rights_export_eligible(rights,article_id,version_id,content_hash):
    return (rights['articleId']==article_id and rights['versionId']==version_id
        and rights['contentHash']==content_hash and rights['basis'] in ('OWNED','AUTHORIZED')
        and bool(rights['notes'].strip()) and (rights['basis']!='AUTHORIZED' or bool(rights['evidenceIds'])))


def next_skill_version(skill_id, existing, base_id=None):
    """Pure plan; integrator MUST serialize on skill identity and enforce unique semver."""
    own=[v for v in existing if v['skillId']==skill_id]
    if base_id is None:
        if own:
            raise ValueError('BASE_VERSION_REQUIRED')
        return '1.0.0'
    if not any(v['id']==base_id for v in own):
        raise ValueError('BASE_VERSION_WRONG_SKILL')
    versions=[tuple(map(int,v['version'].split('.'))) for v in own]
    major,minor,patch=max(versions)
    return f'{major}.{minor}.{patch+1}'


def switch_skill(job,snapshot,expected_lock):
    if job['lockVersion']!=expected_lock:
        raise ValueError('PRECONDITION_FAILED')
    if snapshot['status']!='PUBLISHED':
        raise ValueError('SKILL_NOT_PUBLISHED')
    if job['status']=='CANCELLED':
        raise ValueError('CANCELLED_CLONE_REQUIRED')
    return dict(job,skillVersionId=snapshot['id'],lockVersion=job['lockVersion']+1,
        generation=job['generation']+1,fencingToken=job['fencingToken']+1,
        status='NEEDS_REVISION',previousExecutionDisposition='PAUSED_STALE',styleSnapshot=copy.deepcopy(snapshot))


def validate_model_routes(routes):
    if len({r['capability'] for r in routes})!=len(routes):
        raise ValueError('DUPLICATE_CAPABILITY_ROUTE')
    for r in routes:
        if not r['model'].strip():
            raise ValueError('MODEL_REQUIRED')


def validate_image_size(byte_size,pixels):
    if not 0<byte_size<=20971520 or not 0<pixels<=40000000:
        raise ValueError('IMAGE_LIMIT')


def validate_text_upload(content):
    if len(content.encode('utf-8'))>1048576:
        raise ValueError('UPLOAD_BYTE_LIMIT')


def restore_allowed(barrier):
    return (barrier['externalJournalAvailable'] and barrier['headSignatureVerified']
        and barrier['journalHeadSequence']>=barrier['backupJournalSequence']
        and barrier['verifiedThroughSequence']==barrier['journalHeadSequence']
        and not barrier['missingSequences'] and not barrier['unappliedDeletionIds'])


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
