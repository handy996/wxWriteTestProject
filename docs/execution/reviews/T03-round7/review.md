# T03 第七轮独立复审 — 第六轮整改（剥注释闸门 + 守卫提取 + 7 项离线负向测试）

- 判决：**CHANGES_REQUIRED**（无 P0/P1；三条新控制中"剥注释"这一条被我的探针打穿，round-6 F-01 只对其两种字面量形式关闭；"四段分别受控"台账措辞不成立；提取守卫本身是等价搬运，未削弱强制性，但"错名真的拒绝启动"仍无任何运行时/装配证据）
- 复审 HEAD `164e3f8`（被审字节 `b813bc3`+`164e3f8`）；T03 范围工作树洁净：`git status --porcelain -- tests/engineering/T03 …/identity backend/src/main/resources docs/execution/STATE.json` 退出 0、空输出。脏文件全部属 cost/T08 域（实测 8 个，非通报的 7 个：多 `docs/execution/reports/T08.md`），未读其内容、不据其下结论、不判污染。
- 方法：`importlib` 载入闸门并对变异后的 sources 字典直接调 `evaluate()`——纯内存、零写盘、未跑 mvn/formal.py/run_pg.py；所有计数由我自己解析 XML 得出。
- 被审字节：`check_session_cookie.py=d8d478d8…`、`T03Configuration.java=dc0bb777…`、`T03SessionCookieGuardTest.java=7ba45cc4…`、`T03PostgresTest.java=ecc2eaed…`、`application.yml=42acb385…`（台账指纹与实算全等）。

## 1. 独立复现

| # | 命令 | 退出码 | 我看到的 |
|---|---|---|---|
| 1 | `python tests/engineering/T03/check_session_cookie.py` | **0** | PASS；`negativeControlCount=20`，20 个标签与台账逐一对得上；`profileOverrides={}`；扫 4 个 `application*.yml` |
| 2 | `python tests/engineering/T02/check_contracts.py` | **0** | rc.3 `27 hashes verified` → 冻结契约未被触碰 |
| 3 | 解析 `tests/engineering/T03/evidence/T03SessionCookieGuardTest.xml` | 0 | `tests=7 failures=0 errors=0 skipped=0 flakes=0`，7 个用例名全 PASS；**XML 内无任何输入指纹**；`sun.java.command` 时间戳 `2026-10-07T22-08-49`，早于引入该文件的提交 `b813bc3`（22:28:38）→ 无法自证跑的是当前字节 |
| 4 | 解析 `…/r06-head-bytes-test-results/TEST-…T03PostgresTest.xml` | 0 | 15 项 6 失败 0 错误 0 跳过；`fixationRotationAndLogout`=**PASS**；6 项失败名逐字记录于 evidence |
| 5 | `git show b813bc3 -- …T03Configuration.java` | 0 | 两条检查**逐字搬入** `static verifySessionCookieContract(Environment)`，调用点未变（仍只在 `identitySecurity` 一处） |
| 6 | 比对 `session-cookie-r06.json` 的 `sha256.code` 与实算 | 0 | 全等 `dc0bb777…` → 已入库闸门证据即 HEAD 字节 |

## 2. 靶一：注释剥离器是不是攻击面 —— **是，已被我打穿**

良性面（不得误剥）全部通过：`"http://x"`、`'"'`、`'\''`、`"it's"`、注释内 `"`/`{/*}`、javadoc `{@code "x"}`、含 `//` 或 `/*` 的文本块、块注释内含 `//` —— 8/8 ACCEPT（无假拒绝）。
当前字节的正向面也真实生效：`//verifySessionCookieContract(env);`、`/*…*/` 包裹、整段行注释 → **全部 REJECT**（与 round-6 的 P08/P09/P11 相反，整改确实在做它声称的事）。

**打穿用的最小输入**（Java 文本块 `"""`；扫描器把三个 `"` 逐个配对，故块内**未转义 `"` 的个数为奇数**时，其后整段状态机错位，`//`/`/*` 不再被剥）：

