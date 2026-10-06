# T07 第四轮独立审核（T07-R03 整改复审）

日期：2026-10-06（Asia/Hong_Kong）。结论：**PASS。T07-R03 关闭；CR-T07-01 登记关闭条件已满足，建议正式关闭。** 本轮另登记 1 项新观察（契约 Cookie 名与服务端实际不一致），不属于 R03 原始修复要求，且为冻结契约既有缺口，不反转本轮判决，但须由主 agent 立项处置。

## 1. 受审版本

审核提交 **`b072abe53bd8945993801d35af88335fb0916d0a`**（分支 `main`），相对受审基线 `c12738f` 共 100 个变更文件（97 新增 / 3 修改）。其中真正的整改提交 `b072abe` 只触达 5 个文件：[diff-pages-v1.1.openapi.yaml](../../api/diff-pages-v1.1.openapi.yaml)、[verify_diff_page.py](../../../tests/engineering/T07/verify_diff_page.py)、新证据 [diff-page-v1.1-check-r03.json](../../../tests/engineering/T07/evidence/diff-page-v1.1-check-r03.json)、[T07-Revision-v3.0](../reports/T07-Revision-v3.0.md) 与 STATE.json；`1f4ea9d`/`21af384` 仅把第三轮审核材料入库并补 STATE.json 与根 `.gitignore` 兜底规则。开工与结束时工作树洁净（结束仅多本轮审核目录），已跟踪文件 1,834 个。交付方自述全部按待验证主张处理，下列判定均有本轮独立退出码或哈希支撑。

按 STATE.json 协议未通读大文件；独立检查脚本 [review_r03.py](review_r03.py) 自行实现守卫与反向控制，**不 import 交付方校验器任何函数**，运行记录见 [checks.json](checks.json)。本轮**不再生成 1,834 文件全量清单快照**（约 344 KB 的上一轮做法被三项更硬证据取代：工作树 `git status` 洁净、T00 rc.3 27 哈希门禁退出 0、`c12738f..b072abe` 名称过滤差分中生产路径为 0），该取舍已在 checks.json 注明。

## 2. R03 修复要求逐项判定

R03 原文修复要求（Review-v3.0 §2）：增量 OpenAPI 声明与冻结契约一致的 Session Cookie scheme 并在根级或 GET 操作引用；补自动化校验，断言有效 security requirement 及 scheme 的 type/in/name；保留服务端登录限制与真实 HTTP 匿名 401、登录成功回归；仅补文字不足以关闭。

| # | 要求 | 判定 | 依据（本轮独立观测） |
|---|---|---|---|
| 1 | 增量契约声明鉴权且与冻结契约字典全等 | **通过** | 根级 `security=[{"session": []}]` 与冻结根级逐项相等；`securitySchemes.session` = `{type: apiKey, in: cookie, name: EDITORIAL_SESSION}`，与冻结定义全字典比较相等，无附加键；GET 操作无操作级声明，有效 security 按"操作级优先，否则根级"（同 round3 check_review.py:44-49）解析为 `[{"session": []}]` |
| 2 | 自动化校验存在且断言该语义 | **通过** | `verify_diff_page.py` 第 39 行 `effective = operation.get("security", root)`，第 41–42 行要求等于冻结 `security`，第 43–46 行对每个被引用 scheme 做全字典相等（覆盖 type/in/name，多余键即失败）；文件 sha256 `90dde491…3068e` |
| 3 | 反向控制真实生效 | **通过（6/6 拒绝）** | 本轮用自己的守卫对深拷贝施加：删根级 security→拒（effective None）；删 `securitySchemes.session`→拒（None≠冻结）；`in: cookie→header`→拒；`security: []`→拒；另加两项超额控制：scheme 多一个 `description` 键→拒；GET 操作级 `security: []` 覆盖根级→拒（证明操作级优先语义被真实断言）。未修改任何文件，变异只在内存 |
| 4 | 冻结契约未被改动 | **通过** | `check_contracts.py` 退出 0，stdout `Approved T00 rc.3: 27 hashes verified, no regeneration`；独立按 [T00-rc3-approval.json](../T00-rc3-approval.json) 复算：openapi.yaml `e2854717…67eb2b`、editorial.schema.json `7b5872e1…cbe2aa` 均与批准记录逐字节一致；增量契约本就不在 rc.3 批准清单内 |
| 5 | 改动范围与未重跑正当性 | **通过** | `git diff --name-only c12738f b072abe` 中 `backend/` 与 `docs/api/openapi.yaml` 匹配数为 **0**；生产源码与迁移相对 c12738f 未变，第三轮真实 HTTP 匿名 401、登录分页、78/78 运行回归按行为等价继续适用，本轮不重跑 Maven/PostgreSQL 有据 |
| 6 | 服务端真实执行鉴权 | **通过** | 代码链：T03Configuration.java:50–52 `/api/v1/**` 需 `hasRole("OWNER")`、:48 入口 401；RequestGuards.java:26 未登录访问 `/api/` 抛 401 `UNAUTHENTICATED`；ActorContext.java:16–19 无主体即 401；VersionController.java:22–23 新路由经 `ActorContext.current()` 进入 `VersionService.diffPage`，无匿名路径。[ReviewDiffHttpTest.java](T07-round3/ReviewDiffHttpTest.java) 仍在工作树且与第三轮**实际执行副本**字节相同（sha256 `d1b25832…14cc18` 双向一致），JUnit `tests=1 failures=0 errors=0` |

