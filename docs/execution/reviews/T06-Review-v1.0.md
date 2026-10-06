# T06 第一轮独立审核

结论：**CHANGES_REQUIRED**。日期：2026-10-05（Asia/Hong_Kong）。本轮有 **2 项 OPEN / P2**：Markdown 嵌套强调解析错误，以及新增交付证据使密钥扫描失败。修复后应再次提交审核；本报告不批准 T06、G1/G2 或生产上线。

## 1. 审核对象与基线

本轮审查当前共享工作区中的 T06 交付，Git HEAD 为 `b115a4022375675c7cbff536b239508db8f3f4e1`，T06 尚未提交。该 HEAD 并不是 T06 的交付提交，审核结论绑定当前文件内容。

- 独立核对作者输入基线：820 个既有文件，变更 0 个。
- 核对交付指纹：17 个 T06 源码、测试、报告及接线文件，变更 0 个；审核指纹以 path/sha256 分字段保存于 [reviewed-files.json](T06-round1/reviewed-files.json)。
- T00 rc.3 的 27 项保护检查通过。未重新生成冻结契约。
- 审核仅新增本报告和 `T06-round1/` 内的测试、脚本、证据；没有修改实施源码、作者报告、作者测试或证据，没有应用共享补丁、安装正式迁移或提交 Git。

比较结果：[input-comparison.json](T06-round1/input-comparison.json)。

## 2. 必须修改

### T06-R01 / P2：嵌套强调解析会丢失格式，并错误计算原文字数

位置：`backend/src/main/java/com/example/editorial/article/ast/ArticleAst.java:80–87`。

解析器用 `indexOf(delimiter)` 寻找最近的结束符，未区分单星号、双星号和嵌套的分隔符。同一段内的内层 `**` 会被外层 `*` 提前消费。该路径直接用于创建文章的 Markdown 原文，并将结果固化为不可变 Original。

独立反例均已实际运行：

| 输入 | 正确结果 | 当前结果 |
|---|---|---|
| `*a **b** c*`，另加足长普通段落 | 可读文字 `a b c`，外层 italic、`b` 为 bold | 文字仍为 `a b c`，但 bold 丢失，拆成多段 italic |
| `***` + 98 个“字” + `***` | 去除强调标记后不足 100 字，拒绝 | 两个星号进入纯文本，作为正文字符计数，错误接受 |
| `***` + 30,000 个“字” + `***` | 正好达到可读文字上限，应接受 | 星号进入纯文本，抛出 `BLOCK_TOO_LARGE` |

依据：SRS §6 的 Unicode 码点及排除 Markdown 标记口径、AC-01 的 100–30,000 字边界、T00 白名单 marks，以及交付报告声明的嵌套加粗/斜体支持。这不是要求引入全部 Markdown 特性；问题发生在已承诺支持的强调语法内。

修复要求：正确识别受限 Markdown 的强调分隔符及嵌套关系，再从解析出的可读文字计算容量和 span；不要靠全局删除星号修复，以免损坏正文中的字面字符。保留码点偏移规则，补充嵌套、三重强调、转义、字面星号和边界用例。对于确实不支持的结构应明确拒绝，不能静默产生错误 Original。

证据：[ReviewArticleAstTest.java](T06-round1/ReviewArticleAstTest.java)、[独立测试结果](T06-round1/evidence/com.example.editorial.article.ast.ReviewArticleAstTest.txt)。3 项反例全部失败，0 error/skip，Maven 退出 1。它们属于同一根因，合并为一项问题。

### T06-R02 / P2：新增基线指纹触发 22 条密钥误报，CI 扫描仍失败

位置：`tests/engineering/T06/evidence/input-baseline.json:100` 等 22 处；完整行号见扫描证据。

按项目 T02 的实际 Git 可见文件扫描入口、相同配置和 Gitleaks 重跑，退出 1、共 28 条。已分清归属：

- 22 条来自本次 T06 的 `input-baseline.json`，是路径作为 JSON 键、SHA-256 作为值的指纹记录触发规则。
- 6 条来自既有 T02 的 `r01-integrity.json`，不计作 T06 新增问题。

这些记录经过文件完整性比对，属于指纹误报；本项不是声称发现真实凭据泄漏。但该文件属于 Git 可见交付内容，现有 CI 会失败。交付报告如实披露失败是正确的，披露本身不能关闭这个交付缺陷。

修复要求：保留指纹信息和可追溯性，可使用路径与 hash 分字段的记录格式并相应更新读取器；或者提交限定到具体文件及已核实匹配内容的共享扫描配置变更申请。不得宽泛排除 evidence、关闭默认规则或删除历史证据来取得绿色结果。复验须证明 T06 新增告警归零；既有 T02 6 条应另行跟踪，不能要求本任务擅自修改上游证据。

