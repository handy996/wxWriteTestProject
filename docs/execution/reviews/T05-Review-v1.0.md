# T05 首次独立审核

日期：2026-10-04（Asia/Hong_Kong）。审核对象：当前工作区。上轮报告：无。

**结论：CHANGES_REQUIRED。发现 7 项需要整改的问题，其中 6 项由独立反例在真实 PostgreSQL / HTTP 环境复现，另 1 项为任务卡明确要求的版本 diff 未交付。作者原有 31 项测试全部通过，不能覆盖这些失败边界。**

## 1. 审核对象、依据与边界

- 分支：`appmod/java-upgrade-20261003114404`；HEAD：`b115a4022375675c7cbff536b239508db8f3f4e1`；上一提交：`74c2525`。
- 比较基线：HEAD 的 T02 骨架及已批准 rc.3 输入。T05 源码、资源、测试、迁移草案及报告均为未跟踪工作区交付，没有可分别表示 T05 原始实现或整改的提交。本次是首次审核，无上轮整改。
- [before.json](T05-round1/before.json) 记录审核前 **689 个既有 Git 可见文件**的逐文件 SHA-256、分支、HEAD 和完整 Git 状态。本报告不能只用 HEAD 标识审核内容。
- T05 范围：`backend/src/main/java/com/example/editorial/editorial/skill/`、`settings/policy/`、对应测试、`resources/skills/`、`resources/prompts/`、`tests/engineering/T05/`、交付报告。其他现存修改属于 T02/T03/T04，未把这些修改归入 T05。
- 新增审核证据仅位于本报告及 [T05-round1](T05-round1/)。未修改业务实现、作者测试、作者证据、冻结文件或既有迁移；没有切换分支、提交、合并或联系其他任务。

审核依据：SRS §5–6、10、16、25–29、32–36、38，尤其 FR-02 / AC-02；执行计划 T05 任务卡、共享文件规则及审核约定；批准记录 `T00-rc3-approval.json`；OpenAPI、Schema、ports、tables、ownership-and-fk、state-guards、invalidation、canonical/hash 约定，以及 ADR-001/004/005 等适用条款。先前候选文档中的状态字样以批准记录为准。没有发现适用的 AGENTS.md。

批准文件、manifest 及原始 SRS/计划 **27/27 指纹一致**，运行时 Schema 副本也与批准 Schema 字节一致。本轮未运行任何契约生成器。

上游：T02 最新审核仍为 CHANGES_REQUIRED（完整扫描的旧指纹误报）；T03 尚无交付报告/批准记录，迁移仍为草案；T04 第三轮为 BLOCKED（真实 S3 环境）。T05 本次使用 T03 当前工作区实现及迁移，在隔离副本中进行已披露的身份接线，不将它写成共享工作区正式集成通过。T04 的 S3 阻塞不作为本任务实现缺陷。

## 2. 待修复问题

以下问题全部为本次 T05 交付中的 OPEN 项。独立用例源见 [ReviewCases.java](T05-round1/ReviewCases.java)，实际执行后的完整测试源见 [executed-tests/2-T05PostgresTest.java](T05-round1/executed-tests/2-T05PostgresTest.java)，结果见 [test-summary.json](T05-round1/test-summary.json)。

### T05-R01 — P1：内置 Prompt 输出契约无法与冻结 Schema 对齐

- **定位**：`backend/src/main/resources/prompts/writer-v1.json:4–7`；`skills/wechat-editorial-skill.json:28`（均相对于 `backend/src/main/resources/`）。关联：`prompts/editorial-reviewer.json:4–7`、`prompts/writer-revision-v2.json:7`。
- **触发与最小复现**：空库加载基线后读取 `PromptService.getPublished("Writer").outputSchema()`，取得 `#/$defs/WriterV1Output`；在批准 Schema 的 `$defs` 中解析该引用。
- **实际 / 预期**：实际引用不存在；批准类型为 `WriterOutput`（Schema 第 2607 行）。独立 `reviewWriterSchemaMustResolveAgainstApprovedDefinitions` 断言失败。即使下游提供整个冻结 `$defs`，仍无法解析这个名称。预期内置 Prompt、Skill 绑定及输出模板使用可解析且一致的冻结输出契约。
- **同组静态不一致**：Reviewer 引用 `ReviewReport`，其冻结必填项为 `meta/skillVersionId/report/items`，但提示词要求顶层 `summary/scores/items/overallDecision/inputHash`；模型输出 DTO 实为 `ReviewOutput`。Revision 模板要求 `perItemDispositions/reviewItemId` 等，而冻结 `RevisionOutput` 要求 `writer/itemDecisions`，元素为 `itemId/disposition/reason`。见 [static-checks.json](T05-round1/static-checks.json)。未将这些静态不一致夸大为已执行真实模型失败。
- **依据与影响**：违反 T05 四个编辑 Prompt 基线交付、FR-02 精确 Prompt 绑定，以及执行计划契约一致性要求。T09/T13 无法直接消费 Writer 基线，Reviewer/Revision 的模板与验证器也会要求不同结构。
- **最小修复 / 关闭条件**：在 T05 资源中使用现有已批准 DTO，统一输出名称、引用和模板字段；不要新增同义 DTO 或改冻结 Schema 掩盖问题。对四个 Prompt 逐一验证引用可解析、模型输出与服务端持久化包装分离，并用符合模板的固定输出样例通过相应冻结 Schema。补齐负例；此关闭条件不要求收费调用。

