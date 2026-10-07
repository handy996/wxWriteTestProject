# T03（会话 Cookie 名契约一致性闸门）第十轮整改报告

- 需求来源：`docs/execution/reviews/T03-round9/review.md`（CHANGES_REQUIRED，P1×5 / P2×4 / P3×3，每条附最小复现）。本报告按 **F-01…F-12** 逐条对应；主 agent 的六条裁决记作 **R1…R6**。
- 状态：**整改完成，提交主 agent 复审**。本报告不自评采纳，不构成 T03 / AC-28 / G1 / G2 的通过声明。
- 本轮未执行 `git add` / `git commit`，未写 `docs/execution/STATE.json`，未修改 `tests/engineering/T02|T07|T08/**`、`backend/src/**/cost/**`、`.github/workflows/ci.yml`、`docs/execution/reviews/**`、冻结契约与既有证据。

## 0. 边界与冻结证据核对

只写：`tests/engineering/T03/**`（含 `.gitignore` 内的 `.work/` 草稿）、`backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java`、以及本报告。`backend/src/main/java/com/example/editorial/identity/T03Configuration.java` 与四个 `application*.yml` 本轮**一字未改**（R1 的执行证明靠测试侧真装配，不需要动产品代码）。

`git status --porcelain` 中属于本卡片的条目（其余为主 agent / 并行会话所有，本轮未读写）：

```
 M backend/src/test/java/com/example/editorial/identity/T03SessionCookieGuardTest.java
 M tests/engineering/T03/check_session_cookie.py
 M tests/engineering/T03/evidence/T03SessionCookieGuardTest.txt
 M tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml
 M tests/engineering/T03/evidence/guard-test-binding.json
?? tests/engineering/T03/evidence/config-census.txt
?? tests/engineering/T03/evidence/session-cookie-r10.json
?? docs/execution/reports/T03-Revision-R10.md
```


同表里另有 `M docs/execution/STATE.json` 与 `?? docs/execution/reports/T02-Revision-R06.md`：**不是我写的**（主 agent 与 T02 会话所有，本轮我只读不写）。`tests/engineering/T03/.work/` 在 `.gitignore` 内，所以载荷审计、影子树变异、字节码读数三个草稿脚本不出现在 `git status` 里，但它们是仓库内可重跑的证据：`load-bearing-audit.json` 落在 `.work/`。

历史证据逐字节核对（`Get-FileHash -Algorithm SHA256` 实测）：

| 文件 | 实测 SHA-256 | 与交回值 |
| --- | --- | --- |
| `evidence/session-cookie-r08.json` | `6EB8EF60213DF62463E07D989B99F3998FC2CF6B4D712D8E92C7A66D724DFE7D` | 一致 |
| `evidence/session-cookie-r09.json` | `F18C88EFA51303A832388745017986EAAB27F1B2BA5AF44C8B860602C9E5E6F7` | 一致 |

本轮新增证据 `evidence/session-cookie-r10.json` 由闸门自身写出，实测 SHA-256 `8F1E9CFA173471A926AFFE06AEE9D342C0F27C9877C482C139C100989B6DA02E`（`--force` 只覆盖本轮早些时候那份 98/31 的过期读数，未触碰 r01…r09）。

### 0.1 主线快照与本会话在途字节（主 agent 的过错通报，照其要求登记）

主 agent 在做仓库级换行保真修复时用了 `git add --renormalize tests/engineering`，该命令把本会话 5 个**在途文件**以“修换行”的名义记进 `e4f0f3c`：`check_session_cookie.py`（入库 58,746→155,999 B）、`record_guard_binding.py`、`evidence/T03SessionCookieGuardTest.txt`、`.xml`、`guard-test-binding.json`。**`e4f0f3c` 内含本会话的中间快照，最终集成以我工作树最新字节为准**（下表就是交付读数）。我没有执行、也不会执行 `git checkout` / `git restore`：工作树字节是权威，主线那个是中间态。

本报告没有任何读数建立在“相对 HEAD 的 diff 行数 / 内容差异”之上（我只引用 `git status --porcelain` 的条目名与文件自身字节数），所以该通报不需要我重算任何结论；下表补齐的是交付指纹本身。

| 文件 | 交付字节 | SHA-256 前 12 | 工作树 blob | HEAD blob | `e4f0f3c` blob | disk 与 HEAD |
| --- | --- | --- | --- | --- | --- | --- |
| `check_session_cookie.py` | 162443 B | `5AED73E5F4A3` | `5c1d9e4a4f0c` | `b19895f4bade` | `b19895f4bade` | 不一致（在途） |
| `record_guard_binding.py` | 8078 B | `3F7D00EAA18D` | `6844752804d4` | `6844752804d4` | `6844752804d4` | 一致 |
| `T03SessionCookieGuardTest.txt` | 363 B | `7CC055B418A7` | `349a55d74395` | `23bf7d6e8ff2` | `23bf7d6e8ff2` | 不一致（在途） |
| `T03SessionCookieGuardTest.xml` | 33734 B | `BCDE9C7E37B9` | `baebab754f6a` | `bbf177d1af17` | `bbf177d1af17` | 不一致（在途） |
| `guard-test-binding.json` | 4920 B | `2116E03E8AE8` | `389774976cc9` | `4ed622154588` | `4ed622154588` | 不一致（在途） |
| `config-census.txt` | 792 B | `E2FF588E1ED4` | `0b8209c2487f` | — | 不在该提交 | 不在 HEAD（本轮新增） |
| `session-cookie-r10.json` | 60738 B | `8F1E9CFA1734` | `cc54b4ff073b` | — | 不在该提交 | 不在 HEAD（本轮新增） |
| `T03SessionCookieGuardTest.java` | 26824 B | `3FA69C6ED386` | `eab203691020` | `ba0438b08fed` | `ba0438b08fed` | 不一致（在途） |


