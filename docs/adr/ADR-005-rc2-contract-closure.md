# ADR-005：rc.2 审核问题闭环设计

状态：REVIEW_CANDIDATE，`1.0.0-rc.2`。依据 T00-T01-Review-v1.0 的 R01–R05、CR-003/006 和模型路由意见。此文更新先前 ADR 中的候选细节；不表示主 agent 已通过复审。

## R01：原文依据与创建线格式

创建使用 SRS §29.3 原样结构：`original={format,title,content}`、`rightsBasis=OWNED/AUTHORIZED/REFERENCE_ONLY/UNKNOWN`、`budget={limit,currency}`。可选 `rightsNotes/rightsEvidenceIds` 补充说明，不能替代四值状态。SRS例子的content占位需换成足长文本，完整可校验示例位于 rc2/srs-create-request.json。标题与正文分别导入 AST；1MiB校验实际UTF-8文件字节，字符上限仍对解析后的码点生效。

四种依据都能创建并内部分析。REFERENCE_ONLY/UNKNOWN不能通过QA-14或正式导出；AUTHORIZED还需可核验授权资料，OWNED需明确声明。Owner通过已有 `PATCH /articles/{id}` 的 `rightsUpdate={versionId,contentHash,basis,notes,evidenceIds}`补证，If-Match/幂等/同文章与当前版本校验不可省略。服务端生成追加的RightsSnapshot并记审计，旧声明不覆盖；有效依据绑定具体稿件内容，新版本必须重新确认或由有证据的适用范围重新关联。补证使QA/候选失效并重新检查，不自动获得导出资格。

RightsSnapshot保存在ArticleJob.originalRightsBasis的带版本历史投影及ReleaseCandidate冻结JSON中，审计仅存引用/hash；不得把声明正文复制进普通日志。T06负责写入入口，T27/T29消费，原稿保存的原始声明不可改写。

## R02：审核包唯一投影

ReleaseCandidate冻结version/manifest引用、FactSet、SkillSnapshot、PolicyRefs、selection/最终variant/license/sourceSnapshot引用和RightsSnapshot。所有依赖在冻结事务中经服务端校验存在、owner/article归属、映射关系、fresh、内容hash及对象可用性；selection引用及对应variant/license必须恰好覆盖实际使用项，事实引用来自当前版本。之后**不得为了计算历史hash查询后来工作头**。

唯一函数 `reference.release_hash_input(ReleaseCandidate) -> ReleaseHashInput` 从该冻结对象取值，再 `digest(projection)`。具名输入字段包括schemaVersion、articleId/ownerId、正文/Manifest ID+hash、factSetHash、Skill ID+rulesHash、rights ID+hash，以及按ID排序的Claim/Verification/Selection/Variant/License/SourceSnapshot/Policy引用。hash字段不自包含；忽略stale、active、ETag、展示URL和审计时间。完整Schema有效候选、投影与预期hash位于rc2/release-vector.json。

引用hash代表冻结的不可变内容，不能将内容变了但未更新hash的伪造快照送入此函数；冻结服务负责重新算hash和校验配对，投影负责唯一序列化。数据跨文章或正文版本不一致直接失败。canonical-v1的整数/定标字符串规则仅用于传输与hash；图片综合评分按0.001精度传输为字符串，不将原始加权结果静默取整，置信度沿用数据库numeric(4,3)，不降低SRS统计精度。

## R03：Analyzer两阶段引用

模型仅输出AnalysisOutput：factClaims.localKey和recommendedTitles.supportedClaimLocalKeys。先检查localKey唯一、所有标题引用存在以及span有效，再由服务端在同事务分配Claim UUID。`resolve_analysis(output, serverAllocator)`产生AnalysisResolvedOutput与claimIdMap；AnalysisResult包裹它们和服务端meta。未知/重复key在分配ID前失败；UUID分配器必须唯一，重试通过inputHash/幂等复用已分配结果。模型不提供持久化UUID。

## R04：Skill首版、发布和切换

新Skill无版本时，POST versions的baseVersionId可省略/null，服务端分配1.0.0；已有版本时必须传同Skill的baseVersionId用于复制。锁住Skill身份行后读取该Skill**包括草稿和退休版本**的最大semver并增加patch，保证永不重用。版本由服务端管理，MVP不提供用户任意指定major/minor的入口；UNIQUE(skillId,version)为最终并发防线。两个首版请求串行后，仅第一条成功，第二条返回409；同幂等请求重放返回原结果。复制来自其他Skill的ID返回422。

发布重新校验config/政策/基准用例，保持既有版本号、将内容锁定；退休只改受控状态，不影响历史快照。`PATCH /articles/{id}`新增可选skillVersionId，仅允许Owner选择其可访问的PUBLISHED版本。一个事务中检查ETag/幂等/非CANCELLED、暂停并STALE旧执行且提升fencing、创建新generation和新styleSnapshot、写失效事件及审计；旧generation保持旧Skill。ArticleArtifact响应含新工作头及执行引用。仅增加预算不会触发这条链，取消文章只能clone。纯函数测试仅演示方案，不证明真实DB原子性。

## R05：分层容量

通用ObjectRef.size最大9007199254740991字节（跨Java/JS安全整数），因此21MiB ZIP可以登记。ImageObjectRef及ImageFetchRequest仍限制20MiB、40000000解码像素；上传文本独立限制1MiB。导出不复用单图片上限；T29若因部署容量需额外限制，应设置明确的exportMaxBytes与EXPORT_SIZE_LIMIT，不能擅用20MiB。ObjectRef只是引用格式，不允许服务端据客户端申报size跳过实际流量计数。

## 模型路由配置

Owner在PUT `/settings/providers/{provider}`提交完整routes数组，每项ModelRoute含capability、model、enabled、maxOutputTokens；capability在同provider唯一。baseConfigVersion与当前版本不符返回409，更新后configVersion递增；GET返回相同routes，credentialConfigured只读，永不返回secret值。T35用此格式编辑，T09用相同格式解析，能力是否可用由真实受控探针确认，配置字段不能冒充探针成功。

每次AIRequest携带routeSnapshot/providerConfigVersion，固定实际请求model与token上限并留调用证据。修改配置只影响后续新请求；已经领取的请求保留原快照。TEXT/VISION/SEARCH/GENERATION可独立选择模型，无对应能力返回CAPABILITY_UNSUPPORTED。任何测试调用均受已确认预算、原子预占、已知价格和对账门禁。
