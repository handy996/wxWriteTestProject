# ADR-007：冻结配图位置与历史渲染

状态：`1.0.0-rc.3 / REVIEW_CANDIDATE`，针对第二轮审核 R02-A 提交，待主 agent 复审。依据 SRS 16.2、17、QA-11、24、FR-17/18、AC-17/18/25；补充 ADR-001/005 中的 Slot 冻结范围。无已批准契约被宣布冻结。

## 唯一位置来源

ReleaseCandidate 必须包含 `slotAnchors: FrozenSlotAnchor[]`。每个实际使用的 Slot 冻结 `slotId、selectionId、versionId、anchorBlockId、blockHash、anchorSide、position、planHash`。FrozenSelectionBinding 增加 slotId，把该位置与既有 selection/asset/variant/license 关联。无图审核包使用空数组，不允许省略。

审核预览、QA-11、批准和正式/历史导出的位置唯一来源是该 Candidate 的 slotAnchors，加上其引用的不可变 ArticleVersion。禁止查询当前 ImageSlot 补齐、覆盖或“修复”历史位置。AST 的 imagePlaceholder 保留为编辑器标记；发布渲染不从它再次输出图片，也不要求每个已选 Slot 有 placeholder。placeholder 不能作为锚点目标。正文没有 placeholder 也能完整还原图片位置。

按正文 AST 中可渲染块的顺序遍历：先输出该块 BEFORE 图片，再正文块，再 AFTER 图片；同一块同一侧按 position 升序输出。position 是非负整数，同一块同一侧不能重复；不同块/侧可以复用。槽位数组顺序没有含义。Manifest 的 displayOrder 表示冻结清单条目顺序，不能用来推断正文插图位置；图注/署名按 slotId + selectionId 关联。

## 冻结前校验

领域服务先按 Schema 校验输入，在同一工作头事务快照中取得完整的实际选图集合、ImageSlot、ArticleVersion 和 Manifest；不得由调用方提交的子集冒充完整集合。完整发布门禁继续检查必选 Slot、最终变体、水印、授权、原文依据、QA 等。本次位置 oracle 不替代这些门禁。

位置冻结至少验证：

1. Candidate、正文、Manifest、每个已选 Slot 都属于同一 article/owner/version，正文 ID 等于 Candidate.version.id。重算正文与 Manifest 内容 hash，验证引用 hash 和内容一致。
2. 每个已选 Slot 恰好一个 selection binding 和一个 anchor。slotId、selectionId 各自唯一；无缺失、多余、重复或交叉配对。Manifest 的 slot/selection/asset/variant/license 五元组与 bindings 完全一致；最终 selection/variant/license 引用覆盖仍沿用原守卫。
3. 锚点存在于该版本真实正文块中，sectionId 匹配，不是 title/subtitle 或 imagePlaceholder。blockHash 从该块 text 的 UTF-8 字节重算；不是客户端申报值。planHash 来自冻结时的 Slot，位置的实际值仍完整嵌入，不依赖后来查计划。
4. side 仅 BEFORE/AFTER；position 非负且边界内无歧义。所有检查通过后，构建新 Candidate，计算 releaseHash，再进入 QA/审批。

`reference.freeze_slot_anchors` 是无 IO 的离线位置冻结计划，返回深复制，不能写批准记录。`render_frozen_positions` 只接受冻结 Candidate 与冻结正文，验证 releaseHash、正文 hash、blockHash 后输出位置及 asset/variant 关联。真实存储存在性、真实选择集合完整性、并发一致性由 T24/T27/T28/T29 实现。

## hash 与版本兼容

唯一投影仍为 `release_hash_input(candidate)`。selectionBindings 按 selectionId 排序；slotAnchors 按 slotId 排序后完整加入 ReleaseHashInput。字段包括 versionId、blockHash、planHash，因此仅移动块、改侧、改 position 或计划 hash 均改变 releaseHash；数组重排不改变它。现有 mutable active/stale/审计字段排除规则不变。

rc.2 缺少可证明的历史位置，不允许在导出时读工作头回填并冒称原批准内容。rc.2 候选保留作审计；新发布须使用 rc.3 重新冻结、QA、审批。rc.1/rc.2 fixtures、T01 材料与标注不升级重写，它们保留自身版本。rc.3 全部 DTO 使用新 schemaVersion。

## 修改与失效事务

PATCH /image-slots/{id} 保留既有 `anchor: {blockId, side}`，新增可选 position。至少一个字段；继续使用认证、If-Match、幂等键和请求 hash。没有新根路由。

任意工作头锚点、side、position 或有效 planHash 变化（包括重排、人工编辑和自动重规划）必须触发 `SLOT_ANCHOR_CHANGED`。entityIds 为受影响 Slot；beforeHash/afterHash 是变更前后位置投影 `{slotId, versionId, anchorBlockId, anchorSide, position, planHash}` 集合按 slotId 排序的 canonical digest。该事件投影也覆盖尚未选图的 Slot，不要求 selectionId；后续选图继续走 SELECTION_CHANGED。服务端不得让 AI 指定 actor。

写入工作头 Slot、递增 job lockVersion、更新依赖修订/fencing、将当前审核资格撤销并持久化事件/outbox 必须同事务；旧 ETag/基于旧依赖或旧 fence 的提交失败，不能重新激活旧 QA。重复幂等请求不重复失效。允许修改的工作头转 NEEDS_REVISION，重新生成当前 Candidate/QA 后才能审核；已取消任务继续按既有状态守卫拒绝修改。

事件映射失效 `SLOT_ANCHORS、IMAGE_CONTEXT_QA、LICENSE_MANIFEST、NOTICES、QA、CANDIDATE、CURRENT_APPROVAL`。CURRENT_APPROVAL 指当前工作头的批准适用性，不修改历史 Approval/Candidate/Manifest 正文或位置。历史批准仍按其他时效/撤回/授权门禁独立判断能否导出；旧位置永不随工作头移动。

## 验证边界

新增离线测试覆盖同正文/图片/图注下的移块、改侧、重排，历史无工作头读取、缺块/跨版本/重复/缺 Slot 拒绝，以及 placeholder 不造成重复位置。Python 生成五组位置向量；JavaScript 独立 canonical-v1 实现复算给定投影。它不是完整 JS Candidate 投影，也不是实际渲染服务、并发事务或最终验收。
