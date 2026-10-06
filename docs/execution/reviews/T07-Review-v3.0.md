# T07 第三轮独立审核

日期：2026-10-06（Asia/Hong_Kong）。结论：**CHANGES_REQUIRED，新增 1 项 P2 契约问题：T07-R03。** R01、R02 保持关闭。本轮分页容量实现及相关运行回归通过，但增量接口的机器可读鉴权声明遗漏，暂不批准完整 T07 或正式关闭 CR-T07-01。

## 1. 受审版本

审核提交 **`c12738f6eff55e3c2cda6190df38cd165bfa7457`**，相对正式集成基线 `5413cf4` 的 37 个变更文件，以及 [T07-Revision-v2.0](../reports/T07-Revision-v2.0.md)。开工和结束核对 1,737 个已跟踪文件，均保持不变，见 [input-snapshot.json](T07-round3/input-snapshot.json) 和 [checks.json](T07-round3/evidence/checks.json)。

这次直接测试正式源码、组合根和 V1–V4 迁移；没有再把旧 T06/T07 扩展补丁叠加到已集成源码。独立运行 `verify_boundaries.py` 确认正式迁移、ArticleService、CanonicalRequest 和两份组合根与集成前受审快照及声明的变换对应。T06 早期 PASS 不因此自动扩张至完整集成版本。前两轮审核报告、反例和证据相对 `ab956ec` 没有变更。

本轮只新增审核方文件，没有修改实施源码、增量契约、作者材料或历史证据，没有提交 Git。

## 2. T07-R03 · P2 · 分页 OpenAPI 漏掉 Session 鉴权契约

位置：[diff-pages-v1.1.openapi.yaml](../../api/diff-pages-v1.1.openapi.yaml:6)，以及第 43 行起的 components。

新文件是一份可以单独校验和消费的 OpenAPI 3.1 文档，但既没有根级或操作级 `security`，也没有 `components.securitySchemes`。原冻结 OpenAPI 则显式要求 `session`，以 `EDITORIAL_SESSION` Cookie 承载。新文件的 description 和 401 响应描述不会自动继承另一份 OpenAPI 的鉴权定义。

因此，按新契约独立生成的客户端或接口调用 agent 无法从机器可读鉴权配置获知必须携带登录 Session，可能把分页操作当作无鉴权操作调用，实际却收到 401。新接口正是解决大版本 Diff 的必需入口，这个差异会影响后续客户端独立接入。

独立证据：

- [ReviewDiffHttpTest](T07-round3/ReviewDiffHttpTest.java) 通过真实 HTTP 确认新路由匿名访问返回 **401**，登录后正常返回分页。这是契约遗漏，**不是实际接口匿名可访问或数据泄露的证据**。
- [checks.json](T07-round3/evidence/checks.json) 的 `contract` 记录：期望 `security=[{"session":[]}]`，实际 `null`；期望 Cookie scheme，实际 `null`。标准 OpenAPI 结构校验通过，但审核方的鉴权一致性校验失败，检查脚本整体退出 **1**。
- 现有 `verify_diff_page.py` 只验证结构和响应 Schema，未检查有效 security requirement，因而不能捕获该问题。

修复要求：在增量 OpenAPI 中声明与冻结契约一致的 Session Cookie scheme，并在根级或 GET 操作上明确引用；保留现有服务端登录限制和旧冻结文件。补充自动化校验，验证该路由有效的 security requirement 及 scheme 的 type/in/name，继续保留真实 HTTP 匿名 401、登录成功的回归。仅补写文字说明或 401 描述不足以关闭本项。

## 3. 容量方案及旧问题复核

本轮认可“保留旧 Diff，增加分页契约”的兼容方向：旧路由仍在超过 1,000 行时明确拒绝，未改 T00 rc.3 返回体；新路由通过不可变版本 ID 和签名游标绑定 Owner、文章、from、to、limit，按固定顺序读取全部行，没有截断伪装完整结果。容量功能已得到以下独立证据支持；CR-T07-01 的正式关闭待 R03 修复及增量契约复审完成。