表里没有本报告自己：写那一行会改变被那一行引用的字节，自引用指纹由集成时现场计算。`record_guard_binding.py` 的 disk 与 HEAD 恰好一致，与你通报里的“只有它当下相等”对得上；其余四个在途文件仍以工作树为准，我不会用 `git checkout` / `git restore` 去“求干净”。

## 1. 基线与终态（每条必跑命令的真实退出码）

| 命令 | 退出码 | 实测读数 |
| --- | --- | --- |
| `python tests/engineering/T03/check_session_cookie.py` | **0** | `PASS - approved name 'EDITORIAL_SESSION'; 106/106 negative controls rejected, 36/36 benign probes accepted`（r08 为 48/11，r09 为 49/12） |
| `python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r10.json --force` | **0** | 同一读数；写出 12 个输入哈希（含 `census`、`recorder`、`binding`） |
| `python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1` | **0** | `exitCode 0`，`counts {tests:15, failures:0, errors:0, skipped:0}`，10 个绑定输入 + `census` |
| `python tests/engineering/T02/check_contracts.py` | **0** | `Approved T00 rc.3: 27 hashes verified, no regeneration` |
| `python tests/engineering/T03/.work/review_replay.py` | **0** | 复审 29 个最小复现形态逐条回放：`29 shapes, 0 disagreed` |
| `python tests/engineering/T03/.work/bytecode_reading.py` | **0** | 7 个 `identitySecurity` 调用点形态的 javac + javap 实测（见 §2 F-01） |
| `python tests/engineering/T03/.work/mutate_shadow.py` | **0**（退出码即“预期结果全部命中”） | 影子树里 15 个改过的产品/配置形态真跑 pinned maven：4 类假形状 mvn **1** 并由装配用例拒绝、3 类 javac **1** 直接拒绝、2 类良性形态 mvn **0**、4 类配置藏名形态被 `contractNameBindsInEveryProfileLayerThroughTheRealLoaders` 拒绝、env 风格下划线键良性 **0**；掏空形态 mvn **0** 而闸门 REJECTED |
| `python tests/engineering/T03/.work/load_bearing.py`（载荷审计） | **0**（该脚本把「还剩无人看守的判据」当失败退出，所以 0 是结论不是默认值） | 54 个桩：46 条判据由控件看守、3 条为共享证人、4 条由良性探针整体看守、1 条声明为文案生成器，**无人看守 0 条** |

守卫测试用例数 **7 → 15**（surefire XML `tests="15"`）。新增 8 条不是数量游戏，而是 R1/R2 要求的"执行面"：

- R1：`assembledIdentitySecurityStartsWithContractCookieName`、`assembledIdentitySecurityAbortsOnNonContractCookieName`、`assembledIdentitySecurityAbortsOnInsecureProdCookie` 用 `AnnotationConfigApplicationContext.register(T03Configuration.class)` 真装配并 `getBean("identitySecurity", SecurityFilterChain.class)`，所以"调用点是否被执行"由 JVM 判定。非契约名走的是产品代码自身的 `T03_COOKIE` 抛出路径（`verifySessionCookieContract` 的第二条子句）。
- R2：`contractNameBindsInEveryProfileLayerThroughTheRealLoaders`、`flowAliasAndMergeKeyShapesAreLiveToTheRealLoader`、`configDirectoryLayerOvertakesTheResourcesRoot`、`commentsAndEnvStyleKeysBindNoCookieName`、`duplicateCookieNameKeysAbortLoading` 走 Spring 的 `YamlPropertySourceLoader` / `PropertiesPropertySourceLoader` + `Binder`。

执行角色（由代码结构读出，不是钉住的短语）：`assemblyAbort 2 / assemblyLive 1 / binderCensus 1 / binderShapes 3 / loaderAbort 1 / guardAbort 6 / guardLive 2`，另有锚点常量层。

## 2. 逐条整改（F-01 … F-12）

### F-01（P1，R1）深度 1 的花括号计数：双向都错

