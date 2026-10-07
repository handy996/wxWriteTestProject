# T03 卡片（身份与会话边界）第十轮独立复审

- 复审方：T03-round10 独立复审 agent
- 被审提交：`11a3d7f`（R10 整改）、`cc91998`（主 agent 注入反证；任务书写作 `cc99998`，仓库中不存在该号，见 §0）
- 上游判决：`docs/execution/reviews/T03-round9/review.md`
- 判决：**CHANGES_REQUIRED**（P1 = 0；P2 = 2；P3 = 4；详见 §12 与文末总判决）
- 十个必答问题：**§1 PASS、§2 PASS、§3 PASS、§4 CHANGES_REQUIRED（P2 一条）、§5 PASS（另带 P2 一条）、
  §6 PASS、§7 PASS、§8 PASS、§9 PASS、§10 PASS**
- 时间基准（本地）：入场 `2026-10-08 06:45 +08:00`；**判决落点 = 07:01:28 之后的字节**（说明见 §5 段首）

---

## §0 基线自证（仓库状态 / 交付指纹 / 独占声明）

- 复审开始时间：`2026-10-08 06:45 +08:00`（机器读数）。
- `git rev-parse HEAD` = `cc91998bb98256162c63d2e0e0e10dc5a10842bf`；`git log --oneline -8` 顶部两笔即被审的
  `cc91998`（注入反证）与 `11a3d7f`（R10 整改）。**任务书里写的 `cc99998` 与 `T03-round9` 的 `11a3d7f` 中，前者是笔误**：
  实际提交号是 `cc91998`（差一个字符），仓库里不存在 `cc99998`（`git cat-file -t cc99998` 会失败）。本轮按磁盘事实使用 `cc91998`。
- `git status --porcelain` = 3 条：`?? docs/execution/reports/T02-Revision-R06.md`、`?? docs/execution/reports/T08-Revision-R5.md`、
  `?? docs/execution/reviews/T03-round10/`（最后一条是我自己刚建的骨架）。**已跟踪文件无修改** ⇒ 工作树字节 == HEAD 字节，
  因此 §10(c) 的「工作树是否等于 `11a3d7f`」可以当场判定（见 §10）。
- `Get-Process postgres` = **0 个进程**（`postgres_proc=0`）；`Get-Process java` = 1 个，命令行是
  `c:\Users\eie04\.vscode\extensions\redhat.java-1.56.0-...` 的 Java 语言服务器，与 maven/Postgres 无关 ⇒ 我没有动别人的库，
  本轮所有需要真库的运行都由 `formal.py` 自起的隔离集群完成（它自己 `initdb` + `pg_ctl`，见 §8）。
- 交付指纹（`Get-FileHash -Algorithm SHA256` 取前 12，字节数取 `Get-Item.Length`，全部实测）：

| 文件 | 磁盘字节 | sha256[:12] | 任务书/报告声明 | 判定 |
| --- | --- | --- | --- | --- |
| `tests/engineering/T03/check_session_cookie.py` | 162,443 | `5AED73E5F4A3` | 162,443 / `5AED73E5F4A3` | 一致 |
| `backend/.../T03SessionCookieGuardTest.java` | 26,824 | `3FA69C6ED386` | 26,824 / `3FA69C6ED386` | 一致 |
| `evidence/guard-test-binding.json` | 4,920 | `2116E03E8AE8` | 报告同值 | 一致 |
| `evidence/T03SessionCookieGuardTest.xml` | 33,734 | `BCDE9C7E37B9` | 报告同值 | 一致 |
| `evidence/T03SessionCookieGuardTest.txt` | 363 | `7CC055B418A7` | 报告同值 | 一致 |
| `evidence/config-census.txt` | 792 | `E2FF588E1ED4` | 792 B | 一致 |
| `evidence/session-cookie-r10.json` | 60,738 | `8F1E9CFA1734` | 60,738 / `8F1E9CFA1734` | 一致 |
| `docs/execution/reports/T03-Revision-R10.md` | **41,804** | `E91A538A5406` | 任务书写 **41,067 B / 288 行** | **字节数不符**（见下） |
| `tests/engineering/T03/record_guard_binding.py` | 8,078 | `3F7D00EAA18D` | 报告同值 | 一致 |
| `tests/engineering/integration/formal.py` | 11,121 | `950254073FA2` | — | 存在（§8 的正确路径） |

- 报告行数口径：`python` 读字节后 `len(text.splitlines())` = **289**（`git show HEAD:…` 亦 289）；
  任务书说 288 行、41,067 B。`git cat-file -s HEAD:docs/execution/reports/T03-Revision-R10.md` = **41,804**，
  与磁盘一致 ⇒ **报告字节以 41,804 / 289 行为准**，任务书那两个数字是旧稿读数。这是任务书侧的转录偏差，不是实施方的缺陷；
  我在 §10 里按事实登记，不判实施方虚报。
- `check_session_cookie.py` 行数：`git show 11a3d7f:… ` = **2,952 行**（`splitlines` 口径），与任务书一致；文件 162,443 B。
- mvn 独占确认：`mvn` 不在 PATH（`Get-Command mvn/mvn.cmd/mvn.bat` 全部 NOT FOUND）。仓库内唯一 maven 是
  `.tools/t02/apache-maven-3.9.11/bin/mvn.cmd`（`Test-Path` True），闸门 `MVN` 常量（`check_session_cookie.py:123`）
  与 `formal.py:33` 默认值都指向它 ⇒ 我用绝对路径调用，不依赖 PATH；本轮期间只有我在跑 maven（影子树 + 全量 verify）。
- `JAVA_HOME` 当前是 `C:\Program Files\Zulu\zulu-17`，而闸门/记录器钉的是 `.tools/t02/jdk-21.0.12.1+1`；
  我所有 maven 运行都显式 `JAVA_HOME=<jdk21>`，否则会与记录器不同构。
- 闸门独立首跑（不带 `--output`，只判定）：exit **0**，stdout 一行
  `T03 session-cookie agreement gate: PASS - approved name 'EDITORIAL_SESSION'; 106/106 negative controls rejected, 36/36 benign probes accepted`
  —— 与主 agent 声明的 exit 0 与读数逐字一致。日志留存：`docs/execution/reviews/T03-round10/logs/gate-plain-run1.log`
  （143 B，sha256[:12] `e88d9554103f`）。

**状态：完成**


---

## §1 执行面证据是否名副其实（R1b 六类假形状重放 + 自造假形状 + 良性半边）

**方法**：影子树 `$env:TEMP\t03r10\shadow\backend`（`shutil.copytree` 排除 `target`，176 个源文件 / 1,275,944 B 的真实树），
每次形状都重新复制后只改 `src/main/java/com/example/editorial/identity/T03Configuration.java` 的调用行，
跑 pinned 工具链：`.tools/t02/apache-maven-3.9.11/bin/mvn.cmd -B -ntp -o -f <shadow>/pom.xml
-Dmaven.repo.local=<abs>.tools/t02/m2 -Dtest=T03SessionCookieGuardTest test`，`JAVA_HOME` 显式设为
`.tools/t02/jdk-21.0.12.1+1`。读数以影子树 surefire XML 的 `testcase` 元素为准，`javap -c -p` 数
`identitySecurity(...)` 的 `Code:` 段里 `invokestatic … verifySessionCookieContract` 的条数。
驱动器 `tests/engineering/T03/.work/r10rev-01/shapes.py`，每条形状的完整 maven 输出留在
`docs/execution/reviews/T03-round10/logs/shadow-<shape>.log`。

**我自己踩到的坑（先自曝，因为它一度让结论变好看）**：第一版 `javap` 归属用正则 `^  \S.*\(.*\);?$` 认方法声明行，
而 `identitySecurity(...)` 的签名带 `throws java.lang.Exception;`，正则要求 `)` 之后直接到行尾 ⇒ **永不匹配** ⇒
所有形状都读成 `identitySecurity=0`，连原始形状都被我读成 0。第二版改成「下一行是 `Code:` 的成员声明行」，
并回显真实签名，才对。若我照抄第一版，就会"独立复现"出一个根本不存在的 javap 结论。

实测结果（mvn 退出码 / 用例读数 / javap，全部本轮现场跑）：

| 形状（改在调用行） | javac | mvn exit | surefire | 失败的用例 | `identitySecurity` 体内 invokestatic |
| --- | --- | --- | --- | --- | --- |
| `PRISTINE`（未改） | 0 | **0** | tests=15 fail=0 err=0 skip=0 | — | **1** |
| 无括号 `if (false)` + 换行调用 | 0 | **1** | 15/2/0/0 | `assembledIdentitySecurityAbortsOnInsecureProdCookie`、`…AbortsOnNonContractCookieName` | **0** |
| `if (Boolean.FALSE.booleanValue())` 无括号 | 0 | **1** | 15/2/0/0 | 同上两条 | **1**（字节码仍在，运行期死） |
| `static final boolean T03_REVIEW_SKIP=false;` + `if (T03_REVIEW_SKIP)` | 0 | **1** | 15/2/0/0 | 同上两条 | **0** |
| `if(!env.matchesProfiles("prod")) return http.build();` 提前返回 | 0 | **1** | 15/2/0/0 | `…AbortsOnNonContractCookieName`、`…StartsWithContractCookieName` | **1** |
| 转义注释 `\u002f\u002a … \u002a\u002f` 包住调用 | 0 | **1** | 15/2/0/0 | 同前两条 | **0** |
| `while (false) { 调用 }` | **1 拒绝**（unreachable statement） | 1（未跑用例） | 无 XML | — | 类未产出，无法数 |
| `return http.build();` 后无条件跟调用 | **1 拒绝**（unreachable statement） | 1（未跑用例） | 无 XML | — | 同上 |
| `try { 调用 } finally { }`（良性） | 0 | **0** | 15/0/0/0 | — | **1** |
| `switch (origin) { case "z": break; default: 调用 }`（良性） | 0 | **0** | 15/0/0/0 | — | **1** |
| **复审自造 ①** `try { 调用 } catch (IllegalStateException swallowed) { }` | 0 | **1** | 15/2/0/0 | 两条装配拒绝用例 | **1** |
| **复审自造 ②** `if (env.getProperty("editorial.t03.review-switch","on").equals("off")) { 调用 }` | 0 | **1** | 15/2/0/0 | 同上 | **1** |
| **复审自造 ③** `if (Integer.signum(origin.length()) == -7) { 调用 }` | 0 | **1** | 15/2/0/0 | 同上 | **1** |

