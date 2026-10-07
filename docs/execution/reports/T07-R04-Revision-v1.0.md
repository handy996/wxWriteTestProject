# T07-R04 整改报告 v1.0 — 会话 Cookie 名一致性

- 登记项：`docs/execution/STATE.json` → `openItems[T07-R04]`（第四轮独立复审发现，主 agent 定级 P1）
- 实施方：**主 agent 本人**（未派发子 agent；改动面 3 个生产/测试文件 + 1 个新闸门）
- 整改基线：`dc95736`（已复审代码基线仍为 `b072abe`，见文末"未经复审"声明）
- 契约版本：rc.3 **未改动**，`check_contracts.py` 27/27 通过（见验证 §2）

## 1. 问题与决策

冻结契约 `docs/api/openapi.yaml:14103-14107` 与增量契约 `docs/api/diff-pages-v1.1.openapi.yaml` 都把会话声明为
`session: {type: apiKey, in: cookie, name: EDITORIAL_SESSION}`，但服务端从未设置
`server.servlet.session.cookie.name`，运行时下发的是容器默认 `JSESSIONID`；第一轮至第四轮的 HTTP 测试
（`T03PostgresTest.java` 3 处字面量）都以 `JSESSIONID` 取证并通过，因此该错位从未被任何闸门抓到。
严格按契约生成客户端的 agent（T09/T30）会对**所有路由**得到 401。

方向选择：**(a) 让实现符合已批准的 rc.3**，而不是 (b) 反向修订契约。
理由：仓库规则规定不得修改已审核公共契约，且 rc.3 已获 T00 批准；(b) 需要走版本化变更申请，成本更高且会把
已生成的客户端契约推倒。本选择不修改任何契约文本。

## 2. 改动清单（4 处，全部在 T03/identity 域内）

| 文件 | 改动 |
|---|---|
| `backend/src/main/resources/application.yml` | `server.servlet.session.cookie` 增加 `name: EDITORIAL_SESSION`（+1 行） |
| `backend/src/main/java/com/example/editorial/identity/T03Configuration.java` | 新增常量 `SESSION_COOKIE_NAME="EDITORIAL_SESSION"`；在组合根增加**启动即失败**断言：配置名 ≠ 契约名则抛 `T03_COOKIE`（+2 行，所有 profile 生效，非仅 prod） |
| `backend/src/test/java/com/example/editorial/identity/T03PostgresTest.java` | 3 处 `JSESSIONID` 字面量改为引用该常量；`fixationRotationAndLogout` 新增一条运行时断言：`Set-Cookie` 必须以 `EDITORIAL_SESSION=` 开头 |
| `tests/engineering/T03/check_session_cookie.py` | 新闸门（零第三方依赖）：冻结契约 / 增量契约 / `application.yml` / `application-prod.yml` / Java 常量五处 Cookie 名必须全等，且禁止容器默认名回流 |

`tests/engineering/T03/check_session_cookie.py` 不用 pyyaml：冻结契约是 JSON 语法 YAML 故 `json.loads` 直读，
增量契约用缩进扫描只取 `security` 与 `securitySchemes` 两块。反向控制对被解析的源文本做**纯内存变异**
（临时改写磁盘上 `openapi.yaml` 的第一版实现被我否决：进程若崩在半路会留下被改动的已批准契约）。

## 3. 验证