- 改了什么：可达性不再靠数括号。`scan_header()` 在深度 0 遇 `{` 即结束语句头（此前该分支不可达：`while (false) { … }` 被读成 `lambda`，整个 bean 体被吞）；`describe_dead_path()` 增加无括号规则（`if/while/for` 条件若能被 javac 折成 `false`，其唯一语句不可达）；`guard_call_site()` 沿 `bean_bodies()` 展开真实语句体并解释死亡原因。
- **执行证明**（R1a 的核心：不是"看起来会执行"，而是"不执行就红"）。影子树里改 `T03Configuration.java` 的调用行，跑 pinned maven 的 `-Dtest=T03SessionCookieGuardTest`，并用 pinned JDK 的 `javap -c` 数 `identitySecurity` 体内 `invokestatic … verifySessionCookieContract` 的条数：

  | 形态（改在调用行上/周围） | javac | mvn 退出码 | `identitySecurity` 体内 invokestatic 条数 | 结果 |
  | --- | --- | --- | --- | --- |
  | 原始 | 0 | 0 | **1** | 15 条全绿 |
  | `if (false)` + 换行调用（无括号） | 0 | **1** | **0** | `assembledIdentitySecurityAbortsOnNonContractCookieName`、`assembledIdentitySecurityAbortsOnInsecureProdCookie` |
  | `if (Boolean.FALSE.booleanValue())` 无括号 | 0 | **1** | 未测 | 同上两条用例 |
  | `static final boolean T03_SKIP = false;` + `if (T03_SKIP)` 无括号 | 0 | **1** | 未测 | 同上两条用例 |
  | `if(!env.matchesProfiles("prod")) return http.build();` 条件提前返回 | 0 | **1** | 未测 | `assembledIdentitySecurityAbortsOnNonContractCookieName`、`assembledIdentitySecurityStartsWithContractCookieName` |
  | 转义注释包住调用（`\u002f\u002a … \u002a\u002f`） | 0 | **1** | **0** | 前两条装配用例 |
  | `while (false) { 调用 }` | **1** 拒绝（unreachable statement） | 未跑（编译期即红） | — | 没有新报告，不冒充跑过 |
  | `return http.build();` 后无条件跟调用 | **1** 拒绝（unreachable statement） | 未跑 | — | 同上 |
  | `while (false) 调用;` 无括号单语句 | **1** 拒绝（unreachable statement） | 未跑 | — | 同上 |
  | `try { 调用 } finally { }` | 0 | **0** | 未测 | 良性半边：不假红 |
  | `switch (…) { default: 调用 }` | 0 | **0** | 未测 | 良性半边：不假红 |
  | `else { 调用 }`（配真实 `if`） | 未进影子树 | — | — | 闸门良性探针 `guard-call-in-else-arm` 保持绿 |

  `invokestatic` 一列由 `.work/bytecode_reading.py` 与 `.work/mutate_shadow.py` 各测一次（两者退出码都是 0，结论一致）：原始 **1**、常量假分支（无括号 `if(false)`）**0**、转义注释 **0**、奇数反斜杠换行注释 **1**、偶数反斜杠换行注释 **0**、`\u0061` 合法标识符 **1**、双反斜杠注释串 **1**。标“未测”的形态只跑到 mvn 层。

  这张表同时覆盖 R1b 要求的六类假形状：无括号 `if (false)`、`Boolean.FALSE.booleanValue()`、`static final false`、无条件提前 `return`、转义注释包裹、`while(false)` —— 六类里四类由 surefire 变红证明，两类（提前 return、`while(false)` 单语句）javac 直接拒绝编译，我没有把它们包装成"跑绿了"。闸门侧对同一批形状另有内置控件：`guard-call-in-constant-false-branch`、`guard-call-under-boolean-false`、`guard-call-under-static-final-false`、`guard-call-under-while-false`、`guard-call-after-unconditional-return`、`guard-call-under-escaped-block-comment`、`guard-call-under-escaped-line-comment`、`guard-call-inside-text-block-prose`、`guard-call-moved-into-lambda`、`guard-call-moved-to-dead-method`、`call-only-recited-in-a-string`；三条良性半边 `guard-call-in-try-finally`、`guard-call-in-switch-default`、`guard-call-in-else-arm` 保持绿。
- 为什么这套执行机制覆盖 R1 的调用点：三条装配用例把 `identitySecurity` 真注册、真取出；若调用点被包进不可达分支，`getBean` 仍能成功但 `verifySessionCookieContract` 不再抛 ⇒ 两条"必须抛"的用例失败；若调用点被完全删除，非契约名与 prod 不安全项都不再抛 ⇒ 同样失败。`else`/`try…finally`/`switch default` 形态下调用确实执行 ⇒ 用例保持绿 ⇒ 上一版"假红"的通道被这条实测堵住。
- 静态层的诚实位置（R1b 辅助）：载荷审计里 `static-reachability` 桩使 13 条控件失去拒绝、`bean-bodies` 71、`dead-path-walk` 7、`constant-folding` 4、`braceless-dead-rule` 3、`brace-stop-in-header` 1 —— 这套判据有人看守，但它在报告里的身份是**辅助**：判定"执行"的是上表，不是它。
- 仍未证明：编译期不可判定的假条件（如 `if (env.getProperty("k","no") == null)`）静态判不了，执行面也没法在离线用例里造出这种部署期取值。

### F-02（P1，R2/R3）别名 / 合并键 / 多行 flow 里藏第二个名

- 改了什么：**取消"手写 YAML 普查当判据"**。`application*.yml|yaml|properties` 与 `config/` 同名层由测试侧真实加载器读取并绑定，结果写进 `evidence/config-census.txt`（`T03-SURFACE` 6 条模式；`T03-CENSUS` 4 个文件 + SHA-256；`T03-BIND base/dev/mock/prod → EDITORIAL_SESSION`）。闸门只做一件事：从当前字节重新推导并逐字段比对这份执行证书（`binder_certificate`）。文本普查降级为第二证人 + 不可归因形状的说明。
- 实测（mvn 退出码）：多行 flow 藏名 → **1**；flow 值后注释藏名 → **1**；`&anchor` + `<<: *alias` 合并键藏名 → **1**；`config/application.properties` 藏名 → **1**；四条都被同一条已执行用例拒绝：`contractNameBindsInEveryProfileLayerThroughTheRealLoaders`。良性半边：`config/application.properties` 写 env 风格下划线键 `SERVER_SERVLET_SESSION_COOKIE_NAME=JSESSIONID` → **0**（实测普通 property 源不做 env 风格松散绑定 ⇒ 这条不该红，也确实没红）。
- 不可见 ⇒ 响亮失败：任一层出现 `spring.config.location` / `optional:` ⇒ `config: a location override moves the config surface outside this census, which cannot attribute it -> […]`（控件 `code-declares-config-location`、`config-declares-location-override`、`config-imports-optional-location`）。证书与当前字节不符 ⇒ `binding: the census certificate is stale for the current bytes -> […]`；文件面不符 ⇒ `the executed census and this gate disagree about the config surface`；无人读的扩展名 ⇒ `config-unread-extension-on-surface`（红）。
- 仍未证明：多 location 覆盖时的**优先级顺序**（只证"不可归因即拒绝"）；`application*.yaml` 后缀本 checkout 里只有模式，没有实例文件。

### F-03（P1，R2/R5）普查面只看 resources 根

