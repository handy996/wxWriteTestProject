# T04 第二轮独立审核

日期：2026-10-04（Asia/Hong_Kong）。对象：当前工作区整改。上轮：[T04-Review-v1.0.md](T04-Review-v1.0.md)。

**结论：CHANGES_REQUIRED。上轮 5 项阻断问题及 N01 建议已关闭；R03 仍有可行动的端点签名缺陷，剩余严重性为 P2；R04 的协议修复已验证，但真实 S3 验收仍因 B01 阻塞。没有新增问题编号。**

## 1. 对象与审核依据

- 分支：`appmod/java-upgrade-20261003114404`；HEAD 仍为 `b115a4022375675c7cbff536b239508db8f3f4e1`。T04 初版和本次整改均未提交，不把该 HEAD 当成整改版本。
- 对比上轮工作区指纹，共 10 个既有文件发生变化：storage 下 DefaultObjectStore、LocalStorageBackend、ObjectRefRegistry、S3StorageBackend、SigV4、SignedUrl、StorageBackend；`infra/storage.env.example`；T04 集成编排器；T02 的 Gitleaks 配置。另新增对象事务锁、Local 下载 handler/配置、回归测试、整改说明和证据。
- 本轮起始 [before.json](T04-round2/before.json) 固定 572 个交付/历史审核文件的 SHA-256、Git 状态、分支和 HEAD。与上轮的具体差异、作者整改指纹核对见 [input-comparison.json](T04-round2/input-comparison.json)：作者交付 33 项指纹全部匹配，批准契约 27 项全部匹配。
- 原始 T04 报告、原始 integration.json、上轮审核及证据保留。作者新报告为 [T04-Revision-v1.0.md](../reports/T04-Revision-v1.0.md)，本轮没有将其中“测试通过”或“用户决定”的叙述代替独立验证。
- 依据沿用 SRS、T04 任务卡、共享文件规则、批准的 rc.3 OpenAPI/Schema/端口/表归属/事务约定和相关 ADR；未发现新增 AGENTS.md。未运行契约生成器，没有新增接口验收范围。

审核只新增本报告和 `T04-round2/`。T02/T03/T05 其他工作区交付不是本轮整改对象；T02 原有 6 项扫描误报继续单独记录。没有因后续领域实现或正式迁移尚未装配而否定已完成的 T04 单任务能力。

## 2. 唯一仍需修改的问题

### T04-R03 — OPEN / P2：显式默认端口仍造成签名 Host 与实际发送 Host 不一致

这是上轮 R03“签名与端点组装不一致”的剩余分支，沿用原编号。原先空查询串、非默认端口丢失和 virtual-hosted 地址问题已修复；残余影响范围缩小，因此从原 P1 调整为 P2。