## 3. 独立验证结果

| 检查 | 结果 |
|---|---|
| 本轮守卫对交付文档 | 通过；OpenAPI 结构校验（openapi_spec_validator）同时通过，修复未破坏文档结构 |
| 本轮反向控制 | **6/6 全部拒绝**（含要求的 4 项 + 附加 2 项） |
| rc.3 哈希门禁 | 退出 0；27/27 |
| 批准清单独立复核 | openapi.yaml、editorial.schema.json 2/2 哈希匹配 |
| 整改提交范围 | 100 文件差分：生产代码 0、冻结契约 0；根 `.gitignore` 放宽为 `**/.work/`（`.work` 下已跟踪文件为 0，该规则不隐藏任何入库证据） |
| `git diff --check` | 退出 0 |
| 交付证据文件 | diff-page-v1.1-check-r03.json 记录的本文件与冻结文件 sha256 与本轮复算一致（仅作对照，不作依据） |

## 4. 新观察（不属 R03，须立项处置）

契约（冻结与增量）声明 Session Cookie 名为 `EDITORIAL_SESSION`，但 `backend/` 全量检索无任何 `server.servlet.session.cookie.name` 配置（application.yml/dev/mock/prod 均无），运行时实际为容器默认 `JSESSIONID`，第一轮至今的 HTTP 测试也全部以 `JSESSIONID` 登录取证。严格按契约生成的客户端将携带 `EDITORIAL_SESSION` 而得到 401。该缺口为 rc.3 冻结声明与实现之间的既有不一致，**并非本轮整改引入**，R03 的字面修复要求（与冻结契约一致）已满足，故不反转判决；但影响所有路由的客户端独立接入，建议登记新项（候选 T07-R04）：要么服务端配置改名为 `EDITORIAL_SESSION` 并回归验证，要么按冻结契约变更规则走版本化修订。不得不了了之。

## 5. 本轮未证明什么（边界）

- 未重跑任何 Maven、PostgreSQL、真实 HTTP 与 601 页 / 60,002 行全量遍历：依据是第 5 项证明的生产字节未变，相关运行证据绑定 `c12738f`，对当前受审字节行为等价适用；若主 agent 要求同轮重验，用 [run_review.py](T07-round3/run_review.py) `--include-review-regressions` 配新证据名即可。
- 未重跑 gitleaks、12 样本 Schema 全量校验与第三轮复审方 `check_review.py`：后者绑定 1,737 文件旧快照，按其设计在本轮必然报 `tracked inputs changed`，其鉴权复算等价式已由本轮脚本独立实现并通过。
- 第三轮审核材料系由被审方在 `1f4ea9d` 补入 git，提交历史本身不能自证未被改写；本轮以内部哈希交叉验证（执行副本与工作树字节一致、冻结 27 哈希、JUnit 计数）作为替代防线。
- 交付方报告的 4/4 反向控制、SECURITY_MATCHES_FROZEN=True 等数字仅为对照，本轮结果全部为独立重算。
- T03 独立批准、T04 真实 S3（B01/R04）、T08、T10/T11/T16/T19、G1/G2 与上线均不在本轮范围，不随本轮通过。

## 6. 关闭状态与建议

- **T07-R03：关闭。** 原始修复要求全部满足，反向控制经本轮独立实现验证真实生效。
- **CR-T07-01：登记关闭条件（R03 修复 + 增量契约复审完成）已在本轮证据范围内满足，建议主 agent 正式关闭**；分页容量证据（旧路由 1,000 行显式拒绝不变、新路由全量读取）继承自第三轮运行记录，绑定未变的生产字节。AC-19"任意合法版本 Diff 完整可读"可据此宣告，前提措辞如实保留：该容量证据非本轮重跑所得。
- 增量契约（diff-pages v1.1）本轮复审通过，批准为可消费契约层；第 4 节新观察另行立项。
- T07 任务整体（含 G1/G2 关联）仍由主 agent 依 STATE.json 统筹，本轮不越权宣告。