对账报告 §2 F-01 的表：

- 报告标 mvn **1** 的四类，我实测四类全 mvn **1**，且红的用例逐名与报告一致（含提前返回那行报的正是
  `NonContract + StartsWith` 这一对，与报告 §2 F-01 表格第 89 行完全相同）。
- 报告标 javac **1**、且明写"未跑（编译期即红）""没有新报告，不冒充跑过"的两类：我实测确实 `compileError=True`、
  影子树没有 surefire XML ⇒ **报告没有把编译期红包装成跑绿**，这一条第九轮的要求被满足。
- 报告标 mvn **0** 的两类良性半边（`try…finally`、`switch default`）我实测都是 15/0/0/0，**不假红**；
  第三类良性半边 `else { 调用 }` 报告说"未进影子树，由闸门内置探针 `guard-call-in-else-arm` 保持绿"——
  我在闸门实跑读数里确认该探针属于 36/36 accepted 集合（`--skip-controls` 未用，全 roster 跑过），
  因此这半句是"探针绿"而非"mvn 绿"，报告口径与事实一致（措辞已如实区分）。
- javap 一列报告只声明了 3 个形态（原始 **1**、常量假分支 **0**、转义注释 **0**），我实测同样 1 / 0 / 0，
  且把报告标"未测"的四行补齐：`Boolean.FALSE.booleanValue()`、`static final false`、提前 return、`try…finally`。
  **补出来的事实有一处值得主 agent 记账**：`Boolean.FALSE.booleanValue()` 与"提前 return"两型
  `invokestatic` **仍是 1**（字节码里有调用，运行期到不了）。⇒ "数 invokestatic" 只能证伪常量折叠型假分支，
  不能证伪这两型；真正把六类假形状全部拦下的是**装配用例**。报告没有夸大这点（它把该列标了"未测"），
  但 §4"证明"第 4 条"javap 数出的 invokestatic 条数与闸门的可达性结论在 7 个形态上一致"这句
  在读者口里容易被读成"字节码读数足以定性"，建议加一个限定（记 P3）。

**自造三型全部被执行面拦下（mvn 红，红在两条必须抛的装配用例），没有任何一型跑绿且不红任何门 ⇒ 本项不构成 P2。**
更值得记的是它们的 javap 都是 **1**：假形状在字节码层面完全隐形，只有真装配会红。这正是第九轮要的"执行面证据"，
本轮名副其实。

结论：**PASS（本项）**。R1b 六类假形状独立复现成功（4 类 mvn 红且红在装配用例、2 类 javac 编译期红且报告未声称跑绿）；
自造三型不绿；两类良性半边不假红；javap 读数与报告已声明的部分一致，并补全了报告标"未测"的四行。

---

## §2 三条装配用例是否真取上下文（register + 产品自身抛出路径）

**最小复现**：读 `T03SessionCookieGuardTest.java:183-197`（`assembleIdentitySecurity`）与 `:238-247`
（`assertAssembledAtTheCallSite`），对照产品 `T03Configuration.java:34-55`（`identitySecurity`）与 `:67-74`
（`verifySessionCookieContract`）；行为面由 §1 影子树真跑证明（同一批用例，改的是调用行）。

实测事实：

1. **真上下文**：`new AnnotationConfigApplicationContext()` → `setEnvironment(...)` → `registerBean(JdbcTemplate /
   PlatformTransactionManager / HttpSecurity)` → **`context.register(T03Configuration.class)`**（`:190`）→ `refresh()` →
   `context.getBean("identitySecurity", SecurityFilterChain.class)`（`:193`）。被注册的是产品配置类，不是测试替身；
   `identitySecurity` 由 Spring 的 bean 创建流程调用（`onlyTheCookieGuardBeanIsEager` 只把别的 bean 设为 lazy，
   `identitySecurity` 保持 eager，`:199-204`）。
2. **走产品自身的抛出路径**：`assembledIdentitySecurityAbortsOnNonContractCookieName`（`:249-258`）断言的是产品抛出的东西
   —— `BeanCreationException`、`root instanceof IllegalStateException`、`root.getMessage().startsWith("T03_COOKIE")`、
   `assertEquals("identitySecurity", failure.getBeanName())`，再加三条栈帧断言：栈里必须有
   `T03Configuration#identitySecurity` 帧、必须有 `verifySessionCookieContract` 帧、必须有 `org.springframework.beans.factory.*` 帧。
   测试不是拿自己写死的常量去比一个自己造的异常，而是把产品抛出的根因取回来验明出处。
3. **调用点是否被执行交给 JVM**：§1 的 `braceless-if-false` 影子跑实测 `Tests run: 15, Failures: 2`，
   失败两条正是 `assembledIdentitySecurityAbortsOnInsecureProdCookie` 与
   `assembledIdentitySecurityAbortsOnNonContractCookieName`（从影子树 surefire XML 逐名取出，非推断）。
4. **正向半边**：`assembledIdentitySecurityStartsWithContractCookieName`（`:260-265`）要求契约名真装配出链，
   且 `assertFalse(chain.getFilters().isEmpty())` ⇒ 防止"返回空链冒充成功装配"。

一处文案不准（不影响判定）：报告 §2 F-01 说非契约名走 `verifySessionCookieContract` 的"**第二条**子句"，
按产品源码那是**第一条** `if`（`:68-69`，cookie 名比较），第二条 `if` 才是 prod 安全项（`:70-73`）。记 P3 措辞。

结论：**PASS（本项）**。三条装配用例确实取真上下文、确实走产品自身抛出路径，"调用点被执行"确实由 JVM 判定；
唯一缺陷是报告里子句序号写反。

---

## §3 五条真实加载用例是否用框架 loader + Binder（禁自研解析）

**最小复现**：读 `T03SessionCookieGuardTest.java:283-336`（`load / yaml / properties / boundTo / declaredAt /
repositoryLayers`）与 `:338-501`（五条用例）。逐条核用到的类型：

| 用例 | 用了什么 | 框架自身？ |
| --- | --- | --- |
| `contractNameBindsInEveryProfileLayerThroughTheRealLoaders` | `PathMatchingResourcePatternResolver` 枚举 6 条 `classpath*:` 模式 → `load(resource)` → `YamlPropertySourceLoader` / `PropertiesPropertySourceLoader` → 读 loader 产出的 `PropertySource` 的 `Map` → `Binder.get(env).bind(NAME,String)` 逐 profile 层绑定 | 是 |
| `flowAliasAndMergeKeyShapesAreLiveToTheRealLoader` | 字符串 → `ByteArrayResource` → **框架 loader** → `boundTo`（多行 flow、值后注释、内嵌注释、锚点别名、合并键、`.properties`） | 是 |
| `configDirectoryLayerOvertakesTheResourcesRoot` | 两个 loader 的产出按 Boot 次序 `addFirst` 后 `Binder` | 是 |
| `commentsAndEnvStyleKeysBindNoCookieName` | 同上；`<none>` 来自 `Binder(...).orElse("<none>")` | 是 |
| `duplicateCookieNameKeysAbortLoading` | 由框架 loader 抛，断言异常文本含 `duplicate key`（SnakeYAML 的重复键错） | 是 |

自研解析搜索结果：测试文件里对配置文本的手工作业只剩两处 —— `classpathTail()`（把 URL 截成 classpath 相对路径）
与 `checksum()`（流式 SHA-256）；两者都不解释 YAML/properties 语义。`declaredAt()` 读 loader 已展平的 `Map` 键值，
不是自研分词。⇒ 第九轮"自研解析冒充真实加载"的教训在本轮**没有复发**，未发现任何一处自研解析顶替框架加载器。

保留边界（影响 F-02 措辞的读法，详见 §12）：闸门侧仍留着 `census_yaml` / `expand_yaml_flow` / `strip_yaml_comment`
这套文本普查，且其载荷审计记录 `yaml-census` 桩 `lost 91` —— 这 91 条控件的**署名理由**仍来自文本普查代码路径。
按审计自己定义（`lost` 包含"被另一面以别的原因拒绝"），这不等于普查仍是判据；但报告"取消手写 YAML 普查当判据"
写得比实测绝对，需要改口径。

结论：**PASS（本项）**。五条执行用例全部经框架 loader + `Binder`，无自研解析冒充。

---

## §4 攻击载荷审计（54 桩归属：46/3/4/1，无人看守 0）

**(1) 声称的算术我核过，是真的。** 机器产物 `tests/engineering/T03/.work/load-bearing-audit.json`
（实施方现场写出，我只读）：`stubResults` 共 **54 行**，`unwatched: []`，`sharedWitness: 3`
（`properties-census` / `input-set-both-directions` / `recorded-current-cases`），`lost>0` 的行 **46** 条，
`lost=0 且 moved=0 且 probeFlips>0` 的行 **4** 条（`tokenizer-selfcheck` / `comment-blanking` / `textblock-blanking` /
`yaml-comment-stripping`），`0/0/0` 的行只有 **1** 条 = `yaml-construct-reasons`。
46 + 3 + 4 + 1 = 54，与报告 §3 表格逐行、逐列（lost/moved/probes 三个数）一致；`errors: []`（没有锚点失配、没有超时桩）。
⇒ **报告那张表不是手抄出来的漂亮数字**，它与审计产物逐格对得上。

