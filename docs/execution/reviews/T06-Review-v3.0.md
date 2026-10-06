# T06 第三轮独立审核

结论：**CHANGES_REQUIRED**。日期：2026-10-05（Asia/Hong_Kong）。两轮原始反例均已通过，但本次解析修改在闭合符后紧跟中文标点时存在回归，**T06-R01 仍为 OPEN / P2**。T06-R02 保持关闭。

## 1. 复审基线

本轮回应 [T06-Revision-v2.0](../reports/T06-Revision-v2.0.md)，审核对象是当前未提交工作区，HEAD 仍为 `b115a4022375675c7cbff536b239508db8f3f4e1`。已核对：820 个既有文件未变、6 项修订指纹匹配、19 项交付源码/测试/报告/接线文件指纹匹配。

相对第二轮，修改集中于 ArticleAst、相关 AST/HTTP 测试、隔离编排器、校验器；基础服务、迁移和共享补丁字节未变。核对依据：[input-snapshot.json](T06-round3/input-snapshot.json)、[input-comparison.json](T06-round3/input-comparison.json)、[reviewed-files.json](T06-round3/reviewed-files.json)。

审核只新增本轮报告和 `T06-round3/` 证据。没有修改实施源码、作者材料、两轮原始反例及失败记录，没有应用共享补丁或提交 Git。结束时重新核验两轮审核材料及当前受审文件，结果见 [summary.json](T06-round3/summary.json)。

## 2. T06-R01：原反例已修复，标点相邻场景仍有回归

位置：`backend/src/main/java/com/example/editorial/article/ast/ArticleAst.java:94–107`，尤其是第 95–97 行的 `canOpen` 与闭合条件。

本次按层级消费分隔符，解决了前两轮列出的行尾共用闭合符问题。两轮原始 6 个反例全部通过；真实 HTTP 创建对不足 100 字的拒绝、无新增 Job、合法 Original 的文本/marks 以及 30,000 字边界也复跑通过。这些修复有效。

剩余问题是：`canOpen` 仅以“后一个字符非空白”判断。中文句号和逗号被判为可开启强调；当当前层只需消耗 1 或 2 个星号、实际结尾是 3 个星号时，第 97 行因此拒绝闭合。随后把本应闭合的 `***` 当成新起始符，在找不到下一组闭合符时抛出 `UNSUPPORTED_MARKDOWN`。

独立实测：以下输入均后接换行与 100 个普通“字”，因此不是字数不足、非法 HTML 或外链引起的失败。

| 输入首段 | 预期 | 实际 |
|---|---|---|
| `***强调***。` | 纯文本 `强调。`，bold/italic 均只覆盖“强调” | 抛出 `UNSUPPORTED_MARKDOWN` |
| `*a **b***，后文` | 纯文本 `a b，后文`，嵌套 marks 正确 | 抛出 `UNSUPPORTED_MARKDOWN` |
| `*强调*。`、`**强调**。` | 正常解析，作为对照 | 通过 |

新增 3 项测试：**1 通过、2 failures、0 error/skip**。证据：[ReviewEmphasisPunctuationTest.java](T06-round3/ReviewEmphasisPunctuationTest.java)、[JUnit 结果](T06-round3/evidence/com.example.editorial.article.ast.ReviewEmphasisPunctuationTest.txt)、[checks.json](T06-round3/checks.json) 第 1 项。

上述失败直接在创建原文所调用的 `ArticleAst.parse` 中复现；本轮新增反例是解析层测试，没有将它们表述为另行执行过的 HTTP 请求。生产创建路径也依赖该解析器，因此含这些正常格式的原文会被拒绝。

这仍是已承诺支持的加粗/斜体与嵌套语法，不是新增 Markdown 功能。既定限制是拒绝未闭合三重强调、超过三个连续强调符等；这里强调已经闭合，仅后接普通中文标点，不应被当作未闭合结构。

修复要求：结合分隔符两侧字符和当前嵌套层级判断开闭关系，避免把“后接非空白”直接等同于必须开启新层。建议用统一的分隔符消费规则或栈处理，并用表驱动测试覆盖单/双/三重强调、两种嵌套方向，分别出现在行尾、空白前、中文句号/逗号前和正文相邻处。保留字面字符、转义、Unicode 偏移及 98/30,000 字边界；不要继续只为特定示例增加条件。

## 3. T06-R02：保持关闭

按现有项目 Git 可见文件扫描入口复扫：**T06 新增告警 0**。扫描整体退出 1，仅有既有 T02 `r01-integrity.json` 的 6 条指纹误报。指纹数据格式、T02 原证据与共享规则均未变。

证据：[gitleaks-findings.json](T06-round3/gitleaks-findings.json)、[checks.json](T06-round3/checks.json) 第 5 项。此结果不代表整体 CI 通过。

## 4. 独立验证结果

| 检查 | 结果 |
|---|---|
| clean test，作者回归与两轮原始反例一起执行 | **43/43 通过**，0 failure/error/skip：AST 13、PG/HTTP/Local 18、删除协议替身 2、canonical 4、原始审核反例 6 |
| 本轮标点相邻回归检查 | **1/3 通过，2 项失败** |
| 本轮实际 ArticleArtifact、ArticleVersion 响应 | jsonschema 4.26.0、Draft 2020-12、FormatChecker：两份均通过 |
| 冻结契约保护 | 27 项通过 |
| T06 patch 可应用性、Git diff 空白检查 | 通过；未安装补丁 |
| Git 可见源文件扫描 | 退出 1，仅 T02 既有 6 条；T06 为 0 |
| 已有数据升级 | 本轮未重复执行；迁移字节未变，保留第二轮独立 1/1 通过证据，不将作者本轮自测计作审核方新执行 |

集成证据：[current-host.json](T06-round3/evidence/current-host.json)。样本检查：[schema-check.json](T06-round3/schema-check.json)。前轮升级证据：[upgrade-host.json](T06-round2/evidence/upgrade-host.json)。临时 PostgreSQL 已成功停止。

复现顺序（仓库根目录，使用现有 Python）：

```text
python docs/execution/reviews/T06-round3/capture.py
python docs/execution/reviews/T06-round3/run_review.py --include-review-regressions --evidence-name current-host
python docs/execution/reviews/T06-round3/verify.py
python docs/execution/reviews/T06-round3/finish.py
```

审核 runner 在新副本中执行作者披露的隔离装配，重定向响应样本以避免覆盖作者证据，并复制审核测试。`verify.py` 保留各子命令退出码；反例和扫描的失败不能被收集器自身的退出 0 替代。

T03 批准基线、共享 canonical 历史兼容与正式接线、真实 S3、T07 业务、T10/T11 工作流/失效、T37 删除恢复等边界继续沿用前两轮报告。本次没有安装这些适配，也不另行把未完成的依赖记作 T06 缺陷。

## 5. 后续复审

继续回应唯一 OPEN 的 T06-R01，修复标点相邻场景并补齐上述语法位置组合的回归，提供新指纹和实际测试结果。保持原有 43 项回归通过及 T06 新增扫描告警为 0，保留本轮失败证据。
