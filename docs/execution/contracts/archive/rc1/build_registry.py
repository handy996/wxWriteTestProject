"""Extract reviewable inventories; explicit ownership/FK/port decisions live here."""
from build_contract import ROOT, write
import re

owners = {
 'T03': 'app_user audit_log idempotency_record',
 'T05': 'editorial_skill editorial_skill_version policy_version prompt_version',
 'T06': 'article_job article_version', 'T07': 'change_proposal', 'T08': 'cost_ledger',
 'T09': 'provider_config agent_execution tool_execution',
 'T10': 'workflow_execution workflow_step_execution', 'T11': 'manual_task',
 'T12': 'analysis_result', 'T13': 'rewrite_plan', 'T14': 'review_report review_item',
 'T15': 'source source_snapshot', 'T16': 'fact_claim', 'T17': 'fact_verification claim_source',
 'T19': 'image_slot', 'T22': 'license_metadata', 'T23': 'image_asset image_variant',
 'T24': 'image_candidate image_selection', 'T25': 'image_generation',
 'T26': 'license_manifest', 'T27': 'release_candidate qa_report', 'T28': 'human_review', 'T29': 'export_artifact'
}
# Each edge is child -> prerequisite. Cycles use a separately installed deferred FK.
fk = {
 'app_user': [], 'policy_version': [], 'prompt_version': [], 'provider_config': [],
 'editorial_skill': ['app_user'], 'editorial_skill_version': ['editorial_skill', 'policy_version', 'prompt_version'],
 'article_job': ['app_user', 'editorial_skill_version'], 'article_version': ['article_job', 'app_user'],
 'workflow_execution': ['article_job'], 'workflow_step_execution': ['workflow_execution'],
 'agent_execution': ['workflow_step_execution', 'prompt_version'], 'tool_execution': ['agent_execution', 'workflow_step_execution'],
 'analysis_result': ['article_version', 'editorial_skill_version', 'agent_execution'],
 'rewrite_plan': ['article_version', 'analysis_result', 'agent_execution'],
 'review_report': ['article_version', 'agent_execution'], 'review_item': ['review_report', 'article_version'],
 'change_proposal': ['article_version'], 'source': ['article_job'], 'source_snapshot': ['source'],
 'fact_claim': ['article_version'], 'fact_verification': ['fact_claim', 'policy_version'],
 'claim_source': ['fact_verification', 'source_snapshot'], 'image_slot': ['article_version'],
 'image_asset': ['article_job'], 'image_variant': ['image_asset'], 'image_candidate': ['image_slot'],
 'license_metadata': ['image_candidate', 'image_asset'],
 'image_generation': ['image_slot', 'image_asset', 'agent_execution'],
 'image_selection': ['image_slot', 'image_asset', 'image_variant', 'license_metadata', 'app_user'],
 'license_manifest': ['article_version', 'policy_version'],
 'release_candidate': ['article_version', 'license_manifest', 'editorial_skill_version'],
 'qa_report': ['release_candidate'], 'human_review': ['release_candidate', 'qa_report', 'app_user'],
 'manual_task': ['article_job', 'workflow_execution'], 'cost_ledger': ['article_job'],
 'idempotency_record': ['app_user'], 'export_artifact': ['release_candidate', 'human_review'], 'audit_log': ['app_user']
}
deferred = [
 ('article_job', 'article_version', 'originalVersionId,currentVersionId'),
 ('article_job', 'workflow_execution', 'activeWorkflowId'),
 ('article_job', 'analysis_result', 'latestAnalysisId'), ('article_job', 'review_report', 'latestReviewId'),
 ('article_job', 'qa_report', 'latestQaId'), ('article_job', 'release_candidate', 'activeCandidateId,approvedCandidateId'),
 ('article_version', 'article_version', 'parentVersionId,restoredFromVersionId'),
 ('article_version', 'agent_execution', 'executionId'),
 ('editorial_skill', 'editorial_skill_version', 'activeVersionId'),
 ('editorial_skill_version', 'editorial_skill_version', 'parentVersionId'),
 ('image_candidate', 'license_metadata', 'licenseId'),
]
immutable = set('article_version analysis_result rewrite_plan fact_claim fact_verification source_snapshot claim_source review_report image_variant license_metadata license_manifest release_candidate qa_report human_review audit_log'.split())
mixed = {'editorial_skill_version': 'DRAFT content editable; published content immutable; retire status only',
 'policy_version': 'DRAFT editable; published rules immutable; retire status only',
 'prompt_version': 'DRAFT editable; published templates immutable',
 'image_selection': 'Only active may UPDATE; new caption/variant/license -> new row'}


