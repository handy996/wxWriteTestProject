# T04 首次独立审核

审核日期：2026-10-04（Asia/Hong_Kong）。审核对象：当前工作区；无上轮 T04 报告，无本轮补充要求。

**总结果：CHANGES_REQUIRED。发现 3 项 P1、4 项 P2；另有 1 项非阻断建议。真实 S3 联调受环境阻塞，单列为 B01。**

## 1. 对象、依据与范围

- 分支：`appmod/java-upgrade-20261003114404`。
- HEAD / 比较基线：`b115a4022375675c7cbff536b239508db8f3f4e1`，原始 T02 交付；父提交 `74c2525` 保存契约输入。Git 中没有 T04 原始或整改提交；T04 的 25 个交付文件均为未跟踪工作区新增，不以 HEAD 单独标识审核对象。
- T04 范围：`backend/src/main/java/com/example/editorial/storage/`、相应 6 个测试类、`tests/engineering/T04/`、`infra/storage.env.example`、`docs/execution/reports/T04.md`。
- 其他任务：T02 的 CI/启动脚本/权限补丁/报告和证据、T03 的 identity/shared/audit 与迁移草案、T05 的 editorial/settings/资源/测试均为本轮开始前已存在的工作区修改。本轮未替这些任务修改实现或重新判定其完整验收。
- 审核起始快照：[before.json](T04-round1/before.json)，记录全部 500 个 Git 可见交付文件的逐文件 SHA-256、分支、HEAD、Git 状态；包含 T04 的 25 个文件及实际参与构建的依赖。结束快照和比较见 [after.json](T04-round1/after.json)、[integrity.json](T04-round1/integrity.json)。审核新增内容仅在本报告和 `T04-round1/`。

依据：SRS §5–6、16、25–29、31–36、38，重点 §25.3/33/35、AC-29/32/33；执行计划 T04 卡（第 137–144 行）、共享文件规则和 §6 审核约定；OpenAPI、`$defs/ObjectRef`、`ports.json` 的三个 ObjectStore 端口、表归属/模块依赖/状态和失效契约；ADR-001/004/005/006；T04 交付报告及 T02 最新报告/审核；T00 rc.3 批准记录及第三轮审核。项目及祖先目录未发现适用的 AGENTS.md。

**批准基线核验：27 个已批准指纹全部一致，未运行契约生成器。** 部分契约文本仍写候选状态，以 `T00-rc3-approval.json` 的明确批准及精确指纹为准。T02 最新结论仍为 CHANGES_REQUIRED（Gitleaks R02）；未找到 T03 交付报告或批准记录。允许以领域解析替身完成 T04 单任务核验，不能据此声称 G1/应用完整集成通过。

ObjectRef 的五字段结构和 ObjectStore 三个方法已提供；T04 没有新增领域表、改写旧迁移或修改冻结文件。表持有引用、存储后端保存状态的分工可用于本任务。新增 ObjectRefRegistry 是交接 SPI，并非真实领域引用库。一个需集成方处理的差异：批准的 `module-dependencies.json` 仅登记 storage→shared，现有 AuditSink 端口却由上游置于 audit 包，T04 直接引用该端口；本轮不把上游端口布局差异伪称为已获批准的新依赖，也不要求 T04 越界移动 T03 文件。

## 2. 待修复问题（均为 OPEN）

### T04-R01 — P1：清理与引用提交竞争，可删除已经提交的对象

