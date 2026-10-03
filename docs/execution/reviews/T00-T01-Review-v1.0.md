# T00 / T01 主 agent 审核报告

审核日期：2026-10-02（Asia/Hong_Kong）  
审核对象：`1.0.0-rc.1` 候选，非已冻结契约；目录无 Git commit。  
依据：SRS v1.0、Execution Plan v1.0、T00/T01 交付报告与实际文件。  
审核方式：静态对照、复跑原有测试、独立反例验证、候选文件 hash 复核。未调用真实 Provider，未执行应用或数据库集成。

## 审核结论

| 任务 | 结论 | 可保留成果 | 未通过原因 |
|---|---|---|---|
| T00 契约设计 | **CHANGES_REQUIRED** | API 路径清单、38 表归属、ADR、Schema/状态/依赖候选、离线校验框架 | R01–R05 影响实际可实现性；变更申请仍有未落定设计 |
| T01 验收集准备 | **CHANGES_REQUIRED** | 合成回归夹具、空白双人标注表、文件清单、指标计算基础 | R06 质量门槛计算错误；代表性验收集和双人金标尚未完成 |

**G0 不通过，不冻结该候选，也不将 T00/T01 标为最终完成。** 人工标注属于外部待办，状态为待人员与证据；不能用它掩盖当前可修复的软件问题。无需等待真人标注即可先修 R01–R06。T02 的环境调查可以基于 SRS 默认技术栈准备，但不能据此宣称已通过 G0 或冻结业务 DTO。

## 已复核证据

- T00：`unittest discover -s tests/contracts/T00 -v`，**10/10 通过，退出 0**。
- T01：`unittest discover -s tests/evaluation/T01 -v`，**11/11 通过，退出 0**。
- 独立反例：`docs/execution/reviews/T00-T01/review_probe.py`，退出 0，确认 R01–R06；退出 0 仅表示审核脚本运行成功。
- 候选契约清单 **21 个文件**、数据清单 **61 个文件**的 SHA-256 全部匹配。
- API 覆盖测试确认 SRS 第 29.2 节 83 个路径/方法，加 2 个删除候选接口，共 85 个 operation。此结果只证明路径覆盖，不证明请求/响应业务语义完整。
- 原测试为每个 Schema 构造正例并加一个额外字段作为反例；不足以发现字段之间、调用之间、Schema 与 hash 函数之间的矛盾。

本次未运行会重生成合同和夹具的 `verify.py`。T00 原测试会重写结构样例/hash 向量，复核后其字节 hash 未改变；本次未修改被审查生成器、契约或原交付报告，只新增审核材料。

