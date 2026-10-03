# ADR-003：图片、三值许可与不可变选择

本轮修订：具体线格式/生命周期以 ADR-005 为准；删除journal与恢复以 ADR-006 为准。旧段落描述的未定事项已在这两份候选中补设计，仍待复审。
状态：REVIEW_CANDIDATE；`1.0.0-rc.2`。

许可属性为 true/false/null，null 表示未知。UNKNOWN、商用未知/禁止、NC、ND、缺必要作者或证据一律 BLOCKED。SA 先 REQUIRES_REVIEW，确认本次变换、衍生许可及实际声明义务后才允许；多许可须选一条并保留全部选项与理由。肖像/商标/敏感上下文单独复核。模型只能提取字段，不能设置 licenseVerified。人工补证必须创建新授权快照并运行同样规则。

此处重述 SRS 的产品政策，不作图库当前条款已经核验的声明。Commons 逐文件记录许可和修订；Pexels 保存内容许可和 API 条款两份版本证据；真实条款、账号能力与响应探针归 T20/T21。生成图使用 GENERATED_TERMS，不能伪填 CC；条款凭据缺失仍阻断。授权页默认 7d 重查，访问失败暂停新批准并复核，旧快照不覆盖。

ImageProvider.capabilities 明确区分 SEARCH/METADATA/LICENSE/DOWNLOAD；GenerativeImageProvider 独立生成端口。AI provider 不提供 SEARCH，调用返回 CAPABILITY_UNSUPPORTED。每 query 每 provider 20 条、每 slot 最多 3 query、去重最多 30 入硬过滤、最多 5 视觉评估。部分失败返回 partial+errors 并保留另一 provider 结果。

EVIDENCE 恒为 mustBeReal=true、aiGenerationAllowed=false。SCENE 默认真实；概念场景须显式改为 EXPLANATION 并标示意。生图前要求已确认预算、已知价格、原子预占，自动生成默认关闭；每 slot 2 次、每篇 4 张。未知受理保留预占并对账，不盲重发。最终人工选择不可由评分或生成成功替代。

selection 的 caption、slot、asset、variant、license、selectedBy/At 永不可改；只有 active 可由受控服务切换。替换、裁剪、图注修改创建新记录，同事务失活旧选择并校验部分唯一索引。active 不属于内容 hash。版本、声明和候选引用明确 selectionId，历史审批仍引用旧记录。

所有图片安全下载、magic/MIME 一致、20MiB/40MP 上限、重编码后验证。生成图在最后变换后添加程序“AI生成”水印；无字体或验证失败不得 READY。实际 variant hash、fontHash、transformHash 入清单，原图不进入正式导出。Manifest 只含实际选择，连续编号，两种声明都保留全部义务；任何换图/文字变更重做事实、Manifest、QA 和候选。

对应 FR-08–18；AC-08–18/25/26/32/35。本次许可输入均为合成规则夹具，不是真实许可授予。
