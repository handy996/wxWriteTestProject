# T03 第九轮独立复审（round 9）

**结论：CHANGES_REQUIRED**

- 复审对象：`1a1f433`（第八轮整改）+ `8385a13`（CI 接线）；闸门 `tests/engineering/T03/check_session_cookie.py`
  （sha256 `a86f64dd3f59d9306628023dd228c2b51569adac467d6ae27229b1d92005970c`，与台账前缀 `a86f64dd3f59…` 一致）；
  台账 `2f510ea`/`bee014c`。
- 本复审实际 HEAD：`fb62212`（会话期间其它任务又前进了 5 个提交；`ci.yml` 被 `0b2a6f8` 改动过一次，
  复审影子树已重新同步到当前字节后再跑，见 [evidence/shadow-tree.md](evidence/shadow-tree.md)）。
  最后一次复核时 HEAD 已到 `9f1df7e`（另两个会话只提交 T02/T08 路径），本判定绑定的 9 个字节**逐一未变**，
  闸门在该 HEAD 下重跑仍是 PASS / 49 反证 / 12 良性 / 8 绑定输入 / 4 配置（见
  [evidence/sha256-table.md](evidence/sha256-table.md) 末尾的 re-check 段）。
- 复现方式：全部变异只发生在内存或 `%TEMP%\t03r9\shadow` 影子树；**未运行 `mvn -f backend/pom.xml clean verify`，
  本复审未写 `backend/target`**（该目录在复审期间被其它会话的 mvn 使用过，不属于我的产物），
  未 `git add`/commit，未写 `docs/execution/STATE.json`，未触碰 rc.3 冻结契约。
  工作区里 `tests/engineering/T02/**`、`tests/engineering/T08/**`、`backend/.../cost/**`、`.tmp_t08fix.py` 等脏文件
  属另外两个在跑的会话，不是本复审造成，也不作为本复审证据。

## 一、我重跑的基线（不是抄来的）

| 声明 | 我的实测 | 证据 |
| --- | --- | --- |
| 闸门 exit 0 / 49 反证全拒 / 12 良性全过 / 8 绑定输入 / 4 配置文件 | **成立**（PASS, 49, 12, 8, `application.yml`+dev+mock+prod） | [evidence/gate-selfrun-current.json](evidence/gate-selfrun-current.json) |
| `check_contracts.py` exit 0，27 哈希不重生成 | **成立**：`Approved T00 rc.3: 27 hashes verified, no regeneration` | [evidence/sha256-table.md](evidence/sha256-table.md) |
| 49 控件 + 12 探针的名单 | 控件 49 条、良性 9 code + 2 config + 1 ci，名单与代码 AST 抽取一致 | review §六 |
| `mvn clean verify` 281/0/143 | **未自证**（卡片禁则），命令交回主 agent | §七 |
| `formal.py --suite identity --inject` ⇒ exit 1 / 15 失败 / 根因 `BeanCreationException identitySecurity`→`IllegalStateException T03_COOKIE` | **未自证**（需活库 + 会写 target），命令交回 | §七 |

## 二、逐条结论（对应卡片 1–9）

### 1. `guard_is_reachable()` 的深度 1：不是可达性，是"花括号计数"——**双向都错**（F-01，P1）

我用同一形状的 15 个最小样例走 `javac -J-Duser.language=en` 编译 + `java` 执行来测"守卫到底跑不跑"，
再对当前真实字节做整闸门变异（包装行加在锚点行**上方**，保证 `        verifySessionCookieContract(env);`
原行不动，从而排除"内置控件锚点被砸"这一混淆）：

| 形状（写在已装配的 `identitySecurity` 体内） | javac | 守卫真执行 | 闸门 | 判定 |
| --- | --- | --- | --- | --- |
| `if (false)` + 换行调用 | exit 0 | 否 | **ACCEPT** | 漏判 |
| `if (Boolean.FALSE.booleanValue())` + 换行调用 | exit 0 | 否 | **ACCEPT** | 漏判 |
| `if (SKIP)`（`static final boolean SKIP=false`） | exit 0 | 否 | **ACCEPT** | 漏判 |
| `if (!"prod".equals(...)) return http.build();` 调用在前 | exit 0 | 否 | **ACCEPT** | 漏判 |
| `if (Optional.empty().isPresent())` | exit 0 | 否 | **ACCEPT** | 漏判 |
| `while (false)` + 换行调用 | **exit 1（unreachable statement）** | — | **ACCEPT** | 漏判 + 接受编不过的文件 |
| `if (false) { … }`（内置控件的写法） | exit 0 | 否 | REJECT | 正确 |
| `try { 调用 } finally {}` | exit 0 | **是** | **REJECT** | 误杀 |
| `switch (0) { default: 调用 }` | exit 0 | **是** | **REJECT** | 误杀 |
| `else` 分支里的调用（真实条件） | exit 0 | **是** | **REJECT** | 误杀 |
| `Runnable r = () -> 调用;`（从不 run） | exit 0 | 否 | REJECT | 正确 |