- 改了什么：普查面 = 测试侧枚举的 6 条 `classpath*:` 模式（根与 `config/` × `yml|yaml|properties`），并与记录双向一致；目录层由 `configDirectoryLayerOvertakesTheResourcesRoot` 真跑证明。
- 实测退出码：见 F-02（`config/application.properties` ⇒ mvn 1）。闸门控件：`config-directory-layer-case-hollowed`、`config-adds-unrecorded-file`、`config-surface-pattern-dropped`、`binding-config-layer-unrecorded`。
- 仍未证明：`config/` 之外的自定义目录，除非触发 F-02 的 location 响亮失败。

### F-04（P1，R1/R6）守卫测试可被掏空且 surefire 计数不变

- 改了什么：不再钉短语。`executed_roles()` 从结构读出每条已执行用例驱动了哪一层（真 context / `Binder` / property 源加载器 / 抛与不抛，按 import 与 helper 跟进）；除"每层至少 N 条"外增加**逐用例规则**（任何已执行用例不驱动任何可命名行为 ⇒ 红），并在 `binding_check` 里双向比对记录的 `executedRoles` 与当前文件读出的角色。
- 复审的原始复现（把已执行用例体换成文本块散文）：第一版散文是裸文本块语句 ⇒ **javac 拒绝**（not a statement；另外测得块内出现裸三引号会破坏开界符）；改成赋值形式 `String prose = …` 后 **javac 0、mvn 0、15 条全绿**，而闸门 **REJECTED**：`guardTest: the executed cases no longer cover every layer -> assemblyAbort: found 0, need at least 1; …`。这条差异（跑绿 ≠ 证明还在）就是 F-04 的闭合方式；`.work/mutate_shadow.py` 的 `all-bodies-replaced-by-prose` 行就是这条复现，退出码 0 表示预期全部对上。
- 内置控件：`guard-test-container-default-case-hollowed`（掏空单条）、`binder-shape-floor-loses-its-cases`（合法退役两条 binderShapes 用例并把记录改成自洽 ⇒ 只有角色下限会红）、`binder-shape-case-hollowed`、`config-directory-layer-case-hollowed`、`assembly-case-hollowed`、`assembly-helper-hollowed`、`file-emptied-of-executed-roles`、`guard-test-case-renamed`、`binding-roles-miscredited`。
- 载荷审计：`case-closure` 桩 44 条控件失去拒绝、`executed-roles` 桩 1 条、`per-case-role` 桩 1 条、`recorded-roles` 桩 1 条。
- 仍未证明：把用例体换成**仍然驱动行为**的等价重写会保持绿（这是设计目标，不是漏洞）；掏空后 `mvn` 仍全绿 ⇒ 只有闸门在看，见 §5。

### F-05（P1，R1/R3）`JSESSION\u0049D` 拼写绕过漂移扫描

- 改了什么：禁名扫描作用在 **JLS 3.3 平移之后的无注释视图**（`forbidden_offsets`），转义规则与 javac 同一条（见 F-08）。豁免只给真正演示容器默认名的那一条用例（`containerDefaultNameAbortsStartup`），用例改名移动豁免 ⇒ 红（`guard-test-hollow-container-default`）。
- 实测：`static final String OLD = "JSESSION\u0049D";` ⇒ 红（`guardTest: the container default is named in code outside containerDefaultNameAbortsStartup at […]`）；`JSESSIONID` 写在 Java 注释里 ⇒ **绿**；写在 `application-prod.yml` 注释里 ⇒ **绿**（R3 后半，良性半边 `container-default-mentioned-in-prose-only`、`container-default-in-config-comment`、`container-default-mentioned-in-prose-only`）。
- 载荷审计：`jls-translation` 桩 4 条控件失去拒绝 + 1 条探针变红；`drift-scan` / `container-default-exemption` 桩各 3 条（含新控件 `container-default-mentioned-in-a-text-block`：文本块是**值**不是注释，所以里面写容器默认名仍算代码 ⇒ 红；这条边界是被本轮一次假红逼出来的，现钉成控件）。
- 仍未证明：非 UTF-8 源码编码（本轮一律按 UTF-8 读，并与 `javac -encoding UTF-8` 对齐）。

### F-06（P2，R4）CI 步骤在场而不再执法

- 改了什么：结构判定。找到所有运行本闸门的步骤 ⇒ 逐个算"可被跳过"的阻碍（步骤/作业 `if:`、`continue-on-error`、`needs` 祖先链、只有 schedule 的触发器）⇒ 没有一个不可跳过的拷贝就红：`ci: no job path in .github/workflows/ci.yml reaches the gate that cannot be skipped -> …`、`ci: job … runs this gate but the workflow triggers are [schedule], so nothing forces it to run`。
- 反向控制（10 条，全部实测红）：`ci-drops-cookie-gate`、`ci-gate-step-continue-on-error`、`ci-gate-step-skippable-if`、`ci-job-continue-on-error`、`ci-job-skippable-if`、`ci-gate-behind-skippable-ancestor`、`ci-workflow-schedule-only`、`ci-gate-path-renamed`。
- 良性半边（8 条 `ci-*` 探针，全部实测绿）：加 `shell: bash`、步骤改名、改 `python3`、块标量写法、加无关且未设门禁的 job、第二个 job 再跑一次同一闸门、加 `workflow_call` 触发器、把步骤挪到同一 job 更后面。
- 载荷审计：`ci-structure` 桩 10 条、`ci-clean` 6 条、`ci-skippable-copies` 6 条、`ci-needs-chain` 1 条、`ci-trigger-required` 1 条控件失去拒绝。
- 仍未证明：**GitHub Actions 真跑会不会红**（离线只有 YAML 结构判定）。交回主 agent。

### F-07（P2，R5）绑定 artefact 可徒手伪造

