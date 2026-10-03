# T00 / T01 第二轮主 agent 审核报告

日期：2026-10-02（Asia/Hong_Kong）  
审查版本：`1.0.0-rc.2`，对应代表性候选 `representative-v1.0.0-rc.1`。  
上一轮：[T00-T01-Review-v1.0.md](T00-T01-Review-v1.0.md)。  
范围：上一轮 R01–R06、CR-003/006、模型路由及代表性材料整改；针对审核包冻结链补充交叉验证。未进行应用/DB/Provider 集成，也未进行人工金标评审。

## 结论

| 审核对象 | 本轮结论 | 说明 |
|---|---|---|
| T00 契约设计 | **CHANGES_REQUIRED** | 原六项具体反例均已纠正，但 R02 的完整冻结范围尚缺 Slot 锚点；仅该工程阻断项需继续返工 |
| T01 工具及候选材料准备 | **PASS（限工程准备子范围）** | R06修复有效；旧数据保留、新候选独立版本、清单与空白标注证据一致 |
| T01 完整任务验收 | **BLOCKED（人工验收证据待补）** | 双人独立标注、分歧复核及产品代表性确认均未完成；不是要求开发 agent 伪造这些证据 |
| G0 契约冻结 | **暂不放行** | T00仍有一项影响历史审批/导出的输入冻结缺口；不冻结rc.2 |

T01的工程准备PASS不表示200条候选已成为人工金标，不表示真实模型质量或全链路业务已验收。无需等待人工标注才能修复T00剩余项。已经关闭的问题不要求重新设计，仅在下一候选保持回归通过。

## 本轮实测

| 验证 | 结果 |
|---|---|
| T00原有及整改测试 | **16/16通过，退出0** |
| T01原有及整改测试 | **15/15通过，退出0** |
| JavaScript canonical-v1向量 | 退出0，与Python生成的预期hash一致 |
| 主agent独立rc.2复审脚本 | 退出0；六项修复后的预期满足，并记录剩余锚点契约缺口 |
| 当前契约manifest | **23个文件hash匹配** |
| 旧工程数据manifest | **61个文件hash匹配**，未因本轮整改覆盖 |
| 新代表性候选manifest | **85个文件hash匹配** |

JavaScript验证的是canonical序列化和给定投影的hash一致性，不是完整JavaScript Candidate投影实现；Java与实际服务实现仍归后续任务。本轮不把尚未进行的生产集成当作T00/T01工具缺陷。

未运行会重生成全部产物的verify.py，未改原报告、生成器或契约。原测试自身重写了rc.2结构样例/向量，最终清单仍匹配。本轮仅新增复审报告、脚本和结果。

## 上轮问题逐项关闭情况

| 问题 | 实际复核 | 判定 |
|---|---|---|
| R01 原文使用依据 | 四种SRS状态均能通过创建契约；LICENSED/PERMISSION被拒。title/content/budget回到SRS结构；补证与当前稿RightsSnapshot已定义 | **关闭**。权利证据真实性仍由领域服务/人工确认 |
| R02 Candidate/hash不互通 | Schema有效Candidate可以经release_hash_input生成Schema有效ReleaseHashInput并得到预期hash | **原报错关闭，冻结范围待补**，见下一节 |
| R03 Analyzer localKey/UUID | 两条新Claim、五个标题可先用localKey，再由服务端分配并形成有效持久化输出；未知/重复key有拒绝测试 | **关闭** |
| R04 Skill首版/切换 | baseVersionId可省略/null，首版及同Skill复制规则明确；PATCH接受skillVersionId，新generation、fencing与semver并发规则已写明 | **关闭**。事务并发正确性在T05/T06/T10集成验证 |
| R05 通用对象误限20MB | 21MiB ZIP对象通过，21MiB单图片对象拒绝；文本/图片字节与像素约束分离 | **关闭** |
| R06 质量门槛漏检 | 编辑五维与Analyzer评分分离；1.6分、3.99分、任一篇论点反转、Analyzer仅17/20达4分均不满足门槛；缺证据有拒绝测试 | **关闭** |

独立复审还确认了全4分、完整事实预测的合成基线能通过指标阈值，避免修复只是把所有结果一律拒绝。`acceptancePassed`依然不会被工具自动设为true。

## 唯一剩余工程阻断：R02-A · P1 · 配图位置未进入冻结审核包

位置：

- `docs/execution/contracts/build_contract.py:208–219`：Manifest、FrozenSelectionBinding、ReleaseCandidate、ReleaseHashInput。
- `docs/execution/contracts/reference.py:50`：release_hash_input。
- ImageSlot/PatchSlotRequest允许独立修改anchorBlockId/anchorSide；这些输入没有出现在上述冻结类型中。

**需求依据：** SRS第16.2节的releaseHash明确包含`slotAnchors`；第17节图片位置依赖稳定正文块；第23节QA-11核对锚点，第24节和FR-18要求预览/审批/历史导出使用同一固定快照。

**现状：**

1. ImageSlot保存`anchorBlockId / anchorSide / position / planHash`，且PATCH接口允许只提交anchor。
2. ManifestItem保存slotId、displayOrder等，但不保存锚点值或不可变Slot快照hash；图片列表顺序无法说明图片是在正文哪一个块之前或之后。
3. FrozenSelectionBinding只有selectionId/assetId/variantId/licenseMetadataId；ReleaseCandidate和ReleaseHashInput也没有Slot/plan快照或锚点字段。
4. AST虽支持imagePlaceholder，但契约未要求所有已选Slot都必须放入AST，也未规定修改Slot锚点必须生成新ArticleVersion并更新contentHash。因而不能仅凭“AST可以存图片”推定versionHash已覆盖所有图片位置。