原始输出：[raw-item1b](evidence/raw-item1b-reachability-constant-false.txt)、
[raw-item1c](evidence/raw-item1c-reachability-misc.txt)、[raw-item1](evidence/raw-item1-reachability-battery.txt)、
交叉表 [item1-javac-versus-gate.md](evidence/item1-javac-versus-gate.md)、命令行
[item1-javac-commands.md](evidence/item1-javac-commands.md)。

**判据是否存在**：存在，但不是"数括号"。把"直接语句"换成"直接语句 **或** 容器不是常量假分支/无条件早退"
即可同时封掉前六行与放行后三行：
(a) 允许 `try/finally`、`switch default`、`else`、`for`、被真实条件包裹的调用；
(b) 拒绝**任何**包裹条件为编译期常量假（`false` / `Boolean.FALSE.*` / `static final boolean X = false`）的调用，
无论有无括号；(c) 拒绝"调用之前存在无条件 `return`/`throw`"的语句序；(d) 保留 lambda/内部类/死方法规则。
(a)(b)(c) 仍是启发式（真实条件恒假不可判定，见 §五），但能把这六例全变成红而不引入新的误杀。
**结论**：第八轮的整改把"文本在场"换成了"括号深度在场"，攻击面没关掉，反而多开了三个误杀方向。
因此 `T03-R8-DEPTH1-STRICTNESS` 的自我定性（"属有意的过严而非缺陷"）**被证伪**——它首先是缺陷（漏判），
其次才是过严。该条不能以"取舍"结案。

### 2. `mask_literals()` / `literal_spans()` 的攻击面与良性半边（F-09，P3）

- **同一文件里存在两个独立词法器**：`bean_bodies()`（可达性用）走 `mask_literals` 遮罩；
  `live_pattern()`/`in_literal()`（消息、prod 子句"只在字面量里"判定）走 `literal_spans` 区间。
  两者对文本块的答案不同：随机模糊 6000 例 balanced 文本中 **1548 例分歧**，
  3000 例纯文本块中 **2308 例分歧**，方向恒为 `spanOnly`（spans 越过 `"""` 收尾多吞字节）。
  数据：[evidence/item3_fuzz2.json](evidence/item3_fuzz2.json)。
- **攻击面**：我未能借这条错位做出整闸门 fail-open（文本块内藏调用会被 spans 正确识别为"字面量内"）。
  真正的代价是**假红通道**：`live_pattern` 判定依赖的区间一旦多吞，字面量之后的真实代码会被当成字面量。
- **良性半边**：闸门自带来 9 条 code 良性探针（含 `textblock-odd-quotes-intact`、`bean-body-string-contains-brace`），
  我另跑的 2a/2b（转义引号收尾的串、字符字面量里的引号）当前字节下 **ACCEPT**（无假红）：
  [evidence/item2_lexer_current.json](evidence/item2_lexer_current.json)。
- **承重审计**（§四）：把 `mask_literals` 换成恒等函数，49 条内置控件**照旧全拒**——即遮罩器没有任何反向控制，
  只有良性探针看着它；`live_pattern` 致盲同样零翻身，但我手制的"prod 三子句只以文本块散文存在"变异被 ACCEPT
  ⇒ **该维度真实存在且无人看守**（[evidence/item8b.json](evidence/item8b.json)）。

### 3. `decode_unicode_escapes()` 残余不对称：一个更宽、一个更严（F-02/F-03，P1/P2）

第 71 行正则 `\\u([0-9a-fA-F]{4})` **没有实现 JLS 3.3 的"偶数反斜杠"规则**（被 `\` 紧随的 `\` 不能起头）。

- **闸门更宽（漏判）**——`// runbook \\u000a` 后接调用行：
  `javac -J-Duser.language=en` exit 0，`javap -c` 的 `build(...)` 里**没有**该调用（真被注释吃掉），
  闸门 **ACCEPT** ⇒ 死调用被印成 `startupGuardLive=true`。
- **闸门更宽（禁用名绕过）**——`JSESSION\u0049D`：`javap -constants` 给出 `ConstantValue: String JSESSIONID`，
  运行时 `"…".equals(FORBIDDEN)=true`，而闸门 `forbiddenDefaultInCheckedSources` 只看原始字节 ⇒ **ACCEPT**。
- **闸门更宽（接受编不过的文件）**——`"\uZZZZ"`（javac `illegal unicode escape`）、`"x\u000ay"`
  （javac `unclosed string literal`）：两例 **javac exit 1，闸门 ACCEPT**。
- **闸门更严（误杀合法文件）**——标识符里用合法转义 `verifySessionCookie\u0043ontract(env);`：
  javac exit 0、字节码里确有该调用（守卫真执行），闸门按原始字节找锚点 ⇒ 整闸门 **REJECT**
  （`"changed nothing; it proves nothing"`，因为内置控件自己的 replace 锚也被这层转义砸了）。
  即"更严"这半边同样存在，且它严的方式是**连带控件一起失效**。
- 反向核对（避免我造假）：`"\u002f\u002f"` 家族的内置控件
  （`guard-call-under-escaped-line-comment`、`guard-call-under-escaped-block-comment`）确实咬得住；
  `"\\u0049D"` 双反斜杠串与 javac 结论一致（无假红）。
