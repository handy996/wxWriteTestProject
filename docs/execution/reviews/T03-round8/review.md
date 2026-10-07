# T03 第八轮独立复审：第七轮整改本身的复审（会话 Cookie 契约闸门）

- 判决：**CHANGES_REQUIRED**（8 条：P1×1、P2×4、P3×3）。HEAD `241083f`（被审整改 `349b51c` 为其祖先；`ed63c3f..HEAD` 无提交触及 T03 受控源，五个受控源 sha 与复审时逐字节相同）。
- 基线复跑（当前字节）：`python tests/engineering/T03/check_session_cookie.py` 退出 **0**（31/31 反向控制被拒、5/5 良性通过）；`python tests/engineering/T02/check_contracts.py` 退出 **0**（"Approved T00 rc.3: 27 hashes verified"）。闸门自身 `sha256 b65c43d5419d0087…`，而证据 `sha256` 段不含它。
- 方法：所有削弱只在内存或仓库外影子树（`%TEMP%\t03r8\shadow6|7`，ROOT 由 `__file__` 推导）里发生，`backend/`、`tests/` 受控源零写入；未跑 maven。Java 语义用仓库内 JDK 21 的 `javac`+`java` 在 TEMP 自证：`LexProbe*.java` 编译 **exit 0**、运行显示守卫 **executedGuard=false**。
- 逐条攻击证据、控制归因表、load-bearing 表见同目录 `evidence/checks.json`。正面认定：**13 项**新检查逐一 load-bearing（删任一即有内置控制转为 ACCEPT），31 条反向控制**归因全部命中预期断言**；真正无控制覆盖的实质分支只有绑定的 sha 比较与计数比较两处（`drop-noop-detector`/`drop-self-pristine-check` 属控制框架自身脚手架，按定义不可自曝）。

## 新发现

**T03R8-F01（P1）文本在场≠可达：整条闸门可以为"运行时永不执行的守卫"出绿证。**
最小复现（`T03Configuration.java` 一处改动，`javac` 证可编译且守卫不执行）：`:42` 的 `verifySessionCookieContract(env);` 外面包一层常量假分支——加 `static final boolean CHECK_COOKIE_AT_STARTUP = false;` 后 `if (CHECK_COOKIE_AT_STARTUP) { … }`（或直接 `if (Boolean.FALSE.booleanValue())`）。**ACCEPT**：影子树 `main()` 退出 0、31/31 控制仍被拒、5/5 良性仍过、`startupGuardLive=true`、`guardCallInsideBeanBody=true`。
为什么绑定层救不了：`T03SessionCookieGuardTest` 有 6 处 `T03Configuration.verifySessionCookieContract(` **静态直调**，一次也不经过调用点——调用点死了它仍 7/0/0，于是主 agent 按文档重跑一次 mvn 就能把四个 sha 与计数合法刷新。同类：**N3** prod 三子句与两条消息整体搬进 `String archived = """ … """;`（**ACCEPT**，exit 0）；**C1** bean 体内放 `String skew = "{";` 把真调用移到文件尾一个从不调用的 static 方法（evaluate 级 **ACCEPT**，正是 :261-262 自己承认的"串内花括号会错位"由假设变成可用攻击）。这是第七轮 T03R7-F01 的同一根因（文本存在≠活代码），本轮只把调用钉进 bean 体，未触及可达性。当前字节干净（受控源内 `\uXXXX`=0、串内花括号=0）→ 延迟型缺陷。

**T03R8-F02（P2）profile 仍能藏第二个 cookie 名：flow 风格对整个闸门不可见（第七轮 T03R7-F05 未闭合）。**
最小复现：`application-prod.yml` 追加一行 `server: { servlet: { session: { cookie: { name: WRONGNAME } } } }` → **ACCEPT**（整闸门 exit 0，`profileOverrides={}`）；dev+mock 同法 **ACCEPT**；追加到 `application.yml` 本体也是 evaluate 级 **ACCEPT**（S6 只因 `baseConfig` 指纹过期而红）。flow 里写 `JSESSIONID` 时 `evaluate()` 仍 **ACCEPT**，只有 `main():559` 的字面扫描偶然接住——即防回流靠"字符串里出现 JSESSIONID"，不靠路径。另：profile 文件不在 `BINDING_INPUTS` 里，改 dev/mock/prod 不必重跑任何测试；`server.Servlet.…` 大小写变体 **ACCEPT**（Spring 宽松绑定实况我没法验）。制表符缩进块 **ACCEPT** 但 tab 缩进本身是非法 YAML，只算扫描器错位。内置控制 `all-profiles-override-cookie-name` 的 replace 打在 4 个文件上，循环在 dev 就抛（归因表可查）→ mock/prod 分支只是被演示：把循环改成只看 dev，31 条控制仍全红。