**(2) 文案生成器的 docstring 确实写明不判据。** `check_session_cookie.py:952-958`：
`construct_reason` 开头就是 "Wording only: why a YAML construct at this path cannot be attributed by text, or None when it can.
… **Stubbing this function to answer "it can be attributed" moves no verdict, which is what the round-ten audit measured;
that is why it is written as a classifier and not counted as a check.**" —— 并且审计脚本里它被单列成
`DIAGNOSTIC = ("yaml-construct-reasons",)`（`load_bearing.py:37`），分类时从 shared/unwatched 里摘出来放进 `declared`。
⇒ 本项要求满足。

**(3) 我按任务书要求自己造桩：三型，全部"无人看守"。** 我用实施方**同一个**审计工装（不改它的 `roster()`、
`signature()`、`stub_source()`、记录策略与 `CORPUS_CAP=40`，只把 `STUBS` 换成我自己的三条、`OUT` 换到我的目录、
`DIAGNOSTIC` 清空），驱动器 `tests/engineering/T03/.work/r10rev-01/my_audit.py`：

```
baseline: 106/106 controls rejected, 36/36 probes accepted (records re-hashed, corpus capped at 40)
  reviewer-tokenizer-recited   lost  0  moved  0  probes  0  unwatched
  reviewer-argv-shell-scan     lost  0  moved  0  probes  0  unwatched
  reviewer-must-report-numbers lost  0  moved  0  probes  0  unwatched
audit: 3 stubs, 0 shared-witness, 3 unwatched, 0 declared-diagnostic      # exit 1
```

三条桩各自是什么，以及它们意味着什么：

| 我的桩 | 锚点 | 削弱内容 | 后果 |
| --- | --- | --- | --- |
| `reviewer-tokenizer-recited` | `def tokenizer_certificate(sources):` 后插入 `return {"sources": [], "corpusFiles": 600, "divergences": 0, "note": "recited, not measured"}` | **不再测**：不跑 `views_agree`、不遍历语料、删掉 `if divergences: raise` —— 改为**口述**结论 | 142 条 roster 全部与基线一致，**0 判定变化**。而它恰好就是报告 §3 里被记作"良性半边看守（probes 36）"的那一条判据：实施方的桩 `return {"stub": True}` 之所以被看见，是因为它把**要报的数字**砸掉了；只要保留字段形状、把测量本身删掉，就完全隐形 |
| `reviewer-must-report-numbers` | `if unfed or not tokenizer["corpusFiles"]:` → `if False:` | 删掉"自测必须报出数字"这条要求 | 同样 0 判定变化。⇒ 报告 §2 F-11 那句"桩化这项自测会让 36 条良性探针全部变红 ⇒ 这条『必须报告』不是装饰"只在一个方向成立：装饰化的是**被删掉的要求自己**无人看守 |
| `reviewer-argv-shell-scan` | `for part in argv:` → `for part in []:` | 删掉 argv 里的 shell 词 / 伪可执行文件扫描 | 0 判定变化。这一条我判为**良性冗余**：`have != want` 的钉死 argv 相等已经先拒了同类变异（审计里 `binding-command-echo-argv` 仍红），所以**没有缺陷漏防**，但它同样不在 54 桩的枚举里 |

**这就是任务书第 4 项要我看的那一型**：`reviewer-tokenizer-recited` 削弱后不改变任何判定，却在报告 §3 的表里
被归入"有人看守（良性半边看守）"—— 因为审计只能证明"把报告砸烂会被发现"，证明不了"报告里的数字来自测量"。
⇒ **P2（一处，口径性，不是造假）**：报告 §3 第 184 行"**闸门源码里每一条判据**"这个完整性口径不成立；
正确写法是"54 个桩（判据枚举方式：`STUBS` 的锚点清单），另有 N 条判据未被枚举，其中 `tokenizer_certificate` 的测量
本身、"必须报数"要求、argv 词法扫描三条实测为无人看守"。缓解事实：三条里没有一条涉及 cookie 名的取值/一致性判定，
所以契约名本身没有失去看守；`unwatched` 在工装里是真会红的退出码（`return 1 if unwatched else 0`），
说明这套方法对我诚实、对实施方也诚实 —— 缺的是枚举的完备性声明。

**(4) 我还核过分类规则的语义，没有发现"算成有人看守"的规则性漏洞**（`load_bearing.py:286-299`）：
`lost` = 基线红而桩化后不红（含 accepted / crashed / wrong-face 三种，`:209-217`）；
`moved` = 同一面仍红但首 70 字符理由变了；`probeFlips` = 基线绿的探针桩化后不绿。
"仍被拒绝"记成 shared 是站得住的 —— 变异体确实被拦下；探针翻红记成看守也站得住 —— 闸门会大声假红。
所以漏洞不在规则，在**枚举**。

结论：**CHANGES_REQUIRED（本项，P2 一条）**。算术、docstring、规则语义三项通过；"每一条判据"的完整性口径被我
三条自造桩（0 判定变化）证伪，其中一型正是"削弱后不改变任何判定却被算作有人看守"。
修法见 §12 D-1（两种可选路径）与 §14 第 1 条的期望值。

---

## §5 记录器由人跑过（重写 3 个受控文件 + 改前/改后 sha + 重写后闸门仍 0）

**并发与读数落点先声明**（主 agent 裁定 1/3，我不据此判缺陷）：会话内 T02 / T08 整改文件全程为 M，
T08 工装会在**自己的副本**里调 maven；仓库根 `backend/target` 与 `.m2` 的写入本轮只发生在我这边
（mtime 链：06:38 主 agent 全量 verify → 06:58:41 我的记录器首跑 → 07:01:23 我的记录器次跑 → 07:05:48/07:05:55 我的全量 verify）。
我 06:5x 曾读到一份"failures=1"的证据快照，主 agent 独立取证判定该读数**无在仓工件、不可再现**，归为我的读数失误；
我另存的 `logs/foreign-0658/` 四份其实正是我 06:58:41 那次干净跑的产物（binding 4,920/`1e4d8ae631b8`、
XML 33,737/`090393f7f0cc`、txt 363/`af77715ac984`、census 792/`e2ff588e1ed4`，XML 头 `tests=15 failures=0 errors=0 skipped=0`）。
⇒ **本报告的判决落点**：§5/§7/§9/§10 的受控文件读数一律取 **07:01:28 之后**（我的第二次记录器运行）与
07:05:55（我的全量 verify）之后的字节；§0 表里的交付指纹取的是我 06:45 入场时、与 HEAD 逐字节相同的入库字节。

**命令**（仓库根，原样可粘贴）：

```
python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1
```

改前（06:45 入场实测；`git status` 当时干净 ⇒ 等于入库 HEAD 字节）：

| 文件 | 字节 | sha256[:12] |
| --- | --- | --- |
| `evidence/guard-test-binding.json` | 4,920 | `2116E03E8AE8` |
| `evidence/T03SessionCookieGuardTest.xml` | 33,734 | `BCDE9C7E37B9` |
| `evidence/T03SessionCookieGuardTest.txt` | 363 | `7CC055B418A7` |
| `evidence/config-census.txt` | 792 | `E2FF588E1ED4` |

跑出的读数（我跑了**两次**，两次 stdout 逐字节相同）：

- 首跑 06:58:41：exit **0**，`{"exitCode": 0, "counts": {"tests":15,"failures":0,"errors":0,"skipped":0}, "cases": 15,
  "censusFiles": 4, "boundInputs": [...10 项...], "output": "tests/engineering/T03/evidence/guard-test-binding.json"}`。
  日志 `logs/recorder-run.log`（589 B，sha256[:12] `63D5327E83E2`）。
- 紧随其后的闸门：exit **0**、`106/106 … 36/36 …`，写出 `session-cookie-r10c.json`
  （日志 `logs/gate-r10c-after-recorder.log`，206 B，`97796C1DEC8B`）⇒ **重写受控文件后闸门仍 0**。
- 次跑 07:01:23→07:01:28：exit **0**，同一批字节 `63D5327E83E2`（日志 `logs/recorder-run2.log`，589 B）。

改后（次跑之后实测）：

| 文件 | 字节 | sha256[:12] | 判定 |
| --- | --- | --- | --- |
| `evidence/guard-test-binding.json` | 4,920 | `CD6412BD1348` | 变了（同字节数，内含新 XML 哈希） |
| `evidence/T03SessionCookieGuardTest.xml` | 33,736 | `95D1B5B2338A` | 变了（33,734 → 33,736，surefire 耗时字段位数） |
| `evidence/T03SessionCookieGuardTest.txt` | 363 | `3DEE0E4FFE5D` | 变了（同字节数，耗时行） |
| `evidence/config-census.txt` | 792 | `E2FF588E1ED4` | **逐字节不变** ✓ |
| `evidence/session-cookie-r04…r10.json` | — | 见 §6 表 | **全部仍等于 HEAD** ✓ |

由此三条事实：

1. **"记录器由人跑过"这条未证明，本轮由我补上**：exit 0、`counts{tests:15,failures:0,errors:0,skipped:0}`、
   15 个用例名、census 4 文件、绑定输入 **10 项含 `census`**（报告 §1 写"10 个绑定输入 + `census`"读起来像 11，
   实测 `inputSha256` 恰好 10 键且 `census` 在其内 ⇒ P3 措辞）。`executedRoles` 实测
   `{anchorConstant:7, assemblyAbort:2, assemblyLive:1, binderCensus:1, binderShapes:3, loaderAbort:1,
   guardAbort:6, guardLive:2}`，与报告 §1 那行逐字吻合 ✓。`surefireJar =
   .tools/t02/m2/org/apache/maven/surefire/maven-surefire-common/3.5.6/maven-surefire-common-3.5.6.jar`、
   `jdk = .tools/t02/jdk-21.0.12.1+1` 都在本机存在，闸门当场重哈希能对上 ✓。
2. **重写后闸门仍 0** ⇒ 记录器与闸门是闭环，不是"一次性产物"。
3. **记录器不字节幂等**：入库 XML 不可能被第二次运行复现成同一批字节；可复现的是**事实**
   （用例名、计数、census、角色、jar/JDK 哈希、census 字节）。报告未声称幂等 ⇒ 不判缺陷，
   但验收应按事实而非字节。