- 逐形态 evaluate 级矩阵：[evidence/item3i_escape.json](evidence/item3i_escape.json)、
  [evidence/item3h_evaluate_only.json](evidence/item3h_evaluate_only.json)、
  [evidence/item3j_legal_escapes.json](evidence/item3j_legal_escapes.json)、
  [evidence/item3a2.json](evidence/item3a2.json)（javap 原文）。

### 4. `expand_flow()` / `_walk_flow()` / `cookie_names()`：别名、合并键、多行 flow 仍能藏第二个名（F-04，P1）

- **攻击**：5 种形状对 `cookie_names()` 不可见（返回 `[]`），而真实 `YamlPropertySourceLoader` + `Binder`
  逐条实测**确实绑出错误名**：多行 flow、flow+行尾注释、flow+内嵌注释、块别名 `*anchor`、合并键 `<<: *d`
  （合并键实测 `boundName=ANCHOR-VALUE`）。整闸门（影子树 + 模拟重录）对这 5 种写 WRONGNAME 全部 **ACCEPT**。
  数据：[evidence/unit_scanners.json](evidence/unit_scanners.json)、
  [evidence/raw-item4-flow-alias-yaml-attacks.txt](evidence/raw-item4-flow-alias-yaml-attacks.txt)、
  [evidence/duplicate_keys.txt](evidence/duplicate_keys.txt)。
- **顺带关掉一条旧"未证明"**：重复键不是"后者覆盖前者"。实测三种重复
  （裸键重复、`"name":` 与 `name:` 并存、flow 与块并存）在 Boot 的 SnakeYAML 配置下**一律抛
  `DuplicateKeyException`** ⇒ 应用根本起不来。这解释了第八轮 `quoted-duplicate-cookie-key` 控件为何有效，
  也说明 `:617-618`"必须恰好声明一次"的写法与真实行为是**一致**的（不是过严）。
- **良性半边**：把**合规名**写成多行 flow ⇒ 闸门 **REJECT**（`found []`）——同一个形状写错名绿、写对名红。
- **配置普查本身仍是子集**：`binding_inputs()` 只 `glob("application*.yml")`。Boot 的实际装载集合是
  `[properties, xml]` + `[yml, yaml]`，且默认搜索位置含 `classpath:/` 与 `classpath:/config/`。
  实测：影子树里加 `backend/src/main/resources/config/application.properties`
  （`server.servlet.session.cookie.name=FROM-CONFIG-DIR`）⇒ 整闸门 **ACCEPT**，
  而真实 `SpringApplicationBuilder`（profiles=prod）启动后解析出 **`FROM-CONFIG-DIR`**——它盖过了根
  `application.yml` 里的 `EDITORIAL_SESSION`（`RESOLVED name=FROM-CONFIG-DIR`，属性源列表逐条印出两级来源），
  且启动器直接打印了两个 loader 的后缀集合：`yamlExtensions=[yml, yaml]`、`propertiesExtensions=[properties, xml]`
  ⇒ 这是能在 prod 生效、闸门既看不见也不绑定的通道。原始输出：
  [evidence/f03_config_dir.json](evidence/f03_config_dir.json)。

### 5. `GUARD_TEST_REQUIRE` + `method_span()`：钉的是措辞，不是断言力（F-05，P1）

- **空壳但最小合规**：把 7 个 `@Test` 体掏空，只留一段文本块散文（含 `assertThrows`、
  `T03Configuration.verifySessionCookieContract`、`server.servlet.session.cookie.*`、两条消息原文）
  ⇒ 整闸门 **exit 0**；该文件 `javac` 编译通过；再用仓库内 JDK21 + `m2` 里的 junit-platform-launcher
  直接跑：**`found=7 succeeded=7 failed=0 aborted=0 skipped=0`，与未掏空的原文件逐字段相同**。
  ⇒ 一次"照文档重跑 mvn"即可合法刷新 8 个指纹 + `7/0/0`。第八轮 F-03 的通道**原样重开**。
  源码：[evidence/item5_hollow_mutant.java](evidence/item5_hollow_mutant.java)；
  运行：[evidence/guardtest-hollow-junit-run.txt](evidence/guardtest-hollow-junit-run.txt)；
  闸门输出：[evidence/raw-item5-guardtest-hollowing.txt](evidence/raw-item5-guardtest-hollowing.txt)。
- **等价改写假红**（变异体都在 101 行真实测试文件上，逐条附断言原文）：参数顺序调换 `assertEquals` ⇒ REJECT
  （`no longer contains ['assertEquals("EDITORIAL_SESSION", T03Configuration.SESSION_COOKIE_NAME']`）；
  `new String[]{SECURE, HTTP_ONLY, SAME_SITE}` → `java.util.List.of(…)` ⇒ REJECT；
  给受钉测试方法加 `throws Exception` ⇒ REJECT（`method prodAcceptsTheContractConformantCookie is gone`）；
  受钉的 `contractConformantProdCookie()` 改名 ⇒ REJECT；而**未受钉**的 `env(…)` helper 改名 ⇒ **ACCEPT**。
  ⇒ needles 钉的是"被抄下来的那几个标识符"，既不是断言结构也不是覆盖强度：**换个写法就红，断言全删反而绿**。
  唯一被容忍的等价形式是全限定 `org.junit.jupiter.api.Assertions.assertThrows(` ⇒ ACCEPT。表：
  [evidence/raw-item5-equivalent-rewrites.txt](evidence/raw-item5-equivalent-rewrites.txt)、
  [evidence/item5_battery.json](evidence/item5_battery.json)。
