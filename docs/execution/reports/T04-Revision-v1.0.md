# T04-Review-v1.0 整改说明

日期：2026-10-04（Asia/Hong_Kong）。依据：[T04 首次审核](../reviews/T04-Review-v1.0.md)。

**实现整改已完成，T04 回归 54 项通过、0 失败、0 跳过。R03/R04 的真实 S3 验收仍待 B01 环境解阻；本说明不替代独立复审，不宣布 G1 或生产验收通过。** 用户已明确确认“暂无测试桶，保留待验状态”。

## 1. 逐项整改

| 编号 | 改动与预期行为 | 验证 / 状态 |
|---|---|---|
| R01 | 新增 `ObjectTransactionLock`，引用提交与清理共用 PostgreSQL 按对象的事务级 advisory lock。引用锁一直保持到外层领域事务提交或回滚；清理在独立 READ COMMITTED 事务内取得同一锁，再检查当前状态、当前/历史引用及 hold，最后删除。拒绝快照隔离调用，避免旧快照忽略已提交引用。 | 真实 PG 的两种并发交错均通过：清理先取得锁时，竞争提交明确失败且领域行和提交审计回滚；引用先取得锁时，清理等待外层提交，最终对象可读、引用保留。测试通过 `pg_locks` 确认实际锁等待，使用两个 service/transaction manager 实例。实现待复审。 |
| R02 | Local HEAD 检查真实字节、大小与 SHA-256；`commitReference` 在数据库提交前调用后端真实内容校验，完成标记也校验正文。缺失、截断、同大小篡改均明确拒绝。 | 三类反例均改为断言拒绝：无 `OBJECT_COMMITTED` 审计、元数据仍为 STAGING、不能获得下载链接。正常路径原测试继续通过。实现待复审。 |
| R03 | 普通请求和签名链接均从实际 URI 派生路径与 authority，保留 scheme/port；空查询串不再写入 `null`。virtual-hosted 模式实际请求也使用桶子域；不设置受限 Host 头、不放宽 JVM 限制。完成标记 COPY 签入全部替换元数据，并拒绝 HTTP 200 内嵌错误及未生效的完成状态。 | AWS 官方 GET Authorization、预签名两组已知向量通过；默认端点、带端口、virtual-hosted、空查询串及 COPY 元数据覆盖通过。**真实私有桶全链路待 B01**。 |
| R04 | 用禁用 DTD/外部实体的 XML 解析器读取 ListObjectsV2，按 key 获取实际元数据，移除全零 hash/size 占位。支持 continuation token、百分号编码、命名空间及重复 token 防循环；列表、XML、元数据和非 404 HEAD 失败明确报错。创建时间缺失不再默认成可过期的 epoch。 | 受控 HTTP 两页列表返回两个合法非空对象，实际发生两次 metadata HEAD；含特殊字符 token 正确编码；坏 XML、XXE、缺 token、HEAD 失败均拒绝。此服务是协议测试替身。**真实桶清理/恢复数量待 B01**。 |
| R05 | 新增 `LocalDownloadHandler` 和条件启用的路由配置，消费 `GET /api/v1/storage/objects/{key}`。验证 HMAC/到期时间/重复参数、COMMITTED 状态和真实内容；重新核对引用及撤销；使用可信 trace、安全错误响应、attachment/no-store/nosniff。 | 真实 Tomcat/Spring Security/HTTP 验证正确字节，未签名、过期、篡改、重复参数、未知、撤销和缺文件拒绝。另以真实 PG 执行 stage→commit→Owner 授权→HTTP 下载，另一 Owner 和匿名无法获链接。禁用存储或 S3 模式不注册 Local 入口。实现待复审。 |
| R06 | 枚举正文和元数据两类文件。缺少 sidecar 的合法 UUID 正文按实际 hash/size/mtime 构造恢复候选；枚举不写文件。清理仍逐对象加锁并核对引用、hold 和 TTL。缺正文的 STAGING sidecar 也可在无引用且过期时清除。 | 故障点磁盘状态测试覆盖正文已发布/元数据缺失、仅余元数据、过期临时片段；孤儿清除、历史引用恢复 COMMITTED、hold/新对象保留。未声称执行了真实杀进程或生产磁盘故障。实现待复审。 |
| R07 | 新日志用 `objectId` 标识对象。保留旧 evidence 原文，在现有完整规则配置中仅添加“指定历史文件路径 AND 指定单个对象 UUID”的误报例外。 | CI 同款 Gitleaks 8.30.1 全部 Git 可见文件扫描：T04 0 命中；全局退出 1 的剩余 6 项均来自 T02 原有 `r01-integrity.json`。未排除 evidence 目录、未关闭检测器。实现待复审。 |
| N01 | preview 不调用临时文件删除，恢复枚举也不补写 sidecar。 | 预览后临时文件、正文和缺 sidecar 状态保持不变；live 才清理。建议已处理。 |

## 2. 集成决定与边界

本次主任务直接集成 storage 所属的 Local 下载 handler、路由和窄范围安全链，修正旧交付报告把下载服务延期到 T23/T29 的建议。入口只有 `editorial.storage.enabled=true` 且 mode=local 才启用；安全链只处理该下载前缀的 GET。已签名链接是 5 分钟 bearer capability，Owner 校验发生在签发前，使用链接时再次检查撤销/引用和存储状态。

