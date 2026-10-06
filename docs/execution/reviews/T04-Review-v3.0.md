# T04 第三轮独立审核

日期：2026-10-04（Asia/Hong_Kong）。对象：当前工作区的第二轮问题整改。上轮：[T04-Review-v2.0.md](T04-Review-v2.0.md)。

**结论：BLOCKED。R03 默认端口签名缺陷已关闭，本轮没有发现需要修改的新增实现、测试或交付缺陷。R04 / B01 仍缺真实 S3 环境的必要验收证据；协议与实际 HTTP/TLS 传输测试不能替代真实桶验收，因此尚不能给出 PASS。**

## 1. 审核对象、依据与变更边界

- 分支：`appmod/java-upgrade-20261003114404`；HEAD：`b115a4022375675c7cbff536b239508db8f3f4e1`，上一提交 `74c2525`。T04 原始交付及两轮整改仍属于未提交工作区内容，没有可独立标识这些修复的提交。
- [before.json](T04-round3/before.json) 固定本轮开始的 **648 个既有文件** SHA-256、Git 状态、分支和提交。比较基线为第二轮工作区指纹，不能仅用 HEAD 代表本次审核对象。
- 与第二轮比较，仅三个既有文件改变：`backend/src/main/java/com/example/editorial/storage/SigV4.java`、同目录 `S3StorageBackend.java`、`infra/storage.env.example`。新增作者端点测试、第二轮整改说明和相关证据。具体见 [input-comparison.json](T04-round3/input-comparison.json)；两个生产文件逐行差异见 [source-diff.json](T04-round3/source-diff.json)。
- 作者 [T04-Revision-v2.0.md](../reports/T04-Revision-v2.0.md) 对应交付的 **34/34 指纹匹配**；批准契约 **27/27 匹配**。本轮没有运行契约生成器，也没有以作者“通过”结论替代独立运行。
- 依据沿用 SRS 第 25.3、31–35 节、执行计划 T04 任务卡及共享文件/审核约定、已批准 rc.3 OpenAPI/Schema、ObjectStore 端口、表归属、hash/事务/清理约定及相关 ADR。上述批准输入未变；无新增适用 AGENTS.md。上游状态及第一、二轮已验证的边界保持不变。

T02/T03/T05 的其他工作区改动不属于本轮整改。整改未改变权限、数据库事务、Local 下载、迁移、依赖清单或 CI 规则，没有借复审新增功能或依赖。原始交付、历史审核和作者证据均保留。

## 2. 待修复问题与环境阻塞

**本轮没有新增或仍为 OPEN 的可行动代码问题，不新增问题编号。**

**B01 / R04：真实 S3 验收仍 BLOCKED。** 宿主只读检查确认 Docker 客户端 29.8.1 存在，但 `dockerDesktopLinuxEngine` 命名管道不存在，`docker version` 和 `docker image ls` 均退出 1；不能推断 Docker 未安装，也不能推断宿主没有镜像。证据：[docker-inventory.json](T04-round3/docker-inventory.json)。作者整改说明继续明确没有可用测试桶；本轮未获得其他可验证的真实桶证据。

本轮未启动 Docker、拉取镜像或创建容器，没有把环境失败归因于实现缺陷。未验证的是实际 S3 服务端验签、私有桶权限及对象全链路和真实分页清理/恢复。这直接限制 T04 两种存储适配器与 R04 关闭条件的完整确认。上轮解析/元数据实现问题已经修复，不能因环境未具备重新写成 OPEN。

## 3. 历轮问题状态

| 编号 | 本轮状态 | 依据及关闭范围 |
|---|---|---|
| T04-R01 | CLOSED，保持 | 相关实现及测试指纹未变；沿用第二轮真实 PostgreSQL 并发交错、锁等待及事务回滚证据，本轮未重跑数据库测试。 |
| T04-R02 | CLOSED，保持 | Local 正文缺失/截断/同大小篡改拒绝及引用事务回滚路径未变，沿用第二轮证据。 |
| T04-R03 | **CLOSED，本轮关闭** | 同一套断言对带第二轮指纹的旧实现复现失败，对当前实现全部通过；默认 HTTP/HTTPS 端口、非默认端口、virtual-hosted、普通签名和预签名路径均验证。真实 S3 全链路限制统一保留在 B01，不把传输验证写成真实桶成功。 |
| T04-R04 | **BLOCKED，保持** | 本轮重新通过分页、metadata HEAD、特殊 token、坏 XML/XXE/异常拒绝等协议回归。真实桶分页清理/恢复仍待 B01 环境。 |
| T04-R05 | CLOSED，保持 | Local handler 与安全链未变，沿用第二轮实际 Tomcat/Spring Security/PG 验证。 |
| T04-R06 | CLOSED，保持 | 崩溃残留枚举与恢复的实现未变，沿用第二轮磁盘状态注入和失败关闭证据。 |
| T04-R07 | CLOSED，保持 | 本轮完整 Gitleaks 复跑：T04 及本轮证据零命中；旧证据和精确误报例外未变。 |
| T04-N01 | CLOSED，保持 | preview 无副作用路径未变，沿用第二轮证据。 |
| B01 | **BLOCKED，保持** | 缺真实 S3 测试环境；本轮宿主检查仍无法连接 Docker daemon。 |

R03 修复位于 `SigV4.java` 第 79、103–122 行及 `S3StorageBackend.java` 第 77–78 行：scheme 对应的默认端口在构造请求 URI 和 URI 签名入口统一移除，原始路径/查询不重新编码，非默认端口保留。未设置全局受限 Host 头豁免，也未放宽 TLS 验证。

## 4. 独立验证和证据