### T05-R02 — P1：运行账号能够改写已发布 Skill / Policy / Prompt 的主键

- **定位**：`tests/engineering/T05/migration-draft.sql:84–106、109–128、131–149、154–156`。
- **触发与最小复现**：通过 `editorial_runtime` 连接真实 PG，对任一已发布行执行 `UPDATE editorial.<table> SET id=<新UUID> WHERE id=<旧UUID>`，分别测试 `editorial_skill_version`、`policy_version`、`prompt_version`。审核在独立事务中执行并回滚。
- **实际 / 预期**：三表均成功更新 1 行，没有触发不可变保护。触发器仅比较部分内容字段，遗漏 `id`；同时赋予表级 UPDATE。预期已发布版本身份不可变，只允许契约规定的受控状态变化。
- **依据与影响**：违反 SRS §10/26 的不可变精确版本、ADR-004 的发布后内容锁定及受控退休、表归属权限约定。Policy/Prompt ID 存在于 Skill JSON 引用中，不会因普通 FK 自动阻止改写；原 ID 随后无法解析。Skill 当前指针也可能成为悬挂引用。这里证实的是运行数据库角色的防线缺口，**不是已经存在匿名 HTTP 改主键入口或发生生产数据破坏**。
- **证据**：`reviewPublishedPrimaryKeysMustBeImmutable` 同时记录三表更新成功；[integration.json](T05-round1/evidence/integration.json) 与测试 XML 保存实际运行结果。
- **最小修复 / 关闭条件**：按不可变行身份、内容、审计元数据明确允许变化的列；触发器或列权限应拒绝主键及其他冻结字段修改，保留草稿编辑和合法退休。使用运行账号重跑三表负例，确认按预期原因拒绝，历史精确 ID 仍可读；不得修改已正式执行的迁移来规避升级（当前此文件仍为任务草案）。

### T05-R03 — P2：服务端签发的游标不能用于下一页

- **定位**：`backend/src/main/java/com/example/editorial/editorial/skill/CursorCodec.java:19、27`；调用者 `SkillService.java:145–169、181–207`。
- **触发与最小复现**：至少两个 Skill，GET `/api/v1/skills?limit=1` 取得 `nextCursor`，保持过滤条件不变，将它原样用于下一次 GET。
- **实际 / 预期**：第一页 200；第二页 422 `INVALID_CURSOR`。编码签名的是原始 payload，解码却签名 Base64 编码后的 `parts[0]`，因此正常游标签名也不匹配。预期下一页成功且稳定、不重不漏；同一 codec 也用于版本分页。
- **依据与影响**：违反冻结 OpenAPI 的 cursor 分页和 contracts/README 的签名游标约定。超过一页的 Skill 或版本无法完整浏览。
- **证据**：`reviewCursorMustBindStatusFilter` 在先验证“相同过滤条件可继续翻页”时失败，返回具体错误码。首轮仅检查换过滤条件返回 422 会误判通过，本轮已增加正向前置断言，保留初次记录说明这个测试陷阱。
- **最小修复 / 关闭条件**：签发和验证使用相同字节序列；验证正常 Skill/版本多页遍历、篡改及跨 Owner 游标拒绝。修复签名后也须核对过滤绑定：当前 Skill 游标 payload 仅含 owner/时间/id，未包含 status；不能用“所有游标均拒绝”证明过滤隔离成立。

### T05-R04 — P2：不存在或错配的 Prompt 输出 Schema 绑定可被正式发布

