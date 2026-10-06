# T04-Review-v2.0 整改说明

日期：2026-10-04（Asia/Hong_Kong）。依据：[第二轮独立审核](../reviews/T04-Review-v2.0.md)。

**R03 的显式默认端口缺陷已修复，受影响路径 23 项回归通过，0 失败、0 跳过。B01 / R04 的真实 S3 验收继续保留待验；本说明不代替独立复审。**

## 1. R03 修复

`SigV4.withoutDefaultPort` 统一去除 HTTP 的显式 `:80` 和 HTTPS 的显式 `:443`。`S3StorageBackend` 先用它构造实际请求 URI，普通签名与 presign 的 URI 入口也使用同一处理。配置与不写默认端口时产生相同的签名 authority，避免 JDK 自动生成的 Host 与签名输入不一致。

该处理仅去除匹配 scheme 的默认端口。非默认端口、桶子域、IPv6 方括号、路径中的双斜杠及已编码的路径/查询内容保持原样，不调用 URI 路径规范化，不重复编码。未设置受限 Host 头，未改变全局 JVM 受限头规则或 TLS 校验规则。

仅修改两个生产文件 `S3StorageBackend.java`、`SigV4.java`，并更新 `infra/storage.env.example` 的端口说明。未修改已关闭问题的实现、冻结契约、构建依赖、迁移、身份模块或 T02 扫描规则。

## 2. 修复前后证据

新增 `S3EndpointAuthorityTest`，在同一套正确行为断言下分别测试修复前与修复后实现。每次都复制源码和原 pom 到新的隔离目录后执行 `Maven clean test`，不复用 `backend/target`。

| 检查 | 修复前 | 修复后 |
|---|---|---|
| 新增端点回归（10 项） | 5 失败、5 通过；无错误/跳过 | 10 通过 |
| 既有 S3 协议及签名测试（13 项） | 13 通过 | 13 通过 |
| 合计 | 23 执行、5 失败，退出 1 | **23 通过、0 失败、0 跳过，退出 0** |

新增测试覆盖：

- 实际 HTTP 请求：无端口、显式 `:80`、非默认 `:19000`。
- 实际 TLS 请求：无端口、显式 `:443`、非默认 `:19443`。
- virtual-hosted：HTTP `:80`、HTTPS `:443`、HTTP `:19000`。
- 上述 9 种组合分别发送真实 JDK PUT 和预签名 GET，捕获实际 Host、请求目标、正文和签名头；普通签名根据捕获的 Host/元数据/正文重算，预签名根据捕获的 Host/路径重算，均断言一致。
- 直接调用签名器时，默认端口与省略端口结果相等，并保留 IPv6、已编码路径/查询和双斜杠。

测试接收端使用回环地址上的临时代理端口，HTTPS 通过 CONNECT 隧道完成实际 TLS 握手，以便不占用本机 80/443、不依赖公网 DNS。证书由本机 JDK keytool 临时生成，仅被该测试 HttpClient 信任，仍校验目标主机名。测试结束关闭 socket、客户端和执行器；测试证书由 JUnit 临时目录清理。

这验证的是实际 JDK 传输行为和签名一致性，**不是 S3 服务端验签或真实桶联调**。修复前的四个端点组合（path-style / virtual-hosted 各自的 HTTP `:80`、HTTPS `:443`）明确失败于签名与捕获 Host 不一致；另一个失败是直接签名器的默认端口等价性。没有把连接、绑定端口或证书错误当作缺陷复现。

两组既有 AWS 官方签名向量继续通过。依据保留在原 `S3ProtocolRegressionTest`；未替换预期签名以迁就实现。

证据：

- [修复前构建](../../../tests/engineering/T04/revision2/before-fix.json)及[测试结果](../../../tests/engineering/T04/revision2/before-fix-results/)。
- [修复后构建](../../../tests/engineering/T04/revision2/after-fix.json)及[测试结果](../../../tests/engineering/T04/revision2/after-fix-results/)。
- [完整性与交付指纹](../../../tests/engineering/T04/revision2/integrity.json)：619 个起始文件中，仅上述 3 个既有文件变更；27 项批准契约指纹一致。所有旧审核、旧整改报告和旧证据保持原文。
- [CI 同款扫描](../../../tests/engineering/T04/revision2/scans.json)及[扫描发现](../../../tests/engineering/T04/revision2/gitleaks-findings.json)：Gitleaks 8.30.1 完整规则、全部 Git 可见文件集；T04 无命中，全局剩余 6 项均来自 T02 原有 `r01-integrity.json`，故扫描全局退出仍为 1。Git 空白检查退出 0。

## 3. 复现

从项目根目录运行，`--name` 使用新的名字，工具会拒绝覆盖旧构建证据：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' `
  tests/engineering/T04/revision2/verify.py --name recheck
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' `
  tests/engineering/T04/revision2/check_integrity.py
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' `
  tests/engineering/T04/revision2/run_scans.py
```

工具使用现有 Temurin JDK 21.0.12.1+1、Maven 3.9.11、Surefire 3.5.6 及离线依赖缓存。独立复审请复制验证工具到新目录并调整证据输出位置，避免覆盖本轮完整性/扫描记录。

## 4. 保留的待验状态

沿用用户此前确认的“暂无测试桶，保留待验状态”，本轮没有重新索要凭证、启动 Docker 或尝试拉取镜像。**B01 及 R04 真实桶分页清理/恢复仍为待验**；R03 的代码缺陷已修复，其真实 S3 全链路证据仍受同一环境限制。

已有环境后仍须运行私有桶 PUT→HEAD→GET→完成标记→五分钟签名下载→DELETE、匿名拒绝，以及过期孤儿/历史引用/hold/新对象/分页的清理与恢复核验。

按第二轮审核的范围约定，本次只回归受影响的 S3 签名/HTTP 路径；未重复已关闭的 Local/数据库事务验收，未运行其他任务全量测试、前端、远程 CI 或生产部署。未提交、合并或切换分支。