- **调用点被当成声明？** 未复现：普通调用、`Runnable verifySessionCookieContract = () -> {};`、
  `list.forEach(this::verifySessionCookieContract);`、三元里的调用，`method_span()` 一律抛
  `guardTest: method … is gone`（不误读成声明）；泛型返回值声明与注解同行声明会被当成声明，但那是它该做的事。
  表：[evidence/item5_method_span.json](evidence/item5_method_span.json)。

### 6. `binding_check()`：字节一致 + artefact 自洽，可伪造性未被 `record_guard_binding.py` 实质改变（F-06，P2）

- **徒手伪造成立**：在影子树里写一份自洽的 XML（7 个 `testcase`，计数 7/0/0）+ 手写 JSON
  （`exitCode:0`、`command:"echo pretend -Dtest=T03SessionCookieGuardTest"`、8 个 inputSha256 与磁盘一致）
  ⇒ 整闸门 **exit 0**。`command` 只被要求**含子串** `-Dtest=<类名>`，"谁来执行"这一维零校验。
- **不受控字段实测**：`surefireJarSha256` 改成 `"f"*64`、`surefireJar` 指向不存在的相对路径、`jdk` 改成假值
  ⇒ 三种各自都 **exit 0**（闸门从不复核这三项，而 `guard-test-binding.json` 的 note 写着
  "the gate re-hashes every input listed here" —— 该 note **过度声称**）。
  数据：[evidence/item6_forge.json](evidence/item6_forge.json)。
- **`record_guard_binding.py` 的实质贡献**（我给正面认定）：它确实真跑 mvn、缺 surefire jar 即拒绝记录，
  把"手搓 JSON"从**默认路径**变成**旁路**；但闸门侧没有对偶校验，所以旁路仍然通。
- **`binding_inputs()` 是否覆盖每个 profile**：**否**。仓库现存 4 个 `application*.yml` 全在集合里（8 个绑定输入
  = 4 Java/XML 源 + 4 配置，实测一致），但：
  `.properties` / `.yaml` / `xml` / `classpath:/config/` 下的任何文件既不进普查也不进绑定（见本条第 4 小点）；
  `pom.xml` 与 CI 文件也不在绑定输入内（CI 侧靠 `CI_GATE_NEEDLE` 文本钉，见 §7）。
- **可证伪的更强锚点**（供主 agent 选做，不选即是明确取舍）：
  (i) 把"跑测试并记录"这一步搬进 CI（artefact 由流水线生成并上传，闸门只信流水线产物）——最强；
  (ii) 校验 `surefireJarSha256` 指向本地仓库里真实 jar 的哈希，`command` 必须是完整 argv 数组并等于
  `record_guard_binding.py` 的常量表（不许 `echo`）；
  (iii) 在 JSON 里记录 `git rev-parse HEAD` 与 `mvn -v` 的 javaVendor，与 `jdk` 字段互证；
  (iv) 至少让 `configFilesScanned` 与绑定输入集合做**双向**相等检查（多一个 `.properties` 就红）。

### 7. CI 接线：当前字节确实在执法，但"步骤在场而不再执法"零控件（F-07，P2）

- **现状**（`.github/workflows/ci.yml` 当前 sha256 `2f651cb7…`）：`verify` 作业 `on: [push, pull_request, workflow_dispatch]`，
  `setup-python@v5.6.0` python 3.12，步骤 `Session cookie contract agreement gate` →
  `run: python tests/engineering/T03/check_session_cookie.py`，其后才是 `mvn … verify`，无 `continue-on-error`、无 `if:`。
  ⇒ **"仓库层零自动拦截"作为当前状态已不成立**；但这句话仍原样留在 `STATE.rounds.T03-8th`（作为第八轮结论文本，
  未标注已被 `8385a13` 取代）⇒ 台账该处需要一行"已由 CI 接线闭合"的更正（F-10，P3）。
- **静默关闭四种，全部绿**（锚点保形，排除"控件空转"混淆）：步骤后加 `continue-on-error: true`；
  加 `if: github.event_name == 'schedule'`；作业级 `if: github.event_name == 'workflow_dispatch'`；
  把步骤整体搬进 schedule-only 作业 —— 四例整闸门 **ACCEPT**（exit 0）。
- **合法写法变红**：在同一 step 里加一行完全合法的 `shell: bash` ⇒ **REJECT**；把 `python` 写成 `python3` ⇒ REJECT；
  只改 `- name:` 文案 ⇒ REJECT。三例的死亡原因都是
  `AssertionError: negative control ci-drops-cookie-gate changed nothing; it proves nothing`
  ——**不是** needle 没匹配上，而是内置控件自己的两行 replace 锚被砸了。
  即钉的是**那两行原文**，不是"这个作业会因本闸门红而红"：块内任何编辑（哪怕不影响执法）必红，
  块外任何编辑（哪怕彻底取消执法）必绿。数据：
  [evidence/item7_ci_current.json](evidence/item7_ci_current.json)、
  [evidence/ci_wording_probes.json](evidence/ci_wording_probes.json)、
  [evidence/item7b_and_fuzz.json](evidence/item7b_and_fuzz.json)。
