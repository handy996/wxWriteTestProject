# ADR-001：模块边界、版本与提交协议

本轮修订：具体线格式/生命周期以 ADR-005 为准；删除journal与恢复以 ADR-006 为准。旧段落描述的未定事项已在这两份候选中补设计，仍待复审。
状态：REVIEW_CANDIDATE；契约 `1.0.0-rc.2`；2026-10-02。主 agent 审核前不可称已冻结。

采用 SRS 指定的 Java 21、Spring Boot 3.5 兼容基线、PostgreSQL、Vue/TypeScript 模块化单体。补丁支持、部署地、真实模型能力留给 T02/T09 核验，本 ADR 不声称这些外部事实已确认。一个 Maven application，HTTP 与 Worker 共用领域服务。拒绝按任务拆微服务、内存异步替代持久化队列、跨网络长事务。

`module-dependencies.json` 是编译依赖 DAG。各领域实现由组合根注入契约端口；运行时调用可以双向，经事件和 generation 隔离，不形成 Java 包实现依赖环。`shared` 仅放 ID、Clock、Error、分页和端口类型，不放业务服务。领域只能通过拥有者服务写表。`tables.json` 指定全部 38 表唯一拥有者；它的 FK 图和编译图不同，不将数据库本来存在的环伪称为无环。

认证产生 ActorContext；Owner 和 SystemWorker 的身份分离。客户端不得提供 actor/owner/approvedBy。所有 ID、JSON 内引用、对象下载都重新校验所有权和同文章关系；隔离失败统一 404。Worker 不能调用人工批准、人工证据复核和警告确认。审计与业务变更同事务，记录 actor、trace、hash 和安全错误，正文及密钥不进入普通日志。

HTTP 校验后在短事务原子写幂等记录、workflow/step、audit，再返回 202+Location。逻辑 key 为 canonical hash(stepCode,scopeId,inputHash,workflowGeneration)，attempt 独立递增。持久化队列容量 50、同时执行文章 2、线程池 4、文本并发 2、生图并发 1。领取租约 60 秒，每 15 秒续租，只有最新 fencing token 可提交。网络 IO 在事务外，结果暂存后验证 hash，再在新短事务复核 fencing/baseVersion/ETag 并提交。人工保存先使旧执行失效；晚到 AI 只保留为候选或历史。暂停/取消后仍结算远端已发生费用。

生产步骤按 SRS 顺序先核验再写作。EDITORIAL_DRAFT 仅为附录 J 开发演示，Claim 保持 UNVERIFIED，批准、QA/正式导出返回 FEATURE_NOT_READY。三次总尝试包括最多一次结构纠正；已受理未知不走普通重试。瞬态确定失败采用 2s/8s 加抖动，429 尊重 Retry-After。人工等待释放线程。

兼容策略：新增可选字段需提升 minor，删字段/改语义提升 major；候选期修改提升 rc。请求不允许额外字段。生成客户端由 T30 负责，不将此候选复制进后端生产包。当前目录没有 Git，基线由 baseline.json 的原文件 SHA-256 固定；T02 建库后主 agent 补 commit 和审核证据。

关联：FR-01–22；AC-01/19–23/27–35。实现状态：文档与离线契约检查；无数据库、HTTP 服务或真实 Provider 集成。
