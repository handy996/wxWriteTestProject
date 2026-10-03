# T00 rc.2 契约候选交接

版本 `1.0.0-rc.2`，REVIEW_CANDIDATE / AWAITING_REVIEW。上次审核CHANGES_REQUIRED，不自行改为PASS或冻结。rc.1合同/报告在archive/rc1，原审核材料未改；原始需求/计划hash见baseline.json，仍无Git commit。

build_contract.py是OpenAPI3.1（JSON语法YAML1.2）和JSON Schema2020-12唯一生成源，build_registry.py生成38表/FK/状态/端口登记。Schema根拒绝实例，必须选择$defs/DTO。T30负责生成客户端，T02补Git与生产版本核验。

## 协议与线格式

/api/v1，camelCase、UUID、UTC Z。Session/CSRF，actor/owner来自认证；客户端无status/approvedBy/licenseVerified入口。跨owner隐藏为404。分页默认20最大100，签名cursor绑定owner/过滤/稳定排序；错误固定code/message/traceId/details/retryable，无正文/密钥/堆栈。

创建输入对齐SRS29.3：original.format/title/content、四值rightsBasis、budget.limit/currency；可选rightsNotes/rightsEvidenceIds。ArticleArtifact.job承载id/status/currentVersionId/lockVersion，artifacts为产物引用，rightsSnapshot是当前稿使用依据。SRS示意响应的四字段对应job下相同字段。

写请求除login外带Idempotency-Key和X-Request-Hash。hash=canonical({method,route:实际路径及排序查询串,body:请求体或null})；服务端重算，scope=(ownerId,method+route,key)。同请求重放原响应/Location/ETag，异请求409；先鉴权再重放再ETag检查。记录7天、业务唯一键/Provider去重长期。202仅持久化受理，Location指operations；查询workflow/step/export时再次鉴权。SSE仅通知，断线用GET重建。

修改工作头、选图、恢复、审批等If-Match为"job-N"，缺失428、过期412；baseVersion/业务状态冲突409。PATCH新增skillVersionId和rightsUpdate，完整事务守卫见ADR-005。暂停/取消后仍结算费用；UNKNOWN保留预占对账。三次总尝试包含至多一次结构纠正；任何收费调用先具备确认预算、已知价格、原子预占和对账能力。

## AST、引用、hash

AST仅heading/paragraph/list/quote/imagePlaceholder。稳定sectionId/blockId；title/subtitle保留。list.text等于items换行连接，其他块items=[]；heading有level，imagePlaceholder有slotId且text空。marks仅bold/italic/HTTPS link。span为Unicode码点半开区间，quote/blockHash匹配；拒绝HTML、孤立surrogate、不存在或跨文章引用。字符数按解析后的可读文字去空白统计，100–30000码点，文本上传≤1MiB。

canonical-v1：UTF8无BOM、ASCII键排序、无空白JSON、Unicode原样不NFC、不转义斜线；仅整数/字符串/布尔/null/数组/对象，拒绝float/NaN/重复键/surrogate，整数≤2^53−1。金额6位、confidence3位、图片评分3位字符串，计算用Decimal；不能把综合评分提前取整。它不是RFC8785。

contentHash覆盖schemaVersion/title/subtitle/contentAst；blockHash为纯文本UTF8 SHA256。Manifest hash覆盖有序items、两版声明、policyVersionId。releaseHash唯一流程为release_hash_input(ReleaseCandidate)→ReleaseHashInput→digest，涵盖article/owner、正文/Manifest、事实集、Skill、原文依据、selection-asset-variant-license关联和证据/政策引用。引用按ID排序，展示顺序已含于Manifest。投影仅读冻结字段，不查后来工作头；active/stale/审计时间不改历史hash。

冻结服务校验真实内容hash、同文章/owner、选择与变体/授权配对、对象存在与全部门禁；投影不能仅凭一个申报hash证明内容真伪。缺最终variant/license或重复绑定拒绝。rc2/release-vector.json含Schema有效完整候选、投影和预期hash，供Java/JS实现。Analyzer先输出localKey引用，服务端验证/分配UUID后形成AnalysisResult和claimIdMap，禁止模型伪造持久化ID。

## 生命周期与边界

通用ObjectRef允许安全整数大小；ImageObjectRef/ImageFetchRequest限制单图20MiB、解码40MP，TextUpload独立1MiB。合法21MiB ZIP不会因单图限制被拒。独立导出容量规则若需增加，必须明确配置和错误。

Skill首版base可空，已有版本复制须同Skill；锁身份行分配semver、唯一约束兜底。切换只选PUBLISHED，ETag/幂等/旧fence失效/新generation/事件同事务。Provider GET/PUT统一ModelRoute，baseConfigVersion并发保护，AIRequest保留routeSnapshot；配置不代表真实能力已探针通过。见ADR-005。

删除journal在不随业务备份回滚的独立恢复域；REQUESTED持久化后才202，完成清理才PURGE_COMPLETED。默认最少45天且覆盖所有可恢复旧备份；恢复向独立journal取当前head并重放备份后删除。不可用/缺口/未重放时禁止开放。生产保留政策仍待确认，Schema/流程与真实灾备区分见ADR-006。

## 复现

安装tests/contracts/T00/requirements.txt到独立环境后运行：

```powershell
python tests/evaluation/T01/verify.py
```

可用临时目录和PYTHONPATH，不改应用依赖。runner生成rc.2及独立representative-v1，运行原测试/新增回归/六项迁移probe/未标注拒绝示例并保存argv、退出码和输出，**不重生成rc.1数据**。旧独立审核脚本针对rc.1线格式；新probe显式迁移输入，不改原脚本或审核结论。

结构样例仅表示Schema有效，业务关系另外测。全部离线mock，无HTTP/DB/Provider或人工标注集成。实际命令与待审核项见T00/T01报告；ADR-005/006覆盖早期ADR被本次修改的细节。