- **反向核对**：删掉整步骤（内置控件 `ci-drops-cookie-gate` 的形状）确实红——但这一条恰恰只能证明
  "文本在场"，证明不了"红会拦"。

### 8. 承重审计（删掉这条新检查，有没有反证翻身？）+ 只红无白的检查（§四表）

方法：影子树里 `importlib` 载入闸门，把单条检查替换为宽容桩，重跑它自带的 49 控件与 12 探针。
完整表：[evidence/item8-loadbearing-audit.md](evidence/item8-loadbearing-audit.md)。

- **承重（红侧有人看守）**：`guard_is_reachable`、`depth_at`、`decode_unicode_escapes`、`expand_flow`、
  `binding_inputs` 的 profile 覆盖（`binding-profile-stale` 翻身）。
- **不承重（删掉后 49 条照旧全拒）**：`mask_literals` 遮罩（仅良性探针看着它）、`live_pattern`/`in_literal`、
  `method_span`、`GUARD_TEST_REQUIRE` 逐体 needles、`CI_GATE_NEEDLE` 的具体性。
- **只红无白（有反向控制、无良性半边）**：`method_span` 的签名形状要求、逐体 needles（5 例等价改写全红）、
  容器默认名的**位置式**扫描（注释/文档提及即红）、`live_pattern` 的字面量维度（我手制散文变异 ACCEPT ⇒
  连红半边也没守住）。
- **只白无红**：`bean_bodies` 里的 `mask_literals`（良性 `bean-body-string-contains-brace` 依赖，控件零翻身）。

### 9. 台账自述与证据并存的诚实性抽查（F-10，P3）

- **自述与实测一致**：49/12/8/4 全部复现；`check_contracts` 27 哈希复现；
  第八轮"两条失效控制已改正"复现（`prod-profile-token-renamed` 仍在 49 控件名单内、
  `guard-reflowed-with-whitespace` 已改为**良性探针**——这是正确的修法而非掩盖，我给正面认定）。
- **`T03-R6-GATE` 该推进没推进**：同一条目 `status: OPEN` 却带 `closedAt: 2026-10-07` 且
  `closure: "由 T03-R7-GATE 接续闭环"`，而 `T03-R7-GATE` 已 CLOSED。三条内容
  （注释误剥 / 引号化 YAML 键 / "重复键的 Spring 行为未证明"）如今已被第九轮实测覆盖：
  引号化键可见、重复键实测抛 `DuplicateKeyException` ⇒ **该条应显式结案或写明还欠什么**，
  挂着 OPEN 同时填 closedAt 是让状态机自相矛盾。
- **`T03-R8-DEPTH1-STRICTNESS` 定性被证伪**：见 §二.1，它首先是漏判（P1），不是"有意的过严"。
- **`T03-CI-IDENTITY-FLAG` 的自述我复核为真**：`backend/pom.xml` 无 surefire include/exclude/skip
  （grep 仅命中 `spring-boot-starter-test` 一行）⇒ 7 项离线守卫用例确实在 `mvn verify` 中执行；CI 也确实没设
  `EDITORIAL_IDENTITY_ENABLED` ⇒ 该 OPEN 条描述准确。
- **数字更正未落地**：`rounds.T03-8th` 承认"台账'T03_COOKIE 出现 9 次'实为 10 次"，但
  `openItems[0].fixEvidence[4]` 与 `openItems[14].evidence` 两处仍写 **9 次**
  （我自己数过：`r07-wrong-cookie-must-not-boot.json` 内 `T03_COOKIE` 恰 **10** 次）。⇒ 更正只改了叙述层。
- **证据不覆盖历史**：`session-cookie-r08.json`（48/11）与 `session-cookie-r09.json`（49/12）并存，
  `main()` 在 `--output` 已存在时直接 `parser.error` ⇒ 声明成立，无覆盖。
- **但 r09 里的 `sha256.ci` 已经过期**：`098b6bb8…` vs 当前 `2f651cb7…`（`0b2a6f8` 之后）。
  不构成缺陷（历史证据绑历史字节是对的），但**当前 CI 接线没有绑定当前字节的闸门产物** ⇒
  建议主 agent 在当前 HEAD 重录一份 r10（我实测当前 HEAD 闸门仍 exit 0，见 §一）。

## 三、发现清单（最小复现 + 期望/实际）