证据：[gitleaks-findings.json](T06-round1/gitleaks-findings.json)、[checks.json](T06-round1/checks.json) 第 5 项。

## 3. 已执行的独立验证

| 检查 | 结果 | 说明 |
|---|---|---|
| 隔离 clean test | 30/30 通过，0 failure/error/skip | AST 8、真实 PG/HTTP/Local 16、删除协议替身 2、T03 canonical 回归 4 |
| 上游已填充数据升级 | 1/1 通过 | T03/T05 草案及既有 actor/skill 升级到 T06 草案，旧行/history 保持，重复 migrate 无新增 |
| 独立 Markdown 反例 | 0/3 通过 | 3 failures，均归 T06-R01 |
| 实际响应 Schema | 两份样本均通过 | 本轮测试产生的 ArticleArtifact / ArticleVersion；jsonschema 4.26.0、Draft 2020-12、FormatChecker |
| 冻结契约保护 | 27 项通过 | 无冻结文件漂移 |
| T06 共享 patch 可应用性 | 通过 | 仅 `git apply --check`，未合入共享目录 |
| Git diff 空白检查 | 通过 | 不代表整个未跟踪交付已通过所有质量门禁 |
| Git 可见源文件密钥扫描 | 退出 1，28 条 | T06 新增 22，T02 既有 6 |

集成证据：[author-tests-host.json](T06-round1/evidence/author-tests-host.json)、[upgrade-host.json](T06-round1/evidence/upgrade-host.json)、[schema-check.json](T06-round1/schema-check.json)。每次运行保留 argv、退出码、输出和 JUnit XML。

首次沙箱运行在 `pg_ctl` 启动时因 Windows restricted token 失败，记录于 [author-tests.json](T06-round1/evidence/author-tests.json)。经允许在沙箱外运行相同隔离 harness 后，临时 PostgreSQL 成功启动，常规测试和升级测试均通过，两个临时实例均已成功停止。该环境失败没有计作代码缺陷，也没有计作测试通过。

本轮仍使用作者披露的隔离装配：真实 T03 Session/CSRF/幂等/审计、T04 Local ObjectStore、T05 配置模块和三组迁移草案；T03 损坏补丁通过副本中的等价接线处理。审核脚本仅重定向证据路径、复制独立反例，未修改生产逻辑。原有测试写样本的路径在副本中改到本轮审核目录，避免覆盖作者证据。

复现顺序，在仓库根目录用可用 Python 执行：

```text
python docs/execution/reviews/T06-round1/run_review.py --evidence-name author-tests-host
python docs/execution/reviews/T06-round1/run_review.py --upgrade-only --evidence-name upgrade-host
python docs/execution/reviews/T06-round1/verify.py
```

数据库步骤需允许创建本机临时 PostgreSQL。`verify.py` 是证据收集器，应读取各子命令退出码；当前预期可观察到反例测试及密钥扫描分别退出 1，不能将收集器自身退出 0 当作验收通过。

## 4. 依赖、共享变更和本轮边界

1. 创建原子性、相同 key 并发重放、ETag、跨 Owner 隐藏、取消后阻断继续编辑、Original 不可修改、基础同文章 FK/完整性、实际对象引用与事务失败回滚等交付测试已复跑通过。未因上述两项问题否认这些有效证据。
2. `Changes`、使用依据 Evidence 和真实删除命令适配尚未装配。当前返回 503、不写入假 generation、不提前返回 202 的做法符合本阶段约定，不单独列作 T06 缺陷。删除协议的 2 项测试是替身协议测试，不能证明真实独立 journal、恢复屏障或物理清理已经可用。
3. CR-T06-01 的请求 envelope 调整、CR-T06-02 的 canonical UTF-8/小写控制字符修正、CR-T06-03 的 composition root 均已审阅，并在隔离副本中运行通过。修改方向与当前冻结向量相符，但本轮未安装共享补丁。正式接入仍需 T03 整合审核及适用的历史 hash/幂等兼容检查；这里的草案升级用例不证明旧错误 canonical 数据的兼容性。
4. T03 仍缺批准基线，T04 真实 S3 证据尚有独立限制；本轮没有重跑 S3，也没有实测 T10/T11/T37 的真实工作流、失效、删除实现。不将这些外部状态重复算为 T06 新增问题。
5. T07 的人工编辑、Diff、RESTORE、提案和 AI fencing 仍需其独立实现及集成审核；T06 当前端口测试不是这些业务的完成证明。

## 5. 复审交付要求

逐项回应 T06-R01、T06-R02，提供修改文件/提交或新的工作区指纹、实际命令与结果。至少重跑解析反例与受影响的创建边界，保持现有回归通过，并出示没有 T06 新增告警的扫描结果。若修改共享规则，提交可审核的窄范围 patch。保留本轮原始审核证据，不改写失败结果。
