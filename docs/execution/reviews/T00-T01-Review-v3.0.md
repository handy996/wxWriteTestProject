# T00 / T01 第三轮主 agent 审核报告

日期：2026-10-03（Asia/Hong_Kong）  
契约版本：`1.0.0-rc.3`。  
范围：第二轮唯一剩余工程阻断R02-A，以及T00/T01必要回归和文件完整性。  
前序：[第一轮](T00-T01-Review-v1.0.md)、[第二轮](T00-T01-Review-v2.0.md)。

## 最终结论

| 审核对象 | 结论 | 适用范围 |
|---|---|---|
| T00 契约设计 | **PASS** | 关闭R02-A，保留R01–R06及其他设计整改的通过结论；批准rc.3作为后续开发的契约基线 |
| T01 工具及候选材料准备 | **PASS** | 维持第二轮工程准备子范围的结论，回归及文件指纹通过 |
| T01 完整验收任务 | **BLOCKED：待人工证据** | 双人独立标注、分歧复核及产品代表性确认未完成；没有用合成候选代替金标 |
| G0 工程契约关口 | **PASS，可进入T02** | 允许后续工程工作依据已审核合同启动；不等于人工金标冻结、MVP完成或上线批准 |

本轮审核范围内未发现新的工程阻断项，不要求继续返工已关闭问题。实际数据库事务、对象存储、Provider、Java实现、前端及最终导出仍按后续任务验收。

## R02-A关闭证据

1. `FrozenSlotAnchor`现在保存slotId、selectionId、versionId、anchorBlockId、blockHash、anchorSide、position、planHash；Candidate与ReleaseHashInput使用同一冻结数据，selection binding补入slotId。
2. 主agent复算五组向量，正文、Manifest和图片关联保持固定时，移动块、修改侧、调整顺序或planHash均改变releaseHash。锚点数组仅重排不改变语义hash。
3. `render_frozen_positions`只接受冻结Candidate与不可变正文。修改并清空当前Slot输入后，旧审核包仍还原原位置，新包对应新位置。
4. 冻结与渲染校验覆盖正文/Manifest内容hash、同文章/owner/version、实际选图集合、缺失/重复/多余绑定、块存在性及blockHash。无图空数组可用。
5. ADR-007明确唯一位置来源、placeholder不重复出图、`SLOT_ANCHOR_CHANGED`失效映射，以及ETag/fencing/工作头/事件同事务要求。历史Approval不会被修改当前Slot的动作覆盖。

| 场景 | releaseHash |
|---|---|
| 原位置 | `19dd1be39c127ac3d7b96f208e1978f70b95a5b5776aa5b69d2eb272e054c03a` |
| 移动至block-B之前 | `8dad7c4b98dc032b6ace9b7ff5c831fd8267ce9a2026f53822f4dc868654b0a9` |
| 同块改为BEFORE | `56823888696bd3a8460e1e8fd61c1aab5fb1c664d97ce2d10966ceadc205c997` |
| 交换position | `8d3f54068aa5194021680e98c68b08166755dfd2ea0298021f4b6dd27a678847` |

以上是离线冻结与位置投影证据，不宣称已运行真实审批、HTML/Markdown/ZIP导出或并发事务。

## 实际复跑结果

| 检查 | 结果 |
|---|---|
| T00 unittest | **24/24通过**：原16项及新增8项锚点测试 |
| T01 unittest | **15/15通过**：未重生成标注材料 |
| JavaScript canonical/hash校验 | 普通release向量与五组锚点向量全部匹配Python预期 |
| 主agent独立第三轮probe | 退出0；复算向量、固定历史、负向输入和文件完整性通过 |
| 当前契约manifest | **24个文件**，hash全部匹配 |
| 旧工程数据manifest | **61个文件**，hash全部匹配 |
| 代表性候选manifest | **85个文件**，hash全部匹配 |

JavaScript只独立验证给定投影的canonical序列化与SHA-256，不代表JS已经实现完整Candidate投影。原测试本身会重写rc.3样例/向量；本轮复核后契约及历史数据清单保持匹配。未执行会重生成合同/数据的完整runner。

环境：使用已有Python 3.12运行时与临时jsonschema/openapi校验依赖。T00读取临时依赖经自动审批提权；没有联网安装、自动审批拒绝或付费调用。独立probe仅用标准库与离线参考函数运行。

## 契约基线如何使用

本报告批准的是**以下指纹所对应的精确rc.3文件集合**，不改名为1.0.0，也不覆盖前序候选/交付证据：

`docs/execution/contracts/candidate-manifest.json` SHA-256：

```text
3db28b3c6ec67ed770adc1c2b7c098b9a7425a66c561d3b9fa75d5a7ccc1b743
```

配套[机器可读审核记录](T00-rc3-approval.json)记录主agent结论、24个文件指纹、证据及T01剩余边界。生成产物中保留的REVIEW_CANDIDATE/待审核文字是作者提交时状态；该审核记录和本报告是更新后的审核结论，避免为改标签而重写已审核产物并破坏指纹。

后续agent必须同时读取候选文件与审核记录。任何契约变更都要提升候选版本、重新生成产物并提交影响范围；不能静默修改当前文件后继续引用本次PASS。T02建立首次Git提交后记录对应commit，当前无可引用的HEAD提交，不编造commit。

rc.1/rc.2缺少充分位置证据的审核包不能自动回填为rc.3已批准包，必须重新冻结/QA/审批。后续真实服务必须实现ADR规定的事务/权限/失效与校验，不能把离线oracle当成已完成服务。

## T01尚待完成的内容

本轮重新读取`representative-v1/annotations/assignment.json`，仍为UNASSIGNED，reviewerA、reviewerB、adjudicator、independenceEvidence、productRepresentativenessApproval、rightsApproval均为空。候选仍未完成人工标注。

这不阻断T02工程底座，但阻断T01完整完成及正式模型质量验收。后续应由项目负责人安排两名独立自然人、分歧复核者和代表性审核，通读补漏并形成至少200个主要Claim的完整证据；不能由开发agent填写虚构身份或用已有建议标签冒充标注。

T01材料仍保留自身rc.2/数据集版本，未为锚点变更重写文章或标注。当前文本评测无需因T00增加位置字段而整批重做；将来涉及Candidate的夹具须按rc.3明确迁移。真实三次模型运行与费用验收在T08/T09和预算就绪后实施。

## 复现命令及附件

```powershell
Set-Location E:/project/codex/wxAgent
$auditPython = 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH = "$env:TEMP/wxagent-t00-validation"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
& $auditPython -m unittest discover -s tests/contracts/T00 -v
& $auditPython -m unittest discover -s tests/evaluation/T01 -v
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' tests/contracts/T00/hash-vector-js.cjs
& $auditPython docs/execution/reviews/T00-T01/reaudit_rc3.py
```

- [独立复审脚本](T00-T01/reaudit_rc3.py)
- [独立复审结果](T00-T01/reaudit-rc3-results.json)
- [机器可读通过记录](T00-rc3-approval.json)
- [ADR-007](../../adr/ADR-007-frozen-slot-anchors.md)

本次只完成审核和基线记录，未启动T02、未向其他聊天派发任务、未执行部署。