| 检查 | 结果 | 证据 |
|---|---|---|
| 当前源码全新副本 clean test | **24 执行，24 通过，0 失败、错误或跳过；退出 0** | [current-verification.json](T04-round3/current-verification.json)、current-results/ |
| 旧源码对照 clean test | **24 执行，6 个预期断言失败，0 错误或跳过；退出 1** | [old-verification.json](T04-round3/old-verification.json)、old-results/ |
| 批准契约检查 | 27/27，无重新生成，退出 0 | [versions-contracts.json](T04-round3/versions-contracts.json) |
| CI 同版本完整 Gitleaks | 8.30.1，退出 1；仅 6 项原有 T02 指纹误报，T04 和本轮审核证据零命中 | [scans.json](T04-round3/scans.json)、gitleaks-findings.json |
| Git 空白检查 | 退出 0 | scans.json |
| 审核完整性与收尾 | 648 个既有文件内容未变，分支/HEAD 未变；80 端口可重新绑定，两次构建的 Java 临时目录为空 | [integrity.json](T04-round3/integrity.json)、[result-summary.json](T04-round3/result-summary.json) |

环境：Windows 11、本机 Temurin JDK 21.0.12.1+1、Maven 3.9.11、Surefire 3.5.6、现有离线依赖缓存。24 项由作者 23 项受影响 S3 回归和审核方 1 项独立实际请求复现组成。包含两组已固定的 AWS 签名向量；没有改动任何已有预期签名。

两个构建都从当前源文件和 pom 复制到本轮不同的 `.work/` 子目录并 clean 编译，不使用原 `backend/target`。旧版对照仅将两个改变的生产文件替换为第二轮隔离副本中的源码，替换前逐个核对第二轮 SHA-256；来源与指纹记录在 old-verification.json。其余源码和测试一致，因此不是使用作者旧构建结果冒充独立对照。

独立 [EndpointAuthorityTest.java](T04-round3/EndpointAuthorityTest.java) 由第二轮测试复制，只去掉“旧版带端口错误签名应相等”的诊断断言，保留“签名必须等于实际 wire Host 重算结果”的正确行为断言。旧文件未修改，两次构建使用相同新测试。结果分别为：

```text
endpoint = http://127.0.0.1:80
wire Host = 127.0.0.1
旧实现 signature matches wire = false
当前实现 signature matches wire = true
```

另 5 项旧版失败为四个 HTTP/HTTPS 默认端口组合的签名一致性断言，以及直接签名器的默认端口等价断言。均不是连接、证书、编译或端口绑定错误。修复版 9 种端点组合均实际发送普通 PUT 和预签名 GET；TLS 经本地 CONNECT 代理真实握手，测试专用证书仅由该 HttpClient 信任，目标主机名校验保持启用。IPv6/编码路径/查询与双斜杠覆盖属于直接签名器断言，**没有宣称实际 IPv6 网络验证**。

接收端返回受控响应，没有执行 S3 服务端验签或桶授权，所以其返回 200 不作为真实 S3 成功证据。测试中的 Future 异常会传播，失败断言确实执行；两次构建都没有跳过测试。独立运行器保留 Maven 非零退出码。

完整扫描使用 CI 实际配置的 8.30.1、同一规则和 Git 可见文件选择，仅将副本和输出改到本轮目录。外层扫描收集器退出 0 表示证据收集完成，**内部 Gitleaks 仍退出 1**；全局 CI 不能称为通过。6 项均来自未改变的 `tests/engineering/T02/evidence/r01-integrity.json` 第 67、110、111、115、124、125 行的文件 SHA-256，不是真实凭证泄露，属于原有 T02 问题，不重复包装成 T04 新缺陷。

复現入口见 [review.py](T04-round3/review.py) 的 `snapshot/current/old/versions/docker/summary/final` 模式与 [run_scans.py](T04-round3/run_scans.py)。完整 argv、退出码和关键输出在上述 JSON。后续运行应复制到新审核目录，避免覆盖历史扫描文件；构建/指纹运行器会拒绝覆盖已有同名证据。测试身份及签名均为公开或专用测试夹具，没有使用真实服务凭证。

## 5. 未验证项和下一轮条件

1. 提供可用的受控真实 S3/MinIO 私有测试桶或可运行的等价本地服务，继续 B01 / R04，不新增问题编号。
2. 核验 PUT→HEAD→GET→完成标记→五分钟签名下载→DELETE、匿名未签名访问拒绝，并覆盖过期孤儿、历史引用、hold、新对象及跨页清理/恢复；记录真实响应、数量和失败原因。补齐后再判断是否可 PASS。
3. 若后续只补环境证据，不必重做未改变的 Local/数据库功能；若实现或契约变化，则按实际影响补回归和指纹核对。

本轮未启动 PostgreSQL，未重跑不受本次改动影响的数据库/Local 验收、迁移升级、前端、依赖扫描或远程 CI。未宣称生产 HTTPS、Linux 部署、完整应用装配、后续领域或生产上线已验收。真实 TLS 传输测试也不等于生产证书/网络部署验证。

## 6. 审核收尾

本轮只新增本报告和 `T04-round3/` 独立证据。结束核对见 before.json、after.json、integrity.json：648 个既有文件未改变，包含作者实现、冻结文件、历史报告和作者证据，分支及 HEAD 保持原值。测试服务随测试结束停止，独立 HTTP 端口已释放，临时证书目录已清空；构建副本留在本轮被忽略的 `.work/`。没有清理他人资源、修改实现、提交、合并、发布、切换工作区或联系其他任务。

本结论仅覆盖 T04 当前工作区及上述已验证环境。