- 改了什么：记录器真跑 mvn，argv 由 `subprocess` 实测记录（含本轮新加的 `-Dmaven.repo.local`，见"本轮自曝"）、退出码、每个输入指纹、`surefireJar` + `surefireJarSha256`、`jdk` 路径 + 指纹 + `jdkVersion`/`jdkVendor`（自述改为 `toolchain: "re-hashed here"`，不再暗示由 mvn 记录）。闸门侧：重新计算 jar 与 JDK launcher 的 SHA-256，并与 surefire XML 的 `java.home`/`java.version`/`java.vendor` 交叉核对；`binding_inputs()` 与记录 `inputSha256` **双向**比较（缺项、多项都红）；`.properties`/`config/` 层未记录即红；记录用例名 ⇔ XML `testcase` 集合、XML 自报计数 ⇔ 元素数、`failures/errors/skipped` 必须为 0；逐条校验。
- 实测：伪造 25 条 `binding-*` 控件全部红（含 `binding-surefire-jar-hash-wrong`、`binding-surefire-jar-path-foreign`、`binding-jdk-hash-wrong`、`binding-jdk-not-the-run-java-home`、`binding-jdk-vendor-disagrees`、`binding-xml-tests-count-inflated`、`binding-roles-miscredited`…）；等价改写探针 `binding-note-whitespace-rewrite` 保持绿 ⇒ 钉的是事实不是 JSON 排版。记录器本次真实退出码 **0**（§1）。
- 载荷审计：`toolchain-rehash` 桩 7 条、`argv-equality` 4 条、`binder-certificate` 6 条、`xml-*`/`recorded-*` 各 1-2 条控件失去拒绝；`input-set-both-directions` 桩属"共享证人"（mutant 仍被另一面拒绝，只是换了原因）。
- 仍未证明：**是否真有人**跑过记录器（本轮只证"伪造同样通不过"，这正是复审 §四 F-07 划的边界）；JDK 目录除 launcher 外未逐个哈希。

### F-08（P2，R3）转义解码缺偶数反斜杠规则

- 改了什么：`translate_unicode_escapes()` 按 JLS 3.3 实现：只有**偶数个**前导反斜杠的 `\uXXXX` 参与平移；`XXXX` 非四个十六进制位 ⇒ 与 javac 同样判非法转义。扫描/平移只作用于代码视图，注释里的转义不再被当代码。
- 实测不对称已消除（pinned JDK，`javac -J-Duser.language=en -proc:none`）：`"\uZZZZ"` ⇒ javac **1**（illegal unicode escape），闸门同样红；`"x\u000ay"` ⇒ javac **1**（unclosed string literal），闸门同样红。
- 良性半边（javac **0** 且闸门绿）：`verifySessionCookieContr\u0061ct(env);`（合法标识符转义，旧闸门会假红）；`// runbook \u000a` + 换行调用（奇数反斜杠 ⇒ 平移成真换行 ⇒ 调用是代码：javap `invokestatic` = 1）；`Object note = "\\u002a runbook \\u002f";`（双反斜杠不平移 ⇒ 调用仍在：1）；双反斜杠 + `\u000a` 注释（不平移 ⇒ 平移不吞掉下一行，注释仍是注释）。
- 与 javac 一致的一侧（红是应该的）：偶数反斜杠 `\u000a` 写在注释里 ⇒ 平移成新行、注释吞掉调用 ⇒ javap `invokestatic` = 0，闸门红（控件 `escape-swallowing-a-closing-quote` 同批）。
- 载荷审计：见 F-05 的 `jls-translation` 行。
- 仍未证明：`Native2Ascii` 之类外部预处理器路径；BOM 与编码组合。

### F-09（P2/P3，R3/R6）注释与文档提 `JSESSIONID` 即红 + 字面量遮蔽攻击面

- 改了什么：注释与文本块散文不算代码；判据由**同一个词法器的三个投影**给出（`translated` / `masked` / `statements`），两套遮罩实现已删（见 F-11）。
- 良性半边实测绿（6 条）：Java 注释里的 `JSESSIONID`；`application-prod.yml` 注释里的 `JSESSIONID`；`# spring.config.location=…`；flow 值后跟注释；文本块散文提**受锚名**且真字面量仍在（`anchor-name-in-prose-and-live-literal`）；双反斜杠字符串提注释符号（`double-backslash-note-in-a-string`）。
- 反向控制实测红（本轮新增/加强）：容器默认名写进活代码、写成转义、写成文本块**值**；守卫调用被注释掉；只把调用抄进字符串（`call-only-recited-in-a-string`）；只把抛发消息抄进字符串（`message-only-in-literal`、`secure-clause-only-in-literal`）；受锚名只留在文本块散文里（`anchor-name-only-in-text-block-prose`）。
- 载荷审计：`comment-blanking` / `textblock-blanking` 桩使 **36 条良性探针全部变红**，`literal-masking` 桩 1 条控件 + 36 条探针 ⇒ "注释/散文不算代码"这条判据是被探针集整体看守的，不是靠文案。
- 仍未证明：散文与代码的边界只能由投影规则定义，语义级"这段字符串其实是配置"不判。

### F-10（P3，R6）钉措辞而不是钉行为

- 改了什么：(a) 执行角色由结构读出（F-04）；(b) 等价改写必须保持绿 —— `guard-reflowed-with-whitespace`、`annotation-between-bean-and-signature`、`call-moved-to-another-assembled-bean`、`binding-note-whitespace-rewrite`、CI 的四条排版探针等，36 条良性半边全绿；(c) 静态结论文案的口径改由载荷审计反过来核对：本轮删掉两条"桩化后没有任何判定变化"的规则（`live()` 里跳过字面量内部命中的位置规则、`live_literals` 里的散文过滤），并把三处过度声称的 docstring 改写为实测事实（`live()`、`construct_reason`、`describe_dead_path`）。
- 载荷审计对应行：`literal-content-skip` 与 `prose-in-live-literals` 两个桩在上一轮审计里 `lost 0 / moved 0 / probes 0` ⇒ 判据已删；`yaml-construct-reasons` 桩同样不动判定 ⇒ 它不判据，只生成"这条形状为何不能按文本归因"的说明，函数 docstring 现在明说这一点（归因由 `census_yaml` 拒、结论由 binder 证书下，桩化那两处分别让 91 条、6 条控件失去拒绝）。
- 仍未证明：等价改写集合不可能穷尽（36 条是抽样）。

