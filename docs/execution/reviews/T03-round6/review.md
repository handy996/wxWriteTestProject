# T03 第六轮独立复审 — 第五轮整改（主 agent 自做的闸门加固）

- 判决：**CHANGES_REQUIRED**（无 P0/P1；加固方向真实有效，我的 12/16 攻击探针被拒且原有 14 条控制全部独立复现；但"守卫受控"存在**注释绕过**这一未覆盖变异类，闸门在守卫已死时仍输出 `startupGuardLive=true`）
- 复审 HEAD：`23c6c2c`；工作树洁净（`git status --porcelain` 退出 0、空输出）；被审字节 `check_session_cookie.py` sha256=`d099d47c…`（`849d784` 引入，156+/48− 对 `2512025`）
- 复现方式：纯 Python 内存探针（未写盘、未跑 mvn/formal.py，依边界约束）；surefire 结论全部由我自己解析 XML 得出

## 1. 必须独立复现的结果

| # | 命令 | 退出码 | 我看到的 |
|---|---|---|---|
| 1 | `python tests/engineering/T03/check_session_cookie.py` | **0** | `verdict=PASS`；`negativeControlsRejected` **14/14**，名称与台账逐一对得上；`profileOverrides={}`；扫 4 文件 `application-dev/mock/prod/.yml` |
| 2 | `python tests/engineering/T02/check_contracts.py` | **0** | `Approved T00 rc.3: 27 hashes verified, no regeneration` → rc.3 未被触碰 |
| 3 | 内存比对 `session-cookie-r05.json` vs 我 live 重跑 | 0 | 14 控制集相等、sha256 映射**逐字节相等** → 已入库证据即 HEAD 字节 |
| 4 | 解析 3 个 surefire `T03PostgresTest.xml` | 0 | r05-head-bytes＝15/6/0，与 r04-session-cookie 及祖先基线 `formal-all-domains-01` 失败方法集**三方逐字相同**；`fixationRotationAndLogout`＝**PASS** |
| 5 | `git grep -c JSESSIONID -- backend/src` | **1**（无命中） | 生产/测试代码 0 残留（同第五轮 §2.3） |

## 2. F01–F07 逐条复验（第五轮发现 vs 本轮实况）

- **F01（报告 §3 证据载体错标）：部分更正，诚实但有残留。** 表行 3 已加"更正（第五轮 F01）"注且为真——我读 `formal.py:135-143` 确认 core 白名单与 `--include-review-regressions` 追加项均**不含** `T03PostgresTest`；identity 白名单恰为它（:137）。STATE `fixEvidence` 首条改指 r05、且 r04 系证据现被表述为"同套件基线对照用"。**残留**：报告 :50-52 段落仍写"运行时修复的直接证据是第 3 项里的 `fixationRotationAndLogout`"——与 9 行前的更正自相矛盾 → 我的 F-03。
- **F02（闸门对守卫盲视）：主体已修，留一类绕过。** 守卫行与运行时断言已入 `SOURCES`（`code`/`test` 键）并各配控制；我的 P06（`if(false&&…)`）、P07（删守卫行）、P18（读错键）、P10（删断言）、P12（`anyMatch(x->true)`）全被拒。**但** P08/P09/P11（把守卫/断言行整体注释掉或块注释包裹）被**接受** → 我的 F-01。
- **F03（无路径锚定/多文档藏名）：已修。** 我的 P02（挪 `spring.cloud` 下）、P03（完整链挪 `management:` 下）、P04（追加 `---` 第二文档放第二个名）、P05（第二文档带 `on-profile: prod`）全部被拒；缩进祖先链 + 按 `---` 重置 + `len(declared)!=1` 三重生效。新留缝：引号化重复键 `"name":` 对扫描器不可见 → 我的 F-02。
- **F04（协同改名接受/两条分支无控制）：已修。** 我的 P01（五源协同改第三名字 `MYSESSION`，非 JSESSIONID，排除 FORBIDDEN 兜底干扰）被**绝对锚**拒（`frozenContract: declared cookie name 'MYSESSION' != approved`）。prod 分支未单列控制，但与 dev 走同一 `for name,text in configs.items()` 循环，我的 P13/P14（dev 覆盖第三名/JSESSIONID）实证该循环 → 可接受；台账 `machineGates` 仍写"五源全等…基础与 prod 配置"旧措辞 → 并入 F-04。
- **F05（证据不再绑 HEAD 字节）：已修，核对为诚实。** r05-head-bytes.json `executedInputs` 含 `42acb385`（application.yml，HEAD）＋`56f4d50a`/`ecc2eaed`（＝HEAD），不含 `fff6a718`；整体 `exitCode:1` 如实记录；surefire XML 独立解析支持"15 项 6 失败、`fixationRotationAndLogout` 不在失败集"读法；`session-cookie-r05.json` 与我 live 重跑全等。旧 r04 证据仍在但台账已改称对照基线 → 未冒充当前字节。
- **F06（过严面）：按建议处理。** 我的 P17 `name: 'EDITORIAL_SESSION'`（引号等价写法）现在**接受**；flow 风格不追踪已在 `cookie_names` docstring 声明为有意保守。
- **F07（dev/mock 未扫）：已修。** glob 扫全部 `application*.yml`，当前 resources 恰只有这 4 个文件（无 `.properties`/`.yaml`，见我的 F-05 前瞻项）。