环境：Python `C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。T00 初次沙箱测试因临时依赖读取限制而导入失败；随后经自动审批提升权限读取已有依赖，测试通过。未安装新依赖、未发生自动审批拒绝。

## 需修复的问题

### R01 · P1 · 创建文章丢失需求规定的原文使用依据

- 位置：[build_contract.py:319](../contracts/build_contract.py#L319)，`CreateArticleRequest.rightsBasis`。
- 依据：SRS 第 9 节 FR-01 明确 `OWNED / AUTHORIZED / REFERENCE_ONLY / UNKNOWN`；后两者可内部分析，正式导出需补依据。第 29.3 节给出创建请求原文标题/内容及预算对象。
- 实际：契约改为 `OWNED / LICENSED / PERMISSION`，将 `AUTHORIZED`、`REFERENCE_ONLY`、`UNKNOWN` 全部结构拒绝。没有已批准变更允许收窄这条业务路径。
- 复现：独立 probe 的 `R01_original_rights` 显示上述三个 SRS 枚举均为 false，而两个新枚举为 true。
- 影响：T06/T30 按生成 client 实现后，合法的“仅参考/使用依据未知，先内部分析”场景无法创建；正式导出前补依据的状态链失去入口。
- 返工：恢复四种 SRS 状态；需要更细授权资料时作为附加字段，不能替换状态。补清创建时原文 title/content 和 budget 的线格式映射，任何改名/结构变动登记变更。内部分析与正式导出资格分别校验。
- 复审：四种依据都可按规则创建；后两种不能正式导出，补充分配给当前稿的有效依据后可重做 QA；完整 SRS 示例或明确迁移后的等价示例可验证。

### R02 · P1 · ReleaseCandidate 与 releaseHash 计算输入没有统一契约

- 位置：[build_contract.py:196](../contracts/build_contract.py#L196)、[reference.py:49](../contracts/reference.py#L49)。
- 依据：SRS 第 16.2、23–24 节；执行计划要求跨 agent 统一 canonical hash 和冻结审核包输入。
- 实际：`ReleaseCandidate` 使用 `meta.schemaVersion`、嵌套 `factSet`、`skillSnapshot`、`policyRefs`；hash 函数要求顶层 `schemaVersion/factSetHash/skillRulesHash`，并要求 `variants/licenses/verifications/policies` 等不同字段。没有定义该 hash 投影的具名 Schema、从 Candidate 构造它的适配器或完整固定输入例子。
- 复现：合法 Candidate 交给参考函数得到 `KeyError: 'schemaVersion'`；hash-vectors 中的 candidate 反而不符合 `ReleaseCandidate` Schema。已有测试分别测试两个世界，未验证互通。
- 影响：T27、T28、T29 及前端无法据同一公开契约复算 hash，集成时会各自增加字段和查询；冻结快照与后续动态查询的边界也不清楚。
- 返工：选择统一 Candidate 输入，或明确新增 `ReleaseHashInput` 及唯一映射。映射须基于已冻结且同文章的选择、最终变体、许可、事实/证据、Skill/政策；历史 hash 不得读取后来变动的工作头。
- 复审：一份 Schema 有效的完整审核包可经明确投影计算预期 hash；每类受保护输入单独改变都会改 hash；仅 active/stale/审计展示变化不改历史 hash；Java/JS 使用同一向量即可实现。

### R03 · P1 · Analyzer 的新 Claim 无法被推荐标题引用

- 位置：[build_contract.py:105](../contracts/build_contract.py#L105)、[build_contract.py:125](../contracts/build_contract.py#L125)。
- 依据：SRS 第 11 节，Claim ID 由服务端生成；建议标题需关联支持 Claim；ADR-002 规定提取时使用 `ClaimDraft.localKey`。
- 实际：同一次 `AnalysisOutput.factClaims` 仅输出 localKey，`recommendedTitles.supportedClaimIds` 却只接受 UUID。初次分析尚无服务端分配的事实 ID，也没有 localKey→UUID 的输出引用契约。
- 复现：`claim-local-1` 是合法 ClaimDraft.localKey，但推荐标题引用此 key 时 Schema 拒绝。
- 影响：Analyzer 只能填空引用、编造 UUID 或依靠未定义映射，无法同时满足有效关联和服务端分配身份的要求。
- 返工：区分 Agent 输出与持久化结果：Agent 标题引用 localKey，服务端统一分配 UUID 并解析/校验引用后形成 AnalysisResult；或者提供同等明确的两阶段契约。禁止让模型自造持久化 ID。
- 复审：含两个新 Claim 和五个引用标题的一次响应可完整入库映射；未知/重复 localKey 拒绝；不要求模型预知 UUID。

### R04 · P1 · Skill 创建首版与主动切换均缺可执行入口

- 位置：[build_contract.py:323](../contracts/build_contract.py#L323)、[build_contract.py:401](../contracts/build_contract.py#L401)；作者已登记 CR-T00-006。
- 依据：SRS 第 10 节多 Skill 身份/草稿/发布与主动更换新运行，AC-02。
- 实际：创建 Skill 身份返回的 activeVersionId 可空，但创建版本强制 baseVersionId 是 UUID；无法从“无版本”创建首版。文章 PATCH 又不接受 skillVersionId，没有其他切换命令。
- 复现：首版请求省略 baseVersionId 被拒绝；仅含 skillVersionId 的文章 PATCH 也被拒绝。
- 影响：T05/T06/T35 即使完整实现所有已列路由，仍不能完成这两条 MVP 场景。登记缺口是正确做法，但未闭环的契约不能冻结。
- 返工方向：首次创建版本允许 baseVersionId=null/省略并校验该 Skill 尚无版本；后续复制基于同 Skill 的已有版本。为主动切换补明确请求字段/命令，保持 ETag、幂等、暂停/失效旧执行、创建新 generation。明确 semver 分配与并发唯一规则。
- 复审：新 Skill→首版草稿→发布→新建文章→换版本产生新运行；旧运行仍引用原快照；不可跨 Skill 复制错归属或修改已发布内容。

### R05 · P1 · 单图片 20MB 限制被扩散到所有存储对象，阻断正常导出包

- 位置：[build_contract.py:75](../contracts/build_contract.py#L75)，及 `ExportArtifact.objectRef`。
- 依据：SRS NFR-10 限制每张图片≤20MB；FR-18 要求导出多图片及清单 ZIP，没有把整个 ZIP 限制到20MB。
- 实际：共用 `ObjectRef.size.maximum=20971520`，该类型也用于正式导出、AI payload、政策和来源对象。
- 复现：一个 21MiB、MIME 为 `application/zip` 的对象引用被 Schema 拒绝。两张各自符合图片上限的图片就可能生成超过该值的 ZIP。
- 影响：T04/T29 按公共类型实现后，合法多图审核包可能无法登记或下载；前端生成类型也无法完整表达结果。
- 返工：将图片输入大小限制放在图片下载/解码请求和校验中；通用 ObjectRef 使用适合大对象的安全整数边界。若需要导出包上限，作为单独可配置规则与明确错误，不沿用单张图片阈值。
- 复审：>20MB 的合法 ZIP 对象引用通过，单图片超过上限依旧拒绝；正文上传1MB、解码40MP各自在正确边界生效。

### R06 · P1 · 编辑质量均分远低于要求，评测器仍返回所有阈值满足

- 位置：[evaluate.py:18](../../evaluation/evaluate.py#L18)、[evaluate.py:74](../../evaluation/evaluate.py#L74)、[evaluate.py:104](../../evaluation/evaluate.py#L104)。
- 依据：SRS AC-03 的 Analyzer 核心论点评分≥4/5 占比≥90%；第 38 节末尾另要求编辑质量平均≥4且任一篇不能反转关键论点，量表包含信息密度。
- 实际：评测器仅将 `THESIS>=4` 的比例计入质量门禁；其它维度均值只展示、不参与判定。没有关键论点反转字段/门禁，也没有单独信息密度维度；同一编辑 THESIS 分数无法替代 Analyzer 的独立评分证据。
- 复现：三次完整合成运行，事实全对、THESIS=4，其余六项均=1，均分 **1.428571/5**，结果仍为 `allRunThresholdsMet=true`。`acceptancePassed` 仍 false，故本发现是阈值计算错误，不宣称工具已经自动批准产品。
- 影响：T01/T36 的质量报告会显示错误达标，主 agent 若依赖汇总字段会遗漏明显失败样本。
- 返工：独立定义 Analyzer 与编辑质量量表；覆盖 SRS 五个编辑维度，包括信息密度；明确汇总方式并实施平均≥4与逐篇论点不反转的硬判定，缺失证据必须阻断。额外维度可保留，但不能替代 SRS 门槛。
- 复审：平均低于4、任一篇关键论点反转、缺信息密度或 Analyzer 评分都不能返回全阈值满足；在边界4.0及90%上有明确正反例；报告分列事实、分析、编辑、成本各自结果。

## T01 的验收集状态

目前是 **20 篇原创合成回归文章 + 200 条 UNREVIEWED 候选**，不是已完成人工金标。双人标注与分歧复核表都是空白；作者如实披露了这些限制，本审核不将其视为伪造。

但五类文章共享生成器同一组十段编辑说明与同构登记册命题，主要变化是主题、数字和标题。文件类别标签不能证明已覆盖科学因果、历史来源、现实政策时效、品牌自述与叙事的代表性。因此：

1. 可保留为离线工程回归集；不要删除现有夹具或改称真人金标。
2. 在相同五类各四篇的要求下另行完善代表性验收候选，取得必要使用依据，冻结独立 datasetVersion/hash。合成文章也可以用，但必须实际覆盖类别差异和目标任务，不能只换标签。
3. 由用户/项目负责人指定两名独立人工标注者及分歧复核责任人；主 agent 不能伪填人员与标注证据。
4. 真实模型三次运行是后续 T08/T09 就绪后的质量验证，**本次不因未提前做付费联调而额外判错**；当前须完成的是工具门槛修复、可标注代表性材料及清晰待办。

## 契约变更申请处理意见

这里给出本次工程审核方向，不冒充业务/版权审批，也不把草案文件状态改为冻结。

| 申请 | 主 agent 审核意见 | 后续动作 |
|---|---|---|
| CR-T00-001 删除接口 | 接受补齐接口的方向，与SRS明确删除一致 | 保留 impactHash/ETag/所有权/异步；与003一起闭环持久化和恢复 |
| CR-T00-002 canonical/定标 | 可以使用有版本的确定性序列化，但暂不冻结 | 先修R02，补统一线格式及跨语言向量；不得以hash约束改变业务评分精度却无说明 |
| CR-T00-003 tombstone | 当前设计不充分，需补充 | 明确删除记录保存位置/保留期/读取权限，以及恢复旧备份后如何取得备份之后的删除记录；不能只依赖一起回滚的旧数据库快照 |
| CR-T00-004 图片文字 | 接受提取状态与人工回退方向 | 保留最终variant/selection绑定、NO_TEXT不可代替失败，补入统一契约验收 |
| CR-T00-005 不可变权限/FK | 接受区分可变列、配置草稿与发布内容的方向 | 完整SQL与真实DB验证按T02/T06/T24实施，本次不要求提前搭业务库 |
| CR-T00-006 Skill生命周期 | 当前阻断，按R04返工 | 首版/切换/版本号并发规则必须落为可执行合同，不能只留申请 |
| CR-T01-001 人工与质量数据 | 保留待办，不代替确认 | 指定自然人、完成独立标注与分歧证据；真实运行费用另按T08/T09约束 |

冻结前还需补一次配置入口核对：SRS 第30节要求模型路由配置，但当前 `SetProviderRequest`/`ProviderConfig` 只有 enabled、limits、secretRef/能力等，没有可读写的模型路由。T00须定义 UI 可配置范围及路由字段，或明确经评审的部署配置方案与前端只读投影；不得让 T09/T35 各自定义不同格式。

## 返工派发与复审顺序

1. **T00 原负责人**：修R01–R05；闭环CR-003/006及模型路由入口；修生成源后重生 OpenAPI/Schema/夹具，不只手改产物。增加跨Schema/业务链反例，将候选升为 `rc.2`，提交新的变更及hash清单。
2. **T01 原负责人**：修R06和评分文档/输入协议，补充反例；保留旧合成集，提交代表性材料补齐计划和明确的人工待办。T00变化后核对依赖的fixture，不静默覆盖已开始人工标注的数据。
3. **主 agent**：复跑原测试与本报告独立反例，逐项确认预期由错误变为正确；检查新hash、合同互通和未决项。整改未完成前结论保持 `CHANGES_REQUIRED`。
4. 本次只形成审核及可派发返工说明，未向其他聊天发送消息、未代改被审查实现、未开展T02或生产上线。

## 可复现命令与附件

```powershell
Set-Location E:/project/codex/wxAgent
$reviewPython = 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH = "$env:TEMP/wxagent-t00-validation"
$env:PYTHONDONTWRITEBYTECODE = '1'
& $reviewPython -m unittest discover -s tests/contracts/T00 -v
& $reviewPython -m unittest discover -s tests/evaluation/T01 -v
& $reviewPython docs/execution/reviews/T00-T01/review_probe.py
```

在Codex沙箱中若临时依赖不可读，前述T00及probe需要相同的只读依赖提权环境；不代表测试本身业务失败。

- [独立审核脚本](T00-T01/review_probe.py)
- [独立反例原始结果](T00-T01/review-probe-results.json)
- [T00原交付报告](../reports/T00.md)
- [T01原交付报告](../reports/T01.md)

最终结论：**保留已有有效成果，T00/T01退回定向修改；当前不冻结、不放行G0。**
