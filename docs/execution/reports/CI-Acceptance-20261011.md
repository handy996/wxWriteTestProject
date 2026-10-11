# 干净检出 CI 验收（2026-10-11）

验收分支：`codex/ci-clean-checkout-acceptance`；仓库：[handy996/wxWriteTestProject](https://github.com/handy996/wxWriteTestProject)。本记录与修复在分支上，尚未合并到 `main`。

## 范围及修复

- `c121111`：将扫描分开，已有构建成功时让独立检查在其他门禁失败后继续执行；保留所有真实失败退出码。T08 报告复制移入 `finally`，即使 Maven 测试失败也导出 XML；上传原始目录作为后备。新增隔离副本中的真实 JUnit 失败探针。
- `2a232ac`：完整检出历史供 T02 生成器读取已审基线。Compose 后端构建改用仓库根上下文，只放行后端源码、schema 和冻结夹具，容器内仍执行 Maven `verify`。
- Boot 4 迁移按用户决定单独登记：[迁移范围与完成标准](../plans/Boot4-Migration.md)。本轮未升级框架、未增加漏洞豁免。

## 实际运行链

1. [main 初始运行 38112558406](https://github.com/handy996/wxWriteTestProject/actions/runs/38112558406)，提交 `4e79cb925c5f180f6c2fe65999b415f7148b8875`：Cookie 与成本测试通过；Maven OSV 两项公告导致失败，后续检查被跳过。失败工件实际下载成功。
2. [第一轮修复运行 38113033655](https://github.com/handy996/wxWriteTestProject/actions/runs/38113033655)，提交 `c121111d7c3e210ce41b3e495d8015cfe83ea353`：故意失败探针及上传通过；独立执行暴露浅检出缺历史基线、Docker 构建缺冻结夹具。已下载 ZIP 并复算其 SHA-256、失败 XML SHA-256，六项探针检查全部为真。
3. [输入修复后运行 38146179873](https://github.com/handy996/wxWriteTestProject/actions/runs/38146179873)，代码提交 `2a232ac272d681cb8f3d14d23650e11411d9e462`：完整执行结束，唯一失败步骤为 Maven OSV。下载工件后复算结果如下；后续文档提交不改变该代码验收 SHA。

检出后检查工作树为空、`.tools`/`.work` 不存在，记录 HEAD，再下载校验固定工具链并生成当次证据。完整历史检出不等于复用本地工具或测试产物。

| 验收项 | 最终结果 |
|---|---|
| Cookie 当次证据 | 15 项，失败/错误/跳过均 0；JDK 21.0.12.1；XML 摘要与 binding 一致；106 负向拒绝、36 良性通过 |
| 正常成本测试 | 28 单元 + 37 真库 = 65 项，失败/错误/跳过均 0；集群停止 |
| 构建与拓扑 | 前后端、SBOM、Compose 冷启动/重复迁移、开发入口 up/down/up 全部通过 |
| 密钥与 npm | Gitleaks 零命中，控制 223/223；npm 漏洞 0 |
| Maven OSV | 查询 78 包；Spring MVC 命中 2 项公告，保持失败 |
| 失败报告 | 真实失败探针 29 项中 1 项失败，runner exit 1；其余五项检查也为真；下载后失败 XML 摘要吻合 |

[最终工件 11704783222](https://github.com/handy996/wxWriteTestProject/actions/runs/38146179873/artifacts/11704783222) 已实际下载，97 个文件、293432 字节；到期时间为 `2027-01-09T14:11:32Z`。ZIP SHA-256：

```text
a4c3f66117fdd64d84beb188914b6943c43001eeac350fbcc22f870209dabb31
```

紧凑验收收据见 [acceptance.json](../../../tests/engineering/CI/evidence/20261011/acceptance.json)；保留运行步骤、工件元数据、原始扫描结果及 XML 复算计数。GitHub 标注的 ZIP 摘要与本地下载件一致。主工作区的 `.work/ci-acceptance-20261011/acceptance-final.zip` 保留完整下载件，未重复提交构建目录。最终默认 Maven 汇总为 305 项、0 失败、0 错误、149 跳过，适用边界见下文。

## 验收边界

- “65 项零跳过”专指正常成本套件：`CostPricingTest` 28 项与 `T08PostgresTest` 37 项。Maven 默认构建仍包含按外部环境开关跳过的其他数据库测试，不能称全部测试零跳过。
- 故意失败探针只在隔离副本新增 `ciReportRetentionFailureProbe`：29 项中恰好 1 项失败，运行器非零退出、集群停止、原源码不变、失败 XML 存在并可从工件下载。探针不计入正常 65 项，也不替代 T03 记录器拒绝发布的真实 Java 前后对照。
- 独立检查通过不覆盖 OSV 失败。Spring MVC 6.2.19 的 `GHSA-j9f9-w8pj-32f8` / `GHSA-pc63-qcmh-9cmg` 保持阻塞，完整流水线尚不能判通过。
- T02/T03 独立复审、T03 人工批准、T04 私有桶、T08 来源判据绕过、缺 SBOM 诊断等既有问题不因 CI 实跑而自动关闭；G0/G1/G2 不提升。主工作区原有 `docs/execution/reviews/T08-round6/` 保留，未纳入本次提交。

## 复跑与证据

推送修复分支或手工触发 `.github/workflows/ci.yml`；不要使用跳过测试、漏洞豁免或 `continue-on-error` 获得绿灯。下载运行中的 `t02-build-evidence`，核对 `.work/ci/checkout-sha.txt`、Cookie XML 与 binding、两份成本 XML、三份扫描 JSON、Compose 记录和失败探针 XML。工件有保留期，验收摘要须同时记录其 ID、到期时间和 ZIP 摘要；本文仅存必要摘要，不在源码树复制全部构建产物。
