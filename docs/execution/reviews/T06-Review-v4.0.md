# T06 第四轮独立审核

结论：**PASS（当前工作区 T06 交付范围）**。日期：2026-10-05（Asia/Hong_Kong）。**T06-R01 关闭，T06-R02 保持关闭，T06 OPEN 项为 0。** 本次修订通过独立复审；结论不等于整体 CI、跨域集成、G1/G2 或生产上线已获批准。

## 1. 审核基线

本轮审核 [T06-Revision-v3.0](../reports/T06-Revision-v3.0.md) 对唯一剩余 R01 的修复，并检查 R02 未回归。Git HEAD 仍为 `b115a4022375675c7cbff536b239508db8f3f4e1`；T06 是未提交工作区交付，该 HEAD 不是 T06 修订提交。

独立核对：820 个既有输入文件未变，6 项修订文件指纹全部匹配，20 项当前交付源码/测试/报告/接线文件指纹全部匹配。相对第三轮，变化集中于 ArticleAst、相关测试、隔离编排器及校验器；迁移草案、基础服务和共享补丁字节未变。

通过结论绑定 [input-snapshot.json](T06-round4/input-snapshot.json) 中的 `reviewedFiles`，不是对后续任意修改的持续批准。结束时再核验受审文件和前三轮审核报告、原始用例及失败证据，变化数为 0，见 [summary.json](T06-round4/summary.json)。

本轮仅新增审核报告、脚本与证据；未修改实施源码、作者材料或历史审核证据，未安装共享补丁、正式迁移，未提交 Git。

## 2. 审核项关闭依据

### T06-R01：关闭

当前解析规则结合分隔符两侧的 Unicode 空白、标点/符号与待闭合层级，按层级消耗共用闭合符。相较前一版，不再仅以“后接非空白”判断必须开启新强调。

本轮独立执行并确认：

- 前三轮原始测试源码不变，9 项全部通过，覆盖嵌套格式、三重强调、共用结束符、98/30,000 字边界及中文标点相邻场景。
- 表驱动回归覆盖 8 种强调结构 × 5 种后续位置，共 40 个组合，检查文本、mark 类型及码点范围。另有非 BMP 偏移、转义和字面星号检查；这些组合属于一个 JUnit 测试方法，没有额外计成 40 项测试。
- 真实 HTTP 创建测试确认 `***强调***。`、`*a **b***，后文` 返回成功，读取已持久化 Original 后，文本、marks 数量和 plainText 与预期一致；marks 类型及精确范围由 AST 组合测试补充验证。
- 98 字共用闭合符输入返回 422，article_job 数量不增加；合法 30,000 字输入成功创建。先前的格式/容量修复未回归。

这些证据足以关闭本轮已发现的解析缺陷。受限 Markdown 仍保持既定白名单和明确不支持结构的拒绝策略，本报告不宣称完整 Markdown 语法兼容。

### T06-R02：保持关闭

指纹仍采用 path/sha256 分字段记录。按项目真实 Git 可见文件扫描入口、现有配置独立复扫，**T06 新增告警为 0**；扫描整体退出 1，仅有既有 T02 `r01-integrity.json` 的 6 条指纹误报。未放宽共享扫描规则或修改 T02 原证据。

扫描证据：[gitleaks-findings.json](T06-round4/gitleaks-findings.json)、[checks.json](T06-round4/checks.json) 第 4 项。R02 关闭不代表整体 CI 已通过，T02 的遗留项仍按其审核记录处理。

## 3. 本轮独立验证

| 检查 | 实际结果 |
|---|---|
| 隔离 clean test | **48/48 通过，0 failure/error/skip** |
| AST 回归 | 14 项通过，包含上述 40 组表驱动断言 |
| 真实 PG/HTTP/Local 集成 | 19 项通过，包含修复后的创建与 Original 持久化验证 |
| 前三轮原始反例 | 9 项全部通过，原始源码未改 |
| 删除协议 | 2 项替身协议测试通过，不冒充真实删除系统 |
| 共享 canonical 回归 | 4 项通过，运行于隔离补丁副本 |
| 实际 ArticleArtifact / ArticleVersion 响应 | jsonschema 4.26.0、Draft 2020-12、FormatChecker：两份均通过 |
| T00 rc.3 保护 | 27 项通过 |
| T06 共享 patch 可应用性、Git diff 空白检查 | 通过；没有将 patch 安装到共享目录 |
| 源文件密钥扫描 | 退出 1，仅 T02 既有 6 条；T06 新增 0 条 |
| 已有数据升级 | 本轮不重复执行未变迁移；保留第二轮审核方独立 1/1 通过证据，不把作者新自测计作审核方新执行 |

证据：[current-host.json](T06-round4/evidence/current-host.json)、[JUnit 结果目录](T06-round4/evidence/current-host-test-results/)、[schema-check.json](T06-round4/schema-check.json)、[summary.json](T06-round4/summary.json)。前轮独立升级证据：[upgrade-host.json](T06-round2/evidence/upgrade-host.json)。临时 PostgreSQL 已成功停止。

审核 runner 从当前 backend 建立隔离副本，沿用已披露的 T03 等价接线、T04 Local 存储、T05 配置及迁移草案；仅把作者测试的样本输出重定向到本轮目录，避免覆盖作者证据。实际执行的测试副本见 [ExecutedT06PostgresTest.java](T06-round4/ExecutedT06PostgresTest.java)。

复现顺序（仓库根目录，使用现有 Python；数据库步骤需允许本机临时 PostgreSQL）：

```text
python docs/execution/reviews/T06-round4/capture.py
python docs/execution/reviews/T06-round4/run_review.py --include-review-regressions --evidence-name current-host
python docs/execution/reviews/T06-round4/verify.py
```

`verify.py` 区分 T06 审核与全局扫描：要求 48 项无失败/错误/跳过、Schema 和完整性通过，并要求扫描仅保留已知 T02 6 条记录；它没有把 Gitleaks 退出 1 改写为退出 0。

## 4. 通过范围与后续集成

T06 当前交付及本轮整改已通过审核，没有继续要求实施 agent 修改的 OPEN 项。若之后改变本轮受审源码、迁移、接线或验证逻辑，应固定新指纹并按实际影响复核。

以下集成条件继续保留，不由本轮 PASS 自动批准：

1. T03 批准基线、损坏旧接线补丁的正式处理，以及共享 canonical 修复的适用历史 hash/幂等兼容检查。
2. 正式全局迁移编号、共享 composition root 和配置装配。当前测试副本中的可用性不等于共享应用已启用文章功能。
3. T04 真实 S3 的独立验证；本轮使用真实 Local 存储。
4. T10/T11 的真实 generation/fencing/失效协作，使用依据 Evidence 适配，以及 T37 独立 journal、删除与恢复屏障。当前未接入时的 503 拒绝行为保持通过，不是这些功能已经完成。
5. T07 的人工编辑、Diff、RESTORE、提案与 AI fencing 业务仍需独立交付和审核；T06 端口测试不能替代其验收。

后续可将本轮文件指纹作为 T06 的已审核输入开展集成与 T07 工作，完整产品及上线仍按各阶段门禁另行验收。