## 3. 我的独立变异探针（18 条，全部内存内，未写盘）

| # | 攻击 | 期望 | 实况 | 首个拒绝分支 |
|---|---|---|---|---|
| P01 | 五源协同改 `MYSESSION` | REJECT | REJECT ✓ | 绝对锚（frozenContract） |
| P02/P03 | 名挪无关父（`spring.cloud` / `management:` 全链） | REJECT | REJECT ✓ | `found []`（len≠1） |
| P04/P05 | `---` 第二文档放第二名（裸/带 on-profile） | REJECT | REJECT ✓ | `found [两值]` |
| P06 | 守卫 `if(false&&!…)` | REJECT | REJECT ✓ | GUARD 正则不匹配 |
| P07 | 删守卫行 | REJECT | REJECT ✓ | 同上 |
| **P08** | 守卫行前置 `//` | REJECT | **ACCEPTED ✗** | —（F-01） |
| **P09** | 守卫 `/* … */` 包裹 | REJECT | **ACCEPTED ✗** | —（F-01） |
| P18 | 守卫读错属性键 | REJECT | REJECT ✓ | GUARD 要求精确键串 |
| P10 | 删运行时自证断言行 | REJECT | REJECT ✓ | TEST_ASSERTION 缺失 |
| **P11** | 断言行前置 `//` | REJECT | **ACCEPTED ✗** | —（F-01） |
| P12 | `anyMatch(x->true)` 阉割 | REJECT | REJECT ✓ | 要求 `startsWith(…+"=")` |
| P13/P14 | dev 覆盖为第三名字 / JSESSIONID | REJECT | REJECT ✓ | profile 循环 `!= APPROVED` |
| P15 | dev 显式写契约名 | ACCEPT | ACCEPT ✓（`profileOverrides` 记录） | 见 F-04 讨论 |
| **P16** | 真声明 + 引号化重复 `"name": MYSESSION` | REJECT | **ACCEPTED ✗** | —（F-02） |
| P17 | 引号等价值 | ACCEPT | ACCEPT ✓ | F06 整改生效 |
| — | pristine evaluate + 原生 14 控制全跑 | PASS/14 | ✓ | — |

**结论：16 条攻击探针拒 12、漏 4**（同一根因两类：Java 侧不剥注释；YAML 侧不识别引号键）。

## 4. 加固代码本身审出的盲区

1. `GUARD`/`TEST_ASSERTION` 是**原文正则**，无注释剥离 → 死守卫可全绿（F-01）。且 `evaluate` 返回的 `startupGuardLive/runtimeAssertionLive` 布尔会进证据 JSON，把"文本还在"包装成"守卫活着"。仓库先例是 `tests/engineering/T08/verify.py` 剥注释后才检查（`STATE.tasks.T08`："noAudit 死工厂已删…verify.py 剥注释后检查"），同一协议（`守卫只能失败关闭`）应当同标尺。
2. `SCALAR=([^:#]+?):` 允许键含引号 → `"name":` 成为隐形声明（F-02）。`FORBIDDEN` 兜底只拦 JSESSIONID 拼写；第三名字只有运行时守卫兜底，而重复键的 Spring 实际行为（报错拒启动 vs 后者覆盖）本轮未证明、也不可证明（禁 mvn）。
3. 缩进敏感/精确空白匹配是**反向**脆弱：`if (!…equals(…))` 换行到下一行的 `throw` 我验过仍可匹配（`\s*` 跨行），但 `server.servlet.session.cookie.name` 点式扁平键（Spring 合法写法）与 flow mapping 都不识别 → 假拒绝，方向 fail-closed，可接受但应写进 docstring（并入 F-05）。
4. `profileOverrides` 只记录不改判：合理——覆盖值不等 APPROVED 已在同循环 raise，相等覆盖语义无害；真正问题只是台账旧措辞未同步（F-04）。
5. 前瞻面：glob 仅 `application*.yml`；未来 `application.properties` / `application*.yaml` / `name:` 空值行都是静默盲区；Java 侧无其它 cookie 名常量（`git grep` 实证 0 残留）。