```java
// 1) 在 public class T03Configuration { 之后插入（1 个内层引号）
    private static final String SAMPLE = """
        cookie "EDITORIAL_SESSION
        """;
// 2) 停用守卫
        //verifySessionCookieContract(env);
```

`evaluate()` → **ACCEPTED**，并印 `startupGuardLive=true`、`guardCheckedAfterCommentStripping=true`，而守卫在运行时已死。同一构造在 `identitySecurity` 内（C3）、`/* */` 包裹（C2）、以及 `T03PostgresTest.java` 加奇数引号文本块后注释掉 `Set-Cookie` 名字断言（F1，`runtimeAssertionLive=true`）同样 ACCEPTED。对照组：内层 0/2/4/8 个引号（成对）→ REJECT（C4），证明触发条件是奇偶而非"文本块本身"。
诚实定级依据：我把 `backend/src/**/*.java` 全部 137 个文件跑过剥离器（检查残留注释标记与 EOF 滞留字面量态）→ **0 个受影响**，仓库现有两处文本块（`DatabaseRolePolicy.java:19`、`PromptContractTest.java:57/66/72/85`）内层引号均为偶数 → **当前字节不被穿透，这是延迟型缺陷**，故记 P2 不记 P1；但它是合法、常见、且仓库已采用的构造，一次普通编辑即可让本轮新增的核心控制失效，round-6 F-01 因此**未真正关闭**。

## 3. 靶二：提取守卫是否削弱强制性 —— 未削弱，但**从来没有装配证据**

- 等价搬运（第 1 节第 5 项）：条件、顺序、消息、`matchesProfiles("prod")` 全部逐字保留 → 启用态下强制性不变。
- 但 `GUARD_CALL` 只证明"文件里有一行调用"。我把调用从 `identitySecurity` **删除**、改放进一个永不执行的 `static void harnessForReviewersOnly(Environment env){ verifySessionCookieContract(env); }` → **ACCEPTED**（D1）。
- 覆盖面：`T03Configuration` 是 `@ConditionalOnProperty(editorial.identity.enabled=true)`，而 `application.yml:65` 默认 `${EDITORIAL_IDENTITY_ENABLED:false}`。identity 未启用（= 仓库默认态）时，守卫**整段不装配**，错名静默启动，只剩 `application.yml` 那一行在守。cost 启用必先 identity 启用（`STATE.tasks.T08.activationPreconditions[0]`），所以"cost 开而 identity 关"不是可部署组合；javadoc 那句"一个部署只要名字不同就无法启动"因此是**越界表述**（真实范围：identity 启用且 `identitySecurity` 被创建时）。
- 静态方法被单测直接驱动 ≠ 运行时被调用。`r06-head-bytes` 证的是"名字对时能跑"，不是"名字错时真会拦"：全套证据里没有任何一次"错名启动"负向运行。建议（成本低、可离线自证）：把守卫搬进 `StartupPolicy`（`META-INF/spring.factories` 注册的 `EnvironmentPostProcessor`，`Ordered.LOWEST_PRECEDENCE` 即配置文档已入位；不受任何开关门控、建库前失败），并复用 `StartupPolicyTest` 的 `MockEnvironment` 夹具——同时解决装配证据与默认态盲区；闸门再把该文件纳入 `SOURCES` 并配变异。

## 4. 靶三：7 项负向测试是否恒真 —— **不恒真，但证明范围被高估**