### F-11（P3，R6）两个词法器对文本块不一致

- 改了什么：**只留一个扫描器**。`JavaSource` 一次分词，三个投影由同一 token 流生成；`mask_literals` / `literal_spans` 两套遮罩删除。`tokenizer_certificate()` 每次运行都把该实现放到全部真实 Java 源 + 600 例确定性合成形状上自测，并且闸门现在**要求这项自测报告数字**（`sources/corpusFiles/divergences` 缺项或语料为空即红）：桩化这项自测会让 36 条良性探针全部变红 ⇒ 这条"必须报告"不是装饰。
- 本轮实测：可编译形状 496/600（其余 javac 也拒绝：未闭合字面量/注释、裸文本块不是语句），投影分歧 **0**。
- 载荷审计：`tokenizer-selfcheck` 桩 `probes 36`（原为 unwatched，因它只自测、不改判定 ⇒ 现由"必须报告数字"这条要求看守）。
- 仍未证明：600 例合成形状不是全集；真实库里没有 `.yaml` 后缀实例文件。

### F-12（P3）台账三处记账不一致

本轮不写 `STATE.json`，素材交回主 agent：`T03-R6-GATE` 的 OPEN+closedAt 应去掉；"闸门未接入 CI ⇒ 零自动拦截"应改写为"已由 CI 结构执法闭合（10 条控件 + 8 条良性半边），但仍无真实 Actions 运行证据"；`STATE.json` 第 45 行附近"9 次"的措辞与本轮 15 条用例的差额需一并更正。

## 3. 载荷审计（R6："留一条没人看守的检查比删掉更糟"）

`.work/load_bearing.py` 把闸门源码里每一条判据换成只会放松、不会加严的桩（54 个桩），在桩化模块里重跑整个 roster（106 控件 + 36 探针），并镜像闸门自身的记录策略：控件未动记录就重新指纹化，探针一律重新指纹化 —— 此前正是这条策略的差异让 14 条控件"看着全红"。分类口径：

- `lost`：桩化后该控件不再因**它自己那条原因**被拒绝 ⇒ 无人看守；
- `moved`：仍被同一面拒绝但换了原因（另一面冗余接手）⇒ 共享证人，不是无人看守；
- 桩化后某条**良性探针**变红 ⇒ 该判据由良性半边看守。