**记录器一处真缺陷（P2，代码层可证，与上面的读数异常无关）**：`record_guard_binding.py` 的 `main()` 顺序是
`:86-96` **先**把 `TEST-*.xml` / `*.txt` / `t03-config-census.txt` 拷进受控证据目录，`:103` **才**判
`result.returncode != 0 or counts["failures"] or counts["errors"] or counts["skipped"]`，`:111-118` 的角色与用例名
校验更在其后 ⇒ "受控证据只由干净运行写入"为假：一次 `failures=1` 的 pinned 运行会把失败产物**留在 `evidence/`**
（只有 `guard-test-binding.json` 不更新）；闸门随后会因 XML 哈希与记录不符而红（fail-closed，方向正确，
不是静默放行），但脏写会污染下一次复跑的起点。修法：全部校验通过后再写，或先拷临时目录、通过后原子落 `evidence/`。
**我没有实机触发它**——触发就必须脏写受控证据，与本轮"只新增不覆盖"硬规则冲突；故按代码事实提 P2，
"实测脏写"列入 §13 未证明。主 agent 已裁定该 P2 成立并立独立项 `T03-R11-RECORD-BEFORE-VALIDATE`，
不由我改、也不由被审方改自己的考题。

结论：**PASS（本项动作已完成：我亲自跑、双次 exit 0、改前/改后 sha 已申报、重写后闸门 0）**，
带出 **P2 一条**（记录器写入顺序）。

---

## §6 闸门重跑不覆盖既有证据（新名 r10b + 历史证据逐字节未变）

**最小复现**（原样可粘贴，仓库根）：

```
python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r10b.json
python tests/engineering/T03/.work/r10rev-01/metrics.py
```

实测：

- 闸门 exit **0**，读数 `PASS - approved name 'EDITORIAL_SESSION'; 106/106 negative controls rejected, 36/36 benign probes accepted`，
  外加一行 `wrote tests\engineering\T03\evidence\session-cookie-r10b.json`。日志：
  `docs/execution/reviews/T03-round10/logs/gate-r10b.log`（206 B，sha256[:12] `06b4bee69792`）。
- **没有用 `--force`**：闸门对已存在的输出名会拒绝写出（`check_session_cookie.py:2930`
  `refusing to overwrite existing ...; pass --force if that is really intended`）⇒ 只要用新名就不可能覆盖。
  重跑后 `session-cookie-r10.json` 仍是 60,738 B / `8F1E9CFA1734…`，`equal=True`（见下表）。
- **同判据**：`r10` 与 `r10b` 都是 `verdict: PASS`，扁平化后各 103 个叶子字段，**逐字段差异 0**
  （含 10 个绑定输入哈希、控件 106 / 探针 36 计数、census 与 binder 证书字段）。闸门输出不含时间戳 ⇒ 重跑确定性。
- 历史证据逐字节核对（磁盘字节 vs `git cat-file blob HEAD:<path>` 字节，两边 sha256[:12] + `equal`）：

| 文件 | 磁盘字节 | sha256[:12] | 与 HEAD 逐字节 |
| --- | --- | --- | --- |
| `session-cookie-r04.json` | 1,329 | `C88A32AB4B89` | equal=True |
| `session-cookie-r05.json` | 2,149 | `EACF5CD36716` | equal=True |
| `session-cookie-r06.json` | 2,393 | `49D62F036FDA` | equal=True |
| `session-cookie-r07.json` | 3,647 | `8ED381AC58EA` | equal=True |
| `session-cookie-r08.json` | 5,492 | `6EB8EF60213D`（任务书前缀 `6EB8EF60` ✓） | equal=True |
| `session-cookie-r09.json` | 5,666 | `F18C88EFA513`（任务书前缀 `F18C88EF` ✓） | equal=True |
| `session-cookie-r10.json` | 60,738 | `8F1E9CFA1734` ✓ | equal=True |

- **事实校正**：证据目录里**不存在 `session-cookie-r01/r02/r03.json`**。目录实测内容：`config-census.txt`、
  `guard-test-binding.json`、`input-baseline.json`、`real-integration.json`、`session-cookie-r04…r10.json`、`r10b.json`（我新增）、
  `T03SessionCookieGuardTest.xml`、`.txt`。所以任务书"验 r01…r09 逐字节未变"只能验到 r04…r09；r01…r03 从未存在
  （`git status --porcelain` 无删除项，HEAD 树里也没有）⇒ 是交回命令的措辞问题，不是实施方覆盖证据。

结论：**PASS（本项）**。新名重跑不覆盖既有证据；r10b 与 r10 同判据（103 字段 0 差异）；现存全部历史证据逐字节等于 HEAD。

---

## §7 census 链条自洽（target → evidence → 闸门哈希；闸门不读 backend/target）

**链条三段，逐段实测**：

1. **测试侧产出**：`T03SessionCookieGuardTest.writeCensusCertificate()`（`:390-396`，`@AfterAll`）把 `CENSUS`
   排序写入 `Path.of(System.getProperty("basedir","."), "target").resolve("t03-config-census.txt")`，用 `Files.write`
   ⇒ Windows 下是 **CRLF**。我的全量 verify 之后实测 `backend/target/t03-config-census.txt` = **806 B / mtime 07:05:48**；
   evidence 那份 792 B ⇒ 差 **14 字节 = 14 行的 CR**，与文件行数（4 BIND + 4 CENSUS + 6 SURFACE = 14）严格对应 ✓。
2. **记录器搬运**：`record_guard_binding.py:86-96` 第三条 copy 把 `CENSUS_TARGET = ROOT/backend/target/t03-config-census.txt`
   经 `copy_text()`（`:44-50`，读文本再以 `newline="\n"` 写）落到 `checker.SOURCES["census"]`
   = `tests/engineering/T03/evidence/config-census.txt` ⇒ **792 B / LF / `E2FF588E1ED4`**，我两次重跑逐字节不变 ✓。
   内容：`T03-SURFACE` 6 条模式、`T03-CENSUS` 4 个文件 + SHA-256、`T03-BIND base/dev/mock/prod EDITORIAL_SESSION` ✓。
3. **闸门再哈希 + 双向对账**：`census_facts()`（`:1520-1550`）只解析 evidence 那份（缺失即 `Rejected`，`:1528-1530`）；
   `binder_certificate()`（`:1905-1946`）做四件事：面集合必须等于闸门自己枚举的 6 条 `classpath*:` 模式（`:1928-1932`）；
   证书文件集与 `config_paths()` **双向**差集皆空（`:1919-1923`）；**逐文件把证书哈希与闸门当场算的当前字节哈希比对**
   （`:1924-1927`）；profile 集 == bind 集且绑定值必须等于 `APPROVED_NAME`（`:1938-1944`）。

我当场用 python 对 `backend/src/main/resources/*` 算了四个 SHA-256，与 census 四行**逐字符相同**：

```
application.yml       42acb38562eb3212b1c66d9875c6f8ab12deca48576d77e0214289151cc1d06d
application-dev.yml   41ee5e1caae10f1351f2c156bd290b60f9a66b9c4a322a2b43555625fd656b68
application-mock.yml  c39f099652737792cc8106d6b121ab7c98a47f706976f2374bd23cbe8c44efe8
application-prod.yml  bb769d087a85807a88b8aaca5c017553527ca086abb6fc6dc6f443904a6ee0a0
```
⇒ 证书对的是**源文件字节**，不是 `target/classes` 里的拷贝，链条不会因为构建目录陈旧而自洽。

**闸门不读 `backend/target`**：对 162,443 B 全文 grep `target` 共 15 处命中，唯一涉及构建目录的是
`census_facts()` docstring 里那句解释（`:1524` "the recorder copies target/t03-config-census.txt into evidence"）；
其余全是无关局部变量名（`:735-761` 的"目标节点"、`:2080` / `:2195` 的"被改的那个 config 文件"）。
`SOURCES`（`:99-112`）里没有任何 `backend/target` 路径 ⇒ **target →（记录器）→ evidence →（闸门哈希 + 当场重推导）→ 判定** ✓。

**我重跑之后链条仍自洽**：`session-cookie-r10b.json`（记录器重跑前）与 `session-cookie-r10c.json`
（记录器重写 XML/.txt/binding 之后）都是 exit 0 + `106/106 / 36/36` ⇒ 重写受控文件没有把证书打成"陈旧"
（census 未变、源码未变、绑定记录同批重生成）；同时 `r10b` 与入库 `r10` 103 个叶子字段 0 差异（见 §6）。

结论：**PASS（本项）**。

---

## §8 注入反证归属与强度（我自己重跑一遍）

**先核路径**：交回命令里写的 `tests/engineering/T03/formal.py` **确实不存在**（`tests/engineering/T03/` 实测只有
`check_session_cookie.py`、`record_guard_binding.py`、`verify.py`、`migration-draft.sql`、`shared-integration.patch`
+ `evidence/` + `.work/`）。共享工装在 `tests/engineering/integration/formal.py`（11,121 B / `950254073FA2`），
其默认 `--evidence-name` 就是 `integration`（`:35`），且证据同名存在即 `RuntimeError: Evidence exists; choose a new name`
（`:50-51`）⇒ 主 agent "改名入库"的叙事与工装行为一致。

**我的命令**（原样可粘贴，仓库根）：

```
python tests/engineering/integration/formal.py --suite identity --inject server.servlet.session.cookie.name=WRONGNAME --evidence-name r10-review-round10
```

实测（完整输出由 python 落字节：`logs/inject-r10-review-round10.log`，8,188 B，sha256[:12] `ADC059034AB1`；
harness 外壳 exit **1**）：