逐条读过 `T03SessionCookieGuardTest.java`：`prodRejectsEachInsecureCookieAttribute` 从"全合规"基线出发，每轮只削弱**一个**属性（`secure=false`/`http-only=false`/`same-site=lax`），所以三项检查各自都是必要条件——我用变异验证：删掉 http-only 与 same-site 两个条件（E2）或把 prod 条件短接（E1）都会让该用例转红。异常类型过宽的问题被消息断言收窄：`absent…`/`thirdName…`/prod 循环都断言 `startsWith("T03_COOKIE")`（仅 `containerDefaultNameAbortsStartup` 只断言类型，小瑕）。夹具不会因环境变量而误绿：`addFirst` 使桩件压过 system properties。
真实限制（台账未写）：
1. 夹具是 `StandardEnvironment`——无 Boot 属性阶梯、无 relaxed binding、无 profile 文件/OS env 覆盖顺序，它证明的是**判定逻辑**，不是"生产有效值会走到这里"。（反向好消息：生产里 `SERVER_SERVLET_SESSION_COOKIE_NAME` 这类高分来源同样经 `getProperty` 生效，方向安全。）
2. `absentCookieNameAbortsStartup` 传**空 map** 且 `addFirst`，查不到时落到真实 system property/OS env；若 CI 恰好设了契约名，该用例转**红**（fail-safe，但它是环境依赖测试）。
3. 闸门 `SOURCES` **不含**这个测试文件：删掉它或把断言掏空，`check_session_cookie.py` 照样 PASS（F-04）。
4. prod 默认值可无声放宽：`cookie.secure` 默认 `false→true`、`same-site` 默认 `strict→lax` 都**ACCEPTED**（E4），而单测显式赋值所以也抓不到；当前 `application-prod.yml:8` 与 `application.yml:44-45` 都显式设值，故现实影响为零，但这是双侧盲区。
CI 缓解：`.github/workflows/ci.yml:46` 跑 `mvn … verify`，`backend/pom.xml` 未覆写 surefire 包含规则 → 7 项确实在 CI 生效。

## 5. 靶四：上一轮自我更正是否诚实 —— 主体诚实，两处未同步

- 报告 :50 **已改对**：现写"直接证据是第 4 与第 10 项里的 `fixationRotationAndLogout`（不是第 3 项…）"，并自陈"上一版只改了表格却漏了本节，第六轮 F-03 再次点名"；与表格行 3 的更正一致、与 `formal.py:137/135-143` 白名单实况一致 → **F-03 关闭**。
- `machineGates[2]` 已同步为"剥注释后匹配 + 20 条控制 + 空操作自证"，与实际 20 标签全等；空操作检测器（`mutated == sources` 深比较）我用其自身代码验证有效 → round-6 F-04 前半关闭。
- **未同步两处**：① `openItems[T07-R04].fixEvidence[1]` 仍写"退出 0，14/14 反向控制被拒"来描述**现在这个文件**，字节已变、条数已 20，违反"复现主张必须绑定当前字节"；② "调用点、名字检查、prod 检查、消息前缀四段分别受控"（`openItems[T03-R6-GATE].evidence/requiredFix` 与 machineGates 同调）**不成立**：prod 段只要求字符串 `"server.servlet.session.cookie.secure"` 还在，`if(false && …)`、`matchesProfiles("prodXX")`、删掉 http-only/same-site 两条分支全部 ACCEPTED（E1/E2/E3）；消息前缀段**无任何控制**（`T03_COOKIE→T03_COOKIE2` 因是子串而 ACCEPTED，E5）。round-6 F-04 后半"注明 profile 控制只演字母序第一个（dev）"未加。
- `activationPreconditions` 确在 STATE（`tasks.T08`，5 条）。

## 6. 新发现