| 判据桩 | 声称 | lost | moved | 探针翻红 | 分类（首见证） |
| --- | --- | --- | --- | --- | --- |
| `jls-translation` | unicode escapes are translated the way javac reads them | 4 | 0 | 1 | 控件看守（`container-default-spelled-with-escape`, `escape-swallowing-a-closing-quote`…） |
| `tokenizer-selfcheck` | the projections are measured against 600 synthetic shapes and every real source | 0 | 0 | 36 | 良性半边看守（`anchor-name-in-prose-and-live-literal`, `annotation-between-bean-and-signature`…） |
| `comment-blanking` | comments are blanked out in every view | 0 | 0 | 36 | 良性半边看守（`anchor-name-in-prose-and-live-literal`, `annotation-between-bean-and-signature`…） |
| `literal-masking` | the masked view blanks literal contents | 1 | 1 | 36 | 控件看守（`call-only-recited-in-a-string`） |
| `textblock-blanking` | the statements view blanks text-block prose | 0 | 0 | 36 | 良性半边看守（`anchor-name-in-prose-and-live-literal`, `annotation-between-bean-and-signature`…） |
| `static-reachability` | guard_call_site decides whether the assembly reaches the call | 13 | 0 | 0 | 控件看守（`call-only-recited-in-a-string`, `guard-call-after-unconditional-return`…） |
| `bean-bodies` | which method bodies a bean assembly runs | 71 | 0 | 36 | 控件看守（`anchor-hides-name-text-cannot-attribute`, `anchor-name-only-in-text-block-prose`…） |
| `constant-folding` | conditions javac can fold to false are dead | 4 | 0 | 0 | 控件看守（`guard-call-in-constant-false-branch`, `guard-call-under-boolean-false`…） |
| `braceless-dead-rule` | a brace-less constant-false if/while/for never runs its single statement | 3 | 0 | 0 | 控件看守（`guard-call-in-constant-false-branch`, `guard-call-under-boolean-false`…） |
| `brace-stop-in-header` | a top-level brace ends a statement header, so a body is a body | 1 | 0 | 0 | 控件看守（`guard-call-under-while-false`） |
| `dead-path-walk` | describe_dead_path explains why a call is unreachable | 7 | 0 | 0 | 控件看守（`guard-call-after-unconditional-return`, `guard-call-in-constant-false-branch`…） |
| `guard-body-scope` | the guard's clauses are judged inside the guard's own body | 13 | 1 | 0 | 控件看守（`guard-line-deleted`, `guard-message-prefix-changed`…） |
| `cookie-name-clause` | the cookie-name comparison is present and reachable | 1 | 2 | 0 | 控件看守（`guard-reads-wrong-property`） |
| `prod-if-clause` | the matchesProfiles("prod") branch is present and reachable | 3 | 0 | 0 | 控件看守（`prod-branch-short-circuited`, `prod-check-neutered`…） |
| `secure-clause` | the secure attribute is read from the environment | 2 | 0 | 0 | 控件看守（`prod-secure-default-flipped`, `secure-clause-only-in-literal`） |
| `http-only-clause` | the http-only attribute is read from the environment | 1 | 0 | 0 | 控件看守（`prod-http-only-clause-deleted`） |
| `same-site-clause` | the same-site attribute is compared to strict | 1 | 0 | 0 | 控件看守（`prod-same-site-clause-deleted`） |
| `guard-messages` | each rejection carries its T03_COOKIE message | 3 | 0 | 0 | 控件看守（`guard-line-deleted`, `guard-message-prefix-changed`…） |
| `runtime-assertion` | the integration test asserts the issued cookie name | 2 | 0 | 0 | 控件看守（`runtime-assertion-commented-out`, `runtime-assertion-deleted`） |
| `drift-scan` | the container default may not be named in code | 3 | 0 | 0 | 控件看守（`container-default-mentioned-in-a-text-block`, `container-default-spelled-with-escape`…） |
| `container-default-exemption` | only the exempt case may name the container default | 3 | 0 | 0 | 控件看守（`container-default-mentioned-in-a-text-block`, `container-default-spelled-with-escape`…） |
| `anchor-literal` | the guard test holds the approved name as a live literal | 2 | 0 | 0 | 控件看守（`anchor-name-only-in-text-block-prose`, `guard-test-anchor-literal-dropped`） |
| `prod-attribute-paths` | the production attribute names appear in live test code | 1 | 0 | 0 | 控件看守（`guard-test-prod-clauses-dropped`） |
| `case-closure` | assertions are followed through the file's own helper methods | 44 | 11 | 36 | 控件看守（`anchor-hides-name-text-cannot-attribute`, `anchor-name-only-in-text-block-prose`…） |
| `executed-roles` | each layer keeps its minimum number of executed cases | 1 | 3 | 0 | 控件看守（`binder-shape-floor-loses-its-cases`） |
| `per-case-role` | every executed case drives a behaviour the gate can name | 1 | 3 | 0 | 控件看守（`guard-test-container-default-case-hollowed`） |
| `yaml-census` | the YAML census attributes declarations across the whole surface | 91 | 7 | 36 | 控件看守（`anchor-hides-name-text-cannot-attribute`, `anchor-name-only-in-text-block-prose`…） |
| `properties-census` | properties layers are censused | 0 | 1 | 0 | 共享证人（`properties-layer-wrong-name`） |
| `yaml-flow-expansion` | multi-line flow mappings are folded before reading | 1 | 2 | 1 | 控件看守（`flow-profile-override-cookie-name`） |
| `yaml-comment-stripping` | trailing comments are cut before a line is parsed | 0 | 0 | 2 | 良性半边看守（`comment-after-flow-value`, `location-override-mentioned-in-comment`） |
| `yaml-construct-reasons` | anchors, merge keys and tags are reported as not attributed by text | 0 | 0 | 0 | 声明为文案生成器 |
| `unread-extension` | config files whose extension no face reads are reported | 1 | 0 | 0 | 控件看守（`config-unread-extension-on-surface`） |
| `location-overrides` | declarations that move the surface out of the census | 3 | 0 | 0 | 控件看守（`code-declares-config-location`, `config-declares-location-override`…） |
| `contract-frozen-name` | the frozen contract declares the approved name | 1 | 1 | 0 | 控件看守（`contract-renames-cookie`） |
| `contract-agreement` | the two contracts agree with each other | 1 | 1 | 0 | 控件看守（`additive-scheme-extra-key`） |
| `binder-certificate` | the executed binder/census certificate is re-derived and compared | 6 | 0 | 0 | 控件看守（`anchor-hides-name-text-cannot-attribute`, `config-adds-unrecorded-file`…） |
| `argv-equality` | the recorded argv against the pinned constant table | 4 | 0 | 0 | 控件看守（`binding-command-dtest-swapped`, `binding-command-echo-argv`…） |
| `toolchain-rehash` | provider jar and JDK launcher re-hashed and cross-checked with the XML | 7 | 0 | 0 | 控件看守（`binding-jdk-hash-wrong`, `binding-jdk-not-the-run-java-home`…） |
| `input-set-both-directions` | the recorded input keys against the surface this gate enumerates | 0 | 3 | 0 | 共享证人（`binding-config-layer-unrecorded`, `binding-input-key-missing`…） |
| `input-bytes` | every bound input re-hashed against the record | 1 | 0 | 0 | 控件看守（`binding-profile-stale`） |
| `xml-name-set` | recorded case names against the XML's own testcases | 1 | 0 | 0 | 控件看守（`binding-testnames-fabricated`） |
| `xml-count-internal` | the XML's declared test count against its own testcase elements | 1 | 0 | 0 | 控件看守（`binding-xml-tests-count-inflated`） |
| `xml-clean` | the recorded run has to be clean | 2 | 0 | 0 | 控件看守（`binding-xml-failure`, `binding-xml-skipped-case`） |
| `xml-sha` | the tracked XML's hash | 1 | 0 | 0 | 控件看守（`binding-xml-sha-wrong`） |
| `recorded-counts` | the recorded counts against the re-parsed XML | 1 | 0 | 0 | 控件看守（`binding-counts-disagree-with-xml`） |
| `recorded-roles` | which case proves which layer, recorded and current, both directions | 1 | 0 | 0 | 控件看守（`binding-roles-miscredited`） |
| `recorded-current-cases` | the recorded run executed exactly the cases the current file has | 0 | 1 | 0 | 共享证人（`guard-test-case-renamed`） |
| `note-verbatim` | the note is exactly the recorder's wording | 1 | 0 | 0 | 控件看守（`binding-note-claim-drift`） |
| `recorded-exit-code` | the recorded run succeeded | 1 | 0 | 0 | 控件看守（`binding-exit-code-nonzero`） |
| `ci-structure` | the CI structural enforcement of the gate step | 10 | 0 | 0 | 控件看守（`ci-drops-cookie-gate`, `ci-gate-behind-skippable-ancestor`…） |
| `ci-clean` | a step or job that can be skipped does not police anything | 6 | 0 | 0 | 控件看守（`ci-gate-behind-skippable-ancestor`, `ci-gate-step-continue-on-error`…） |
| `ci-needs-chain` | an ancestor job that could be skipped | 1 | 0 | 0 | 控件看守（`ci-gate-behind-skippable-ancestor`） |
| `ci-skippable-copies` | every copy of the gate step is checked for skippability | 6 | 0 | 0 | 控件看守（`ci-gate-behind-skippable-ancestor`, `ci-gate-step-continue-on-error`…） |
| `ci-trigger-required` | the job is reached by push or pull request | 1 | 0 | 0 | 控件看守（`ci-workflow-schedule-only`） |