- 证据 `tests/engineering/integration/evidence/r10-review-round10.json`：491,541 B / `622C6F15A185`；
  `mode = REAL_POSTGRES_REAL_HTTP_SESSION_CSRF`、`exitCode = 1`、`injections = ["server.servlet.session.cookie.name=WRONGNAME"]`、
  **9 条命令**（第 8 条 maven `exitCode 1`，argv 末尾即 `-Dserver.servlet.session.cookie.name=WRONGNAME`）、
  **151 条 executedInputs**、`failure = "RuntimeError: Recorded command failed"`、
  `isolatedWork = tests\engineering\integration\.work\93cccd49ef5d43bab93eb9bf24ee01c1`（我自己的副本，收尾删除）。
- 与 `cc91998` 那份逐项对照：命令 9=9、executedInputs 151=151、mode 同、injections 同、
  XML `tests=15 / failures=0 / errors=15 / skipped=0` 同、`WRONGNAME` 命中 1=1、`T03_COOKIE` 命中 10=10、
  `EDITORIAL_SESSION` 命中 10=10；我的 XML 463,769 B vs 那份 463,760 B（9 字节差 = 路径/耗时抖动）。
  **⇒ 这条反证的归属不再依赖主 agent 那一次：第三方（我）用自己的证据名复现成功。**
- **真实失败链**（从首个失败用例 `emptyInitializationAndRepeatNeverReset` 的 error 文本逐段取出）：
  `Failed to load ApplicationContext` → `BeanCreationException: Error creating bean with name 'identitySecurity'`
  → `BeanInstantiationException: Factory method 'identitySecurity'` →
  **`IllegalStateException: T03_COOKIE: session cookie name must equal the approved contract name EDITORIAL_SESSION`**
  ⇒ 红在装配、红在产品自身守卫抛的那句，不是红在测试写死的比较。

**它能证明什么**：错误 cookie 名在"真 Postgres + 真 HTTP 会话 + 真 CSRF"的 live 路径上让 boot 起不来，
失败点落在 `identitySecurity` bean 创建；注入通道被如实记进证据（`injections` + maven argv +
XML 里 `<property name="server.servlet.session.cookie.name" value="WRONGNAME"/>`）。

**它不能证明什么**（须如实记账）：

1. **不证明 15 条各是一次独立装配失败**。我的 XML 命中统计：`Failed to load ApplicationContext` **3** 次、
   `failure threshold` **42** 次 —— 只有首个用例真去装载并拿到根因，其余 14 条是 Spring 的
   `ApplicationContext failure threshold (1) exceeded: skipping repeated attempt to load context`。
   ⇒ `cc91998` commit message 那句"全部 `Failed to load ApplicationContext … WRONGNAME`"字面夸大：
   15 条 error 里只有 3 条带那句原文；`WRONGNAME` 全文只出现 **1** 次（作为被记录的 JVM 属性），
   15 条失败理由文本里都不含 WRONGNAME。**P3 精度问题**，对象是主 agent 的散文，不是证据本身。
2. 不证明守卫**文案**整体正确：prod 安全项那条（`T03_COOKIE: secure production cookie required`）本实验没触发
   （未注入 `secure=false` + `prod` profile）。
3. 不证明**多 location 优先级**（`spring.config.location` / `optional:` 仍只做到"不可归因即拒绝"）。
4. 不证明 T03 之外的连带影响：`--suite identity` 只跑 `T03PostgresTest`（`formal.py:139-141`）。
5. 不证明 CI 会红（离线事实，见 §13）。

结论：**PASS（本项）**。方向、退出码、失败点与主 agent 那次一致且可由第三方复现；只对其散文口径记一条 P3。

---

## §9 全量 verify 149 项 skipped 构成（覆盖边界，有无静默吞断言）

**最小复现**（仓库根；`JAVA_HOME` 必须换到钉住的 JDK 21，否则 `maven-enforcer` 的 `requireJavaVersion [21,22)`
会当场红 —— 当前机器默认 `JAVA_HOME=C:\Program Files\Zulu\zulu-17`，我实测换 JDK 后才是绿）：

```
$env:JAVA_HOME='E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1'
.tools\t02\apache-maven-3.9.11\bin\mvn.cmd -B -ntp -o clean verify -f backend/pom.xml
```

我的实测（**输出由 python 落字节留存**：`docs/execution/reviews/T03-round10/logs/full-verify-round10.log`，
12,288 B / sha256[:12] `525747A0D2E7`；140 行、无 BOM、原始 CRLF 字节）：exit **0**、
`Tests run: 305, Failures: 0, Errors: 0, Skipped: 149`、`BUILD SUCCESS`、`Total time: 31.009 s`、
`Finished at: 2026-10-08T07:05:55+08:00`；日志里有 34 个 `Running com.example…` 类与 35 行 `Tests run:` ⇒ 留存的是完整运行，
不是摘要。**⇒ 主 agent 那两个读数（exit 0、305/149）我复现到了**（耗时 31.009 s vs 它报的 19.2 s，同数量级）。

149 条 skip 我逐条从 `backend/target/surefire-reports/TEST-*.xml` 的 `<skipped message=…>` 属性取出，**完整归因于 5 个环境变量门**：

| reason 原文 | 条数 | 涉及类（tests/skipped） |
| --- | --- | --- |
| `Environment variable [T06_REAL_PG] does not exist` | **58** | T06PostgresTest 19/19、T07PostgresTest 16/16、T07RevisionBoundaryTest 20/20、T07UnavailableTest 1/1、T07UpgradeTest 1/1、T06MigrationUpgradeTest 1/1 |
| `Environment variable [T08_REAL_PG] does not exist` | **37** | T08PostgresTest 37/37 |
| `Environment variable [T05_REAL_PG] does not exist` | **24** | T05PostgresTest 24/24 |
| `Environment variable [T03_REAL_PG] does not exist` | **15** | **T03PostgresTest 15/15**（本卡片的 live 套件全跳） |
| `Environment variable [T04_REAL_PG] does not exist` | **15** | T04PostgresTest 8/8、T04RevisionPostgresTest 7/7 |

合计 58+37+24+15+15 = **149** ✓，XML 汇总 `{tests:305, failures:0, errors:0, skipped:149}` ⇒ 真跑 **156** 条。

判定要点：

1. **没有"该跑的没跑还被计入绿灯"**：被跳的 11 个类全是需要真库的 `*PostgresTest` / `*UpgradeTest`；
   本卡片离线该跑的都跑了 —— `T03SessionCookieGuardTest` 实测 **15/0/0/0、0 skip**，15 个 `<testcase>` 名字与
   入库 XML、`guard-test-binding.json.executedRoles` 三方一致（§5）。
2. **没有断言被静默吞掉冒充绿灯**：149 条 skip 每条都带显式 reason；我在 `backend/src/test/java` 全树 grep
   `@Disabled` / `assumeTrue` / `Assumptions` ⇒ **0 处**，20 处命中全是 `EnabledIfEnvironmentVariable` 的 import 与注解
   （`T03PostgresTest.java:32` `@EnabledIfEnvironmentVariable(named="T03_REAL_PG",matches="true")`）。
3. **覆盖边界（P3，事实陈述）**：离线 `clean verify` 全绿**不包含** T03 的 15 条 live 用例；那 15 条只在
   `formal.py` 真库运行里跑（§8：正名 15 条过、注入错名 15 条 error）。所以任何"305 全绿 ⇒ live 路径验过"的读法都不成立，
   报告与 STATE 都须按"156 执行 + 149 显式跳过"来讲。
4. **一条构建级静默跳过 —— 按主 agent 裁定，归属改到主 agent 自己的台账，不是 T03 缺陷**：我的留存日志里有
   `[WARNING] Goal makeAggregateBom requires online mode for execution but Maven is currently offline, skipping`
   ⇒ 离线 `verify` 不产出 `backend/target/sbom/application.json`，而 `tests/engineering/T02/dependency_scan.py:12`
   无兜底地读它（主 agent 实测离线跑后 exit 1、裸 `FileNotFoundError`，未指向"离线把该目标跳过了"）。
   **CI 是在线的**（`ci.yml:63` 的 `mvn -B -ntp -f backend/pom.xml verify` 没有 `-o`，插件绑 `verify` 阶段，
   `ci.yml:97` 上传 `backend/target/sbom`）⇒ 洞在"我用 `-o` 立标准本地门"这句台账措辞，不在 CI、不在被审对象。
   我按主 agent 要求**不去试在线本地跑**（会下载插件并与其它作业争写入），把"本地未复现 CI 的 SBOM 产出"记入 §13 未证明，
   并指名归属：`T02` 侧工装的具名响亮失败 + 主 agent 的 machineGates 措辞。

结论：**PASS（本项，按事实 P3 记账）**。149 条 skip 全部显式、全部可归因、无静默吞断言；唯一需要纠正的是"全绿"的读法边界。

---

## §10 审主 agent 两笔 + `11a3d7f` 是否含工作树最新字节

**(a) 你那三句话逐句核，三句都与事实相符，而且第一句比你的说法更有据：**

1. "证据是我用默认名 `integration` 生成后**改名入库**的" ⇒ **确证，且工件内部留痕**。
   `cc91998` 里入库的那份 `r10-wrong-cookie-inject.json` 内部字段仍写着默认名：
   `testResults = tests\engineering\integration\evidence\integration-test-results`、
   `samples = tests\engineering\integration\evidence\integration-samples`（全文里 `integration*` 出现
   `integration` / `integration-samples` / `integration-test-results` 三种）。
   ⇒ 这不是"用新名重跑一次再入库"，而是**跑在默认名下、事后改名**，与你说的话一致；我的反证（改名会不留痕）被数据否掉了。
   同时它也暴露一处真实短板：**改名不会修内部路径**，所以入库证据里有两条指向不存在目录的路径。建议你把这两条
   也记进 `T03-R11-*`（工装侧：写 JSON 前把 `evidence_name` 落到字段、或改名时一并重写路径字段）。
   我的对照跑（`r10-review-round10.json`）里 `testResults` / `samples` 都是我自己的新名 ⇒ 这条差异只能来自"事后改名"。