**独立验证：** anchor-only PatchSlotRequest合法；给Candidate添加显式slotAnchors则被additionalProperties规则拒绝；冻结投影、ManifestItem和selection binding的字段清单均无锚点。完整结果见附件`remainingFindings.R02_ANCHOR_SNAPSHOT`。

**影响：** T27/T28/T29不能只从冻结审核包确定历史稿的真实图片位置；若导出实现回读后来可变的ImageSlot，就可能使历史批准稿的版面位置随工作头变化；若不回读，又缺少还原位置的数据。当前没有业务实现，本报告确认的是契约输入缺失，**不声称已复现生产错批或错导出**。

**最小返工方向（二选一，明确一个权威来源）：**

- 建议在Candidate中冻结每个实际使用Slot的`slotId、selectionId、versionId、anchorBlockId、anchorSide、position`及必要内容hash/计划版本，并将规范化锚点输入纳入ReleaseHashInput。冻结时检查锚点属于该正文版本、覆盖全部已选图且无多余/重复绑定。历史预览、QA和导出只读这份冻结位置。
- 或者明确AST为图片位置唯一权威，强制每个已选Slot都有对应placeholder；任何锚点调整都创建新ArticleVersion并更新contentHash；Slot接口与AST版本事务一致。若采用此方案，需要相应状态/版本/接口契约和测试，不能仅补一句说明。

同时明确Slot锚点改变触发当前QA/Candidate/审批失效的事件或服务调用。可以扩展现有事件，但需把映射写进契约，不要求为了命名再新增不必要架构。

**复审退出标准：**

1. 同一正文、同一图片与图注，仅把图从block-A之后移动到block-B之前，生成的新审核包hash不同。
2. 只改anchorSide或图片排序，同样受保护；若方案采用AST，必须验证正文版本/hash确实变化。
3. 已批准历史快照在工作头改锚点后，仍能从自身数据还原原位置，不读取当前ImageSlot。
4. 不存在的block、跨正文版本锚点、缺Slot/重复绑定在冻结前拒绝。
5. Python向量和JS canonical验证更新，原31项测试及上轮修复回归继续通过。无需此阶段提前实现完整导出服务，可用冻结DTO与独立渲染位置投影验证。

## 其他待定契约项的本轮处理

- **CR-003删除journal：设计方向通过。** ADR-006已明确独立恢复域、202之前登记REQUESTED、完成再记PURGE_COMPLETED、覆盖所有可恢复旧备份、恢复追最新head与拒绝开放条件。相比只依赖随备份回滚的数据库，设计缺口已补齐。签名、权限、日志覆盖下界、并发head追赶及真实恢复测试交T04/T37；OQ-16生产保留安排继续待业务确认，不据此阻止开发合同整改。
- **CR-006 Skill生命周期：通过本轮设计复核。** 首版、同Skill复制、版本分配、主动切换及旧运行快照均有具体方案。
- **模型路由入口：通过本轮设计复核。** Provider GET/PUT使用同一ModelRoute，baseConfigVersion防并发覆盖，AIRequest保存routeSnapshot；配置不能代替真实能力探针。
- **CR-001/004/005：维持上一轮接受的方向。** 本轮无要求额外扩展范围；真实删除、图片文字、安全权限和SQL约束仍按各实现任务验证。

## T01准备子范围为何可通过

新数据与旧数据分目录、分版本，有独立manifest和标注assignment。测试验证20篇、五类各4篇、200候选的数量/定位/文件hash；本轮人工阅读抽查了科学试验、政策过渡和叙事出处样例，能看到不同的限制条件、同源资料与冲突场景，比第一轮仅换登记册主题有实质改进。

这些材料仍是合成文本，类别内包含共用解释段落；本审核只认可它们是可供下一步标注的候选和工程测试材料。`assignment.json`仍为UNASSIGNED，A/B、adjudicator、independenceEvidence、productRepresentativenessApproval、rightsApproval都为空。该状态如实保留，不能将工程准备PASS升级为完整T01 PASS。

完整T01的下一步是由项目负责人安排两名独立自然人、分歧复核者及产品代表性审核，通读补漏并形成至少200条主要Claim的双人证据。不要求作者为了“通过”伪填人员，也不要求此刻提前消耗真实模型预算。T00锚点修订后只检查T01实际受影响的契约/fixture；不要求无关文章全部重写。

## 下一轮范围

仅交T00负责人修复R02-A，升级候选版本、更新生成器/产物/向量/manifest并提交报告。主agent复核该项和必要回归；不要重开已经关闭的五项缺陷。T01继续人工待办，开发工具暂不要求额外返工。

本轮不冻结rc.2、不启动其他研发任务、不向其他聊天派发消息。以上状态由本复审报告记录；保留上一轮报告作为历史，未覆盖作者交付证据。

## 复现入口

```powershell
Set-Location E:/project/codex/wxAgent
$auditPython = 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH = "$env:TEMP/wxagent-t00-validation"
$env:PYTHONDONTWRITEBYTECODE = '1'
& $auditPython -m unittest discover -s tests/contracts/T00 -v
& $auditPython -m unittest discover -s tests/evaluation/T01 -v
& $auditPython docs/execution/reviews/T00-T01/reaudit_rc2.py
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' tests/contracts/T00/hash-vector-js.cjs
```

T00和独立probe需读取既有临时校验依赖，本轮经自动审批使用相应提权环境；未联网、未安装新依赖、无付费调用。所有命令各自退出0，不以组合命令最后的退出码代替前面结果。

- [主agent独立复审脚本](T00-T01/reaudit_rc2.py)
- [独立复审原始结果](T00-T01/reaudit-rc2-results.json)
- [T00 rc.2交付报告](../reports/T00.md)
- [T01 rc.2交付报告](../reports/T01.md)