- **位置**：[DefaultObjectStore.java:133](../../../backend/src/main/java/com/example/editorial/storage/DefaultObjectStore.java#L133)，删除在第 149 行；提交路径第 82–99 行。
- **触发/最小复现**：存在 25 小时前的 STAGING 对象。清理线程从真实 PostgreSQL 查询得到无引用后暂停；另一线程在事务内插入对象引用并调用 commitReference，提交完成、对象已 COMMITTED；恢复清理线程。
- **实际**：清理继续按旧判断删除文件。独立测试确认数据库引用行仍为 1，backend.get 返回 OBJECT_MISSING，cleanup.deleted 为 1。这里的暂停仅控制真实并发交错，引用查询/写入、事务、文件操作均为真实实现。
- **预期/依据**：删除与新增引用须协调，已引用对象不能被孤儿清理删除。违反 T04 验收、AC-29、SRS §25.3/35 与 ADR-004 的当前/历史引用保护要求。
- **影响**：恢复提交与清理并发时会制造悬挂引用，破坏下游图片、证据、导出对象；本轮只在隔离测试中证实，没有推断生产数据已丢失。
- **证据**：[ReviewCounterexamplesTest.java](T04-round1/ReviewCounterexamplesTest.java) 的 `concurrentRealDatabaseReferenceIsDeletedByCleanup`；[verification.json](T04-round1/verification.json)；[测试输出](T04-round1/test-results/TEST-com.example.editorial.storage.ReviewCounterexamplesTest.xml)。
- **最小修复/关闭条件**：给引用提交与删除建立同一个按对象协调的临界区或有条件状态协议，覆盖整个引用事务提交边界；只增加一次普通查询不能消除竞态。复测两种交错，要求已提交引用始终可读，或者提交明确失败且数据库不留下成功引用；保留历史引用/hold 用例。

### T04-R02 — P1：Local HEAD 只相信边车元数据，文件丢失或被改写仍能提交

- **位置**：[LocalStorageBackend.java:74](../../../backend/src/main/java/com/example/editorial/storage/LocalStorageBackend.java#L74)（第 74–80 行）；调用点 [DefaultObjectStore.java:85](../../../backend/src/main/java/com/example/editorial/storage/DefaultObjectStore.java#L85)、第 110 行。
- **触发/最小复现**：stage 成功后保留 `.meta`，删除实际对象文件；或将正文替换成同长度的不同字节。然后调用 commitReference，再授权下载。
- **实际**：HEAD 只比较元数据里的 hash/size，提交成功并标为 COMMITTED。缺文件时仍返回下载 URL；真正 GET 才报 OBJECT_MISSING。内容变更时提交仍成功，GET 才报 OBJECT_CORRUPT。
- **预期/依据**：HEAD 至少确认实际对象存在与大小；引用提交前验证实际内容与 hash，缺失/损坏明确拒绝。违反 SRS §35“不提交指向不存在文件的完成记录”、暂存→hash 校验协议、T04 步骤②及 AC-32 对存储可用性的前提。
- **影响**：T29 按交接说明依赖 HEAD 重查文件时会得到错误的可用性结论，已完成业务记录可能指向不可读对象。本轮未运行 T29，也未声称已经生成了错误正式 ZIP。
- **证据**：同一 [反例工具](T04-round1/ReviewCounterexamplesTest.java) 的 `missingBodyStillCommitsAndGetsDownloadUrl`、`corruptedBytesStillCommit` 及 [运行记录](T04-round1/verification.json)。
- **最小修复/关闭条件**：让物理对象检查与提交校验覆盖真实文件；对缺失、截断、同大小篡改分别断言拒绝且不留下成功提交审计/状态。正常对象仍能提交并下载。

### T04-R03 — P1：S3 请求签名和端点组装不一致，已配置也不能正确工作

- **位置**：[SigV4.java:61](../../../backend/src/main/java/com/example/editorial/storage/SigV4.java#L61)，调用例 [S3StorageBackend.java:80](../../../backend/src/main/java/com/example/editorial/storage/S3StorageBackend.java#L80)；端点处理第 53–67、173–177 行，presign 返回地址在 SigV4 第 89 行。
- **触发/最小复现**：正常无查询串的 PUT/HEAD/GET/DELETE 均传入 null；canonicalRequest 的字符串连接把它写为字面量 `null`。独立调用同一签名器时，null 与规范要求的空查询串产生不同签名。另配置 `http://127.0.0.1:19000` 后 presign 实际返回 `https://127.0.0.1/...`，端口被丢弃。
- **实际/预期**：请求 URI 没有查询串，签名内容却包含 `null`；实际端点的 scheme/port 与生成链接也不一致。AWS 规范要求无查询串使用空串，签名必须与真实请求匹配；参见 [AWS 官方 SigV4 规范](https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html)。符合该规范的服务会拒绝错误签名。这里是已证实的协议错误，真实 MinIO/AWS 拒绝响应因 B01 尚未取得。
- **依据/影响**：T04 卡步骤①③、SRS §31 的 S3 PUT/GET/HEAD/私有下载交付不能由“configured=true”和 URL 有签名字段证明。生产适配器的基础操作及常见带端口兼容端点受影响。
- **证据**：[ReviewS3ProtocolTest.java](T04-round1/ReviewS3ProtocolTest.java) 的 `noQuerySignatureDiffersFromEmptyQueryRequiredByS3`、`configuredEndpointPortAndSchemeAreLostFromPresignedUrl`；[测试输出](T04-round1/test-results/TEST-com.example.editorial.storage.ReviewS3ProtocolTest.xml)。
- **最小修复/关闭条件**：从唯一的实际请求 URI 构造 canonical URI/query/authority，并按配置生成可访问的下载地址；不靠 JVM 放宽 Host 头限制规避。补规范已知向量及默认端点/带端口/virtual-hosted 场景，使用真实私有 S3 兼容桶完成 PUT→HEAD→GET→完成标记→签名下载→DELETE，匿名未签名访问拒绝。端点若不支持某模式应显式拒绝配置。

### T04-R04 — P2：S3 孤儿枚举解析错误，正常对象永远不能进入清理候选

- **位置**：[S3StorageBackend.java:218](../../../backend/src/main/java/com/example/editorial/storage/S3StorageBackend.java#L218)（第 218–223 行），第 162–168 行。
- **触发/最小复现**：受控 HTTP 测试服务返回标准 ListObjectsV2 XML，其中有一个合法 `objects/<UUID>` key，并可提供该对象的真实测试元数据。
- **实际**：`split(">")` 后从 `<Key` 片段中提取出 `<Key`，并非标签内容；非法 key 被跳过，结果为空，列表期间 HEAD 调用数为 0。即使修正 XML，后续用全零 hash 和 size=0 调用会验证 hash/size 的 head，合法非空对象仍报 OBJECT_MISSING，且异常被吞掉。
- **预期/依据**：列出真实 STAGING 候选，再按引用/hold/TTL 分类；不能把枚举失败变成无候选的成功结果。违反 T04 步骤④和 AC-29 的孤儿可清理要求。
- **影响**：S3 暂存孤儿无法清除，已引用 STAGING 的恢复标记也不会执行；磁盘/费用和长期保留行为不符合交付。
- **证据**：[协议反例](T04-round1/ReviewS3ProtocolTest.java) 的 `normalListXmlYieldsNoCandidatesAndZeroMetadataHeads`；[运行记录](T04-round1/verification.json)。该服务只用于精确验证 HTTP 响应解析，不冒充真实 S3。
- **最小修复/关闭条件**：使用安全 XML 解析，从 key 查询实际元数据的内部接口不能要求预知 hash/size；区分列表/HEAD 失败与空列表。真实 S3 中包含过期孤儿、已引用、hold、新对象时，实际清理/恢复数量和结果正确，并覆盖分页。

### T04-R05 — P2：Local 签名链接指向未实现的下载服务

- **位置**：[SignedUrl.java:24](../../../backend/src/main/java/com/example/editorial/storage/SignedUrl.java#L24)，[LocalStorageBackend.java:125](../../../backend/src/main/java/com/example/editorial/storage/LocalStorageBackend.java#L125)；交付报告 §11/13 的延期声明。
- **触发/最小复现**：给 Local 配置合法 base/密钥，对已提交且已授权的对象调用 authorizeDownload。返回 `/api/v1/storage/objects/{key}`，但生产代码没有处理该路径的 controller/handler，也没有对 SignedUrl.verify 的调用或静态对象映射。完整调用点检索见证据。
- **实际/预期**：实现交付到生成字符串为止，没有消费链接并返回文件的能力。预期 T04 应提供可集成、可验证的 Local 受权下载处理能力；根路由的注册可由共享维护者完成，但 handler 本身不能缺失。
- **依据/影响**：执行计划 T04 步骤③及“受权下载能力”交付、SRS §28 storage 职责、冻结 authorizeDownload 的五分钟链接语义。作者自行建议改由 T23/T29 实现，没有批准记录，不能改变任务边界。此项不以尚未实现的图片/导出业务接口为前提。
- **证据**：[scans.json](T04-round1/scans.json) 的生产源码检索；[作者报告](../reports/T04.md) §13.1；原下载单测只断言 URL 前缀，没有 HTTP 获取断言。
- **最小修复/关闭条件**：在允许的 storage 范围交付下载 handler/集成导出及测试入口，需要共享路由变更时按主 agent 流程提交；用真实 HTTP 验证授权链接获取正确字节、过期/篡改/未授权拒绝和缺文件拒绝。不要求提前实现 T23/T29。

### T04-R06 — P2：Local 双文件写入中断会留下永久不可枚举的孤儿

- **位置**：[LocalStorageBackend.java:67](../../../backend/src/main/java/com/example/editorial/storage/LocalStorageBackend.java#L67)（第 67–68 行），[LocalStorageBackend.java:117](../../../backend/src/main/java/com/example/editorial/storage/LocalStorageBackend.java#L117)。
- **触发/最小复现**：进程在对象文件原子移动完成后、元数据写入前中断。本轮直接构造这个精确磁盘状态：`objects/<UUID>` 存在、mtime 为 25 小时前，没有 `.meta`，然后运行真实清理方法。
- **实际/预期**：listStaging 只扫描 `.meta`，cleanupStaleTemp 只扫描 `.tmp`，实际文件永久不被发现；实测 scanned=0、文件保留。预期中断上传能恢复或按 TTL/引用检查清理，不能产生不可追踪的永久正文。
- **依据/影响**：T04 暂存/孤儿清理交付、AC-29、SRS §35。失败上传遗留内容占用存储，且不能通过现有对象清理机制处理。
- **证据**：[反例工具](T04-round1/ReviewCounterexamplesTest.java) 的 `twoFileWriteCrashLeavesUnenumeratedOrphan` 及 [运行记录](T04-round1/verification.json)。这是故障点状态注入，未声称真实杀进程测试已执行。
- **最小修复/关闭条件**：采用可恢复的发布顺序/对象目录原子发布，或受控地枚举并核查无元数据对象；不能直接批量删除以规避引用保护。覆盖两个文件写入各个中断点，超 TTL 的无引用孤儿可清理，引用/hold 对象不误删。

### T04-R07 — P2：T04 作者证据新增 Gitleaks 命中，提交后会阻断 CI

- **位置**：[tests/engineering/T04/evidence/integration.json:73](../../../tests/engineering/T04/evidence/integration.json#L73)；日志来源 DefaultObjectStore 第 151 行；CI 调用 `.github/workflows/ci.yml:55`。
- **触发/最小复现**：按 CI 的 Gitleaks 8.30.1、原始完整规则和全部 Git 可见文件集运行 `run_scans.py`。该证据中的对象 UUID 以 `key=<UUID>` 输出，触发 generic-api-key。
- **实际/预期**：扫描退出 1；T04 作者文件命中 1 项。该值来自对象随机 UUID，**是误报，没有发现真实凭证泄露**；但当前 CI 会失败，不能以“不是密钥”代替处理现有规则。T02 既有 6 项误报另列，不归因于 T04。
- **依据/影响**：执行计划要求可复验交付、现有 CI 完整扫描步骤；把当前未跟踪 T04 文件提交后仍会纳入扫描。只有简化正则扫描或 Maven 通过不够。
- **证据**：[scans.json](T04-round1/scans.json)、[gitleaks-findings.json](T04-round1/gitleaks-findings.json)。首次扫描还包含审核自己新增日志的 4 项同类对象 UUID 误报，明确归于审核证据；本轮已只规范化自己的展示文本并保存转换记录，没有修改作者证据或扫描规则。
- **最小修复/关闭条件**：处理对象 ID 日志格式及交付证据，或提交精确、有依据的误报例外；不能排除整个 evidence 目录/关闭检测器。保留历史记录，新增整改证据，在最终交付文件集复跑 CI 同款扫描；确认本项消失，T02 的独立问题另由其负责人关闭。

## 3. 历轮状态与非阻断观察

首次审核，没有可关闭的 T04 历轮问题；T04-R01–R07 均为本次工作区交付问题，当前 OPEN。未用其他任务的未提交整改替原 T02 提交证明通过；T00 已批准项及 T02 历史 CLOSED 状态不在本轮重判。

**T04-N01 / P3，非阻断建议**：[DefaultObjectStore.java:120](../../../backend/src/main/java/com/example/editorial/storage/DefaultObjectStore.java#L120) 在检查 dryRun 前调用 cleanupStaleTemp，`preview()` 实际删除 25 小时前的 `.part`。`previewDeletesStaleTemporaryFile` 已复现，与 ObjectRetention 第 15 行“without mutating storage”文档不符。当前仅影响过期临时文件，未发现引用数据损失，故不单独作为拒收依据。建议让 preview 不写存储，或明确拆分维护操作与预览语义；关闭时断言临时文件也保持不变。

## 4. 实际运行的验证与证据解释

| 验证 | 结果 | 证据 |
|---|---|---|
| 已批准 rc.3 精确文件指纹 | 27/27 一致，退出 0，无生成器 | verification.json |
| 复制当前源码到本轮隔离目录，Maven clean test | 退出 0；重新编译 64 个生产源文件与 16 个测试源文件 | verification.json |
| 作者 T04 单测 | 27 项通过，0 跳过 | test-results/ |
| 作者 T04 真实 PostgreSQL 测试 | 8 项通过，0 跳过 | test-results/TEST-com.example.editorial.storage.T04PostgresTest.xml |
| 新增独立反例 | 8 项全部确认所描述的错误行为，0 跳过 | ReviewCounterexamplesTest / ReviewS3ProtocolTest |
| 真实 PostgreSQL 并发引用提交/清理 | 复现已提交引用对象被删除 | T04-R01 |
| CI 完整 Gitleaks 8.30.1 | 退出 1；最终 7 项作者文件误报：T02 6、T04 1 | scans.json、gitleaks-findings.json |
| Git 空白检查 | 退出 0 | scans.json |
| MinIO 真实服务 | 未能建立；两官方镜像源拉取失败 | environment-attempts.json |
| 临时 PostgreSQL 停止核验 | stop 退出 0，status 退出 3 / no server running | verification.json |

上述总计 **43 项测试执行、0 失败、0 跳过**，其中 8 项审核测试明确断言“错误现象被复现”，因此此数字不能解释为 T04 通过。原作者测试没有覆盖文件消失、实际内容提交复核、真实并发引用、S3 正常列表响应、可用 HTTP 下载；S3 原测试只验证未配置、签名字段结构、非法 key，并未访问真实桶。

数据库环境：PostgreSQL 17.11、独立临时集群、T02 bootstrap 的独立运行账号、真实 Hikari/DataSourceTransactionManager/JdbcAuditSink。继承作者最小 app_user/audit_log 测试结构；审核另外创建仅该临时库内的 `editorial.review_object_ref` 作为领域表替身。原作者的 Ownership 解析和部分引用映射是内存测试替身；并发反例的引用查询/插入已改用真实 PostgreSQL。这不是 T03 完整迁移权限验收，也不是 T06 等真实领域表集成。

工具版本：Temurin 21.0.12.1+1、Maven 3.9.11、Surefire 3.5.6、PostgreSQL 17.11、Gitleaks 8.30.1；宿主 Docker 客户端/服务端 29.8.1。使用现有 pom 与 Maven 本地仓库，未改依赖清单，未复用 backend/target。未引入付费调用。

复现入口（项目根目录）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T04-round1/review_runner.py verify
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T04-round1/run_scans.py
```

后续复审应复制工具到新轮次目录再运行，避免覆盖本轮结果。具体完整 argv、退出码、输出见 JSON。审核包装器只复制源码并在副本添加测试；没有在交付源码中注入绕过逻辑。脚本会启动并停止自己创建的数据库。

审核工具自身的失败也保留：[sandbox-attempt.json](T04-round1/sandbox-attempt.json) 记录沙箱 restricted-token 启动错误；[runner-pipe-attempt.json](T04-round1/runner-pipe-attempt.json) 记录第一版审核记录器使用管道捕获后台 PostgreSQL 导致等待，主动停止自己的临时库后修正记录器，随后完整成功重跑。这两次不作为实现缺陷。

日志展示规范化：[evidence-normalization.json](T04-round1/evidence-normalization.json) 保存原始/规范化 SHA-256 与替换次数，仅将本轮输出的对象 UUID 标签从键值式改为描述式，UUID、断言和结果未变；原始本轮输出仍在本轮 `.work/raw-evidence/`。未更改作者历史证据。首次与最终完整扫描均保留。

## 5. 未验证项、环境限制和边界

- **B01 / BLOCKED（验证项）**：真实 S3 PUT/GET/HEAD、签名下载、元数据更新、删除/恢复与权限能力未验证。先确认宿主 Docker 可用；`quay.io/minio/minio:latest` 返回 401 UNAUTHORIZED，`minio/minio:latest` 返回 pull access denied。没有现成 MinIO 镜像或提供的受控业务桶凭证。本轮没有创建容器，不能把受控 HTTP 解析服务或本机 Local 当作 S3 通过。
- T02 尚有独立 CI 问题，T03 无批准记录/正式迁移装配；这些依赖状态限制完整 G1 结论，但不用于掩盖或扩大本轮 T04 缺陷。后续 T06/T09/T15/T23/T29/T37 尚未完成不单独构成本轮缺陷。
- 本轮未验收完整应用 Session/CSRF HTTP 链、实际 T29 ZIP/QA/批准门禁、T37 删除 journal/灾备/生产保留政策。T04-R05 判断依据是下载处理代码的实际缺失，并非声称已运行尚未装配的应用链路。
- 本轮没有 T04 新迁移，因此不重新跑无关的 T02 旧版升级；已执行迁移源码包含在前后指纹保护内。没有对原始提交“修复前/后”作虚假比较：T04 历史实现提交不存在。
- 验证平台是 Windows 本地文件系统和宿主 PostgreSQL；Local 的 Linux/POSIX 权限、容器部署及真实生产磁盘故障尚未验证。未用 Windows 权限 no-op 证明生产私有目录权限通过。
- 未重新运行前端构建、全量其他任务测试、在线依赖公告扫描、SBOM 或远程 Actions；T04 未改依赖定义。完整 Gitleaks 使用实际 CI 版本/规则及交付文件集；未把简化扫描当其替代。

## 6. 下一轮复审条件与收尾

1. 提交逐项关联 T04-R01–R07 的整改说明、准确文件指纹和可复现证据；不要改写本报告或作者原始证据。
2. 保留现有正常路径测试，新增断言预期正确行为的回归；特别是数据库并发引用/删除、缺失/损坏文件拒绝、断写恢复、S3 枚举/真实签名、Local HTTP 下载。
3. 提供可访问的受控 S3 兼容测试环境或可拉取的固定镜像，关闭 B01；不能只再检查 URL 结构。
4. 涉及共享路由、端口归属、迁移或契约时交主 agent 审批/集成，不能把作者交付报告中的建议当作批准变更。
5. 最终完整扫描必须确认 T04 命中已消失；T02 的既有 6 项由 T02 独立复审处理，不在本轮重复包装成新问题。

结束核验：交付实现、旧迁移、冻结文件和作者原始证据的 500 项指纹保持不变；本轮 PostgreSQL 已停止，受控 HTTP 测试服务在 finally 中停止；未创建 Docker 容器。构建副本及停止的临时集群保留在本轮隔离 `.work/`，未删除或清理任何其他任务资源。没有提交、合并、发布、联系其他任务或切换/清理共享工作区。

本结论仅覆盖 T04 当前工作区交付和已说明的验证环境，不代表 G1、产品人工质量验收或生产上线批准。