命令均在 `E:\project\codex\wxAgent` 执行；`$py` = `C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。

| # | 命令 | 退出码 | 结果 |
|---|---|---|---|
| 1 | `$py tests/engineering/T03/check_session_cookie.py` | 0 | 整改当时只有**相对相等**检查，五源全等 `EDITORIAL_SESSION`；6/6 反向控制被拒。**第五轮复审判为不足**（F02/F03/F04/F07：闸门对守卫本身盲视、配置扫描无路径锚定、五源协同改名仍通过、dev/mock profile 未扫），已加固为绝对锚 `APPROVED_NAME` + 缩进路径匹配 `server.servlet.session.cookie.name` + 按 `---` 分段 + 扫全部 `application*.yml` + 把启动守卫与运行时自证断言纳入受控源，现 **14/14 反向控制被拒**（见第 8 项） |
| 2 | `$py tests/engineering/T02/check_contracts.py` | 0 | `Approved T00 rc.3: 27 hashes verified, no regeneration`；`openapi.yaml` sha `e285471760a5dce4…` 与第四轮复审记录一致 |
| 3 | `$py tests/engineering/integration/formal.py --include-review-regressions --evidence-name r04-core-post-change` | **0** | 真实 PostgreSQL + 真实 HTTP Session/CSRF，12 个测试类 75 项全通过、0 失败 0 错误 0 跳过；`paidCalls=0`。**更正（第五轮 F01）**：本行原先被当作"改名生效"的证据是错的——该套件的 `-Dtest` 白名单**不含 `T03PostgresTest`**（`fixationRotationAndLogout` 命中 0），它只证明改名没有破坏 core 组合根；改名的直接证据是第 4 行与第 10 行 |
| 10 | `$py tests/engineering/integration/formal.py --suite identity --evidence-name r05-head-bytes`（HEAD 字节，含 T08 集成后的 `application.yml`） | 1 | `T03PostgresTest` 15 项 6 失败，失败集与第 4、5 行**同一既有 6 项**；`fixationRotationAndLogout` **不在失败集**（逐方法解析 surefire XML 得出）→ 运行时确实发出 `EDITORIAL_SESSION=`。第五轮 F05 指出台账原先绑的 `application.yml` 指纹 `fff6a718…` 已被 T08 提交刷新为 `42acb385…`，本行即 HEAD 字节的补证 |
| 11 | `$py tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r05.json` | 0 | 加固后闸门：绝对锚 `APPROVED_NAME`、缩进路径匹配 `server.servlet.session.cookie.name` 且按 `---` 分段、扫 `application-dev/mock/prod.yml` 全四个 profile（`profileOverrides={}`）、启动守卫行与运行时自证断言成为受控源；**14/14 反向控制被拒**（新增：守卫行删除、守卫 `if(false)` 阉割、守卫读错属性键、cookie 名挪到 `spring.datasource` 下、追加 `---` 文档藏第二个名、profile 覆盖成 `JSESSIONID`、运行时断言删除、五源协同改回 `JSESSIONID`） |
| 4 | `$py tests/engineering/integration/formal.py --suite identity --evidence-name r04-session-cookie` | 1 | `T03PostgresTest` 15 项中 6 失败（见 §4 归因） |
| 5 | 同上，在**未改动的基线工作树** `dc95736`（`git worktree add --detach`，含 3 处 `JSESSIONID` 字面量） | 1 | 失败的 6 个方法名与第 4 项**逐字相同，`Compare-Object` 差集为 0** |
| 6 | `$py tests/engineering/integration/formal.py --suite all --evidence-name r04-all-with-identity` | 1 | 120 项中 16 失败（9 failures + 7 errors） |
| 7 | 基线工作树跑 `--suite all --evidence-name baseline-all` | 1 | 120 项 16 失败，失败集合与第 6 项差集 0 |
| 8 | 第 6/7 项失败集合 vs 仓库历史 `formal-all-domains-01-test-results`（先前记录，`exitCode=1`） | — | **完全相同（`sets identical: True`）**，即该状态在我改动之前就已入库 |

**运行时修复的直接证据**是第 3 项里的 `fixationRotationAndLogout`：它现在断言 `Set-Cookie` 以
`EDITORIAL_SESSION=` 开头并使用该名字的会话轮换比较。若配置未生效，该测试必然失败——因此它同时充当本次改名的
反向控制。第 5/7 项证明我没有引入任何新失败；基线工作树建在被忽略的 `tests/engineering/integration/.work/` 下，
用完已 `git worktree remove` 删除，未触碰生产文件与历史提交。

`formal.py` 把 `backend` 复制到自身隔离目录再构建，因此**不写 `backend/target`**，与并行进行的 T08 实施不冲突。

## 4. 多域套件的既有失败（非本次引入，非新缺陷）

`--suite identity` 与 `--suite all` 在当前批次下必然部分失败，原因与仓库历史证据一致：
`domainSubstitutes` 记录 *"T10/T11 not installed: production Changes and Deletion fail closed"*。
可观察到的症状为跨域调用返回 503 `OWNERSHIP_NOT_READY`、审计写入 `AUDIT_WRITE_FAILED`，
以及 `emptyInitializationAndRepeatNeverReset` 的初始化用户数期望差（1 vs 2）。
判定整改是否引入回归的正确方法因此是**同套件基线对照**（第 5/7 项），而不是要求 120 项全绿。
此规则已写入 `STATE.protocol`，对应台账项 `openItems[MULTI-DOMAIN-SUITE]`，其闭合条件是 T10/T11 安装后重跑 `--suite all`。

## 5. 本次未证明什么

- 未运行 **prod profile 的真实启动**（需真实 S3 与生产 DB 角色）；prod 侧仅有静态一致性证据：`application-prod.yml` 不设 `name` 因而继承基础值，且 `secure: true`/`http-only`/`same-site=strict` 仍受原 `T03_COOKIE` 校验。
- 未跑前端契约生成产物对 `EDITORIAL_SESSION` 的端到端使用（T12+ 范围）。
- 未重跑 T04/T05 **单域**历史绿色套件（本轮只跑了 `all`，其失败集合已按 §4 与基线等同）。
- 本次改动由主 agent 实施，**尚未经独立复审**：`b072abe` 仍是最后一个已复审的字节基线，紧随其后的整改提交（含本报告、3 个证据集与 `STATE.json`）不得作为 PASS 依据，须由第五轮 T03 复审或 T03 独立批准覆盖。

## 6. 待主 agent 集成事项

无新增依赖、无迁移、无 Flyway 序号占用、无前端改动；`pom.xml`/`package.json`/CI 未触碰。
唯一共享文件改动是 `backend/src/main/resources/application.yml` 的一行 Cookie 名。