2. "我查过 git 历史确认那个默认名从未被提交/删除过（0 提交、0 删除）" ⇒ **相符**：
   `git log --all --oneline -- tests/engineering/integration/evidence/integration.json` 空；
   `--diff-filter=A` 空；`--diff-filter=D` 空；磁盘上 `Test-Path ...integration.json` = False。
   ⇒ 没有任何人的东西被盖掉 ✓。
3. " comparable prior runs r07 / r08 都带描述性名字" ⇒ **相符**：`integration/evidence/` 实测
   `r07-wrong-cookie-must-not-boot.json` 491,452 B、`r08-wrong-cookie-via-system-property.json` 491,598 B、
   `r10-wrong-cookie-inject.json` 491,519 B，命名风格一致。
   另外 `formal.py:50-51` 确实"同名即 `RuntimeError: Evidence exists; choose a new name`" ⇒ 默认名不会被静默复用，
   与你写的"silently reused a name that had never been committed"在**风险描述**上一致（它只保护同一次运行之后）。
4. 顺带核到你自己认领的第二句：commit message 明写"the harness writes no producer stamp into its own JSON"⇒
   我实测 `r10-wrong-cookie-inject.json` 的顶层键里**确实没有任何 producedBy/author 字段**（只有
   `commands/mode/domainSubstitutes/executedInputs/exitCode/failure/injections/isolatedWork/paidCalls/samples/testResults/transformations`）
   ⇒ 这条自我记账成立，归属你的共享工装，不在被审方。

**(b) 引用无留存证据的读数 —— 判定：成立，且你已按正确方式修复。**
`cc91998` 与 `533c0dc` 都写着"305 tests / 149 skipped / 19.2 s / exit 0"而当时无工件；这正是你自己在 commit message 里
认下的"an exit code I quote is evidence and should have been promoted"。**修复方式你也写对了**：不是复述数字，而是把
重跑与留存交给复审方。本节 §9 就是那次重跑，读数被你原样复现（exit 0、305/0/0/149），留存件 =
`logs/full-verify-round10.log`（12,288 B / `525747A0D2E7`，python 落字节，无 BOM）。
⇒ **这条不再是"引用无留存证据的读数"，从 `533c0dc`+我的 §9 起闭环**。唯一残留：你那次 19.2 s 的运行本身仍无工件，
不可追认；建议在 STATE 里把该读数标为"由 `full-verify-round10.log` 追认"。

**(c) `11a3d7f` 是否含实施方工作树最新字节 —— 是，逐blob对上：**

| 文件 | `e4f0f3c` blob/字节 | `11a3d7f` = HEAD blob/字节 | 工作树 `git hash-object` | 判定 |
| --- | --- | --- | --- | --- |
| `check_session_cookie.py` | `b19895f4bade` / 155,999 | `5c1d9e4a4f0c` / **162,443** | `5c1d9e4a4f0c` | **一致** ⇒ 交付指纹 `5AED73E5F4A3` / 162,443 B 成立（disk sha256[:12] 实测同） |
| `T03SessionCookieGuardTest.java` | `ba0438b08fed` / 5,090（旧的 7 用例版） | `eab203691020` / **26,824** | `eab203691020` | **一致** ✓ |
| `record_guard_binding.py` | `6844752804d4` / 8,078 | `6844752804d4` / 8,078 | `6844752804d4` | 一致（报告"只有它当下相等"✓） |
| `evidence/config-census.txt` | 不在该提交 | `0b8209c2487f` / 792 | `0b8209c2487f` | 一致 ✓ |
| `evidence/session-cookie-r10.json` | 不在该提交 | `cc54b4ff073b` / 60,738 | `cc54b4ff073b` | 一致，disk sha256[:12] `8F1E9CFA1734` ✓ |
| `evidence/T03SessionCookieGuardTest.{xml,txt}`、`guard-test-binding.json` | `bbf177d1af17`/33,738、`23bf7d6e8ff2`/363、`4ed622154588`/4,920 | `baebab754f6a`/33,734、`349a55d74395`/363、`389774976cc9`/4,920 | `8a19fb88763c`、`0f0ad8d7f119`、`9f08d909a840` | **现不等于 HEAD —— 是我按第 5 项亲跑记录器重写的**（§5 已申报改前/改后 sha）；报告 §0.1 里对 `e4f0f3c` 那几个 blob 的点名逐格与实测相符 |

⇒ `e4f0f3c` 含中间快照（155,999 B 的那版）、**权威是工作树**这件事你已公开撤回越界，本轮我复核成立：
被审对象的交付字节确已进 `11a3d7f`，没有任何"以旧 blob 为准"的残余。

结论：**PASS（本项）**。(a) 三句话与事实相符并获工件内部路径的正面确证；(b) 判定成立且已按正确方式闭环；(c) 逐 blob 一致。

---

## §11 F-01…F-12 与 R1…R6 闭合判定

依据：第九轮复审的 F-01…F-12 与主 agent 的六条裁决 R1…R6，逐条对到本轮实测（我跑的，不是抄报告）。

| 第九轮发现 | 级别 | 本轮闭合方式（报告主张） | **我的独立复现** | 判定 |
| --- | --- | --- | --- | --- |
| F-01 深度 1 = 数括号，可达性双向都错 | P1 | 三条装配用例真 `register`/`getBean`，不可达即红 | §1：R1b 六类假形状 + 我三类自造 ⇒ 4 类 mvn 红（`15/2/0/0`，失败用例名与报告逐字对上）、2 类 javac 编译期红（报告标"未测"，未冒充绿跑）；3 类 `invokestatic=0`、2 类仍为 1 ⇒ 报告承认字节不是普适判据 | **闭合** |
| F-02 别名 / 合并键 / 多行 flow 藏第二个名 | P1 | 改由框架 loader + `Binder` 现场判定 | §3：五条用例真走 `YamlPropertySourceLoader` / `PropertiesPropertySourceLoader` / `Binder`；`duplicateCookieNameKeysAbortLoading` 的红来自 SnakeYAML 的 duplicate key | **闭合** |
| F-03 普查只看 resources 根 | P1 | 面改两棵 resources 树 + `config/` + 三扩展名，不可归因即拒 | §7：`binder_certificate()`（`:1919-1944`）双向差集 + 6 条 `classpath*:` 模式 + 当场重哈希源文件（我另算 4 个 SHA-256 与 census 逐字符相同） | **闭合**（`config/` 之外的自定义目录仍只到"响亮失败"，见 §13） |
| F-04 守卫测试可掏空且 surefire 计数不变 | P1 | 执行角色由结构读出 | `scripts/hollow_probe.py` 把实施方留下的 `.work/hollowed-guard-test.java`（15 个 `@Test`、`assert` 48→25）灌进闸门内存源：**REJECTED** `guardTest: the executed cases no longer cover every layer -> assemblyAbort: found 0, need at least 1; assemblyLive: found 0…`；只删装配用例同样 REJECTED | **闭合** |
| F-05 `JSESSION\u0049D` 拼写绕过禁名扫描 | P1 | 作用在 JLS 3.3 平移后的无注释视图 + 单点豁免 | §1：我的 `escaped-block-comment-wrap` 形状（`\u002f\u002a`）确被 javac 当作注释、mvn 红；闸门 106 控件含该家族并在交付字节上 106/106 通过 | **闭合** |
| F-06 CI 步骤在场而不再执法 | P2 | 控件 + 良性半边钉住 `if:` / `continue-on-error` / 搬家 | `.github/workflows/**` 是我禁止修改项，未做端到端；但 CI 家族的控件在 106/106 内、36/36 良性半边绿 | **闭合（静态）**；真实 Actions 运行证据仍未证明（§13） |
| F-07 绑定 artefact 可徒手伪造；jar/JDK 不校验 | P2 | argv 逐元素钉 + jar/JDK 当场重哈希 + 记录器生成 | §5：**由我亲跑记录器两次**，exit 0，`counts{15,0/0/0}`，10 项绑定含 `census`；`surefireJar` / `jdk` 路径实测存在；重写后闸门仍 0（`r10c`） | **闭合**（第九轮划的"无人跑过"这条边界由本轮补上） |
| F-08 转义解码缺偶数反斜杠规则 | P2 | 与 javac 同一条转义规则 | 同 F-05 家族；`tokenizer_certificate()`（`:1775-1799`）`divergences` 非空即拒，消费者 `:2018-2022` 还要求 `corpusFiles` 非空 | **闭合** |
| F-09 注释/文档提禁名即红 + 字面量遮蔽 | P2/P3 | 注释与文本块散文不算代码，同一词法器三投影 | §1：`try…finally` / `switch default` 良性半边 mvn 0、闸门 36/36 接受；我的 `unconditional-return` / `while(false)` 被 javac 拒（不是误红） | **闭合** |
| F-10 钉措辞不钉行为 | P3 | 等价改写必须保持绿（36 条良性半边） | 36/36 实测接受；`guard-reflowed-with-whitespace`、`annotation-between-bean-and-signature` 一类在场 | **闭合** |
| F-11 两个词法器对文本块不一致 | P3 | 两套遮罩已删，同一词法器出三投影 | 分歧计数成为拒绝条件；`comment-blanking` / `textblock-blanking` 桩各 `lost 1` ⇒ 有反证在场 | **闭合** |
| F-12 台账三处记账不一致 | P3 | 素材交回主 agent | 属主 agent 侧（本轮我不写 `STATE.json`），`533c0dc` 已改台账 | **转交主 agent，我不判** |