**T03R8-F03（P2）guardTest 半边太浅：负向用例可被掏空而闸门照印 `negativeGuardCases=7`。**
**N4**：保留 7 个 `@Test void` 名 + 一处 `assertThrows(IllegalStateException.class`（改成自抛自证），清空其余六个方法体 → 整闸门 **ACCEPT**（exit 0）。**N5**：`containerDefaultNameAbortsStartup` 里 `properties.put(NAME, "JSESSIONID")` 改成 `"OTHERSESSION"` → **ACCEPT**，且 `main():558` 把 `guardTest` 从回流扫描里 pop 掉，`JSESSIONID` 消失无人知。**F3**：用例改调本类内一个 no-op 桩 → evaluate 级 **ACCEPT**。

**T03R8-F04（P2）绑定 JSON 的边界：它只能证明字节一致，且两条实质分支没有任何控制。**
可伪造且全部 **ACCEPT**：**G1** 用当前四个 sha256 + 计数 7/0/0、测试从未运行；**G2** `exitCode:1`；**G3** `surefireXmlSha256` 全 0；**G4** 编造 `testNames`；**G5** `command: "echo pretend"`；**G10** 内存里改 `guardTest` 字节而盘上绑定不动。删掉实质分支也不自曝：**`binding-sha-never-compares`**（`want != have` → `want != want`）与 **`binding-counts-never-checked`**（计数断言 → `if False`）两个变体下，31 条控制无一转为 ACCEPT → **这两条分支是"无控制覆盖"的死重**（唯一绑定类控制只演文件存在性）。确实会红的：`tests=8`、`failures=1`、陈旧 sha、文件缺失、影子树里把 code sha 归零。审计：记录里的 `surefireXmlSha256` 与跟踪 XML 的真实哈希全等（`6d0234e0…`），但闸门从不比较该字段。

**T03R8-F05（P2）剥离器仍不等于 javac 词法：`\uXXXX` 转义注释对扫描器隐形。**
最小复现 **A1**：`        verifySessionCookieContract(env);` → `        \u002f\u002fverifySessionCookieContract(env);`（JLS 3.3：转义先于分词，javac 视其为行注释；`javac` exit 0 + `executedGuard=false`）→ evaluate **ACCEPT**；**A4** `\u002f\u002a … \u002a\u002f` 包裹、**A2** 整段守卫包进转义块注释、**A5** `String desync = "\u0022 /*"` 亦 **ACCEPT**。诚实补一句：这几个形态在**整闸门**上偶然变红（`probe6` M1/M2 RED），原因是内置控制自己的锚点错位（`guard-call-moved-to-dead-method` 变空转），不是剥离器认出来了——不可依赖。反向不对称：**A6** 行注释里放 `\u000a`，javac 认为其后的调用是活代码（实测 `executedGuard=true`），闸门当注释 → **REJECT 合法文件**。

