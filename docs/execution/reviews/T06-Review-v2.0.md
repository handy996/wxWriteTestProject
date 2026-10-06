# T06 第二轮独立审核

结论：**CHANGES_REQUIRED**。日期：2026-10-05（Asia/Hong_Kong）。**T06-R02 关闭；T06-R01 部分修复，仍为 OPEN / P2。** 首轮三个具体反例已通过，但相同解析问题在内外层强调共用结尾分隔符时仍存在。本轮不批准 T06、整体 CI、G1/G2 或上线。

## 1. 复审范围与输入

审查 [修订报告](../reports/T06-Revision-v1.0.md) 对首轮两项问题的整改，基线是当前未提交工作区；HEAD 仍为 `b115a4022375675c7cbff536b239508db8f3f4e1`，不是 T06 修订提交。

独立核对结果：820 个既有输入文件无变化、6 个修订指纹全部匹配、18 个当前交付源码/测试/报告/接线文件指纹全部匹配。对照首轮受审文件，改动集中于 ArticleAst、其单测、T06PostgresTest 和 verify_delivery.py；另外按修订声明调整了 input-baseline 的记录格式并新增修订报告。基础服务、迁移草案与共享补丁未变化。

输入与结束时的完整性证据：[input-snapshot.json](T06-round2/input-snapshot.json)、[input-comparison.json](T06-round2/input-comparison.json)、[summary.json](T06-round2/summary.json)。原首轮审核报告、原反例和失败证据在本轮前后字节未变。审核没有修改实施源码或作者材料，没有安装共享补丁、正式迁移或提交 Git。

## 2. T06-R01：部分修复，仍需修改

位置：`backend/src/main/java/com/example/editorial/article/ast/ArticleAst.java:90–112`，关键判断为第 96 行的 `closing.equals(delimiter)`。

本次递归解析正确修复了首轮的 `*a **b** c*` 与 `***正文***`。首轮未修改的三个测试独立复跑全部通过，作者新增的格式/码点测试和实际创建 Original 测试也通过。

但是，当前实现把连续的三个星号视作不可拆分的完整分隔符。内层需要两个星号、外层需要一个星号时，结尾的 `***` 既不等于 `**` 也不等于 `*`，最终落入“未配对字面符号”分支并被写入纯文本。没有解决已承诺的嵌套强调在同一位置结束的情形。

新增独立反例的实际结果：

| 输入 | 预期 | 当前结果 |
|---|---|---|
| `*a **b***`，后接足长普通段落 | 纯文本 `a b`，保留外层 italic 和内层 bold | 纯文本是完整的 `*a **b***` |
| `*` + 97 个“字” + ` **字***` | 可读正文共 98 字，拒绝 | 未抛出错误，星号使不足 100 字的输入错误通过 |
| `*` + 29,999 个“字” + `**字***` | 可读正文恰为 30,000 字，接受 | 抛出 `BLOCK_TOO_LARGE` |

三个测试均实际执行并失败，0 error/skip。第一个测试在首个输入即失败，测试源码中其余变体没有作为已执行通过或失败的证据计入结论。

这是首轮 R01 的剩余问题，沿用同一编号；没有要求扩展代码块、表格等其他 Markdown 功能。解析结果会继续成为不可变 Original，并参与正文 hash、字数与锚点计算，因此不能按“原始三个测试已绿”关闭。

修复要求：在嵌套强调中按所需数量消费闭合符号，并把剩余符号交给外层；兼顾三重强调的开闭、相邻闭合、转义、字面字符及 Unicode 码点偏移。若某种组合明确不在受限语法范围，应给出明确拒绝，不能静默接受错误正文。不要只针对示例字符串特殊处理或删除全部星号。

证据：[ReviewNestedClosureTest.java](T06-round2/ReviewNestedClosureTest.java)、[独立失败结果](T06-round2/evidence/com.example.editorial.article.ast.ReviewNestedClosureTest.txt)、[checks.json](T06-round2/checks.json) 第 1 项。后续应补充真实创建入口的共用闭合符反例，验证不足 100 字时返回 422 且没有业务行；合法嵌套的已保存 Original 与预期文本/marks 一致。

## 3. T06-R02：关闭

`input-baseline.json` 已改成 path/sha256 分字段记录；820 个路径唯一且对应实际文件 hash 均匹配。校验器已适配新结构，没有修改共享扫描规则或 T02 原证据。

本轮按项目实际 Git 可见文件扫描入口复扫：**T06 新增告警 0；全部 6 条告警都来自既有 T02 `r01-integrity.json`**。扫描退出 1 如实保留。本项关闭仅表示 T06 不再新增扫描失败原因，不表示整体 CI 已通过。

证据：[gitleaks-findings.json](T06-round2/gitleaks-findings.json)、[checks.json](T06-round2/checks.json) 第 5 项。

## 4. 本轮实际验证

| 验证 | 结果 |
|---|---|
| 作者修订回归 | 34/34 通过：AST 11、真实 PG/HTTP/Local 17、删除协议替身 2、共享 canonical 4 |
| 首轮原始反例，未改测试源码 | 3/3 通过 |
| 上述两组一起 clean test | 37/37 通过，0 failure/error/skip |
| 新增共用闭合符反例 | 3 项全部失败，0 error/skip |
| 已有 T03/T05 数据升级至 T06 草案 | 1/1 通过 |
| 本轮实际 ArticleArtifact / ArticleVersion 样本 | jsonschema 4.26.0、Draft 2020-12、FormatChecker：两份均通过 |
| T00 rc.3 保护、T06 patch 可应用性、Git diff 空白检查 | 均通过；冻结保护 27 项 |
| 密钥扫描 | 退出 1，仅 T02 既有 6 条；T06 0 条 |

测试证据：[current-host.json](T06-round2/evidence/current-host.json)、[upgrade-host.json](T06-round2/evidence/upgrade-host.json)、[schema-check.json](T06-round2/schema-check.json)。两次临时 PostgreSQL 均已成功停止。

复现顺序（仓库根目录，使用已安装的 Python）：

```text
python docs/execution/reviews/T06-round2/run_review.py --evidence-name current-host
python docs/execution/reviews/T06-round2/run_review.py --upgrade-only --evidence-name upgrade-host
python docs/execution/reviews/T06-round2/verify.py
python docs/execution/reviews/T06-round2/finish.py
```

`verify.py` 汇总每个子命令，当前反例 Maven 和扫描的退出码均为 1；不能用收集器自身退出 0 宣称验收通过。审核 runner 复用上轮隔离装配方式，仅在副本中重定向样本输出并加入审核用例；实际执行的集成测试副本见 [ExecutedT06PostgresTest.java](T06-round2/ExecutedT06PostgresTest.java)。

共享 canonical/接线补丁仍未正式安装，T03 批准基线、真实 S3、T10/T11 工作流和失效、T37 独立 journal/删除恢复、T07 业务的边界沿用首轮报告。本轮没有将这些未完成依赖另列为 T06 缺陷，也没有把删除协议替身计作真实删除系统已完成。

## 5. 下一次复审

仅需继续回应 OPEN 的 T06-R01，提交新的源码指纹与修复说明，重跑首轮及本轮反例、相关原文创建边界和现有解析回归。R02 已关闭；后续只需保持新增扫描告警为 0。保留本轮失败证据，勿覆盖为成功结果。
