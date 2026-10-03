# ADR-002：事实政策与版本重对齐

本轮修订：具体线格式/生命周期以 ADR-005 为准；删除journal与恢复以 ADR-006 为准。旧段落描述的未定事项已在这两份候选中补设计，仍待复审。
状态：REVIEW_CANDIDATE；`1.0.0-rc.2`。

核验单位为带时间、地域、单位、样本和条件的原子命题。提取输出 ClaimDraft.localKey，服务端分配 UUID；模型不能授予 SUPPORTED。标题保留锚点 `title`，副标题 `subtitle`；正文 blockId 禁止占用这两个名称。文本锚点采用 Unicode 码点半开区间 [start,end)，quote 和 blockHash 必须与权威纯文本相符。一个 Claim 的多处出现分别保存。

数字、日期、引号、实体扫描作为补漏，无法形成命题则生成阻断人工待办。普通主要事实需要相关 A 级一手证据或两个独立 B 级证据。搜索摘要不构成证据；转载、通讯稿、同一研究的解读按 independenceGroup 合并。法规需要适用地区官方有效文本，科学因果不能只用相关性研究；重大健康/安全/法律/争议命题还需人工证据复核。此为产品验收规则，不对真实法律或健康问题作判断。

ClaimSource 绑定不可变 SourceSnapshot 的实际摘录及 locator。必须验证摘录存在、限定条件、来源等级、独立性和反证。confidence 只是信号，API 使用固定三位小数字符串，数据库 numeric(4,3)，避免跨语言 hash 浮点差异。冲突保留双方，不能按票数消解。REMOVE 必须确认命题从当前正文及标题/图注消失；REPHRASE 形成新命题后重核，添加“可能”不是通过门禁。

每个 V1/V2/MANUAL/RESTORE 都对全稿 reconciliation，复用只限命题、上下文与证据仍匹配且未过期；仍产生新版本关系。实时政策/身份/价格重查 24h，一般事实 30d，稳定资料 180d，事件期限更短时优先。到期比较 `now >= validUntil` 即失效。网页暂不可达独立于真假，合法已有摘录须人工复核，撤稿/反证不能沿用旧结论。

图片文字按 `ImageTextExtraction(selectionId,variantId,variantHash)` 绑定最终变体；box 是解码像素的左上角 x/y/width/height，必须在图内。NO_TEXT 必须来自已执行提取，不能用超时替代。UNREADABLE/PARTIAL 或提取失败建立 required IMAGE_TEXT ManualTask；人工转写同样留 evidence/actor。图注锚点 `caption`，图中文字锚点 `image-text:<regionIndex>`，与 selection scope 一起解析。新 selection/variant 使旧提取和下游 Claim 失效。该能力不扩大为原文 OCR/PDF 导入。

QA 要求当前所有主要事实 SUPPORTED、所有硬数据有证据、无过期/撤稿依赖，不能由人工一句同意覆盖。对应 FR-03–07/16，AC-03–07/24/30/32。T18 实现图片提取；本次只有契约和 mock 验证。