| 主 agent 裁决 | 内容 | 我的核验 | 判定 |
| --- | --- | --- | --- |
| R1 | 调用点必须由执行面证明，不得只靠静态 | §1 + §2：三条装配用例真取 `identitySecurity`，红因来自产品抛出的 `T03_COOKIE`，非测试自写比较 | **达成** |
| R2 | 配置加载必须真走框架 loader + Binder | §3：五条用例 + `PathMatchingResourcePatternResolver` | **达成** |
| R3 | 良性半边不得假红 | §1：`try…finally` / `switch default` mvn 0，闸门 36/36 | **达成** |
| R4 | CI 接线要有控件 | F-06 行：控件与良性半边都在 106/36 内 | **达成（静态）** |
| R5 | 记录器与闸门须成闭环，且须有人真跑 | §5：我亲跑 exit 0，重写后闸门 0 | **达成** |
| R6 | "留一条没人看守的检查比删掉更糟" | §4：54 桩算术真、docstring 真，但"每一条判据都有人看守"的**完整性口径**被我的三条自造桩证伪（1 条正是"削弱后不改变任何判定却被算作有人看守"那一型） | **未达成 ⇒ P2** |

---

## §12 缺陷清单（P1 / P2 / P3）

**P1：无。** 第九轮五条 P1（F-01…F-05）我逐条复现到闭合，本轮未发现新的 P1 级漏洞。

**P2（两条，都需要整改）**

**D-1 载荷审计的完整性口径过度声称**（报告 §3："54 个桩…**无人看守 0**" / "每一条判据都有人看守"）。
- 最小复现：`scripts/my_audit.py` —— 用实施方**同一个**审计工装（不改 `roster()` / `signature()` / `stub_source()` /
  记录策略 / `CORPUS_CAP=40`，只把 `STUBS` 换成我的三条、`OUT` 换到我的目录、`DIAGNOSTIC` 清空）。
- 期望：闸门对每条桩的削弱至少改动一次判定；**实际**：三条全部 `lost 0 / moved 0 / probes 0` ⇒
  `audit: 3 stubs, 0 shared-witness, 3 unwatched, 0 declared-diagnostic`，工装 **exit 1**（基线仍 `106/106 + 36/36`）。
- 最硬的一条是 `reviewer-must-report-numbers`：把它改成"不报数字也照样通过"，**没有任何判定变化**，
  但它落在被审计的代码里，按现口径会被计入"有人看守"的 54。这正是 R6 要防的那一型。
- 修法（二选一）：(a) 把口径改写成实测事实 —— "54 条桩全部可归因，其中 1 条为已申报的文案生成器，
  其余 53 条至少改动一次判定"，并删去"每一条判据都有人看守"；(b) 给"报告必须带数字"这类规则补一条反向控件
  （去掉数字即红）或良性半边，使之进入 watched 集合。

**D-2 记录器先拷贝、后校验**（`tests/engineering/T03/record_guard_binding.py`）
- 代码事实：`:86-96` 先把 `TEST-*.xml` / `*.txt` / `t03-config-census.txt` 写入受控 `evidence/`，
  `:103` 才判 `result.returncode / failures / errors / skipped`，`:111-118` 的角色与用例名校验更在其后。
- 后果：一次脏运行会把失败产物留在受控证据目录（只 `guard-test-binding.json` 不更新）；闸门随后因
  `binding-xml-sha` 不符而红（fail-closed，方向正确），但"受控证据只由干净运行写入"为假，且脏写污染下次复跑起点。
- 期望 / 实际：期望"脏运行不写受控证据"，实际由代码顺序直接可读；**实测触发需脏写受控证据**，
  与本轮"只新增不覆盖"硬规则冲突 ⇒ 我不触发，列入 §13。
- 主 agent 已裁定该 P2 成立并立独立项 `T03-R11-RECORD-BEFORE-VALIDATE`；修法按本条方向（校验通过后再写，或先拷临时目录后原子落）。

**P3（四条，措辞 / 台账精度，不动判据）**

- **D-3** 报告 §1 与 F-01 行称非契约名走的是 `verifySessionCookieContract` 的"第二条子句"：实测
  `T03Configuration.java:68-69` 的**第一条** `if` 才是 cookie 名比较（`:70-73` 是 prod 安全项）。方向无误，口径要改。
- **D-4** 报告"取消手写 YAML 普查当判据"写得比实测绝对：`census_yaml` / `expand_yaml_flow` / `strip_yaml_comment`
  仍在闸门里，`yaml-census` 桩 `lost 91` ⇒ 91 条控件的**署名理由**仍来自文本普查路径。应改写为"普查只登记归因缺口，
  判定权在 binder 证书"。
- **D-5** 报告 §1 "10 个绑定输入 + `census`" 读起来像 11 项；实测 `inputSha256` 恰 10 键且 `census` 已在其内。
- **D-6** 交回命令 / commit message 三处精度：`tests/engineering/T03/formal.py` 不存在（应为
  `tests/engineering/integration/formal.py`）；`session-cookie-r01…r03.json` 从未存在（目录从 `r04` 起）；
  `cc91998`（非 `cc99998`）的 message 写"全部 `Failed to load ApplicationContext … WRONGNAME`"，实测 15 条 error 里
  只有 **3** 条带该原文、`failure threshold` 命中 **42** 次、`WRONGNAME` 全文仅 **1** 次（作为被记录的 JVM 属性）。
  另：目标提交号应为 `cc91998`。

**另有两条归属不在本卡片**（主 agent 已接走）：`FORMAL-NO-PROVENANCE-STAMP`（harness 不写 producer 盖章）、
`T02` 侧 `dependency_scan.py` 缺 SBOM 时的具名失败 + machineGates 的 `-o` 措辞（§9 第 4 点）。

---

## §13 未证明清单（本轮仍无法证明的事）

1. **在线 CI 的真实运行**：本轮全程离线（`-o`）。"闸门在 GitHub Actions 上真跑过并拦下过东西"仍无运行记录级证据
   （沿用第九轮 F-06 的边界）。
2. **记录器脏写的实测触发**（D-2）：触发它必须脏写受控 `evidence/`，与"只新增不覆盖"冲突 ⇒
   缺陷按代码顺序提出，"failures=1 运行后 evidence 里留着失败字节"需在**副本仓库**由持有 mvn 独占的一方验。
3. **主 agent 已删除的那次 mvn 原始运行字节**：我只能证明同一条命令在同等条件下可复现（§9 exit 0 / 305 / 149），
   不能证明它那一次（19.2 s）的字节。
4. **`11a3d7f` 与工作树的"全量"一致性**：我逐 blob 验的是报告点名的 8 个文件（全部一致，§10(c)）；
   工作树里其它未跟踪草稿（`.work/` 下的驱动脚本、影子树）本就不入库，无从逐字节证明，也无"漏入库"风险。
5. **本地未复现 CI 的 SBOM 产出**：`makeAggregateBom` 在离线被跳过（留存日志有该 WARNING），
   CI 在线产出的事实属主 agent 的读取（`ci.yml:63` / `:97` + `pom.xml` 插件绑定），我没有在线跑。
6. **`config/` 之外的自定义目录**：只做到"不可归因即响亮拒绝"，未证明多 location 优先级
   （`spring.config.location` / `optional:` 组合），沿用报告 §7 自曝。
7. **运行期恒假条件**（例如"某属性缺失才假"的分支）：任何静态判据都判不了；执行面只覆盖三条装配用例的形态。
8. **JDK 目录除 launcher 外的逐个哈希**、其它机器上 surefire jar 与本地仓库的可获得性：未测。
9. **06:5x 那份"failures=1"快照的来源**：主 agent 独立取证判定无在仓工件、此后不可再现，归为我的读数失误；
   我按事实登记在 §5 段首，不作为任何判决依据。

---

## §14 需主 agent 代跑的精确命令（含期望值与可原样粘贴路径）

**本轮不需要你代跑**：十个问题的最小复现我全部自己跑完了（§1–§10 全部有在仓留存工件）。
以下三条留给**第十一轮整改方 / 你自己在收尾时**复跑，期望值我都按实测口径写死：

1. 整改后复跑闸门（**必须新名，禁止 `--force`**）：
   ```
   python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r11.json
   ```
   期望 exit **0**，stdout 含 `PASS - approved name 'EDITORIAL_SESSION'; 106/106 negative controls rejected, 36/36 benign probes accepted`
   （若 D-1 的整改动了控件/探针数，两个分母会同步变化，须一并更正报告）。
   同时期望：`session-cookie-r04…r10.json`、`r10b/r10c/r10d.json` **逐字节不变**（历史证据只增不改）。
2. 整改记录器（D-2）后再跑一次，确认它现在**只在校验通过后**写受控证据：
   ```
   python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1
   ```
   期望 exit **0**、`counts{tests:15,failures:0,errors:0,skipped:0}`、`boundInputs` 10 项含 `census`；
   并且**新增一条控件或影子实验**：一次 `failures=1` 的 pinned 运行之后，`evidence/` 三件套仍等于运行前字节。
3. 若要复现我的注入反证（注意路径，报告 handback 段写的 `tests/engineering/T03/formal.py` 不存在）：
   ```
   python tests/engineering/integration/formal.py --suite identity --inject server.servlet.session.cookie.name=WRONGNAME --evidence-name r11-review-<新名>
   ```
   期望外壳 exit **1**、`T03PostgresTest` `tests=15 / failures=0 / errors=15`、根因链含
   `IllegalStateException: T03_COOKIE: session cookie name must equal the approved contract name EDITORIAL_SESSION`；
   跑完请删自己那个 `integration/.work/<uuid>`（`formal.py` 不自动删）。

**给主 agent 的两条台账更正**（我在 §12 D-3…D-6 已列，归属你/实施方）：交回命令路径与 `r01…r03` 措辞；
以及 §9 第 4 点的 machineGates `-o` 措辞（你已接走）。

---

## §15 交回命令（复现本复审关键步骤）

我的驱动脚本已从工作植入目录**移到** `docs/execution/reviews/T03-round10/scripts/` 保留（§16 记录删除动作）。
仓库根执行；`mvn` 不在 PATH，须用绝对路径；`JAVA_HOME` 须显式指 JDK 21，否则 enforcer `[21,22)` 当场红。