**准确位置**：[SigV4.java:103](../../../backend/src/main/java/com/example/editorial/storage/SigV4.java#L103) 直接以 `uri.getRawAuthority()` 签名；[S3StorageBackend.java:75](../../../backend/src/main/java/com/example/editorial/storage/S3StorageBackend.java#L75) 保留显式端口，并在第 85 行调用签名器、第 87 行依赖 HttpClient 自动生成 Host。预签名分支第 82 行也直接使用 rawAuthority，修复时须一并核对。

**触发条件与最小复现**：使用当前接受的 `endpoint=http://127.0.0.1:80`、path-style 模式及合法测试桶名，对一个 4 字节 STAGING 对象执行实际 `S3StorageBackend.put`。独立测试在本机 80 端口捕获 JDK HttpClient 发出的 HTTP 请求，以相同 payload、时间及全部 metadata 头重算签名，只改变 authority 输入。

**实际行为**：

```text
configured authority = 127.0.0.1:80
wire Host            = 127.0.0.1
signature matches configured authority = true
signature matches wire Host            = false
```

第二次定向验证明确断言：使用带端口 authority 重算的值与请求 Authorization 完全一致，证明其他签名输入一致；再断言实际 Host 应匹配时失败。两次运行均复现，均退出 1；不是绑定端口失败、连接异常或泛化的“非零即拒绝”。

**预期与依据**：签名必须绑定真正发出的 Host；对外宣称支持的端点配置不能生成无效认证请求。违反 T04 步骤①③的 S3 PUT/GET/HEAD/受权下载交付及上轮 R03 关闭条件。无查询串和 Host 等规范化要求依据 [AWS 官方签名规范](https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html)。符合 SigV4 验签规则的服务会拒绝这类签名；本轮实际证明了传输头与签名不一致，**没有冒称获得真实 AWS/MinIO 的拒绝响应**。

**影响**：显式配置 HTTP 默认端口的受支持 S3 兼容端点无法完成正常认证操作。未显式写默认端口和带非默认端口的已测场景不受这个反例否定；本轮没有实际验证 HTTPS `:443`，但关闭时需覆盖对应规范化分支。

**独立证据**：[EndpointAuthorityTest.java](T04-round2/EndpointAuthorityTest.java)、[完整构建运行](T04-round2/verification.json)、[定向确认](T04-round2/endpoint-confirmation.json)、[定向测试结果](T04-round2/endpoint-results/TEST-com.example.editorial.storage.EndpointAuthorityTest.xml)。接收端只用于捕获真实 HTTP，不模拟签名通过或宣称真实 S3 集成成功。

**最小修复方向与关闭条件**：在构造实际请求 URI 时统一处理 scheme 对应的默认端口，并让普通签名和 presign 使用相同规范化后的地址/Host；或明确拒绝当前无法正确处理的配置，不能静默接受。不得通过全局放宽 JVM 受限 Host 头规则解决。回归至少覆盖不写端口、显式 `:80`、显式 `:443`、非默认端口和 virtual-hosted；实际捕获请求的 Host 与用于签名的 Host 必须一致，保留两组 AWS 已知向量。真实 S3 全链路仍需 B01 环境完成。

## 3. 上轮问题逐项复核

| 编号 | 本轮状态 | 独立验证与关闭范围 |
|---|---|---|
| T04-R01 | **CLOSED** | PostgreSQL advisory transaction lock 被提交和清理共用。两种实际并发交错通过，测试查询 pg_locks 确认竞争操作真正等待；引用先提交则对象/引用保留，清理先执行则竞争提交失败且引用行与提交审计回滚。锁覆盖外层事务，READ COMMITTED 前提与 hold 写入协议已记录。 |
| T04-R02 | **CLOSED** | 缺文件、截断、同大小改写均拒绝。额外独立测试确认错误分别为 OBJECT_MISSING / OBJECT_CORRUPT，真实数据库引用插入随事务回滚，无 OBJECT_COMMITTED 审计。正常路径继续通过。 |
| T04-R03 | **OPEN** | null 查询串、scheme/非默认 port、桶子域地址、COPY 元数据签名与 HTTP 200 错误检查已有修复；官方签名向量通过。但显式默认端口反例仍失败，见 §2；真实桶也仍未验证。 |
| T04-R04 | **BLOCKED** | 原 XML 解析与占位 hash/size 缺陷在受控 HTTP 响应中已消失：两页、两个真实 metadata HEAD、特殊 token 编码、坏 XML/XXE/缺 token/HEAD 失败拒绝均通过。尚缺上轮关闭条件要求的真实桶分页清理/恢复数量，受 B01 阻塞；不继续把已修复的解析错误记为 OPEN。 |
| T04-R05 | **CLOSED** | 新 LocalDownloadHandler/条件路由与窄 GET 安全链在真实 Tomcat/Spring Security 下可用。字节及 attachment/no-store/nosniff 正确；无签名、过期、篡改、重复参数、未知/撤销/缺文件均按预期拒绝；禁用或 S3 模式不注册入口。真实 PG stage→commit→授权→HTTP 下载通过，另一 Owner/匿名无法获链接。 |
| T04-R06 | **CLOSED** | body-only 与 metadata-only 中断状态可枚举；过期无引用孤儿清除，历史引用恢复，hold/新对象保留。独立增加无 registry 和引用查询异常两种反例，均不删正文、不臆测修复 sidecar。仍明确这是磁盘状态注入，未声称真实杀进程。 |
| T04-R07 | **CLOSED** | 完整 Gitleaks 8.30.1 与当前 CI 规则复跑，T04 无命中。新增例外同时限定单个历史文件路径和已核实对象 UUID，旧证据原文未改；没有排除 evidence 目录或关闭检测器。剩余 6 项全属 T02 原有指纹误报。 |
| T04-N01 | **CLOSED** | preview 不删除过期临时文件，也不为 body-only 对象补写 sidecar；live 路径才清理。 |
| B01 | **BLOCKED** | 真实 S3 环境未具备，详见 §5。 |

上轮旧行为已由第一轮带指纹的反例和运行记录证明，本轮针对整改版验证正确行为；未通过重写旧报告构造“修复前”证据。

## 4. 实际执行的检查

| 检查 | 结果 | 证据 |
|---|---|---|
| 批准契约指纹 | 27/27 匹配，无生成器 | input-comparison.json、verification.json |
| 作者整改交付指纹 | 33/33 匹配 | input-comparison.json |
| 隔离源码副本 Maven clean test | 重新编译 67 个生产文件、19 个测试文件；**57 项执行，56 通过、1 失败、0 跳过；退出 1** | verification.json、test-results/ |
| 其中作者 T04 测试 | **54/54 通过**，包括 17 项真实 PostgreSQL 测试及真实 Local HTTP 测试 | test-results/ |
| 新增审核测试 | 真实 DB 回滚/原因校验、恢复候选失败关闭共 2 项通过；默认端口 Host 一致性 1 项失败 | IndependentRevisionTest.java、EndpointAuthorityTest.java |
| 默认端口定向重跑 | 1 项执行、1 失败，明确确认只有 Host 输入不同；退出 1 | endpoint-confirmation.json、endpoint-results/ |
| CI 完整 Gitleaks | 退出 1，6 项均为原有 T02 误报；T04 及本轮审核证据 0 命中 | scans.json、gitleaks-findings.json |
| Git 空白检查 | 退出 0 | scans.json |
| PostgreSQL 收尾 | stop 退出 0；status 退出 3，no server running | verification.json |

环境：Temurin JDK 21.0.12.1+1、Maven 3.9.11、Surefire 3.5.6、真实 PostgreSQL 17.11、Windows 本地文件系统；HTTP 使用 JDK HttpClient 和真实 Tomcat/本机接收端。复制当前交付源码到本轮 `.work/` 全新构建，不使用原 backend/target，不改原测试；只在副本增加审核测试。定向重跑复用该已核验副本，仅重编新增审核测试，目的在确认首次失败的具体原因。

数据库是本轮新建的隔离集群，运行账号来自原 bootstrap；继承作者最小 app_user/audit_log，领域引用仍是测试表/解析替身。独立测试另建 `review_round2_ref`，仅存在本轮临时数据库。并发测试中的引用 SQL、事务、锁等待、文件 IO 为真实实现，不把领域解析替身当完整集成。

审核工具第一次因新增测试自身的 Java 泛型推断编译失败，未执行测试，记录在 [reviewer-compile-attempt.json](T04-round2/reviewer-compile-attempt.json)。只修正审核工具后重新 clean 构建；该次失败不归因于交付实现。正式 57 项运行及定向运行的非零退出均由 R03 的明确断言失败导致，包装器也保留非零总退出。

复现入口（后续复审请复制到新轮次目录，避免覆盖本轮证据）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T04-round2/review_runner.py verify
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T04-round2/run_endpoint.py
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T04-round2/run_scans.py
```

完整 argv、退出码和输出在上述 JSON；动态测试口令未输出，JVM 的临时目录也限制在本轮 `.work/`。定向 endpoint 测试需要本机 80 端口空闲；本轮绑定成功，finally 已停止服务。

## 5. 环境阻塞与范围边界

**B01：真实 S3 全链路仍未验证。** 本轮以宿主权限重新检查 Docker，客户端 29.8.1 存在，但 Docker Desktop Linux Engine 命名管道不存在，version/image ls 均退出 1，当前 daemon 无法连接。证据：[docker-inventory.json](T04-round2/docker-inventory.json)。不能将它解释为 Docker 未安装。整改报告另保留固定 MinIO 镜像拉取失败以及暂无测试桶的状态；本轮没有重复索要凭证，也没有用协议测试替代真实桶。没有启动 Docker 或创建容器。

解阻后仍需在受控私有桶执行 PUT→HEAD→GET→完成标记→五分钟签名下载→DELETE、匿名未签名访问拒绝，以及过期孤儿/历史引用/hold/新对象/分页下的清理和恢复。R04 标记 BLOCKED 仅针对这个尚缺的关闭证据。

本轮不宣称生产 HTTPS、Linux/POSIX 权限、真实磁盘故障、完整 T03 Session/CSRF 应用装配、真实领域引用表、T29 正式 ZIP 或 T37 删除/恢复 journal 已验收。Local 的签名链接是授权后发放的短期 bearer capability，下载端无会话不等于匿名能自行获取链接；已核验撤销和对象状态重查。

没有新增迁移、依赖或更改冻结文件，所以未重复无关空库/旧迁移升级、前端构建、在线依赖公告扫描或其他任务全量测试。T02 原有 CI 阻断和 T03 批准/迁移装配状态仍需各自处理。共享 Gitleaks 文件唯一新增内容为 R07 的精确误报例外，其技术效果已核验；没有扩大为对其他发现的豁免。

## 6. 下一轮条件与收尾

1. 修复 R03 的默认端口规范化，提供可复验回归，沿用 R03，不另造编号或覆盖本轮失败记录。
2. 提供可用的受控真实 S3 测试环境，补齐 B01/R04 关闭证据；没有环境时继续保留明确的待验状态。
3. 回归受影响的签名/HTTP 路径并复核冻结指纹和最终 CI 扫描；无需因本轮已关闭项而重做无关功能。

结束前 [after.json](T04-round2/after.json)、[integrity.json](T04-round2/integrity.json) 确认：572 个既有文件的内容未变，HEAD 未变；包括历史报告/证据、作者整改和冻结文件。所有本轮 PostgreSQL 及 HTTP 测试服务已停止；停止后的临时集群和构建副本留在本轮隔离 `.work/`，未清理他人资源。未修改业务实现、提交、合并、发布、切换分支或联系其他任务。

本轮结论仅覆盖 T04 当前工作区整改，不代表 G1、完整产品或生产上线通过。