- **定位**：`backend/src/main/java/com/example/editorial/editorial/skill/SkillConfigValidator.java:51–68`；作者夹具 `backend/src/test/java/com/example/editorial/editorial/skill/T05PostgresTest.java:143` 把全部 Agent 的 outputSchema 都填写为 `AnalysisOutput`。
- **触发与最小复现**：保留正确 Analyzer 的 `promptVersionId/hash/agentName`，仅将 `promptBindings[0].outputSchema` 改为 `NonexistentOutputSchema`，创建草稿，再发布。
- **实际 / 预期**：创建返回 201，发布返回 200/PUBLISHED；验证器完全不检查 `binding.outputSchema()`。预期名称必须存在并与所绑定 Prompt 的实际输出契约一致，不存在/错配应拒绝。
- **依据与影响**：违反 FR-02 精确 Prompt 绑定快照、T05 受校验 JSON 编辑及发布重验要求。合法 Prompt 的 hash 并不能证明旁边任意申报的输出类型正确；下游读取同一已发布 Skill 会得到相互矛盾的配置。
- **证据**：`reviewUnknownOutputSchemaBindingMustBeRejected` 保存 201 创建及 200 发布结果；并非仅以 DTO 文件存在推断。
- **最小修复 / 关闭条件**：从实际 Prompt / 批准 Schema 校验绑定的一致性；补不存在名称及存在但属于其他 Agent 的错配负例，创建、编辑、发布均不能持久化非法绑定。修正作者夹具，使其四个真实 Agent 使用各自正确输出契约。

### T05-R05 — P2：status=DRAFT/RETIRED 的 Skill 列表无法返回相应版本

- **定位**：`backend/src/main/java/com/example/editorial/editorial/skill/SkillService.java:138–143`；退休清空活动指针位于第 123–124 行。
- **触发与最小复现**：创建新 Skill 和首个 DRAFT 版本，再请求 GET `/api/v1/skills?status=DRAFT&limit=100`。
- **实际 / 预期**：200，但 `items=[]`，刚创建的草稿身份消失。查询把 status 条件施加在 `active_version_id` 指向的版本上；该指针只在发布时设置，退休时清空，因此正常数据下无法通过 DRAFT 或 RETIRED 筛选。预期冻结接口已接受的状态筛选能找到具有相应版本的 Skill。
- **依据与影响**：SRS §10 最小草稿/发布/停用管理及 §29.2 GET /skills 的 status 查询契约。用户不能通过草稿/停用列表找回待管理配置。DRAFT 已真实复现，RETIRED 的同因路径经静态确认，未伪称第二个 HTTP 反例已运行。
- **证据**：`reviewDraftStatusFilterMustReturnDraftSkill`，创建成功后精确查找其 ID，实际返回空列表。
- **最小修复 / 关闭条件**：依据相应版本状态进行筛选并消除身份重复，不将“活动已发布版本”当作全部状态索引。覆盖只有草稿、发布版并存草稿、已退休、分页不重复场景，保持 Owner 隔离。

### T05-R06 — P2：政策和 Prompt 读取按文本排序，升级后仍选旧版

- **定位**：`backend/src/main/java/com/example/editorial/settings/policy/PromptService.java:59`；`PolicyService.java:45`。
- **触发与最小复现**：同 Agent 分别 seed 已发布 `1.0.9`、`1.0.10` 后调用 `getPublished`；同一 COST 政策类型重复该步骤。
- **实际 / 预期**：两者均返回 `1.0.9`。`version varchar` 的 `ORDER BY version DESC` 是字典序，预期按语义版本顺序返回 `1.0.10`。
- **依据与影响**：SRS §10 的语义版本规则、T05 政策/Prompt 版本读取交付。新的读取/绑定可能继续使用较旧模板或政策；已有按 ID 固定的历史快照不受此排序直接影响。
- **证据**：`reviewPromptLatestUsesSemanticVersion` 的两个独立断言都失败，测试摘要记录 Prompt 和 Policy 实际版本。
- **最小修复 / 关闭条件**：按已验证的数字 major/minor/patch 排序或明确受控当前发布选择；验证 `1.0.9→1.0.10`、`1.9.0→1.10.0`，同时保留旧版本按 ID 读取能力。

### T05-R07 — P2：任务卡要求的版本 diff 未交付