```
# §6 / §5 闸门重跑（新名，不 --force）+ 逐字段对照 + 历史证据字节核对
python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r10b.json
python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r10c.json
python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r10d.json
python docs/execution/reviews/T03-round10/scripts/cmp.py         # r10 vs r10b：103 叶子字段，差异 0
python docs/execution/reviews/T03-round10/scripts/metrics.py      # 交付字节/行数/占位符 + 磁盘 vs HEAD blob
python tests/engineering/T03/record_guard_binding.py --jdk .tools/t02/jdk-21.0.12.1+1   # §5：会重写 3 个受控文件

# §1 执行面：R1b 六类假形状 + 我三类自造 + 良性半边 + PRISTINE 对照（影子树在 %TEMP%，不碰仓库）
python docs/execution/reviews/T03-round10/scripts/shapes.py

# §4 载荷审计：灌我自己的三条桩（期望工装 exit 1，三条全 unwatched；基线仍 106/106 + 36/36）
python docs/execution/reviews/T03-round10/scripts/my_audit.py

# §11 F-04：把掏空版守卫测试灌进闸门内存源（期望 REJECTED：executed cases no longer cover every layer）
python docs/execution/reviews/T03-round10/scripts/hollow_probe.py

# §8 注入反证（必须用未占用的新证据名；跑完删自己的 .work/<uuid>）
python tests/engineering/integration/formal.py --suite identity --inject server.servlet.session.cookie.name=WRONGNAME --evidence-name r10-review-round10

# §9 全量 verify + 149 skip 归因 + 留存日志自检
$env:JAVA_HOME='E:\project\codex\wxAgent\.tools\t02\jdk-21.0.12.1+1'
.tools\t02\apache-maven-3.9.11\bin\mvn.cmd -B -ntp -o clean verify -f backend/pom.xml
python docs/execution/reviews/T03-round10/scripts/skips.py

# §10 blob 三方对照 + 注入 XML 命中统计 + 本复审所有留存日志的字节与 sha256
python docs/execution/reviews/T03-round10/scripts/blobs.py
python docs/execution/reviews/T03-round10/scripts/inject_scan.py
python docs/execution/reviews/T03-round10/scripts/logs_check.py
python tests/engineering/T02/check_contracts.py                    # exit 0：Approved T00 rc.3: 27 hashes verified
```

---

## §16 清理自证（植入/削弱目录删除 + Test-Path False）

**第三次闸门重跑（安排在写 §13/§14 之前，已完成）**：

```
python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r10d.json
```
exit **0**，`PASS - approved name 'EDITORIAL_SESSION'; 106/106 negative controls rejected, 36/36 benign probes accepted`；
日志 `logs/gate-r10d-final.log`（206 B，sha256[:12] `9C2D1BA253D4`）。取数时点 = 我的第二次记录器运行（07:01:28）
与全量 verify（07:05:55）之后的当前字节。与入库 `r10` 的逐字段对照（`scripts/cmp2.py r10 r10d`）：
**两边各 103 个叶子字段，差异 2** ——
`evidence.binding` `2116e03e8ae8…` → `cd6412bd1348…`、`evidence.guardTestXml` `bcde9c7e37b9…` → `95d1b5b2338a…`，
**正是第 5 项要求我重跑记录器所重写的那两份受控文件**（§5 表里的改后 sha，逐字符吻合）；
`verdict` 两边 PASS、`controls.negative/benign/benignAccepted` 与 10 个绑定输入哈希全部相同 ⇒ **同判据**。
⇒ 这一跑顺带证明闸门**对受控证据的字节替换并不盲目**（它把 artefact 哈希记进结论字段）。
`r10b` 与 `r10c`、`r10d` 三份新名证据都是只新增，未 `--force`，`session-cookie-r04…r10.json` 全程未动（§6 表）。

**删除的植入/削弱目录**（三条都是我自己造的，收尾时实测 `Test-Path` = **False**）：

| 植入根 | 用途 | `Resolve-Path` 确认 | 删除后 `Test-Path` |
| --- | --- | --- | --- |
| `%TEMP%\t03r10`（= `C:\Users\eie04\AppData\Local\Temp\t03r10`） | §1 影子树 13 个形状 + `runlog.py` 捕获器 | 路径一致 ✓ | **False** |
| `tests/engineering/T03/.work/r10rev-01` | 我的全部驱动脚本工作副本 | 路径一致 ✓ | **False** |
| `tests/engineering/integration/.work/93cccd49ef5d43bab93eb9bf24ee01c1` | §8 注入反证里 `formal.py` 自起的隔离集群与后端副本（`formal.py` 不自动删） | 路径一致 ✓ | **False** |

**必须留在原地的邻居，我核对过仍存在、未触碰**：
`integration/.work/c2dee2b518954fe1ac160da74e7d8bb3`（主 agent 注入那次的现场，`Test-Path` = True）
与 `tests/engineering/T03/.work/1141d282874843d29cd553826d53a337`（实施方影子树，True）；
其余 30+ 个 `.work/<uuid>` 与 `t04-http-*` / `tomcat.*` 目录我一个都没动。
收尾时 `Get-Process postgres` = **0**（`formal.py` 的 `pg_ctl -m immediate stop` 是第 9 条命令，exit 0）。

**一处我留下的副产物，如实申报**：`tests/engineering/T03/.work/__pycache__/` 里有 `load_bearing.cpython-312.pyc`
与 `review_replay.cpython-312.pyc`。后者是实施方自己跑 `review_replay.py` 时先建出来的；
前者可能是我的 `my_audit.py` `import load_bearing` 时生成/刷新的。该目录被 `tests/engineering/T03/.gitignore`
的 `.work/` 忽略 ⇒ 不构成仓库改动，我没有删除它（不是我的目录，也不影响任何判据）。

**我在仓内的全部落地物（只新增；唯一一组"改动"是被要求的记录器重写）**：

```
?? docs/execution/reviews/T03-round10/            # 本报告 70,498 B + logs/ 27 份留存输出 + scripts/ 14 个驱动脚本
?? tests/engineering/T03/evidence/session-cookie-r10b.json
?? tests/engineering/T03/evidence/session-cookie-r10c.json
?? tests/engineering/T03/evidence/session-cookie-r10d.json
?? tests/engineering/integration/evidence/r10-review-round10.json
?? tests/engineering/integration/evidence/r10-review-round10-test-results/
 M tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml   # §5 第 5 项：我亲跑记录器重写
 M tests/engineering/T03/evidence/T03SessionCookieGuardTest.txt   # 同上
 M tests/engineering/T03/evidence/guard-test-binding.json         # 同上
```
收尾时 `git status --porcelain` 里另有 `backend/src/test/java/com/example/editorial/cost/CostPricingTest.java`、
`tests/engineering/T02/{check_gitleaks_allowlists.py,gitleaks.toml}`、`tests/engineering/T08/{run_pg.py,verify.py}`、
`docs/execution/reports/T02-Revision-R{02,05,06}.md`、`T08*.md`、`tests/engineering/T02/evidence/r06-anchor-battery-*.json`
—— **全部不是我写的**（其它卡片会话在并发，见 §5 段首的并发事实）。

**未触碰清单**：`backend/src/main/**`、`.github/workflows/**`、`tests/engineering/{T02,T07,T08}/**`、
`tests/engineering/integration/formal.py`、`tests/engineering/integration/verify_boundaries.py`、
`docs/execution/STATE.json`、冻结契约（`docs/api/openapi.yaml`、`docs/schemas/editorial.schema.json`）、
其它卡片的 review 目录。**未做**：`git add`、`git commit`、写 `STATE.json`、修改被审代码 / 测试 / 闸门。

---

## 总判决：**CHANGES_REQUIRED**

**为什么不是 PASS。** 十个必答问题里九个由实测直接通过；唯一在**被审交付物自身口径**上站不住的是 §4：
报告 §3 与 R6 相关的"54 个桩…**无人看守 0** / 每一条判据都有人看守"这句话，被我用实施方同一个审计工装灌进去的
三条自造桩证伪 —— 三条全部 `lost 0 / moved 0 / probes 0`（工装 exit 1，基线仍 `106/106 + 36/36`），
其中 `reviewer-must-report-numbers` 正是任务书要求我构造的那一型：**削弱后不改变任何判定，却会被计入口径里的"有人看守"**。
R6 的原文是"留一条没人看守的检查比删掉更糟"，所以这条措辞过度声称按定义就是未达成，不能给 PASS。
第二条 P2 是记录器的写入顺序（先拷受控证据、后判干净），主 agent 已裁 P2 成立并立 `T03-R11-RECORD-BEFORE-VALIDATE`。

**为什么不是 BLOCKED。** 我这一轮没有跑不动的东西：`mvn`（绝对路径 + JDK 21）、真库注入反证（`formal.py` 自起集群）、
记录器、闸门、全量 verify 全部由我在本机跑通并留存工件；唯一的选择性放弃是"实测脏写触发"，
因为它必须脏写受控证据、与本轮硬规则冲突（列入 §13 并给了副本仓库的验法）。

**整改面很小，不需要重做执行面**：P2 两条（一条改口径或补反向控件，一条调整写入顺序）+ P3 四条措辞/台账精度
（§12 D-3…D-6，其中两条属于交回命令与 commit message，不归实施方）。

**第九轮 P1 全部闭合**：F-01…F-05 逐条由我复现到红/到绿（§11 表），F-06…F-11 静态与记录面闭合，
F-12 与 SBOM 归属在主 agent 台账。本轮未发现新 P1。

**关键实测（可核对，全在 `docs/execution/reviews/T03-round10/`）**：
闸门 `106/106 + 36/36`、记录器双次 exit 0、`r10b/r10c/r10d` 三份新名证据、全量 verify `305/0/0/149` exit 0 且 149 逐条归因、
注入反证 exit 1 且根因链落到 `IllegalStateException: T03_COOKIE: … approved contract name EDITORIAL_SESSION`、
F-04 掏空灌进闸门当场 REJECTED、三条自造桩 exit 1 unwatched。