**T03R8-F06（P3）装配范围与措辞未收窄（第七轮 T03R7-F02 的措辞半边）+ CI 不跑本闸门。**
判定 (a)：**部分成立**。`application.yml:65` `enabled: ${EDITORIAL_IDENTITY_ENABLED:false}` 与 `T03Configuration.java:22 @ConditionalOnProperty(havingValue="true")` ⇒ identity 关闭时守卫整段不装配，"错名部署必启动失败"对仓库默认态不成立；对 identity=true 且 `identitySecurity` 被创建时成立，且有当前字节反证（`r07-wrong-cookie-must-not-boot.json`：exit 1、15 tests/0 failures/**15 errors**、根因 `BeanCreationException 'identitySecurity' → IllegalStateException T03_COOKIE…`，`formal.py:115` 自设该开关、`:54-57` 不剥 `SERVER_` 前缀，基线 6 项确为子集）。(b) 台账**未自我采纳**：`tasks.T03=INTEGRATED_UNREVIEWED`、`T03-REVIEW-8TH` OPEN、`T07-R04.note` 明写整改"属 T03 域且未经复审"——诚实；但 `T03Configuration.java:60-62` javadoc 仍无条件断言，`openItems[T03-R6-GATE]` 仍 OPEN 且正文保留已被否的"四段分别受控"。(c) 若仍要搬 `StartupPolicy`：可执行边界=只改 `backend/.../bootstrap/StartupPolicy.java`（`require(...)` 加一项）+ `StartupPolicyTest.java` 配负向 + 闸门 `SOURCES`/`GUARD_*` 重定位；`check_contracts.py` 只钉 rc.3 批准清单的 27 个哈希、不含 Java 源 ⇒ 不违反冻结契约，但该文件属 T02/T08 交叉引用面（`T08/verify.py:242` 按正则钉它的 `require(...)` 形状）⇒ 需 T02 owner + 人类批准。本轮**不阻塞**：更便宜的等效动作是把闸门进 CI。

**T03R8-F07（P3）脆性/误拒与良性半边缺口。** 合法 Java 被 **REJECT**：**C2** bean 体内字符串含 `"}"`（方法体被截断）、**C3** `@Bean` 与返回类型间插一行注解、**C4** `@Bean(name = "identitySecurity")`、**A6**、**N2** 把调用移到另一个被装配的 `@Bean`（`initializeIdentity`，仍在建库前失败）→ 整闸门 RED。第七轮"每条反向控制配一条良性探针"只对剥离器兑现：bean 体定位、绑定、profile 循环三个新维度只有攻击半边。**D3** 文件尾未闭合 `/*` → **ACCEPT**（非法 Java，仅记录）。

**T03R8-F08（P3）报告与台账小错。** `check_session_cookie.py:287 for label, path in BINDING_INPUTS.items()` **遮蔽形参 `path`** ⇒ PASS 输出与 `session-cookie-r07.json` 里 `binding.bindingFile` 印成 `backend\src\main\resources\application.yml`（实为 `tests/engineering/T03/evidence/guard-test-binding.json`，且反斜杠风格与其余 posix 路径不一致）；证据 `sha256` 不含闸门自身字节 ⇒ "31 条控制"无法绑定到闸门版本；`STATE.openItems[T07-R04].fixEvidence` 写"T03_COOKIE 出现 9 次"，工件 `commands[7].output` 实测 **10** 次；r07 证据未记录注入变量（`formal.py:83` 只存 argv/exitCode/output）。

## 第七轮 F-01…F-06 逐条（括号内为第八轮新发现编号 T03R8-*）

- **F-01 剥离器文本块错位 → 部分闭合**：文本块独立成态有效（D1 文本块内 `/*`、D2 串内三连引号、D4 `/* /* */`、D5 转义收尾，全部 REJECT）；同根因两处仍穿透——`\uXXXX`（R8-F05）与守卫文本进字符串/文本块算活代码（R8-F01/N3）。
- **F-02 调用点+装配+措辞 → 部分闭合**：bean 体定位生效且 load-bearing（删定位即 `guard-call-moved-to-dead-method` 翻身）；装配态反证已入库并绑当前字节；可达性（R8-F01）与 javadoc/STATE 范围（R8-F06）未闭。`T03SessionCookieGuardTest.java` 确已入 `SOURCES`。
- **F-03 prod 三子句与两条消息逐条受控 → 闭合**：`GUARD_PROD_IF/SECURE/HTTP_ONLY/SAME_SITE` + `GUARD_MESSAGES` 逐条 load-bearing；31 条控制**归因全部命中预期断言**，上轮两条错位（`prod-profile-token-renamed` 打到 origin、`guard-reflowed-with-whitespace`）确已改正。
- **F-04 guardTest 入受控源 + 指纹绑定 → 部分闭合**：删文件/清空 assertThrows/陈旧 sha/计数不符/文件缺失均红；但用例可掏空（R8-F03）、sha 与 counts 两分支零控制覆盖且其余字段不校验（R8-F04）。
- **F-05 profile/flow 覆盖 → 未闭合**：见 R8-F02（N6/N7/E1 整闸门 exit 0）。
- **F-06 台账同步与良性半边 → 部分闭合**：计数与 r07 证据已同步、空操作检测器有效；`bindingFile` 路径错、9/10 次不符（R8-F08）、新维度缺良性探针（R8-F07）。

## 未证明清单

闸门在 CI 中执行（`ci.yml:38-46` 只跑 `check_contracts.py` + `mvn verify`，也不设 `EDITORIAL_IDENTITY_ENABLED`）；flow/大小写/tab 的 Spring 实际绑定结果；identity 关闭部署下错名被谁接住；重复键与 SnakeYAML 行为（第六轮遗留）；绑定 JSON 声称的那次运行确实发生过；调用点在真实装配里可达（r07 只证当前字节一次）；profile 循环的 mock/prod 分支；以及"报告 `startupGuardLive=true`"这一字段的语义强度（F-01 使其不成立）。

## 请求主 agent 代跑（我不跑 maven）

1. `mvn -B -ntp -o -f backend/pom.xml "-Dmaven.repo.local=.tools/t02/m2" -Dtest=T03SessionCookieGuardTest test` —— 整改后刷新 `guard-test-binding.json`（四个 sha + 7/0/0）。
2. `mvn -B -ntp -f backend/pom.xml clean verify`。
3. `mvn -B -ntp -f backend/pom.xml "-Deditorial.identity.enabled=true" "-Dserver.servlet.session.cookie.name=WRONGNAME" "-Dtest=T03PostgresTest#fixationRotationAndLogout" test` —— 装配态反证，并把注入变量写进 `evidence.transformations`（现有 r07 工件没记注入通道）。
4. `python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r08.json`；`python tests/engineering/T02/check_contracts.py`；`python tests/engineering/T03/verify.py`。
5. 若要搬 `StartupPolicy`（F-06c）：需 T02 owner + 人类批准，并附跑 `python tests/engineering/T08/verify.py`；不搬则请采纳更便宜的等效动作——把本闸门加进 `.github/workflows/ci.yml`，并把 `T03Configuration.java:60-62` javadoc 与 `openItems[T03-R6-GATE]` 措辞改为"identity.enabled=true 且 identitySecurity 被创建时"。