- **定位**：交付清单 `docs/execution/reports/T05.md:20–28`；公开版本读取服务 `backend/src/main/java/com/example/editorial/editorial/skill/SkillService.java:170`；对照执行计划 `docs/AI-Editorial-Agent-Execution-Plan-v1.0.md:150`。
- **触发与最小复现**：复制同 Skill 已发布版本为草稿，修改一个规则字段，需要在发布前查看两版本差异。检查已交付服务、控制器、DTO、资源与测试。
- **实际 / 预期**：只提供身份/版本列表与整个 config，没有版本比较入口、比较结果或可复用 diff 实现/测试；报告也没有交接此项。预期提供任务卡明列的“固定快照及版本 diff”。SRS §30 同样要求发布前校验及版本 diff。
- **依据与影响**：这是已有明确交付缺口，不是新增产品功能或要求可视化编辑器。下游 Skill 管理页面无法复用本任务的版本比较能力，也没有经批准的移交记录。
- **证据**：[static-checks.json](T05-round1/static-checks.json) 对 34 个领域实现/测试文件搜索 diff/差异零命中，结合完整读取路径人工核对；不是仅凭一次关键词搜索下结论。
- **最小修复 / 关闭条件**：在本任务拥有的范围内交付可复用的两个精确版本配置比较能力、结果及测试；覆盖新增/删除/修改、相同配置、越权访问。可由已存在版本读取能力配合内部比较服务完成，**不要求私自新增冻结 HTTP 端点**。如要变更归属，需提供明确批准的调整，不能由交付报告自行取消。

## 3. 历轮问题状态

首次审核，没有 T05 上轮问题或关闭项。本轮 T05-R01–R07 均为 OPEN，不继承或重编号 T02/T04 的问题。

## 4. 实际运行及证据

| 验证 | 结果 | 证据 |
|---|---|---|
| 审核对象固定 | 689 个既有文件 SHA-256、Git 状态、分支与 HEAD | before.json |
| 正式批准指纹检查 | 27/27，退出 0；Schema 运行副本字节一致 | checks.json、static-checks.json |
| 隔离副本 clean 编译及相关测试 | **37 项：31 通过、6 失败、0 error、0 skipped；Maven / runner 退出 1** | evidence/integration.json、test-results/、test-summary.json |
| 作者原有离线测试 | 14/14 通过 | 同上，4 个测试类 |
| 作者原有真实 PG / HTTP 用例 | 17/17 通过 | 同上，原有 17 个方法 |
| 独立新增反例 | 6/6 触发预期产品断言失败，未把非零退出泛称安全拒绝 | ReviewCases.java、实际执行源、XML |
| 空库迁移 | 真 PG 17.11 上执行 T02 bootstrap/callback、T03 V1 草案、T05 V2 草案，四张领域表和基线加载成功 | evidence/integration.json |
| 全量 CI Gitleaks | 8.30.1，退出 1；仅旧 T02 r01-integrity.json 的 6 项指纹误报；T05/本轮证据无新增命中 | checks.json、gitleaks-findings.json |
| Git 空白检查 | 退出 0 | checks.json |
| 清理 | 3 个本轮临时目录精确清理；各 PG cluster status=3（无运行服务器），两次宿主测试端口可重新绑定 | cleanup.json |

使用工具：Temurin JDK `21.0.12.1+1`、Maven `3.9.11`、PostgreSQL `17.11`、本轮 Python `3.12.14`、Git `2.53.0.windows.3`、Gitleaks `8.30.1`。与作者不同的 Python/Git 版本明确记录，未照抄作者旧工具信息。

