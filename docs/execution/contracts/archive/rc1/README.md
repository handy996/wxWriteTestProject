# T00 契约候选交接

版本 `1.0.0-rc.1`，状态 **REVIEW_CANDIDATE**。没有上游审核证据，不等于已冻结。目录 baseline.json 锁定两份原文 hash；没有 Git commit。T00 有新契约创建职责，本次仅新增候选，不覆盖任何已冻结公共类型或其他领域代码。根构建、迁移、路由均未触碰。

入口：`../../api/openapi.yaml`（JSON 语法的合法 YAML 1.2 / OpenAPI 3.1）、`../../schemas/editorial.schema.json`（JSON Schema 2020-12）。Schema 根拒绝任何实例，调用方选 `$defs/<DTO>`。`build_contract.py` 是 Schema/API 唯一生成源；`build_registry.py` 生成表、状态、端口与依赖登记。不要单独手改生成结果。主 agent 审核后提升版本并冻结文件 hash；T30 由 OpenAPI 生成客户端。

## 公共协议

- `/api/v1`，JSON camelCase，UUID，UTC `Z` 时间。金额固定六位十进制字符串+USD，数据库 numeric(18,6)；其它币种需新价格/币种契约。confidence 固定三位字符串，数据库 numeric(4,3)。这些线协议细化见 CR-T00-002，未改变预算或事实门禁。
- GET 分页返回 `{items,nextCursor}`，limit 默认20、最大100；cursor 是签名不透明游标，绑定 owner、过滤条件、排序(lastCreatedAt,id)，不同过滤重用报422。详情返回具体 DTO。聚合 artifacts 带 article/version/input/content hash/stale/模式；审计主体由服务端写。
- 写操作（login 除外）统一要求 Session、CSRF、Idempotency-Key UUID、X-Request-Hash。请求 hash 为 canonical({method, route:实际路径, body:请求体或null})；服务端必须自行重算。scope=(ownerId,route,key)，包括 method；同内容重放返回原状态码/响应/Location/ETag；异内容409。先鉴权再查幂等，重放在 ETag 检查前，防止成功请求因新锁版本无法取原结果。记录7d，业务唯一约束永久保留。不同 query 影响命令时也纳入 route 的排序查询串。
- 修改工作头、选择、恢复、批准/驳回等接口必须 If-Match `"job-N"`，missing428、stale412；baseVersion与head不一致409。约束状态不能通过 PATCH status 更改。Cookie/CSRF 由 T03 接入，登录校验 Origin、限流；对匿名没有任何批准入口。
- 错误 code/message/traceId/details/retryable；503 不等于可自动重试，OUTCOME_UNKNOWN 必须对账。跨 owner 一律404。details 仅安全字段名/理由/实体引用，无供应商响应正文。
- 202 表示持久化受理而非业务成功，Location 指向 operations；operationId 在 workflow/step/export UUID 间解析并再次鉴权。SSE 只发序列/类型/状态/引用；断线用 GET 重建，不能将 SSE 当唯一事实源。

## 文本和 hash

权威 AST 仅 heading/paragraph/list/quote/imagePlaceholder；heading 使用 level，list 的纯文本为 items 用 `\n` 连接，其 text 必须等于该结果；imagePlaceholder text 必须空并有 slotId；其他块 level/slotId=null、items=[]。marks 只有 bold/italic/link，码点半开区间，link 只 HTTPS。不接受 HTML 标签/事件/可执行 URL，Unicode surrogate 拒绝。引用 ID 必须存在且同文章。blockId/sectionId 稳定；拆并新 ID 和 BlockMapping，不能重用旧 span 猜位置。

字符数在已解析 AST 中计算，去 Unicode White_Space 后计码点；Markdown 标记在解析时去除，不全局删 `*` 等可能是正文的字符。原文100–30000字符且上传≤1MiB。标题/副标题分别锚定；统计口径固定为标题+副标题+正文可读文字，不计算技术 ID。

`canonical-v1`：UTF-8 无 BOM、ASCII 字段名按字节排序、无空格，字符串保留 Unicode 原样（不 NFC）、JSON 转义控制字符，不转义 `/`。只允许整数/字符串/布尔/null/数组/对象，禁止 float/NaN/重复键/孤立 surrogate；金额和置信度用定标字符串。Python reference.py 是跨语言向量生成器，不声称采用 RFC8785。Java/JS 应按向量实现，不能直接信任默认 Map 顺序。

contentHash = hash({schemaVersion,title,subtitle,contentAst})；blockHash=SHA256(块纯文本UTF8)。Manifest hash 覆盖有序 items、两版声明、policyVersionId，不含 meta。releaseHash 覆盖 version.id/hash、manifest.id/hash、按ID排序的 selection/最终variant/许可/source snapshot/verification 引用、factSetHash、skill规则hash、policy版本hash；不包括自身hash、stale、active、展示URL、审计时间或lockVersion。所有数组在规范中未指定排序时保留业务顺序。inputHash 覆盖实际输入快照、Prompt/Schema/Skill/Policy 版本、生成参数；不是仅正文hash。

## 语义校验及端口

JSON Schema 只验证结构。`reference.py` 演示 AST/锚点、许可三值、fencing/人工批准与预算等纯函数语义；测试不会把它们当生产实现。每个端口在 ports.json 登记提供者、输入输出、错误和共同审计语义。结构失败与引用/业务失败分开记录。AIResult.SUCCEEDED 必须 rawResponse、structuredOutput、schemaValid 和 semanticsValid 全部具备；OUTCOME_UNKNOWN 保留预占、providerRequestId可null。模型不可直接填写服务端 meta/actor/status，Analyzer/Writer/Reviewer 使用单独 Output DTO，服务端封装为产物。

所有租约提交先校验 StepContext 与持久化 current fence/generation/deadline 再入库；执行输出不得授予批准。ImageText UNREADABLE/PARTIAL 强制人工待办。QaReport 必须包含16条不同 ruleId、所需检查全部执行且鲜活，WARNING 的人工说明附加审计并复检产生新报告；原 QA 不覆盖。ManualTask.resolve 根据 type 校验证据，不能仅把字符串 resolution 当通过。

## 重现

使用 Python 3.12。标准库生成不联网：

```powershell
python docs/execution/contracts/build_contract.py
python docs/execution/contracts/build_registry.py
python docs/evaluation/build_fixtures.py
python -m unittest discover -s tests/contracts/T00 -v
python -m unittest discover -s tests/evaluation/T01 -v
python docs/evaluation/evaluate.py --demo --output docs/evaluation/results/demo.json
```

T00 测试另需 tests/contracts/T00/requirements.txt 的标准校验器；可装到临时目录并设置 PYTHONPATH，不修改应用依赖。环境具体可执行路径、真实命令/退出码见 reports/T00.md、T01.md。
