"""Build the review candidate contracts. Offline; never edits SRS or application code."""
from pathlib import Path
import copy
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
VERSION = '1.0.0-rc.1'
S = {}


def obj(**properties):
    return {'type': 'object', 'additionalProperties': False,
            'properties': properties, 'required': list(properties)}


def optional(schema, *names):
    schema = copy.deepcopy(schema)
    schema['required'] = [n for n in schema['required'] if n not in names]
    return schema


def ref(name):
    return {'$ref': '#/$defs/' + name}


def arr(items, minimum=0, maximum=1000):
    return {'type': 'array', 'items': items, 'minItems': minimum, 'maxItems': maximum}


def enum(*values):
    return {'type': 'string', 'enum': list(values)}


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def text(maximum=1000, minimum=1):
    return {'type': 'string', 'minLength': minimum, 'maxLength': maximum}


def integer(minimum=0, maximum=2147483647):
    return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}


ID = {'type': 'string', 'format': 'uuid'}
HASH = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
TIME = {'type': 'string', 'format': 'date-time', 'pattern': 'Z$'}
BOOL = {'type': 'boolean'}
MONEY = {'type': 'string', 'pattern': '^(0|[1-9][0-9]{0,11})\\.[0-9]{6}$'}
CONF = {'type': 'string', 'pattern': '^(0\\.[0-9]{3}|1\\.000)$'}
URL = {'type': 'string', 'format': 'uri', 'pattern': '^https://'}
IDS = arr(ID)
STRINGS = arr(text())


def artifact(**fields):
    return obj(meta=ref('ArtifactMeta'), **fields)