| id | 级别 | 发现 / requiredFix |
|---|---|---|
| T03R7-F01 | **P2** | 剥离器不识别文本块：奇数个未转义 `"` 使后续状态错位，注释掉的守卫/断言重新可见 → `evaluate()` 接受而守卫已死（C1/C2/C3/F1）。requiredFix：`"""` 作为三字符定界符单独建态（或改用注释区间不可伪造的匹配：把守卫四段提为**只可能出现在代码区**的结构化断言）；剥离器自带夹具自测（`//` in string、`'"'`、`'\''`、奇/偶内引号文本块、注释内 `"`），并新增两条反向控制 `textblock-desync-guard-commented`、`textblock-desync-assertion-commented`（20→22）；证据里 `guardCheckedAfterCommentStripping` 改称 `…ForTestedLiteralForms` 或在 docstring 声明边界 |
| T03R7-F02 | **P2** | 无装配证据：`GUARD_CALL` 匹配死方法里的调用（D1）；`identity.enabled` 默认 false 时守卫整段不装配；javadoc/台账"必然拒绝启动"越界。requiredFix：守卫移入 `StartupPolicy`（无条件、建库前、可 `MockEnvironment` 离线负向）或补一次真实"错名启动"负向证据；javadoc 与 STATE 改范围为"id==true 且 identitySecurity 装配时" |
| T03R7-F03 | **P2** | "四段分别受控"名不符实：prod 段仅字符串在场检查（E1/E2/E3 ACCEPTED），消息前缀段零控制（E5 ACCEPTED）。requiredFix：新增 `prod-branch-shortcircuited`、`prod-http-only-check-deleted`、`prod-same-site-check-deleted`、`message-prefix-changed`（含子串超串）四条控制，并把 `http-only`/`same-site` 属性字面量与 `matchesProfiles("prod")` 一起纳入必匹配结构 |
| T03R7-F04 | P3 | 负向测试文件不在闸门受控源内、跟踪 XML 无输入指纹且时间戳早于引入提交。requiredFix：`SOURCES` 加 `guardTest` 并配"文件删除/断言注释"控制；evidence 增 `T03SessionCookieGuardTest.json`（两 java 文件 sha256 + 退出码 + tests/failures） |
| T03R7-F05 | P3 | YAML flow 风格在**追加文档或 profile 文件**里藏第二个名 → ACCEPTED（G1），与 docstring"不追踪 flow 风格=保守"的方向叙述相反（此处是 fail-open）。round-6 F-05 的 `.yaml/.properties` 边界项仍未处理 |
| T03R7-F06 | P3 | 台账两处未同步（§5）：`fixEvidence[1]` 的 14/14 描述过期字节；profile 控制只演 dev 未注明 |

## 7. round-6 F-01…F-04 是否真闭合

F-01 **未闭合**（行注释/块注释与 `"…"`、`'…'` 两类字面量已覆盖，文本块未覆盖，见 §2）；F-02 **闭合**（引号键去引号生效：`"name":` 与 `'name':` 重复键均被拒，G2 + 内置控制）；F-03 **闭合**（报告 :50）；F-04 **部分闭合**（machineGates 描述已同步，但新措辞的"四段受控"过度，见 §5/F-03；dev-only 注释未加）；F-05 **未闭合**（扩展名边界 + flow 风格 fail-open）。

## 8. 距人工批准还差什么（签署权在人类，T03-APPROVAL/G1 我一律不代宣）

1. F-01/F-02/F-03 三条 P2 同批整改并重出 `--output …session-cookie-r07.json`（控制 20→≥26），F-04/F-05/F-06 同批清。
2. 需要 Maven 的两项由主 agent 代跑并入库（我不跑）：`mvn -B -ntp -o -f backend/pom.xml "-Dmaven.repo.local=.tools/t02/m2" -Dtest=T03SessionCookieGuardTest test`（把 7/0/0 重新压在 `7ba45cc4`/`dc0bb777` 上，并附指纹 JSON）；以及"错名真会拒绝启动"的一次性负向运行（`StartupPolicy` 路线可离线，`identitySecurity` 路线需 `formal.py --suite identity` 加 `-Dserver.servlet.session.cookie.name=JSESSIONID` 并断言失败集合**多出**该项）。
3. 台账把上述两条证据与"闸门只证文本、不证装配"写清，再交人工批准；若批准前后 `application.yml`/`T03Configuration.java`/`T03PostgresTest.java` 任一字节再变，identity 套件须按 r06 做法重跑并绑 `executedInputs`。

判决词汇限于 PASS / CHANGES_REQUIRED / BLOCKED。证据：`docs/execution/reviews/T03-round7/evidence/checks.json`。