## 5. 新发现

| id | 级别 | 发现与 requiredFix |
|---|---|---|
| **T03R6-F01** | **P2** | 闸门不剥 Java 注释：守卫/自证断言被 `//` 或 `/* */` 整体停用后 `evaluate` 仍 ACCEPTED 且证据里写 `startupGuardLive=true`（探针 P08/P09/P11）。requiredFix：对 `code`/`test` 源先剥行注释与块注释再做 `GUARD`/`TEST_ASSERTION` 搜索，新增 `guard-commented-out`、`guard-block-commented`、`assertion-commented-out` 三条反向控制（14→17），重出 `--output` 证据 |
| **T03R6-F02** | P3 | 引号化键对 `cookie_names` 隐形：`name: EDITORIAL_SESSION` + `"name": MYSESSION` 重复键对闸门不可见、FORBIDDEN 兜底亦不触发（探针 P16）。requiredFix：键匹配前剥离引号；或在 cookie 映射的缩进区间内拒绝任何其它 `*name*:` 兄弟行；docstring 记明"重复键运行时行为未证明" |
| **T03R6-F03** | P3 | 报告 §3 自相矛盾残留：:50-52"直接证据是第 3 项里的 `fixationRotationAndLogout`"未随表行更正改写（表行 3 已明确否认第 3 项）。requiredFix：该句改指第 4/10 行（identity 套件），与 STATE"第 3 节已按 F01 更正"的宣称真正一致 |
| **T03R6-F04** | P3 | 台账旧措辞未同步：`machineGates[2]` 仍写"五源全等（契约/增量契约/基础与 prod 配置/Java 常量）"，实况已改为"四文档+代码+测试+全 profile 扫描、prod 未覆盖（继承）"（第五轮 F04 requiredFix 的后半项）。`profile-overrides-cookie-name` 控制只演第一个 profile（字母序 dev）；prod 走同一循环可接受，建议注释一句以免被误读为 prod 专属验证 |
| **T03R6-F05** | P3 | 前瞻脆弱面（当前 HEAD 无违例）：扫描器只见 `application*.yml`（`.properties`/`.yaml`/扁平键/空值行不可见）；点式合法写法会假拒。requiredFix：glob 扩到 `application*.{yml,yaml,properties}` 或至少 docstring 声明边界 |

## 6. 距 T03 可提交人工批准还差什么（我的清单，签署权在人类）

1. F-01 修复并重出证据（三条新控制进 17/17）；F-02/F03 同批修掉——都是小改动，不构成方向问题。
2. 批准提交落地后：若 HEAD 字节再动 `application.yml`/`T03Configuration.java`/`T03PostgresTest.java` 任一，identity 套件须在新字节重跑（同 r05 做法）并绑入 `executedInputs`；否则 r05 只对其当前字节有效。
3. 仍未证明、需由有写权限会话代跑或人工批准的运行时负项：(a) 配置缺失/错名 → 真实容器抛 `T03_COOKIE` 的负向证据；(b) prod profile 真实启动与 `SERVER_SERVLET_SESSION_COOKIE_NAME` 环境变量覆盖顺序；(c) YAML 重复键在 Spring 下的真实行为；(d) 前端/生成客户端端到端消费（T12+ 范围，可留给后续域）。
4. `T03-APPROVAL` 与 G1 只能由人类签署；本判决只是记录，不代宣。

判决词汇限于 PASS / CHANGES_REQUIRED / BLOCKED。证据：`docs/execution/reviews/T03-round6/evidence/checks.json`。
