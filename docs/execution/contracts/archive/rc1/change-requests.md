# 契约变更申请（交主 agent）

所有项状态 SUBMITTED，提交人 T00/T01，审核人未指派，审核证据无。候选内容可以 mock 自测，不能作为已审核依赖。

| 编号 | 缺口与候选决定 | 影响/验证 | 审核前限制 |
|---|---|---|---|
| CR-T00-001 | SRS33要求明确删除，29.2无接口；补 deletion-impact GET 和 deletion POST，impactHash/ETag/异步 | T04/T06/T10/T37；过期预览、hold、重复请求、恢复删除标记 | 仅契约，无生产路由 |
| CR-T00-002 | hash未定义跨语言数值序列化；canonical-v1禁止浮点、金额6位/置信度3位字符串；AST list纯文本和subtitle锚点明确 | 所有 hash 消费者；Unicode/顺序/定标正反例 | 主 agent 确認线格式后再生成客户端 |
| CR-T00-003 | 删除状态/tombstone持久化位置缺失；建议现有workflow snapshot及最小审计元数据，不增加第39表 | T06/T10/T37；删除后恢复备份重放 | 保留期/hold责任人及实现仍待定 |
| CR-T00-004 | 图中文字提取缺契约；新增 ImageTextExtraction，绑定最终variant，无法读取强制待办 | T18/T23/T27；不得由NO_TEXT掩盖失败 | 无真实视觉/OCR集成 |
| CR-T00-005 | 配置发布后不可变与selection.active可变冲突；列级权限+状态触发器；article创建延迟完整性检查 | T02/T05/T06/T24；SQL草案、待空库和并发验证 | 不修改既有迁移 |
| CR-T00-006 | 主动更换Skill有需求但29.2 PATCH无skillVersionId；首次Skill从何创建版本号也未明确 | 建议PATCH可选skillVersionId且新generation，发布时由服务端分配semver；需产品/主agent决定 | 本候选未擅自加更换Skill入口；T05/T06需审核后补 |
| CR-T01-001 | 尚无两名独立标注者、业务类别/来源权利确认或真实三次模型运行预算 | 提供20篇合成文章、200候选Claim和空白双盲表；负责人/证据/状态字段齐备 | UNREVIEWED，不得计入人工金标验收 |

OQ-01–18 的默认值与负责人/截止原文完整登记 open-questions.json，全为 UNCONFIRMED。5/20 USD 只是示例，不是批准的费用预算。真实收费调用在预算确认、原子预占/对账和凭证就绪前禁止；本次未调用任何收费 Provider。