def main():
    srs = (ROOT / 'docs/AI-Editorial-Agent-SRS-v1.0.md').read_text(encoding='utf-8')
    table_rows = []
    for line in srs.splitlines():
        match = re.match(r'\| (\d+) \| ([a-z_]+)(?: / [^|]+)? \| (.+) \| (.+) \|$', line)
        if match and match[2] in fk:
            table = match[2]
            table_rows.append({'name': table, 'owner': next(k for k,v in owners.items() if table in v.split()),
                'fieldsFromSrs': match[3], 'constraintsFromSrs': match[4], 'prerequisites': fk[table],
                'runtimeMutation': mixed.get(table, 'INSERT_ONLY' if table in immutable else 'OPTIMISTIC_LOCK_AND_AUDIT'),
                'deleteRole': 'retention_worker via approved deletion command; never generic application DELETE'})
    write('docs/execution/contracts/tables.json', {'tables': table_rows,
        'deferredForeignKeys': [{'from': a, 'to': b, 'fields': c} for a,b,c in deferred],
        'polymorphicReferences': {'fact_claim.scopeId':'ARTICLE_VERSION -> same version; IMAGE_SELECTION -> same article immutable selection; constraint trigger',
          'cost_ledger.executionId':'agent/tool execution resolved by type with ownership check',
          'idempotency_record.operationId':'workflow/step/export registry; no operations table',
          'manual_task.entityId':'type-specific same-article resolver',
          'audit_log.entityId':'retained metadata reference; no cascading FK'},
        'jsonReferences': 'Prompt bindings, policy refs, manifest items, result refs, fact sets: same-article/service validation plus retention references in the business transaction.'})
    state_rows = []
    section = srs.split('### 25.1')[1].split('全局迁移：')[0]
    for line in section.splitlines():
        m = re.match(r'\| ([A-Z_]+) \| (.+) \| (.+) \|$', line)
        if m:
            state_rows.append({'from': m[1], 'to': re.findall(r'\b[A-Z][A-Z_]+\b', m[2]), 'dynamic': 'resumeTarget' in m[2] or 'failedStep' in m[2], 'guard': m[3]})
    write('docs/execution/contracts/state-guards.json', {'article':state_rows,
       'execution':['QUEUED','RUNNING','WAITING','PAUSED','SUCCEEDED','FAILED','CANCELLED'],
       'step':['PENDING','RUNNING','RETRY_WAIT','WAITING_HUMAN','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED','STALE'],
       'globalMachineTransitions':['PAUSED','FAILED','CANCELLED'],
       'globalGuard':'Only active machine steps; authenticated command or exhausted technical failure. CANCELLED has no exits.',
       'approvalGuard':['OWNER','HUMAN_REVIEW','matching ETag','matching candidate and releaseHash','QA PASS and fresh','no hard blockers','all required human tasks resolved','all dependencies fresh'],
       'transactionGuard':'ownership -> request idempotency -> aggregate lock -> ETag -> input/fencing -> evidence -> append artifacts/audit -> commit'})
    # Compile-time edges use ports; workflow implementations registered by composition root.
    modules = {'shared':[], 'identity':['shared'], 'audit':['shared'], 'storage':['shared'],
       'cost':['shared'], 'settings':['shared'], 'article':['shared'], 'editorial':['shared'],
       'research':['shared'], 'factcheck':['shared'], 'image':['shared'], 'license':['shared'],
       'qa':['shared'], 'review':['shared'], 'export':['shared'], 'ai':['shared'], 'workflow':['shared']}
    write('docs/execution/contracts/module-dependencies.json', {'compileDependencies':modules,
        'note':'shared holds small types and contract-only ports. Each domain owns implementation. Composition root wires ports. Runtime event loops are guarded generations, not compile-time dependency cycles.'})
    ports = [
      ('Ownership.require', 'T03','ActorContext + ArtifactRef','ArtifactRef','OWNER_MISMATCH'),
      ('AuditSink.append','T03','ActorContext + AuditRecord','AuditRecord','AUDIT_WRITE_FAILED'),
      ('ArticleSnapshot.read','T06','ActorContext + articleId + versionId','ArticleVersion','NOT_FOUND'),
      ('VersionCommand.commit','T07','StepContext + WriterOutput + ETag','ArticleVersion','STALE_FENCE'),
      ('SkillSnapshot.read','T05','ActorContext + skillVersionId','SkillSnapshot','SKILL_NOT_PUBLISHED'),
      ('PolicySnapshot.read','T05','policyVersionId','PolicySnapshot','POLICY_NOT_FOUND'),
      ('WorkflowStep.execute','T10','StepContext + ObjectRef','ObjectRef','STEP_FAILED'),
      ('Command.submit','T10','ActorContext + route + Idempotency-Key + X-Request-Hash + typed request','CommandAccepted','IDEMPOTENCY_CONFLICT'),
      ('ManualTask.resolve','T11','ActorContext + ResolveTaskRequest','DispositionResult','EVIDENCE_REQUIRED'),
      ('Budget.reserve','T08','ActorContext + BudgetReservation','BudgetReservation','BUDGET_EXCEEDED'),
      ('Budget.settle','T08','Settlement','BudgetReservation','RECONCILIATION_REQUIRED'),
      ('AIGateway.call','T09','AIRequest','AIResult','CAPABILITY_UNSUPPORTED'),
      ('SourceSnapshot.read','T15','ActorContext + sourceSnapshotId','SourceSnapshot','SOURCE_UNAVAILABLE'),
      ('FactSet.resolve','T17','ActorContext + articleId + versionId','FactSet','FACTS_BLOCKED'),
      ('ImageText.extract','T18','StepContext + ImageSelection + Variant','ImageTextExtraction','IMAGE_TEXT_UNREADABLE'),
      ('ImageProvider.search','T19/T20/T21','SearchQuery + ProviderContext','SearchPage','CAPABILITY_UNSUPPORTED'),
      ('ImageProvider.getMetadata','T19/T20/T21','externalId + ProviderContext','ImageCandidate','PROVIDER_FAILED'),
      ('ImageProvider.getLicense','T19/T20/T21','externalId + ProviderContext','LicenseMetadata','LICENSE_UNKNOWN'),
      ('ImageProvider.download','T19/T23','SafeFetchRequest + ProviderContext','SafeFetchResult','UNSAFE_DOWNLOAD'),
      ('GenerativeImageProvider.generate','T25','GenerationRequest + ProviderContext','GenerationResult','OUTCOME_UNKNOWN'),
      ('LicensePolicy.evaluate','T22','LicenseMetadata + ImageSlot + Variant','LicenseDecision','LICENSE_BLOCKED'),
      ('Variant.create','T23','StepContext + VariantRequest','Variant','WATERMARK_FAILED'),
      ('Manifest.build','T26','StepContext + ImageSelection[]','Manifest','OBLIGATIONS_UNSATISFIED'),
      ('Candidate.freeze','T27','ArticleVersion + Manifest + FactSet + SkillSnapshot','ReleaseCandidate','STALE_DEPENDENCIES'),
      ('Approval.decide','T28','ActorContext + ApproveRequest + ETag','Approval','APPROVAL_FORBIDDEN'),
      ('ObjectStore.stage','T04','ActorContext + bytes + expected hash + size','ObjectRef','OBJECT_WRITE_FAILED'),
      ('ObjectStore.commitReference','T04','ActorContext + ObjectRef + ArtifactRef','ObjectRef','OBJECT_MISSING'),
      ('ObjectStore.authorizeDownload','T04','ActorContext + ObjectRef','5-minute signed HTTPS URL','NOT_FOUND'),
      ('SafeFetch.fetch','T15','ActorContext + SafeFetchRequest','SafeFetchResult','SSRF_BLOCKED')]
    write('docs/execution/contracts/ports.json', [{'name':n,'provider':o,'input':i,'output':out,'error':err,
        'schemaVersion':'1.0.0-rc.1','audit':'traceId + actor + input/output hashes; never log content or secrets',
        'ownership':'All article-scoped refs must resolve to same article and authenticated owner before IO',
        'stale':'Reject stale input for new commit; history remains readable'} for n,o,i,out,err in ports])
    write('docs/execution/contracts/invalidation.json', {
      'TITLE_CHANGED':['TITLE_CLAIMS','TITLE_QA','CANDIDATE','CURRENT_APPROVAL'],
      'BODY_CHANGED':['CLAIM_RECONCILIATION','EDITORIAL_REVIEW','SLOT_ANCHORS','QA','CANDIDATE','CURRENT_APPROVAL'],
      'SELECTION_CHANGED':['IMAGE_TEXT','LICENSE_MANIFEST','NOTICES','QA','CANDIDATE','CURRENT_APPROVAL'],
      'VARIANT_CHANGED':['IMAGE_TEXT','WATERMARK','LICENSE_MANIFEST','NOTICES','QA','CANDIDATE','CURRENT_APPROVAL'],
      'SOURCE_CHANGED':['DEPENDENT_CLAIMS','QA','CANDIDATE','APPROVAL_VALIDITY'],
      'SOURCE_RETRACTED':['DEPENDENT_CLAIMS','QA','CANDIDATE','APPROVAL_VALIDITY'],
      'SKILL_CHANGED':['NEW_GENERATION','ANALYSIS','ALL_DOWNSTREAM'],
      'POLICY_CHANGED':['NEW_GENERATION','AFFECTED_FACT_OR_LICENSE_CHECKS','QA','CANDIDATE','APPROVAL_VALIDITY'],
      'BUDGET_CHANGED':['NEXT_RESERVATION'], 'MANUAL_RESOLVED':['REVALIDATE_RESUME_TARGET']})
    oq = []
    for line in srs.splitlines():
        if line.startswith('| OQ-'):
            p = [x.strip() for x in line.strip('|').split('|')]
            oq.append(dict(zip(['id','question','developmentDefault','decisionOwnerAndDeadline'],p), status='UNCONFIRMED', evidence=None))
    write('docs/execution/contracts/open-questions.json', oq)
    graph_lines=['# 表归属及 FK 图（候选）','','完整字段/索引/权限见 tables.json；实线是普通建表依赖，虚线是后置安装的延迟 FK。运行时引用环不等于模块编译环。','','| 表 | 唯一拥有者 | 运行时写权限 |','|---|---|---|']
    graph_lines += [f'| {t["name"]} | {t["owner"]} | {t["runtimeMutation"]} |' for t in table_rows]
    graph_lines += ['','```mermaid','graph LR']
    graph_lines += [f'  {table} --> {parent}' for table,parents in fk.items() for parent in parents]
    graph_lines += [f'  {a} -.-> {b}' for a,b,_ in deferred]
    graph_lines += ['```','']
    (ROOT/'docs/execution/contracts/ownership-and-fk.md').write_text('\n'.join(graph_lines),encoding='utf-8',newline='\n')
    print(f'Registry: {len(table_rows)} tables, {len(state_rows)} article states, {len(ports)} ports, {len(oq)} open decisions.')


if __name__ == '__main__':
    main()