| 编号 | 严重度 | 一句话 | 最小复现（影子树，锚点保形） | 期望 | 实际 |
| --- | --- | --- | --- | --- | --- |
| F-01 | **P1** | 深度 1 = 数括号：常量假分支去括号即活 | `T03Configuration.java` 调用行上方插一行 `        if (false)` | exit 1 | **exit 0** |
| F-02 | **P1** | 别名/合并键/多行 flow 里能藏第二个 cookie 名 | `application-prod.yml` 末尾追加多行 `server: { servlet: { session: { cookie: { name: WRONG } } } }`（拆成 6 行 flow） | exit 1 | **exit 0**（`profileOverrides={}`） |
| F-03 | **P1** | 配置普查只看 resources 根下的 `application*.yml` | 新建 `backend/src/main/resources/config/application.properties` 写 `server.servlet.session.cookie.name=FROM-CONFIG-DIR` | exit 1 | **exit 0**；真实 Boot 启动 `RESOLVED name=FROM-CONFIG-DIR`（盖过合规名） |
| F-04 | **P1** | 守卫测试可被掏空且 surefire 计数不变 | 用文本块散文替换 7 个 `@Test` 体（`item5_hollow_mutant.java`） | exit 1 | **exit 0** + JUnit 实测 7/0/0 |
| F-05 | **P1** | 禁用名可写成 `JSESSION\u0049D` | 常量后加 `static final String OLD="JSESSION\u0049D";` | exit 1 | **exit 0**（javap 证常量池即 JSESSIONID） |
| F-06 | P2 | CI 步骤在场而不再执法 | 步骤下加 `        continue-on-error: true` | exit 1 | **exit 0**（`if:`/作业级 `if:`/搬到 schedule 同） |
| F-07 | P2 | 绑定 artefact 可徒手伪造；`surefireJarSha256`/`surefireJar`/`jdk` 不校验 | 自写 XML + `command:"echo pretend -Dtest=…"` | exit 1 | **exit 0** |
| F-08 | P2 | 转义解码缺偶数反斜杠规则：接受 javac 编不过的文件 | `String odd="\uZZZZ";`（javac `illegal unicode escape`） | exit 1 | **exit 0** |
| F-09 | P2 | 注释/文档提及 `JSESSIONID` 即红（禁名扫描作用在原文上） | `T03Configuration.java` 加一行 `// container default JSESSIONID` | exit 0 | **exit 1**（`container default JSESSIONID reappears in: ['code']`） |
| F-10 | P3 | 钉措辞不钉行为：合法等价改写全红（CI 三例的红色来自内置控件锚碎裂，见 §二.7） | step 加 `shell: bash`；测试加 `throws Exception`；受钉 helper 改名；`List.of` | exit 0 | **exit 1**（`method … is gone` / `no longer contains` / `changed nothing`） |
| F-11 | P3 | 两词法器（mask vs spans）对文本块不一致 | 模糊 3000 例纯文本块：2308 例 `spanOnly` 分歧 | — | 分歧率 76.9% |
| F-12 | P3 | 台账三处记账不一致 | `T03-R6-GATE` OPEN+closedAt；"9 次"未落地；"零自动拦截"未标注被取代 | — | 见 §二.9 |

## 四、第八轮 F-01…F-08 闭合判定

| 第八轮 | 判定 | 依据 |
| --- | --- | --- |
| F-01 文本在场≠可达（常量假分支） | **未闭合**（原样重开） | 去括号形态、`while(false)`、无条件早退仍绿（§二.1 / F-01） |
| F-02 flow/大小写/profile 不可见 | **部分闭合** | 单行 flow、大小写宽松键已可见；别名/合并键/多行 flow/`.properties`/`config/` 目录仍不可见（F-02/F-03） |
| F-03 guardTest 可掏空 | **未闭合**（重开） | 散文掏空 + javac 通过 + JUnit 实跑 7/0/0（F-04） |
| F-04 绑定 JSON 字段不校验 | **部分闭合** | 现在交叉校验 exitCode/command/8 指纹/XML 计数与 testcase 名（7 条控件）；但可伪造、3 个字段不受控、profile 集合不全（F-03/F-07） |
| F-05 `\uXXXX` 注释剥离器≠javac | **部分闭合** | `\u002f\u002f` 家族已入控件并咬得住；偶数反斜杠规则缺失、接受编不过的文件、禁用名转义绕过仍在（F-05/F-08） |
| F-06 CI 不跑闸门 ⇒ 零自动拦截 | **闭合（当前事实）** | 当前 ci.yml 在 push/PR 的 verify 作业里跑本闸门且无 `continue-on-error`/`if:`；**但**"在场而不执法"零控件（F-06），台账文字未标注闭合（F-12） |
| F-07 新维度缺良性半边 | **部分闭合** | 补了 12 条良性探针（含 block scalar、flow 合规名）；仍缺：`live_pattern` 字面量维度、逐体 needles、`method_span` 形状、禁名注释场景（F-09/F-10/F-11） |
| F-08 `binding_check` 形参遮蔽 + 9/10 计数 | **部分闭合** | 形参 `label` 已不再被循环变量遮蔽（现进 `bindingLabel`）；更正写进了 `rounds`，但两处证据文本仍是 9 次（F-12） |

## 五、我**没有**证明的东西（别当成已排除）