def build_schemas():
    S['ErrorDetail'] = obj(field=text(), reason=text(), entityId=nullable(ID))
    S['Error'] = obj(code=text(80), message=text(), traceId=ID,
                     details=arr(ref('ErrorDetail')), retryable=BOOL)
    S['ActorContext'] = obj(actorId=ID, ownerId=ID, actorType=enum('OWNER', 'SYSTEM_WORKER'),
                            traceId=ID, authenticatedAt=TIME)
    S['ArtifactMeta'] = obj(id=ID, articleId=ID, ownerId=ID, versionId=nullable(ID),
        executionId=nullable(ID), schemaVersion={'const': VERSION}, inputHash=HASH,
        contentHash=HASH, stale=BOOL, createdBy=ID, createdAt=TIME, traceId=ID,
        mode=enum('MOCK', 'REAL'))
    S['ArtifactRef'] = obj(id=ID, articleId=ID, versionId=nullable(ID), kind=text(80),
                           hash=HASH, stale=BOOL)
    S['ObjectRef'] = obj(key=text(), hash=HASH, size=integer(0, 20971520),
                         mime=text(100), encrypted=BOOL)
    S['Span'] = obj(blockId=text(80), start=integer(), end=integer(), quote=text(30000), blockHash=HASH)
    S['Mark'] = obj(type=enum('bold', 'italic', 'link'), start=integer(), end=integer(), href=nullable(URL))
    S['Block'] = obj(sectionId=text(80), blockId=text(80),
        blockType=enum('heading', 'paragraph', 'list', 'quote', 'imagePlaceholder'),
        text=text(30000, 0), marks=arr(ref('Mark')), claimRefs=IDS,
        level=nullable(integer(1, 6)), items=arr(text(30000)), slotId=nullable(ID))
    S['ContentAst'] = obj(schemaVersion={'const': VERSION}, blocks=arr(ref('Block'), 1, 30000))
    S['BlockMapping'] = obj(fromBlockIds=STRINGS, toBlockIds=STRINGS, reason=enum('SPLIT', 'MERGE', 'REPLACE'))
    S['ArticleVersion'] = artifact(versionNo=integer(1), parentVersionId=nullable(ID),
        restoredFromVersionId=nullable(ID), kind=enum('ORIGINAL', 'DRAFT', 'REVISION', 'MANUAL', 'RESTORE'),
        changeSource=enum('AI', 'USER', 'SYSTEM'), title=text(300), subtitle=nullable(text(500)),
        contentAst=ref('ContentAst'), plainText=text(200000, 0), changeSummary=text(), blockMappings=arr(ref('BlockMapping')))
    S['PolicySnapshot'] = obj(id=ID, type=enum('FACT', 'LICENSE', 'QA', 'WATERMARK', 'COST'),
                              version=text(40), hash=HASH, rules=ref('ObjectRef'))
    S['PromptBinding'] = obj(agentName=text(80), promptVersionId=ID, hash=HASH, outputSchema=text())
    S['SkillConfig'] = obj(name=text(100), description=text(), locale={'const': 'zh-CN'}, channel={'const': 'WECHAT'},
        audience=STRINGS, tone=STRINGS, structureRules=STRINGS, titleRules=STRINGS,
        openingRules=obj(problemWithinChars=integer(1, 300)), headingRules=STRINGS,
        readabilityRules=obj(recommendedMin=integer(1), recommendedMax=integer(1),
            longParagraphWarning=integer(1), veryLongParagraph=integer(1), shortParagraphMax=integer(1), shortParagraphRun=integer(1)),
        imageRules=obj(maxBodyImages=integer(0, 5), optionalCover=BOOL),
        factPolicyRef=ID, licensePolicyRef=ID, promptBindings=arr(ref('PromptBinding'), 4),
        examples=STRINGS, antiExamples=STRINGS, evaluationRubric=STRINGS)
    S['SkillSnapshot'] = obj(id=ID, skillId=ID, version=text(40), rulesHash=HASH,
        schemaVersion={'const': VERSION}, config=ref('SkillConfig'), policySnapshots=arr(ref('PolicySnapshot'), 2),
        status=enum('DRAFT', 'PUBLISHED', 'RETIRED'))
    S['Qualifiers'] = obj(asOfDate=nullable({'type': 'string', 'format': 'date'}),
        time=nullable(text()), region=nullable(text()), population=nullable(text()),
        unit=nullable(text()), sample=nullable(text()), conditions=STRINGS, studyType=nullable(text()))
    S['ClaimDraft'] = obj(localKey=text(80), claimText=text(2000),
        claimType=enum('NUMBER', 'DATE', 'PERSON', 'ORGANIZATION', 'SCIENTIFIC', 'HISTORICAL', 'LEGAL', 'POLICY', 'LOCATION', 'GENERAL_FACT', 'QUOTE', 'CAUSAL', 'COMPARISON'),
        importance=enum('CRITICAL', 'MAJOR', 'MINOR'), requiresVerification=BOOL, reason=text(),
        subject=text(), predicate=text(), object=text(), qualifiers=ref('Qualifiers'), spans=arr(ref('Span'), 1))
    S['Claim'] = artifact(logicalClaimId=ID, scopeType=enum('ARTICLE_VERSION', 'IMAGE_SELECTION'),
        scopeId=ID, draft=ref('ClaimDraft'), claimHash=HASH,
        verificationStatus=enum('UNVERIFIED', 'SEARCHING', 'SUPPORTED', 'PARTIAL', 'CONTRADICTED', 'UNVERIFIABLE', 'REQUIRES_REVIEW', 'STALE'),
        confidence=CONF, disposition=enum('KEEP', 'REMOVE', 'REPHRASE', 'REQUIRES_REVIEW'),
        contextHash=HASH, checkedAt=nullable(TIME), validUntil=nullable(TIME))
    S['SectionEvidence'] = obj(sectionId=text(80), reason=text(), evidenceSpans=arr(ref('Span'), 1))
    S['SectionAction'] = obj(sectionId=text(80), reason=text(), action=enum('DELETE', 'COMPRESS', 'EXPAND'), targetChars=integer(), factImpact=text())
    S['AnalysisOutput'] = obj(coreThesis=text(300), targetReader=obj(persona=text(), priorKnowledge=text(), readerQuestion=text()),
        articleType=enum('KNOWLEDGE', 'COMMENTARY', 'STORY', 'NEWS', 'BRAND', 'OTHER'),
        outline=arr(obj(sectionId=text(80), blockIds=STRINGS, summary=text(), function=text())),
        strongSections=arr(ref('SectionEvidence')), weakSections=arr(ref('SectionEvidence')),
        repeatedArguments=arr(obj(clusterId=text(80), argument=text(), blockIds=STRINGS, keepBlockId=text(80), reason=text())),
        sectionsToDelete=arr(ref('SectionAction')), sectionsToCompress=arr(ref('SectionAction')), sectionsToExpand=arr(ref('SectionAction')),
        logicProblems=arr(obj(fromBlockId=text(80), toBlockId=text(80), type=text(), reason=text(), severity=enum('BLOCKER', 'WARNING', 'INFO'))),
        factClaims=arr(ref('ClaimDraft')), recommendedStructure=arr(obj(order=integer(1), purpose=text(), sourceBlockIds=STRINGS, needsResearch=BOOL)),
        recommendedTitles=arr(obj(text=text(300), angle=text(), rationale=text(), supportedClaimIds=IDS, risk=text()), 5, 5),
        recommendedHeadings=arr(obj(sectionId=text(80), text=text(300), reason=text())),
        imageOpportunities=arr(obj(blockId=text(80), purpose=enum('EVIDENCE', 'EXPLANATION', 'SCENE', 'EMOTION', 'COVER'), description=text(), mustBeReal=BOOL)),
        risks=arr(obj(type=enum('FACT', 'COPYRIGHT', 'PRIVACY', 'SENSITIVE', 'STRUCTURE', 'PROMPT_INJECTION'), severity=enum('BLOCKER', 'WARNING', 'INFO'), span=ref('Span'), reason=text(), suggestedAction=text())), uncertainties=STRINGS)
    S['AnalysisResult'] = artifact(skillVersionId=ID, result=ref('AnalysisOutput'))
    S['RewritePlan'] = artifact(analysisId=ID, factSetHash=HASH, targetLength=integer(1500, 5000),
        sections=arr(obj(sectionId=text(80), purpose=text(), claimIds=IDS)), removeClaimIds=IDS,
        missingMaterials=STRINGS, forbidNewFacts={'const': True}, toneConstraints=STRINGS, imageOpportunities=STRINGS)
    S['WriterOutput'] = obj(title=text(300), subtitle=nullable(text(500)), contentAst=ref('ContentAst'),
        changeSummary=text(), usedClaimIds=IDS, newClaimCandidates=arr(ref('ClaimDraft')), requiresReviewItems=STRINGS)
    S['ReviewItemDraft'] = obj(localKey=text(80), sectionId=text(80), blockId=text(80), span=ref('Span'),
        problemType=enum('REPETITION', 'LOW_INFORMATION_DENSITY', 'TOO_LONG', 'TOO_SHORT', 'WEAK_HEADING', 'CLICKBAIT', 'LOGIC_JUMP', 'FACT_RISK', 'BAD_TRANSITION', 'MOBILE_READABILITY', 'AI_TONE', 'OTHER'),
        severity=enum('BLOCKER', 'WARNING', 'INFO'), reason=text(), recommendedAction=text(),
        suggestedReduction=integer(), suggestedHeading=nullable(text()), rewriteSuggestion=nullable(text()), relatedClaimIds=IDS)
    S['Score'] = obj(dimension=enum('THESIS', 'STRUCTURE', 'LOGIC', 'READABILITY', 'TITLE', 'TONE', 'FACT_FIDELITY'), score=integer(1, 5), reason=text())
    S['ReviewOutput'] = obj(summary=text(), scores=arr(ref('Score'), 7, 7), items=arr(ref('ReviewItemDraft')),
        overallDecision=enum('PASS', 'REVISE', 'MAJOR_REVISION'))
    S['ReviewReport'] = artifact(skillVersionId=ID, report=ref('ReviewOutput'))
    S['ItemDecision'] = obj(itemId=ID, disposition=enum('ACCEPTED', 'ALTERNATIVE', 'NOT_APPLIED'), reason=text())
    S['RevisionOutput'] = obj(writer=ref('WriterOutput'), itemDecisions=arr(ref('ItemDecision')))
    S['SourceSnapshot'] = artifact(sourceId=ID, url=URL, canonicalUrl=URL, title=nullable(text()),
        publisher=nullable(text()), author=nullable(text()), publishDate=nullable(TIME), updatedDate=nullable(TIME), retrievedAt=TIME,
        authorityLevel=enum('A', 'B', 'C', 'D', 'UNCLASSIFIED'), authorityReason=text(),
        primarySource=BOOL, independenceGroup=text(), sourceType=enum('OFFICIAL', 'PAPER', 'REPORT', 'BOOK', 'MEDIA', 'BLOG', 'FORUM', 'SOCIAL', 'USER_DOCUMENT'),
        excerpt=text(10000, 0), locator=text(), objectRef=nullable(ref('ObjectRef')), rightsBasis=text(),
        captureMode=enum('METADATA', 'EXCERPT', 'FULL_ALLOWED'),
        accessStatus=enum('AVAILABLE', 'UNAVAILABLE', 'RETRACTED'), httpStatus=nullable(integer(100, 599)), validUntil=TIME)
    S['Evidence'] = obj(sourceSnapshotId=ID, relation=enum('SUPPORTS', 'CONTRADICTS', 'CONTEXT'), quote=text(10000), locator=text(), qualifiersMatch=BOOL, independenceGroup=text())
    S['FactVerification'] = artifact(claimId=ID, status=enum('SUPPORTED', 'PARTIAL', 'CONTRADICTED', 'UNVERIFIABLE', 'REQUIRES_REVIEW', 'STALE'),
        confidence=CONF, method=enum('RULE_ASSISTED', 'HUMAN'), evidence=arr(ref('Evidence')),
        reason=text(), policyVersionId=ID, contextHash=HASH, validUntil=TIME)
    S['FactSet'] = obj(articleId=ID, versionId=ID, claims=arr(ref('ArtifactRef')), verifications=arr(ref('ArtifactRef')),
        removedClaimIds=IDS, policyVersionId=ID, hash=HASH, stale=BOOL, validUntil=TIME)
    S['ImageTextExtraction'] = artifact(selectionId=ID, variantId=ID, variantHash=HASH,
        status=enum('READABLE', 'NO_TEXT', 'UNREADABLE', 'PARTIAL'),
        regions=arr(obj(box=obj(x=integer(), y=integer(), width=integer(1), height=integer(1)), text=text(3000), confidence=CONF)),
        method=enum('VISION', 'HUMAN'), manualTaskId=nullable(ID))
    S['ImageSlot'] = artifact(sectionId=text(80), anchorBlockId=text(80), anchorSide=enum('BEFORE', 'AFTER'), position=integer(),
        purpose=enum('EVIDENCE', 'EXPLANATION', 'SCENE', 'EMOTION', 'COVER'), description=text(), priority=integer(1, 5),
        preferredImageType=text(), searchQueries=arr(text(), 0, 3), aspectRatio=text(30), mustBeReal=BOOL,
        aiGenerationAllowed=BOOL, mandatory=BOOL, status=enum('PLANNED', 'SEARCHING', 'WAITING_SELECTION', 'READY', 'STALE', 'CANCELLED'), planHash=HASH)
    S['ImagePlanOutput'] = obj(slots=arr(ref('ImageSlot'), 0, 6), noImagesReason=nullable(text()))
    S['ImageScores'] = obj(**{k: integer(0, 100) for k in ['narrativeRelevance', 'visualQuality', 'authenticity', 'resolution', 'aspectRatioFit', 'licenseSuitability', 'sourceReliability', 'overallScore']})
    S['ImageCandidate'] = artifact(slotId=ID, provider=enum('COMMONS', 'PEXELS', 'AI'), externalId=text(),
        sourceUrl=URL, thumbnailUrl=URL, width=integer(1), height=integer(1), mime=enum('image/jpeg', 'image/png', 'image/webp'),
        metadataSnapshotId=ID, licenseMetadataId=nullable(ID), scores=ref('ImageScores'),
        scorePolicyVersion=ID, evaluationExecutionId=nullable(ID), exclusionReasons=STRINGS,
        eligibility=enum('ELIGIBLE', 'BLOCKED', 'REQUIRES_REVIEW'), evaluatedAt=nullable(TIME))
    S['LicenseOption'] = obj(name=nullable(text()), version=nullable(text()), url=nullable(URL),
        attributionRequired=nullable(BOOL), commercialUseAllowed=nullable(BOOL), modificationAllowed=nullable(BOOL),
        shareAlikeRequired=nullable(BOOL), publicDomain=nullable(BOOL))
    S['LicenseMetadata'] = artifact(assetId=nullable(ID), candidateId=nullable(ID), revision=integer(1),
        rightsBasis=enum('OPEN_LICENSE', 'PUBLIC_DOMAIN', 'PROVIDER_LICENSE', 'DIRECT_PERMISSION', 'GENERATED_TERMS'),
        author=nullable(text()), authorUrl=nullable(URL), sourceUrl=URL, licenseOptions=arr(ref('LicenseOption')),
        selectedLicense=nullable(ref('LicenseOption')), selectionReason=nullable(text()),
        licenseVerified=BOOL, verificationStatus=enum('PENDING', 'VERIFIED', 'UNKNOWN', 'REJECTED', 'REQUIRES_REVIEW'),
        evidence=arr(ref('ObjectRef')), evidenceHash=HASH, providerTermsVersion=nullable(text()), providerAttributionRequired=nullable(BOOL),
        modificationDescription=text(), derivativeLicense=nullable(text()), otherRightsStatus=enum('CLEAR', 'REVIEW_REQUIRED', 'BLOCKED'),
        restrictions=STRINGS, validatedBy=nullable(ID), validatorVersion=ID, retrievedAt=TIME, checkedAt=nullable(TIME), validUntil=nullable(TIME))
    S['LicenseDecision'] = obj(licenseMetadataId=ID, policyVersionId=ID, decision=enum('ALLOW', 'BLOCKED', 'REQUIRES_REVIEW'),
        reasons=STRINGS, obligations=STRINGS, obligationsSatisfied=BOOL, evidenceHash=HASH, validUntil=TIME)
    S['Variant'] = artifact(assetId=ID, objectRef=ref('ObjectRef'), originalHash=HASH, transformHash=HASH,
        transformChain=STRINGS, width=integer(1), height=integer(1), generated=BOOL,
        watermarkStatus=enum('NOT_REQUIRED', 'PENDING', 'SUCCEEDED', 'FAILED'), watermarkVersion=nullable(text()),
        fontHash=nullable(HASH), processedAt=TIME)
    S['ImageSelection'] = artifact(slotId=ID, assetId=ID, variantId=ID, licenseMetadataId=ID,
        caption=text(), selectedBy=ID, selectedAt=TIME, active=BOOL)
    S['ManifestItem'] = obj(displayOrder=integer(1), slotId=ID, selectionId=ID, assetId=ID, variantId=ID,
        assetHash=HASH, licenseMetadataId=ID, caption=text(), attributionText=text(), attributionLinks=arr(URL),
        modifications=STRINGS, obligations=STRINGS, obligationsSatisfied=BOOL, generatedDisclosure=nullable(text()))
    S['Manifest'] = artifact(items=arr(ref('ManifestItem'), 0, 6), noticeCompact=text(10000, 0), noticeFull=text(30000, 0), policyVersionId=ID)
    S['ReleaseCandidate'] = artifact(version=ref('ArtifactRef'), manifest=ref('ArtifactRef'), factSet=ref('FactSet'),
        skillSnapshot=ref('SkillSnapshot'), policyRefs=arr(ref('PolicySnapshot')), selections=arr(ref('ArtifactRef')),
        sourceSnapshots=arr(ref('ArtifactRef')), releaseHash=HASH, validUntil=TIME)
    S['QaCheck'] = obj(ruleId=enum(*[f'QA-{i:02}' for i in range(1, 17)]),
        result=enum('PASS', 'FAIL', 'NOT_EXECUTED'), severity=enum('BLOCKER', 'WARNING', 'INFO'),
        entityIds=IDS, spans=arr(ref('Span')), evidence=STRINGS, remediation=text(), acknowledgementAllowed=BOOL)
    S['QaReport'] = artifact(candidateId=ID, releaseHash=HASH, ruleSetVersion=ID, skillVersionId=ID,
        checks=arr(ref('QaCheck'), 16), blockerCount=integer(), warningCount=integer(), status=enum('PASS', 'FAIL'),
        executedAt=TIME, validUntil=TIME)
    S['Approval'] = artifact(candidateId=ID, releaseHash=HASH, qaReportId=ID,
        decision=enum('APPROVED', 'REJECTED'), reviewerId=ID, comment=text(), acknowledgedWarningIds=IDS, decidedAt=TIME)
    S['BudgetReservation'] = obj(id=ID, articleId=ID, executionId=ID, amount=MONEY, currency={'const': 'USD'},
        pricingVersion=ID, status=enum('RESERVED', 'SETTLED', 'RELEASED', 'UNKNOWN'),
        costType=enum('ESTIMATED', 'ACTUAL'), idempotencyKey=ID, createdAt=TIME)
    S['Settlement'] = obj(reservationId=ID, providerRequestId=nullable(text()), actualAmount=nullable(MONEY),
        currency={'const': 'USD'}, result=enum('SETTLED', 'UNKNOWN', 'RELEASED'), settlementKey=ID)
    S['Usage'] = obj(inputTokens=integer(), cachedInputTokens=integer(), outputTokens=integer(),
        reasoningTokensIfProvided=nullable(integer()), imageUnits=integer(), searchCalls=integer())
    S['StepContext'] = obj(actor=ref('ActorContext'), jobId=ID, workflowId=ID, stepExecutionId=ID,
        stepCode=enum('ANALYZE', 'VERIFY_FACTS', 'BUILD_REWRITE_PLAN', 'WRITE', 'EDITORIAL_REVIEW', 'REVISE', 'RECONCILE_FACTS', 'PLAN_IMAGES', 'SEARCH_IMAGES', 'VALIDATE_LICENSES', 'EVALUATE_IMAGES', 'GENERATE_IMAGE', 'WATERMARK', 'BUILD_MANIFEST', 'FINAL_QA', 'EXPORT', 'DELETE_ARTICLE'),
        attempt=integer(1), scopeId=ID, workflowGeneration=integer(1), logicalKey=HASH, baseVersionId=ID,
        inputHash=HASH, skillVersionId=ID, policyVersions=IDS, deadline=TIME, traceId=ID,
        fencingToken=integer(1), budgetReservationId=nullable(ID))
    S['ProviderContext'] = obj(reservationId=nullable(ID), deadline=TIME, traceId=ID, secretRef=text(),
        mode=enum('MOCK', 'REAL'), pricingVersion=nullable(ID), idempotencyKey=ID)
    S['AIRequest'] = obj(context=ref('StepContext'), provider=ref('ProviderContext'),
        capability=enum('TEXT', 'VISION', 'SEARCH', 'GENERATION'), promptBinding=ref('PromptBinding'),
        input=ref('ObjectRef'), outputSchemaId=text(), allowedTools=STRINGS, maxToolCalls=integer(0, 8), maxOutputTokens=integer(1, 40000))
    S['AIResult'] = obj(status=enum('SUCCEEDED', 'FAILED', 'REFUSED', 'INCOMPLETE', 'OUTCOME_UNKNOWN', 'CANCELLED'),
        providerRequestId=nullable(text()), modelRequested=text(), modelReturned=nullable(text()),
        rawResponse=nullable(ref('ObjectRef')), structuredOutput=nullable(ref('ObjectRef')), schemaValid=BOOL,
        semanticsValid=BOOL, refusal=nullable(text()), incompleteReason=nullable(text()), error=nullable(ref('Error')), usage=ref('Usage'), settlement=ref('Settlement'))
    S['ToolCall'] = obj(id=ID, agentExecutionId=ID, ordinal=integer(1, 8), toolName=text(), arguments=ref('ObjectRef'), result=nullable(ref('ObjectRef')), providerRequestId=nullable(text()), error=nullable(ref('Error')))
    S['SafeFetchRequest'] = obj(url=URL, purpose=enum('SOURCE', 'IMAGE', 'LICENSE'), maxBytes=integer(1, 20971520), maxPixels=integer(1, 40000000), deadline=TIME)
    S['SafeFetchResult'] = obj(finalUrl=URL, redirectChain=arr(URL, 0, 5), accessStatus=enum('AVAILABLE', 'UNAVAILABLE', 'BLOCKED'), objectRef=nullable(ref('ObjectRef')), error=nullable(ref('Error')))
    S['SearchQuery'] = obj(slotId=ID, queries=arr(text(), 1, 3), cursor=nullable(text()), limit=integer(1, 20))
    S['SearchPage'] = obj(items=arr(ref('ImageCandidate'), 0, 20), nextCursor=nullable(text()), partial=BOOL, errors=arr(ref('Error')))
    S['GenerationRequest'] = obj(slotId=ID, prompt=text(10000), style=text(), reason=text(), size=text(30), termsSnapshotId=ID)
    S['GenerationResult'] = obj(generationId=ID, providerRequestId=nullable(text()), assetId=nullable(ID),
        status=enum('SUCCEEDED', 'FAILED', 'OUTCOME_UNKNOWN', 'REFUSED'), seedIfAvailable=nullable(integer()), error=nullable(ref('Error')))
    S['ManualTask'] = artifact(workflowId=ID, type=enum('FACT_EVIDENCE', 'LICENSE_EVIDENCE', 'IMAGE_TEXT', 'BUDGET', 'RECONCILIATION', 'WARNING', 'REANCHOR'),
        entityId=ID, required=BOOL, status=enum('OPEN', 'RESOLVED', 'CANCELLED'), requiredEvidence=STRINGS, resumeStep=text(80))
    S['Operation'] = obj(operationId=ID, resourceType=enum('WORKFLOW', 'STEP', 'EXPORT'),
        status=enum('QUEUED', 'RUNNING', 'WAITING', 'PAUSED', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'PENDING', 'RETRY_WAIT', 'WAITING_HUMAN', 'TIMED_OUT', 'STALE', 'READY', 'REVOKED'),
        step=nullable(text()), resultRefs=arr(ref('ArtifactRef')), error=nullable(ref('Error')), traceId=ID)
    S['CommandAccepted'] = obj(operationId=ID, status={'const': 'QUEUED'}, traceId=ID)
    S['DependencyEvent'] = obj(eventId=ID, articleId=ID, generation=integer(1), sequence=integer(1),
        type=enum('TITLE_CHANGED', 'BODY_CHANGED', 'SELECTION_CHANGED', 'SOURCE_CHANGED', 'SOURCE_RETRACTED', 'POLICY_CHANGED', 'SKILL_CHANGED', 'MANUAL_RESOLVED', 'BUDGET_CHANGED', 'VARIANT_CHANGED'),
        entityIds=IDS, beforeHash=nullable(HASH), afterHash=nullable(HASH), actor=ref('ActorContext'), occurredAt=TIME)
    S['AuditRecord'] = obj(id=ID, actorId=ID, actorType=enum('OWNER', 'SYSTEM_WORKER'), action=text(),
        articleId=nullable(ID), entityType=text(), entityId=ID, beforeHash=nullable(HASH), afterHash=nullable(HASH), traceId=ID, createdAt=TIME)
    S['ArticleSummary'] = obj(id=ID, ownerId=ID, name=text(300), originalVersionId=ID, currentVersionId=ID,
        skillVersionId=ID, targetLength=integer(1500, 5000), budget=MONEY, spentAmount=MONEY, reservedAmount=MONEY,
        currency={'const': 'USD'}, status=enum('CREATED','ANALYZING','ANALYZED','FACT_CHECKING','FACT_VERIFIED','WRITING','DRAFTED','REVIEWING','REVIEWED','REVISING','REVISED','FACT_RECHECKING','FACT_RECHECKED','IMAGE_PLANNING','IMAGE_SEARCHING','IMAGE_GENERATING','WAITING_IMAGE_SELECTION','IMAGES_READY','FINAL_QA','READY_FOR_REVIEW','HUMAN_REVIEW','APPROVED','REJECTED','NEEDS_REVISION','WAITING_MANUAL','PAUSED','FAILED','CANCELLED'), lockVersion=integer(), archived=BOOL, updatedAt=TIME)
    S['ArticleArtifact'] = obj(job=ref('ArticleSummary'), artifacts=arr(ref('ArtifactRef')))
    S['ExportArtifact'] = artifact(candidateId=nullable(ID), approvalId=nullable(ID),
        status=enum('QUEUED', 'RUNNING', 'READY', 'FAILED', 'REVOKED'), format=enum('ZIP', 'MARKDOWN', 'HTML'),
        draft=BOOL, downloadUrl=nullable(URL), expiresAt=nullable(TIME), objectRef=nullable(ref('ObjectRef')))
    S['DeletionImpact'] = obj(articleId=ID, impactHash=HASH, lockVersion=integer(),
        objectCount=integer(), versionCount=integer(), approvalCount=integer(), retainedAuditFields=STRINGS,
        backupRetentionDays={'const': 30}, holds=STRINGS, expiresAt=TIME)
    S['Proposal'] = artifact(baseVersionId=ID, scopeBlockIds=STRINGS, proposedVersionId=ID,
        status=enum('PENDING', 'ACCEPTED', 'REJECTED', 'STALE'), acceptedVersionId=nullable(ID))
    S['Diff'] = obj(articleId=ID, fromVersionId=ID, toVersionId=ID,
        blocks=arr(obj(blockId=text(80), kind=enum('ADD', 'DELETE', 'CHANGE', 'UNCHANGED'), before=text(30000, 0), after=text(30000, 0))))
    S['ProviderConfig'] = obj(provider=text(80), enabled=BOOL, capabilities=arr(enum('TEXT', 'VISION', 'SEARCH', 'GENERATION')),
        limits=obj(requestsPerMinute=integer(1), concurrency=integer(1, 4)), credentialConfigured=BOOL, configVersion=integer(1))
    S['Dashboard'] = obj(articleCount=integer(), blockedCount=integer(), pendingManualCount=integer(), spent=MONEY, reserved=MONEY, currency={'const': 'USD'})
    S['CurrentUser'] = obj(id=ID, displayName=text(), role={'const': 'OWNER'}, capabilities=STRINGS, csrfToken=text())
    S['SkillIdentity'] = obj(id=ID, code=text(100), name=text(100), activeVersionId=nullable(ID))
    S['DispositionResult'] = obj(entityId=ID, status=text(50), auditId=ID)
    S['ReviewItem'] = artifact(reportId=ID, issue=ref('ReviewItemDraft'),
        status=enum('OPEN', 'ACCEPTED', 'REJECTED', 'RESOLVED', 'STALE'),
        dispositionReason=nullable(text()), resolvedInVersionId=nullable(ID))
    S['ReviewReport']['properties']['items'] = arr(ref('ReviewItem'))
    S['ReviewReport']['required'].append('items')
    S['ClaimDetail'] = obj(claim=ref('Claim'), verifications=arr(ref('FactVerification')))
    S['Source'] = artifact(url=URL, canonicalUrl=URL, urlHash=HASH, title=nullable(text()),
        publisher=nullable(text()), author=nullable(text()), authorityLevel=enum('A','B','C','D','UNCLASSIFIED'),
        status=enum('DISCOVERED','FETCHED','REVIEWED','UNAVAILABLE','RETRACTED'),
        snapshots=arr(ref('ArtifactRef')), referencedClaimIds=IDS)
    S['SourceDetail'] = obj(source=ref('Source'), snapshots=arr(ref('SourceSnapshot')))
    S['ImageAsset'] = artifact(provider=enum('COMMONS','PEXELS','AI'),externalId=text(),generated=BOOL,
        mime=enum('image/jpeg','image/png','image/webp'),width=integer(1),height=integer(1),
        originalHash=HASH,status=enum('READY','QUARANTINED','FAILED'),sourceUrl=nullable(URL),
        variants=arr(ref('Variant')),generation=nullable(ref('GenerationResult')))
    S['ExecutionDetail'] = obj(id=ID,articleId=ID,versionId=ID,workflowId=ID,stepId=ID,attempt=integer(1),
        agentName=text(),traceId=ID,mode=enum('MOCK','REAL'),promptVersion=ID,skillVersion=ID,
        policyVersions=IDS,inputHash=HASH,inputRef=ref('ObjectRef'),result=ref('AIResult'),
        tools=arr(ref('ToolCall')),startedAt=TIME,finishedAt=nullable(TIME),latencyMs=integer())
    S['WorkflowView'] = obj(execution=ref('Operation'),steps=arr(ref('Operation')),generation=integer(1),definitionVersion=text())
    S['LicenseView'] = obj(manifests=arr(ref('Manifest')),missingItems=STRINGS)
    S['UsageSummary'] = obj(currency={'const':'USD'},actual=MONEY,estimated=MONEY,unknownReserved=MONEY,
        inputTokens=integer(),cachedInputTokens=integer(),outputTokens=integer(),searchCalls=integer(),imageUnits=integer(),
        entries=arr(ref('BudgetReservation')),nextCursor=nullable(text()))
    S['ImageSlotDraft'] = copy.deepcopy(S['ImageSlot'])
    del S['ImageSlotDraft']['properties']['meta']
    S['ImageSlotDraft']['required'].remove('meta')
    for field in ['status','planHash']:
        del S['ImageSlotDraft']['properties'][field]
        S['ImageSlotDraft']['required'].remove(field)
    S['ImagePlanOutput']['properties']['slots'] = arr(ref('ImageSlotDraft'),0,6)
    for name in ['ArticleSummary', 'ArticleVersion', 'AnalysisResult', 'ReviewReport', 'Claim', 'Source', 'SourceSnapshot', 'ImageSlot', 'ImageCandidate', 'Proposal', 'Manifest', 'QaReport', 'Approval', 'ManualTask', 'AuditRecord', 'SkillIdentity', 'SkillSnapshot', 'ProviderConfig', 'BudgetReservation', 'ArtifactRef']:
        S[name + 'Page'] = obj(items=arr(ref(name), 0, 100), nextCursor=nullable(text()))