## 4. 静态检查现在证明了什么（R1c：措辞不得超过实际证明的东西）

证明（每一条都有上表或内置控件支撑）：

1. 在当前字节上，契约文本（冻结与附加 OpenAPI）、Java 常量、prod 配置层、surefire XML、绑定记录五者互相一致；单改任何一面都红。
2. 记录里的执行事实可以重新推导：mvn argv、退出码、输入指纹集合（双向）、provider jar 与 JDK launcher 的再哈希、XML 内部自洽（自报计数 ⇔ 元素数）、角色归属与当前文件的读出一致。伪造其中任何一项都红。
3. 注释 / 字面量 / 文本块三个投影出自同一个扫描器，且在 496 个可编译合成形状上零分歧；桩化任一投影会让 36 条良性探针全部变红。
4. JLS 3.3 的平移规则与 javac 在同一批字节上结论一致（非法转义、未闭合字面量、奇偶反斜杠换行），并且 javap 数出的 `invokestatic` 条数与闸门的可达性结论在 7 个形态上一致。
5. 装配可达性判据（无括号常量假分支、提前 return、`try…finally`、`switch default`、`else`、`while(false)`）确实影响判定，且**方向被实测**：该红的红、不该红的绿。

不证明（不冒充）：

- **调用点在真实运行里被执行** —— 这是 `mvn -Dtest=T03SessionCookieGuardTest` 的 15 条用例（其中 3 条真装配）与 §2 F-01 表格的责任；静态检查只是提前拦截，不是执行证明。
- 编译期不可判定的假条件；GitHub Actions 真会红；配置多 location 覆盖的优先级顺序；记录器是否由人跑过；`identity.enabled=false` 的部署形态；整套件离线运行；YAML/Java 形状的全集。

## 5. 交回主 agent 代跑的命令与期望值

| 命令 | 期望 |
| --- | --- |
| `mvn -B -ntp -f backend/pom.xml clean verify` | 0。本轮只在影子树里跑过 `-Dtest=T03SessionCookieGuardTest test`（0，15 条全绿），全量 `clean verify` 未跑，属你。 |
| `python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1` | 0（本轮已跑，会重写 XML / 记录 / census ⇒ 之后请重跑闸门与 r10 证据） |
| `python tests/engineering/T03/formal.py --suite identity --inject server.servlet.session.cookie.name=WRONGNAME` | **15 条失败**（每条用例都在契约名上断言） |
| `python tests/engineering/T02/check_contracts.py` | 0，27 hashes |
| `python tests/engineering/T03/check_session_cookie.py` | 0，`106/106 … 36/36 …` |

我跑不了、因此不构成任何声明的：真实 Actions 的一次红；`formal.py --suite identity --inject …`（需全量 mvn，交回你）；多 location 优先级实测。

关于主 agent 撤回的那条 `mvn clean verify` 违规通知：那次 maven 在 0.062 s 失败（缺 `-f backend/pom.xml`），`clean` 从未执行，`backend/target` 未被触碰 ⇒ 我没有为此重跑任何东西；本轮所有需要重跑的测量都已按最终字节重做（§1 表）。

## 6. 本轮自曝

影子树第一次跑 `mutate_shadow.py` 时，我把 13 条 mvn 结果全读成 `exit=1 compileError=True`，因为形状里用 `"\\n"` 拼出了字面反斜杠 n 而不是换行 —— javac 报的是 `illegal character: '\'`，不是我以为的"不可达语句"。这轮把换行换成真实 `chr(10)` 后才是上表那批数。同理，`hollowing` 的第一版形状（裸文本块语句）根本编不过，我当时差点把它当成"掏空后仍绿"的证据；改正后的形状才真正 mvn 全绿并被闸门拒绝。**读错了不会红，只会让结论变好看**，所以这两条写进报告而不是只写在注释里。

## 7. 仍未证明（本轮结束时）

1. 运行期恒假条件静态判不了；R1 的修法只覆盖编译期可判定部分。
2. CI 结构执法 ≠ Actions 真会红。
3. 配置层优先级（多 location / 多 profile 交叉）只做到"不可归因即响亮失败"。
4. 记录器是否由人跑过；JDK 目录只哈希 launcher 与 provider jar。
5. `identity.enabled=false` 部署形态、全套件离线。
6. 600 例合成语料不是全集；`.yaml` 后缀无实例文件。
7. `yaml-construct-reasons` 与 `input-set-both-directions`、`properties-census`、`recorded-current-cases` 属"共享证人/说明文案"，桩化后判定不变（已在代码与本报告里写明它们不判据）；若主 agent 认为说明文案也该有控件，这是可以再加的一处。
8. STATE.json 三处台账与 §四 措辞更正属主 agent（F-12）。