1. 真实条件下恒假（`if (env.getProperty("x","no")==null)` 一类）——任何静态判据都判不了，F-01 的修法只覆盖编译期可判定的那部分。
2. GitHub Actions 上"作业真的红"（我只读 YAML 语义，没跑过流水线）。
3. 多次 `spring.config.location`/环境变量注入下的实际优先级（我只证到 `classpath:/config/*.properties` 覆盖根 yml）。
4. 真实 mvn/CI 是否发生过 `record_guard_binding.py` 声称的那一次运行（F-07 只能证"伪造同样通"）。
5. SnakeYAML 与 Spring 的组合里**所有** YAML 形状（我枚举到别名/合并键/多行 flow/注释/文档分隔符/tab/引号化键，未做穷尽形式化）。
6. `identity.enabled=false` 部署下错名被谁接住（第八轮遗留，仍未证明）。
7. 281/0/143 与装配态 15 失败/根因链（未自证，见 §七）。

## 六、控件与探针名单（我抽取的，用于对齐口径）

49 条反向控制：`config-drops-cookie-name`、`config-changes-cookie-name`、`cookie-path-relocated-under-unrelated-parent`、
`extra-document-carries-second-name`、`all-profiles-override-cookie-name`、`contract-renames-cookie`、`additive-drops-scheme`、
`additive-scheme-extra-key`、`code-constant-drifts`、`guard-call-deleted`、`guard-call-commented-out`、
`guard-call-moved-to-dead-method`、`guard-name-check-commented-out`、`prod-check-neutered`、`prod-branch-short-circuited`、
`prod-profile-token-renamed`、`prod-http-only-clause-deleted`、`prod-same-site-clause-deleted`、`prod-secure-default-flipped`、
`guard-message-prefix-changed`、`guard-line-deleted`、`guard-neutered-never-fires`、`guard-reads-wrong-property`、
`quoted-duplicate-cookie-key`、`textblock-desyncs-commented-guard`、`guard-test-file-emptied`、`guard-test-assertions-removed`、
`binding-file-missing`、`binding-exit-code-nonzero`、`binding-command-not-pinned`、`binding-testnames-fabricated`、
`binding-counts-disagree-with-xml`、`binding-xml-sha-wrong`、`binding-profile-stale`、`guard-call-in-constant-false-branch`、
`guard-call-under-boolean-false`、`guard-call-under-escaped-line-comment`、`guard-call-under-escaped-block-comment`、
`message-only-in-literal`、`secure-clause-only-in-literal`、`flow-profile-override-cookie-name`、`flow-base-second-name`、
`case-variant-flow-override`、`guard-test-hollow-container-default`、`guard-test-prod-clauses-dropped`、`ci-drops-cookie-gate`、
`runtime-assertion-deleted`、`runtime-assertion-commented-out`、`all-sources-rename-in-lockstep`。

12 条良性探针：9 code（`textblock-odd-quotes-intact`、`url-string-looks-like-comment`、`char-literals-hold-quote-chars`、
`guard-reflowed-with-whitespace`、`block-comment-containing-slashes-and-quotes`、`bean-body-string-contains-brace`、
`annotation-between-bean-and-signature`、`escaped-newline-inside-block-comment`、`call-moved-to-another-assembled-bean`）+
2 config（`yaml-flow-unrelated-keys`、`yaml-flow-approved-name`）+ 1 ci（`ci-invokes-gate-as-block-scalar`）。

**注意**：这 49 条里没有任何一条是"闸门必须接受某段合法代码"的反向保证——良性半边全押在 12 条探针上，
而 F-09/F-10/F-11 三条假红通道均不在这 12 条覆盖内。

## 七、交回主 agent 的确切命令（我跑不了 ≠ 缺陷，冒充跑过才是）

```powershell
# 1) 全量后端验证（卡片禁则：本复审不得写 backend/target）
mvn -B -ntp -f backend/pom.xml clean verify

# 2) 在当前 HEAD 重录守卫绑定（r09 的 sha256.ci 已过期到 098b6bb8）
python tests/engineering/T03/record_guard_binding.py

# 3) 装配态反证（需活库）：期望 exit 非 0，15 项失败，根因 BeanCreationException identitySecurity -> IllegalStateException T03_COOKIE
python tests/engineering/integration/formal.py --suite identity --inject server.servlet.session.cookie.name=WRONGNAME

# 4) 整改后重跑闸门并另存新一轮证据（不得覆盖 r09）
python tests/engineering/T03/check_session_cookie.py --output tests/engineering/T03/evidence/session-cookie-r10.json

# 5) 复现本复审 F-06（CI 静默关闭）：在 ci.yml 的闸门步骤后加一行 continue-on-error: true，期望闸门仍 exit 0
```

**要求整改的最小集合（P1）**：F-01、F-02、F-03、F-04、F-05 各配一条内置反向控制 + 一条良性半边；
P2 的 F-06/F-07/F-08/F-09 至少要有控件或探针其一；P3 允许与整改同批或转台账。
下一轮复审会优先攻击"新加的判据是否又只是换了个措辞定义"，而不是重复本轮样例。

## 八、证据索引（`docs/execution/reviews/T03-round9/evidence/`，全部为我自跑的原始输出）