- 对两端各 30,000 块、完全不同 ID 的合法 AST，审核新增测试遍历 **601 页、60,002 行**，逐行核对位置、ID、ADD/DELETE 类型和前后文本，没有只抽查首尾页。
- 小版本混合修改、重排、新增和删除，在 1、2、3、7、100 的页大小下，拼接结果均与旧路由完整 Diff 一致。
- 原作者真实 PG/HTTP 测试完整读完 1,004 行，验证旧接口超限拒绝、签名篡改、版本和页大小重绑。审核新增 HTTP 测试补充匿名 401、游标跨文章拒绝、跨文章版本先返回 404、非法页大小拒绝。
- 第一轮 R01/R02 原始反例 **2/2** 通过，第二轮四项修订边界回归 **4/4** 通过，原有晚到 AI、恢复、提案接受、事务回滚及 T06 Markdown 回归继续通过。

没有发现本轮新增的 Java 行为缺陷；本轮唯一新增问题是上面的可执行接口契约缺口。

## 4. 独立验证结果与证据

| 检查 | 结果 |
|---|---|
| 正式组合根隔离 clean test | **78/78 通过，0 failure/error/skipped**：交付用例 75 项，审核新增 3 项 |
| 最大容量独立全量遍历 | 601 页、60,002 行逐行验证通过，属于上述 1 个测试方法，不另计测试数 |
| 标准响应 Schema | **12/12 通过**：原 11 份样本及实际 DiffPage 响应，Draft 2020-12 + FormatChecker |
| 新 OpenAPI 结构 | 通过；**鉴权语义一致性失败，R03** |
| 冻结保护 | T00 rc.3 **27/27** 哈希一致 |
| 正式集成边界 | `verify_boundaries.py` 通过 |
| 密钥扫描 | 使用当前项目配置和完整 Git 可见文件集，Gitleaks **退出 0、0 告警**；T02 既有精确例外来自正式集成，本轮未改扫描规则 |
| Git diff 空白检查 | 通过 |
| 输入完整性 | 1,737 个已跟踪输入均未改动 |
| 数据库清理 | 本轮两次临时 PostgreSQL 均已停止，stop 退出 0 |

最终执行证据：[final.json](T07-round3/evidence/final.json)、[JUnit](T07-round3/evidence/final-test-results/)、[全部检查](T07-round3/evidence/checks.json)。测试直接使用已合入的正式生产源码和迁移，只重定向测试样本目录并加入审核测试，实际执行副本指纹保留在运行记录中。

首次运行 [current.json](T07-round3/evidence/current.json) 为 78 项中 1 error：审核方新增的小版本夹具只有 4 字，触发既有最短正文限制 `CONTENT_LENGTH_INVALID`。这是审核夹具错误，没有计作实施缺陷；修正为合法长度后另建 final 证据，未覆盖初次输出，原夹具保存在 [ReviewDiffPageTest-initial.java](T07-round3/evidence/ReviewDiffPageTest-initial.java)。

本轮未重复执行未变化的升级场景或作者报告中的默认全后端测试，不将其列为本轮新通过结果。真实 T10/T11/T16/T19、QA/Approval/导出、S3 和崩溃恢复仍未完成；相关事务与引用适用性测试使用明确替身。当前数据库验证证明本轮正式组合下的 T07/T06 行为，不替 T03/T04 或其他任务补签独立验收。

复跑入口（仓库根目录，允许启动本机临时 PostgreSQL，使用新 evidence-name）：

```powershell
& 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/execution/reviews/T07-round3/run_review.py --include-review-regressions --evidence-name after-r03
```

下一轮以 R03 的契约修复和鉴权一致性回归为重点；若只改 OpenAPI/校验器，不必无理由重复全部未变化的后端和迁移测试。关闭 R03 后再正式确认增量契约和 CR-T07-01 的验收状态。