def request(schema_name, **fields):
    S[schema_name] = obj(**fields)
    return schema_name


def build_api():
    # Explicit operation inventory, ordered as SRS 29.2. Tuple: method path, request, response, status, ETag required.
    rows = []
    def add(route, body=None, result='DispositionResult', code=200, etag=False, query=None):
        rows.append((route, body, result, code, etag, query or {}))
    reason = request('ReasonRequest', reason=text())
    version = request('VersionRequest', versionId=ID)
    base = request('BaseVersionRequest', baseVersionId=ID)
    add('POST /auth/login', request('LoginRequest', username=text(100), password=text(1000)), 'CurrentUser')
    add('POST /auth/logout', code=204)
    add('GET /me', result='CurrentUser')
    add('GET /dashboard', result='Dashboard', query={'range': enum('DAY', 'WEEK', 'MONTH')})
    add('POST /articles', request('CreateArticleRequest', original=obj(format=enum('TEXT', 'MARKDOWN'), text=text(1048576)), skillVersionId=ID,
        targetLength=integer(1500, 5000), rightsBasis=obj(kind=enum('OWNED', 'LICENSED', 'PERMISSION'), declaration=text(), evidenceIds=IDS), budget=MONEY), 'ArticleArtifact', 201)
    add('GET /articles', result='ArticleSummaryPage', query={'status': S['ArticleSummary']['properties']['status'], 'query': text(300)})
    add('GET /articles/{id}', result='ArticleArtifact')
    request('PatchArticleRequest', name=text(300), targetLength=integer(1500, 5000), budget=MONEY, archived=BOOL)
    S['PatchArticleRequest']['required'] = []
    S['PatchArticleRequest']['minProperties'] = 1
    add('PATCH /articles/{id}', 'PatchArticleRequest', 'ArticleArtifact', etag=True)
    add('POST /articles/{id}/clone', request('CloneRequest', fromVersionId=ID, skillVersionId=ID), 'ArticleArtifact', 201)
    add('POST /articles/{id}/workflow/start', request('StartRequest', runMode=enum('EDITORIAL_DRAFT', 'FULL'), allowAutoGeneration={'type': 'boolean', 'default': False}), code=202, etag=True)
    add('POST /articles/{id}/analyze', base, code=202)
    add('POST /articles/{id}/fact-check', request('FactCheckRequest', versionId=ID, claimIds=IDS), code=202)
    S['FactCheckRequest'] = optional(S['FactCheckRequest'], 'claimIds')
    add('POST /articles/{id}/generate', request('GenerateRequest', baseVersionId=ID, rewritePlanId=ID), code=202, etag=True)
    add('POST /articles/{id}/review', version, code=202)
    add('POST /articles/{id}/revise', request('ReviseRequest', versionId=ID, reportId=ID, itemDecisions=arr(ref('ItemDecision'))), code=202, etag=True)
    add('GET /articles/{id}/analyses', result='AnalysisResultPage', query={'versionId': ID})
    add('GET /articles/{id}/reviews', result='ReviewReportPage', query={'versionId': ID})
    add('PATCH /review-items/{id}', request('ReviewDispositionRequest', disposition=enum('ACCEPTED', 'REJECTED', 'RESOLVED'), reason=text()))
    add('GET /articles/{id}/versions', result='ArticleVersionPage')
    add('GET /articles/{id}/versions/{versionId}', result='ArticleVersion')
    add('POST /articles/{id}/versions', request('SaveVersionRequest', baseVersionId=ID, title=text(300), subtitle=nullable(text(500)), contentAst=ref('ContentAst'), blockMappings=arr(ref('BlockMapping')), reason=text()), 'ArticleVersion', 201, True)
    add('GET /articles/{id}/diff', result='Diff', query={'from': ID, 'to': ID})
    add('POST /articles/{id}/restore', request('RestoreRequest', versionId=ID, reason=text()), 'ArticleVersion', 201, True)
    add('POST /articles/{id}/regenerate-section', request('RegenerateRequest', baseVersionId=ID, blockIds=arr(text(80), 1), instruction=text(10000)), code=202)
    add('GET /articles/{id}/proposals', result='ProposalPage', query={'status': enum('PENDING', 'ACCEPTED', 'REJECTED', 'STALE')})
    add('POST /proposals/{id}/accept', base, 'ArticleVersion', 201, True)
    add('POST /proposals/{id}/reject', reason)
    add('GET /articles/{id}/claims', result='ClaimPage', query={'versionId': ID, 'status': S['Claim']['properties']['verificationStatus']})
    add('GET /claims/{id}', result='ClaimDetail')
    add('POST /claims/{id}/verify', request('VerifyRequest', sourceIds=IDS), code=202)
    S['VerifyRequest'] = optional(S['VerifyRequest'], 'sourceIds')
    add('POST /claims/{id}/human-verifications', request('HumanFactRequest', evidenceIds=arr(ID, 1), decision=enum('SUPPORTED', 'PARTIAL', 'CONTRADICTED', 'UNVERIFIABLE', 'REQUIRES_REVIEW'), reason=text()), 'FactVerification', 201)
    add('GET /articles/{id}/sources', result='SourcePage')
    add('POST /articles/{id}/sources', request('AddSourceRequest', url=URL, providedExcerpt=text(10000, 0), reason=text()), 'Source', 201)
    add('GET /sources/{id}', result='SourceDetail')
    add('POST /sources/{id}/refresh', code=202)
    add('POST /articles/{id}/images/plan', version, code=202)
    add('GET /articles/{id}/image-slots', result='ImageSlotPage', query={'versionId': ID})
    add('PATCH /image-slots/{id}', request('PatchSlotRequest', anchor=obj(blockId=text(80), side=enum('BEFORE', 'AFTER')), purpose=enum('EVIDENCE', 'EXPLANATION', 'SCENE', 'EMOTION', 'COVER'), mandatory=BOOL, description=text()), 'ImageSlot', etag=True)
    S['PatchSlotRequest']['required'] = []
    S['PatchSlotRequest']['minProperties'] = 1
    add('DELETE /image-slots/{id}', reason, code=204, etag=True)
    add('POST /image-slots/{id}/search', request('SearchRequest', queries=arr(text(), 1, 3), providers=arr(enum('COMMONS', 'PEXELS'), 1, 2)), code=202)
    add('GET /image-slots/{id}/candidates', result='ImageCandidatePage', query={'eligibleOnly': BOOL})
    add('POST /image-slots/{id}/generate', request('GenerateImageRequest', prompt=text(10000), style=text(), reason=text()), code=202)
    request('SelectImageRequest', candidateId=ID, assetId=ID, variantId=ID, caption=text(), reason=text())
    S['SelectImageRequest'] = optional(S['SelectImageRequest'], 'candidateId', 'assetId')
    S['SelectImageRequest']['oneOf'] = [{'required': ['candidateId']}, {'required': ['assetId']}]
    add('PUT /image-slots/{id}/selection', 'SelectImageRequest', 'ImageSelection', etag=True)
    add('DELETE /image-slots/{id}/selection', reason, code=204, etag=True)
    add('GET /images/{id}', result='ImageAsset')
    add('POST /images/{id}/variants', request('VariantRequest', crop=nullable(obj(x=integer(), y=integer(), width=integer(1), height=integer(1))), resize=nullable(obj(width=integer(1), height=integer(1)))), code=202)
    add('GET /images/{id}/license', result='LicenseMetadata', query={'revision': integer(1)})
    add('POST /images/{id}/license-verifications', request('HumanLicenseRequest', evidence=arr(ref('ObjectRef'), 1), selectedLicense=ref('LicenseOption'), reason=text()), 'LicenseMetadata', 201)
    add('GET /articles/{id}/licenses', result='LicenseView', query={'candidateId': ID})
    add('POST /articles/{id}/qa', version, code=202)
    add('GET /articles/{id}/qa-reports', result='QaReportPage', query={'candidateId': ID})
    add('POST /qa-reports/{id}/acknowledgements', request('AcknowledgeRequest', checkIds=arr(text(20), 1), reason=text()), code=201)
    add('POST /articles/{id}/human-review', request('BeginReviewRequest', candidateId=ID, qaReportId=ID), etag=True)
    add('POST /articles/{id}/approve', request('ApproveRequest', candidateId=ID, releaseHash=HASH, qaReportId=ID, comment=text()), 'Approval', 201, True)
    add('POST /articles/{id}/reject', request('RejectRequest', candidateId=ID, reason=text(), issueIds=IDS), 'Approval', 201, True)
    add('POST /articles/{id}/reopen', reason, etag=True)
    add('GET /articles/{id}/human-reviews', result='ApprovalPage')
    add('POST /articles/{id}/exports', request('ExportRequest', approvalId=ID, format=enum('ZIP', 'MARKDOWN', 'HTML')), code=202)
    add('POST /articles/{id}/previews', request('PreviewRequest', versionId=ID, format=enum('MARKDOWN', 'HTML')), code=202)
    add('GET /exports/{id}', result='ExportArtifact')
    add('GET /articles/{id}/workflow', result='WorkflowView')
    add('POST /workflows/{id}/pause', reason)
    add('POST /workflows/{id}/resume', code=202)
    add('POST /workflows/{id}/cancel', reason)
    add('POST /workflow-steps/{id}/retry', reason, code=202)
    add('GET /articles/{id}/manual-tasks', result='ManualTaskPage', query={'status': enum('OPEN', 'RESOLVED', 'CANCELLED')})
    add('POST /manual-tasks/{id}/resolve', request('ResolveTaskRequest', resolution=text(5000), evidenceIds=IDS))
    add('GET /operations/{id}', result='Operation')
    add('GET /articles/{id}/events', result='DependencyEvent')
    add('GET /articles/{id}/executions', result='ArtifactRefPage', query={'type': enum('AGENT', 'TOOL')})
    add('GET /executions/{id}', result='ExecutionDetail')
    add('GET /articles/{id}/audit-logs', result='AuditRecordPage')
    add('GET /skills', result='SkillIdentityPage', query={'status': enum('DRAFT', 'PUBLISHED', 'RETIRED')})
    add('POST /skills', request('CreateSkillRequest', code=text(100), name=text(100)), 'SkillIdentity', 201)
    add('GET /skills/{id}/versions', result='SkillSnapshotPage')
    add('POST /skills/{id}/versions', request('CreateSkillVersionRequest', baseVersionId=ID, config=ref('SkillConfig')), 'SkillSnapshot', 201)
    add('PUT /skill-versions/{id}', request('EditSkillVersionRequest', config=ref('SkillConfig')), 'SkillSnapshot')
    add('POST /skill-versions/{id}/publish', request('PublishSkillRequest', changeLog=text()), 'SkillSnapshot')
    add('POST /skill-versions/{id}/retire', reason, 'SkillSnapshot')
    add('GET /settings/providers', result='ProviderConfigPage')
    add('PUT /settings/providers/{provider}', request('SetProviderRequest', enabled=BOOL, limits=S['ProviderConfig']['properties']['limits'], secretRef=text()), 'ProviderConfig')
    add('POST /settings/providers/{provider}/test', request('ProbeRequest', capability=enum('TEXT', 'VISION', 'SEARCH', 'GENERATION')), code=202)
    add('GET /usage', result='UsageSummary', query={'dateFrom': {'type': 'string', 'format': 'date'}, 'dateTo': {'type': 'string', 'format': 'date'}, 'groupBy': enum('DAY', 'ARTICLE', 'PROVIDER', 'MODEL'), 'cursor':text(), 'limit':dict(integer(1,100),default=20)})
    add('GET /articles/{id}/deletion-impact', result='DeletionImpact')
    add('POST /articles/{id}/deletion', request('DeleteArticleRequest', impactHash=HASH, reason=text()), code=202, etag=True)
    paths = {}
    inventory = []
    for route, body, result, code, etag, query in rows:
        method, path = route.split(' ')
        operation_id = method.lower() + ''.join(w.title() for w in re.findall(r'[A-Za-z]+', path))
        parameters = [{'name': n, 'in': 'path', 'required': True, 'schema': text(80) if n == 'provider' else ID} for n in re.findall(r'\{([^}]+)\}', path)]
        if result.endswith('Page'):
            query = dict(query, cursor=text(), limit=dict(integer(1, 100), default=20))
        parameters.extend({'name': n, 'in': 'query', 'required': path.endswith('/diff') and n in ('from', 'to'), 'schema': s} for n, s in query.items())
        if method != 'GET' and path != '/auth/login':
            parameters += [{'name': 'X-CSRF-Token', 'in': 'header', 'required': True, 'schema': text()},
                {'name': 'Idempotency-Key', 'in': 'header', 'required': True, 'schema': ID},
                {'name': 'X-Request-Hash', 'in': 'header', 'required': True, 'schema': HASH}]
        if etag:
            parameters.append({'name': 'If-Match', 'in': 'header', 'required': True, 'schema': {'type': 'string', 'pattern': '^"job-[0-9]+"$'}})
        if path.endswith('/events'):
            parameters.append({'name': 'Last-Event-ID', 'in': 'header', 'required': False, 'schema': text(100)})
        response = {'description': 'Accepted durable command' if code == 202 else 'Success'}
        if code != 204:
            response['content'] = {'application/json': {'schema': ref('CommandAccepted' if code == 202 else result)}}
        if path.endswith('/events'):
            response['content'] = {'text/event-stream': {'schema': {'type': 'string'}, 'example': 'id: 1\nevent: dependency\ndata: {"type":"BODY_CHANGED"}\n\n'}}
        if code == 202:
            response['headers'] = {'Location': {'schema': {'type': 'string'}, 'description': '/api/v1/operations/{operationId}'}}
        if etag or result in ('ArticleArtifact', 'ArticleVersion'):
            response.setdefault('headers', {})['ETag'] = {'schema': {'type': 'string'}, 'description': 'Current aggregate ETag: "job-{lockVersion}"'}
        responses = {str(code): response}
        for status in (400, 401, 403, 404, 409, 412, 422, 428, 429, 503):
            responses[str(status)] = {'description': {400:'Malformed request',401:'Unauthenticated',403:'Forbidden / CSRF',404:'Not found or concealed ownership',409:'State, idempotency or dependency conflict',412:'Stale ETag',422:'Rule or field validation',428:'Missing If-Match',429:'Capacity / rate limit',503:'Dependency unavailable / FEATURE_NOT_READY'}[status], 'content': {'application/json': {'schema': ref('Error')}}}
        op = {'operationId': operation_id, 'summary': route, 'parameters': parameters, 'responses': responses,
            'x-contract-status': 'REVIEW_CANDIDATE', 'x-actor': 'OWNER',
            'x-srs': '33 (CR-T00-001)' if '/deletion' in path else '29.2'}
        if body:
            op['requestBody'] = {'required': True, 'content': {'application/json': {'schema': ref(body)}}}
        if path == '/auth/login':
            op['security'] = []
            op['description'] = 'Validate same-site Origin; rate limit 5/IP/min. On success issue Secure HttpOnly SameSite session cookie.'
        paths.setdefault(path, {})[method.lower()] = op
        inventory.append({'method': method, 'path': path, 'operationId': operation_id, 'request': body, 'response': 'CommandAccepted' if code == 202 else result, 'status': code, 'ifMatch': etag})
    api = {'openapi': '3.1.0', 'info': {'title': 'AI Editorial Agent — review candidate', 'version': VERSION,
        'description': 'Unapproved contract candidate. No provider capability or production integration claim.'},
        'servers': [{'url': '/api/v1'}], 'security': [{'session': []}], 'paths': paths,
        'components': {'securitySchemes': {'session': {'type': 'apiKey', 'in': 'cookie', 'name': 'EDITORIAL_SESSION'}}, 'schemas': S}}
    # JSON is also YAML 1.2; keeping serialization deterministic avoids a runtime YAML dependency.
    api = json.loads(json.dumps(api).replace('#/$defs/', '#/components/schemas/'))
    write('docs/api/openapi.yaml', api)
    write('docs/execution/contracts/api-inventory.json', inventory)


def write(path, data):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',newline='\n')


def main():
    build_schemas()
    build_api()
    write('docs/schemas/editorial.schema.json', {'$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': 'https://contracts.editorial.invalid/1.0.0-rc.1/editorial.schema.json', '$defs': S,
        'description': 'Select an explicit $defs target; root intentionally accepts no instance.', 'not': {}})
    write('docs/execution/contracts/baseline.json', {'contractVersion': VERSION, 'status': 'REVIEW_CANDIDATE',
        'gitCommit': None, 'gitReason': 'Repository is not initialized; T02 owns initialization.',
        'reviewedDependencies': [], 'sourceHashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / 'docs').glob('AI-Editorial-Agent-*.md'))}})
    print(f'Built {len(S)} schemas and API inventory, {VERSION}; awaiting main-agent review.')


if __name__ == '__main__':
    main()