| 文件 | 内容 |
| --- | --- |
| `ci_wording_probes.json`（650B） | CI 三例合法改写为何变红（归因到内置控件锚碎裂） |
| `crosstable.json`（11042B） | 交叉表的原始结构（javac 行 + 闸门行 + 合并行） |
| `crosstable_en.json`（10423B） | 同上，英文诊断版本（含 javac stderr 原文） |
| `duplicate_keys.txt`（988B） | 真实 YamlPropertySourceLoader 对重复键/合并键的绑定结果（DuplicateKeyException） |
| `f03_config_dir.json`（709B） | classpath:/config/application.properties 通道：闸门 ACCEPT + 真实 Boot 解析出错误名 |
| `final_capture.json`（5458B） | 基线抓取：闸门摘要、sha256、HEAD、脏文件、影子树清单、check_contracts 退出码 |
| `gate-selfrun-current.json`（5666B） | 当前 HEAD（fb62212）下我自己跑的完整闸门 JSON：PASS、49 反证、12 良性、8 绑定输入、4 配置、自印 sha256 |
| `guardtest-hollow-junit-run.txt`（146B） | 真实 JUnit Platform 实跑：掏空版与原版同为 found=7 succeeded=7 failed=0 |
| `item1-javac-commands.md`（8426B） | 每条 javac、java 命令的完整命令行与退出码 |
| `item1-javac-versus-gate.md`（2440B） | §二.1 交叉表：javac 编译结果 / 守卫是否真执行 / 闸门判定 |
| `item2_lexer_current.json`（1103B） | 当前字节下三条良性字面量探针（转义引号收尾/字符字面量/单反斜杠换行） |
| `item2_maskattacks.json`（1998B） | 注释里提及 JSESSIONID 的 Java/YAML 两条假红原始断言 |
| `item3_endtoend.json`（1681B） | 转义族的整闸门端到端记录 |
| `item3_escape_gate.json`（3091B） | 转义族的整闸门版本（含被控件锚混淆的样例，已标注） |
| `item3_fuzz2.json`（20840B） | mask_literals 与 literal_spans 的模糊分歧计数（6000 + 3000 例） |
| `item3a2.json`（3351B） | `JSESSION\u0049D` 的 javap 常量池原文 + 运行时 equals 结果 + 闸门 ACCEPT |
| `item3f.json`（615B） | 双反斜杠形态与 javac 一致性核对（无假红） |
| `item3g.json`（498B） | 注释内 `\u000a` 的 javap 反证（调用确实不在字节码里） |
| `item3h_evaluate_only.json`（3324B） | evaluate() 级矩阵（剔除内置控件锚碎裂造成的假红） |
| `item3i_escape.json`（2164B） | 转义族：javac/javap 真值 + 闸门 evaluate 判定逐条对照 |
| `item3j_legal_escapes.json`（1352B） | 合法转义族（引号/大括号/斜杠/反斜杠/换行）是否被误杀 |
| `item5_battery.json`（2421B） | 同上结构化版本 |
| `item5_hollow_mutant.java`（3166B） | 掏空变异体源码（第三方可直接 javac 复跑） |
| `item5_method_span.json`（1694B） | method_span 对 8 种调用/声明形状的判定表 |
| `item6_forge.json`（1300B） | 伪造 artefact 与不受控字段（surefireJarSha256/surefireJar/jdk）结果 |
| `item7_ci.json`（2167B） | 早一批 CI 变异记录（同结论，保留原始行） |
| `item7_ci_current.json`（3190B） | 当前 ci.yml 字节下的 9 例接线矩阵（4 例静默关闭全绿） |
| `item7b_and_fuzz.json`（10143B） | 控件锚保形后的 CI/配置补充变异与模糊记录 |
| `item8-loadbearing-audit.md`（2262B） | 承重审计表：把每条新检查换成宽容桩后，哪些控件/探针翻身 |
| `item8b.json`（504B） | 隔离实验：live_pattern 致盲后 49 控件照旧全拒 + 手制散文变异 ACCEPT |
| `raw-item1-reachability-battery.txt`（3441B） | 15 例可达性形状整闸门原始输出 |
| `raw-item1b-reachability-constant-false.txt`（2109B） | 常量假分支/早退（锚点保形）7 例原始输出 |
| `raw-item1c-reachability-misc.txt`（1775B） | lambda/三元/else/早退/双语句 7 例原始输出 |
| `raw-item4-flow-alias-yaml-attacks.txt`（8321B） | flow/别名/合并键/.properties/.yaml 整闸门攻击原始输出 |
| `raw-item5-equivalent-rewrites.txt`（3775B） | 5a-5j 等价改写与掏空矩阵原始输出 |
| `raw-item5-guardtest-hollowing.txt`（648B） | 守卫测试掏空（文本块散文）整闸门 ACCEPT |
| `sha256-table.md`（2559B） | 本判定绑定的每个文件 sha256 + check_contracts 结论 + 工作区脏文件清单 |
| `shadow-tree.md`（1594B） | 影子树 16 个文件与仓库逐文件 SAME/DIFF（证明变异只发生在仓库外） |
| `shadow_baseline_current.json`（4959B） | 影子树（当前 ci.yml 字节） pristine 整闸门输出，CI 矩阵的对照基线 |
| `unit_scanners.json`（11667B） | cookie_names/bean_bodies/reachability 单元级真值表（含 5 种隐形 YAML 形状） |

影子树与全部临时探针目录（`%TEMP%\t03r9`）已删除；本目录下不含任何仓库外绝对路径的产物。