完整应用的 T03 Session/CSRF 装配和真实领域表仍归上游/领域任务。本轮使用真实 Servlet 容器与生产下载组件验证该入口，不声称已完成整个应用身份链。签名链接不得写入访问日志或共享给无权人员；当前 handler 不记录 URL、签名或正文。

`ObjectRef` 五字段 DTO、ObjectStore 三方法、OpenAPI、冻结契约、迁移、根构建及其他任务实现均未修改。T02 唯一改动是 `gitleaks.toml` 的 R07 精确误报例外，由本主任务集成；T02 的 6 个旧误报未扩大处理范围。

领域接入约束：

- 引用行插入与 `commitReference` 必须处于**同一个 READ COMMITTED 事务、同一数据库**，调用失败必须回滚。所有新增引用走这个协议。
- 新增 hold 时，在同一事务用 `ObjectTransactionLock.acquire` 加锁，并确认对象仍存在后写入 hold。多个对象时使用固定排序取得锁以减少死锁。
- `ObjectRefRegistry.referenced/held` 使用当前事务连接查询当前及历史领域表，不得读延迟副本或缓存；没有 registry 时保留全部候选。该 SPI 的真实领域实现仍由领域任务提供。
- Local 是开发后端；生产 POSIX 权限及真实磁盘故障仍需相应平台验收。校验后发生的外部磁盘破坏不属于数据库锁可阻止的行为。
- S3 endpoint 不支持 path/query/fragment；virtual-hosted 要求 DNS endpoint 和无点桶名，不支持组合显式拒绝配置。

## 3. 实际验证与证据

最终命令为既有 T04 编排器加上测试选择和工作区临时目录参数。使用 PostgreSQL 17.11 临时集群、真实运行角色、Hikari、DataSourceTransactionManager、JdbcAuditSink、Local 文件系统及 Tomcat。Ownership 领域解析仍是测试替身；R01 的引用读写是真实 PostgreSQL 表，不是内存替身。

- [最终集成证据](../../../tests/engineering/T04/evidence/revision1-integration.json)：54 项通过、0 失败、0 跳过；包含启动、bootstrap、测试、停止和 `pg_ctl status` 无运行服务核验。新增 19 项正确行为回归，保留原 35 项测试。
- [测试报告](../../../tests/engineering/T04/revision1/test-results/)：最终 T04 Surefire XML/TXT。
- [扫描证据](../../../tests/engineering/T04/revision1/scans.json)、[扫描发现](../../../tests/engineering/T04/revision1/gitleaks-findings.json)：完整规则/文件集，T04 零命中，T02 6 项旧误报仍在；Git 空白检查通过。
- [起始指纹](../../../tests/engineering/T04/revision1/before.json)、[完整性核验及交付指纹](../../../tests/engineering/T04/revision1/integrity.json)：原始文件仅 10 项发生本次预期修改；旧审核、旧交付报告、旧 evidence 均保留，批准的 27 项契约指纹一致。
- [环境及失败尝试](../../../tests/engineering/T04/revision1/environment.json)：保留沙箱 PostgreSQL 令牌限制、JUnit 临时目录限制、两处 MinIO 拉取失败说明。两轮 HTTP 测试失败证据分别保存在同目录 `integration-attempt1.json`（测试隔离环境的 health group 配置）与 `integration-attempt2.json`（下载入口缺少 trace scope）；均已修复并在最终回归通过。

规范向量依据：[AWS Header 签名示例](https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html)、[AWS 预签名示例](https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sigv4-query-string-auth.html)、[ListObjectsV2](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html)。

## 4. 复现

在项目根目录运行（路径按本机现有工具安装位置）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' `
  tests/engineering/T04/integration.py `
  --pg-bin E:/project/codex/wxAgent/.tools/t02/postgresql-full/pgsql/bin `
  --mvn E:/project/codex/wxAgent/.tools/t02/apache-maven-3.9.11/bin/mvn.cmd `
  --java-home E:/project/codex/wxAgent/.tools/t02/jdk-21.0.12.1+1 `
  --m2 E:/project/codex/wxAgent/.tools/t02/m2 `
  --evidence-name revision1-recheck --tests 'com.example.editorial.storage.*Test'
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' `
  tests/engineering/T04/revision1/run_scans.py
```

新的复审请另建证据目录，避免覆盖本轮记录。沙箱若无法启动 PostgreSQL，需要在允许启动本机测试服务的执行环境运行；编排器只管理自己新建的临时集群。

## 5. 待验事项

**B01 保留：真实 S3 私有桶联调。** 固定 MinIO 版本在 Quay 返回 401，在 Docker Hub 返回 pull access denied；本机无缓存 MinIO 镜像，用户确认暂无测试桶。本轮没有创建任何容器、使用业务凭证或调用付费服务。R03/R04 不能仅凭协议服务与签名向量宣告全部关闭。

取得受控私有桶后，仍需执行实际 PUT→HEAD→GET→完成标记→签名下载→DELETE，验证匿名未签名读取拒绝；再以过期孤儿、历史引用、hold、新对象和分页数据验证清理/恢复数量。该待验不影响本轮已完成的 Local、事务并发及协议层修复。

未运行远程 CI、前端构建、其他任务全量测试或生产部署。未提交、合并或切换分支。
