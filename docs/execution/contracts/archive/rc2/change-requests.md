# 契约变更申请与rc.2整改

审核依据：[T00-T01-Review-v1.0](../reviews/T00-T01-Review-v1.0.md)。已接受部分工程方向但G0未通过；以下为已修订提交复审或外部待办，不填最终PASS。

| 申请 | rc.2处理 | 证据/待办 |
|---|---|---|
| CR-T00-001 删除接口 | 保留impact/ETag/异步，与独立journal闭环 | ADR-006；真实对象/DB未集成 |
| CR-T00-002 canonical | R02唯一投影、完整向量；金额6位、confidence3位、评分3位，避免整数化 | ADR-005；Java/JS待对齐 |
| CR-T00-003 tombstone | 独立恢复域、签名序号链、至少45天且覆盖旧备份、权限、202前登记、恢复追最新head | ADR-006及RestoreBarrier；OQ-16待生产确认 |
| CR-T00-004 图片文字 | 保留最终selection/variant绑定与失败人工回退 | 真实视觉未执行 |
| CR-T00-005 权限/FK | 保留草稿可变/发布不可变、active例外、延迟完整性SQL草案 | DB验证归T02/T06/T24 |
| CR-T00-006 Skill | R04首版base可空、同Skill复制、semver并发规则、PATCH切换新generation | Schema/回归；真实事务待集成 |
| CR-T00-007 原文线格式恢复 | R01四值状态、SRS29.3 original/title/content和budget对象；rightsUpdate及当前稿RightsSnapshot | 等价示例及导出阻断测试；不代替业务权利确认 |
| CR-T00-008 模型路由 | GET/PUT routes同型、baseConfigVersion、AIRequest routeSnapshot | T09/T35待按此候选接入，无真实能力探针 |
| CR-T01-001 人工与质量 | 保留旧回归集，新增独立representative-v1，修R06分析/编辑独立门槛 | 自然人/分歧复核者和代表性审核待指派 |

18项OQ仍UNCONFIRMED，不把工程默认值当业务确认。5/20USD不构成批准预算；本次无付费Provider调用。rc.2待主agent复审冻结。