主要复现命令（从项目根目录执行）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T05-round1/run_review.py
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T05-round1/run_checks.py
```

runner 复用经阅读的作者编排，但将输出、工作目录、测试源注入全部重定向至审核目录；全新复制 backend（不复制 target），仅在副本中移除骨架临时拒绝链、添加 T03 身份配置、安装迁移草案，并追加独立反例。实际 Maven 参数为 `-o -B -ntp ... clean test -Dtest=T05PostgresTest,SemVerTest,HashingTest,JsonSchemaSkillConfigTest,BaselineResourcesTest`，逐命令参数、退出码、关键输出、版本及停止记录全部保存。

初次 sandbox 启动 PG 因 restricted token 失败，证据为 `evidence/sandbox-attempt.json`；按权限流程在宿主隔离目录重试后启动成功，未认定宿主未安装或实现故障。初次反例运行和后续完善的运行分别保存于 `initial-integration.json`、`integration.json`，旧审核运行证据没有覆盖。初次过滤游标负例之所以“通过”，是所有签发游标本来都会失败；后续增加正常翻页前置断言，揭示 R03，不能把首次通过当作过滤绑定成立。

独立数据库修改使用随机 ID、隔离库和运行账号，主键反例均主动 rollback；两个宿主运行最终 stop 退出 0。没有收费 Provider 调用。

## 5. 未验证项、限制与范围判定

1. **上一个正式集成版本升级仍未验证**：T03 未批准/未合入迁移，T05 全局 Flyway 版本号及后置跨域 FK 也未由主 agent 安装。空库中先执行 V1、再 V2 不等于从上一正式应用版本保留数据升级。本轮不将该集成前置条件计为 T05 私自漏建其他域表或要求 T05 改共享迁移。正式集成时须补升级、历史行及 migration history 保持验证。
2. **文章换 Skill、新 generation、失效传播未实测**：T06/T11 尚未装配，本轮只测 T05 精确快照和发布/退休事件收集。`ConfigChangeSink.InMemory` 是进程内测试/接线替身，不能证明提交后可靠投递、回滚隔离或进程崩溃恢复。报告 §9 的“无测试替身”与这一事实不一致，其 §8 将发布/退休事件直接描述为新 generation 的交接也不能替代 ADR-005 的“Owner 主动更换文章 Skill”事务。集成时须保持 AC-02：单纯发布新 Skill 不得改动旧任务。
3. **StyleSnapshot 边界**：任务卡写“生成 StyleSnapshot”，冻结 T05 端口实际返回 SkillSnapshot/PolicySnapshot，ArticleJob 的 styleSnapshot 归 T06 聚合。当前已有固定输入投影，未额外发明一个未冻结 DTO 作为否决门槛；T06 组装与主动切换的真实事务仍须验证。
4. **历史读取与新选择必须分开**：现有 read 允许 RETIRED 版本用于历史快照；新文章/主动切换只能选 PUBLISHED，未来 T06 必须检查返回状态。本轮不因允许历史读取直接判错误。
5. **PolicySnapshot.rules 的对象引用适配尚未集成**：当前规则权威为 DB JSONB，返回 `policy-rules/<type>/<version>` 的 ObjectRef；未实测把该 key 交给 T04 对象存储。报告的数据库读取说明不等于真实对象下载成功，需在消费方接线时确认；未因此要求 T05 建文章级对象表。
6. **硬政策与 Prompt Injection 范围**：本轮证实未知绕过字段、错误引用/阈值被作者用例拒绝，内置硬规则存在；没有真实模型执行、工具调用或正式 QA/批准/导出流程，因此不能把结构校验和提示词文字当作 AC-27 全链路通过。后续模块未实现本身不是 T05 缺陷。
7. **CI 限制**：完整 Gitleaks 仍失败，原因是已有 T02 指纹误报，未发现真实凭证泄漏，未重复计入 T05 问题。没有改变依赖清单，未重跑无关前端、远程依赖漏洞服务、Docker/S3、压力或人工质量验收；本轮不是全 CI / G1 / 生产 PASS。
8. **审核测试质量**：作者部分反例仅断言 HTTP 状态或任意 DataAccessException；没有覆盖游标往返、Prompt 输出类型解析/匹配、主键不可变、数字版本排序。本轮反例按具体实际行为断言。没有用 mock 或静态配置冒充真实 PostgreSQL/HTTP；也没有将进程内事件收集称为可靠消息集成。

## 6. 下轮复审条件与收尾

- 沿用 T05-R01–R07 编号逐项提供实现和针对性测试证据，保留当前失败证据。优先关闭不可解析 Prompt 基线、已发布 ID 可改及正常分页失败。
- 以本轮固定指纹/实际执行源证明旧版可复现，在新的工作区指纹下证明整改版不再复现；R01/R04 一起验证四个真实绑定与输出 Schema，R03 必须同时有正常和错误游标测试。
- 明确版本 diff 的实际交付入口；更新交付报告，区分固定快照单测、进程内替身与 T06/T11 未完成集成，不自行宣布全链路通过。
- 正式集成验收另需 T03 批准基线、全局迁移分配、必要后置 FK 和上一正式版本升级环境。不能以未完成集成为由跳过本报告已有可行动缺陷。

收尾检查见 [after.json](T05-round1/after.json) 与 [cleanup.json](T05-round1/cleanup.json)：既有交付文件指纹和冻结文件保持不变，HEAD/分支不变；临时数据库已停止，仅清理本轮创建的目录。本结论只覆盖 T05 当前工作区及上述实际验证环境。
