# T03 第五轮独立复审 — T07-R04 会话 Cookie 名整改（提交 `2512025`）

- 判决：**CHANGES_REQUIRED**（无 P0/P1；生产代码方向正确且契约零改动，需整改的是闸门覆盖面与证据表述）
- 复审 HEAD：`b3a909d`；工作树洁净（`git status --porcelain` 空）；范围仅 `2512025` 触及的 T03 面（84 个路径中 5 个属本次边界内源码/闸门，其余为证据与台账）
- 复现方式：纯 Python/git（依边界约束未跑任何 `mvn` 与 `formal.py`，因并行复审 agent 在用 `backend/target`）

## 1. 必须独立复现的结果

| # | 命令 | 退出码 | 我看到的 |
|---|---|---|---|
| 1 | `python tests/engineering/T03/check_session_cookie.py` | **0** | `verdict=PASS`；`negativeControlsRejected` 恰为台账所称 6 条（逐名比对） |
| 2 | `python tests/engineering/T02/check_contracts.py` | **0** | `Approved T00 rc.3: 27 hashes verified, no regeneration` |
| 3 | `Get-FileHash SHA256 docs/api/openapi.yaml docs/api/diff-pages-v1.1.openapi.yaml` | **0** | `e285471760a5dce4…` / `0db04ea086c2c563…`；前者＝`T00-rc3-approval.json:41`＋`candidate-manifest.json:35`，后者＝`diff-page-v1.1-check-r03.json:9`；`candidate-manifest.json` 自身 `3db28b3c…`＝`STATE.contract.manifestSha256` |
| 4 | `git show --name-only --pretty=format: 2512025` | **0** | 命中 `docs/api/|docs/schemas/|docs/execution/contracts/` = **0**；命中 `pom.xml|package*.json|.github|.gitlab|Jenkinsfile` = **0**；blob `f7c1f4f2…`/`1ce9f337…` 在 `2512025^`、`2512025`、HEAD 三处同一 |
| 5 | surefire 三套证据聚合 + 基线失败集合差集 | **0** | 见 §3 |

五源全等在 HEAD 字节上由我自己证明：`configuredCookieName=EDITORIAL_SESSION`、`javaConstant=EDITORIAL_SESSION`、契约/增量契约 scheme 字典全等 `apiKey/cookie/EDITORIAL_SESSION`。

## 2. 实质问题结论

1. **方向**：正确。实现服从 rc.3，契约文本零改动（第 1 节第 3/4 项独立证明）。闸门以冻结契约为权威源（`cookie = frozen_scheme["name"]`），不存在变相要求改契约：`contract-renames-cookie` 变异被拒，且该拒绝来自"增量契约 vs 冻结契约"与"配置 vs 契约"两条真实比较分支（我逐条取出拒绝原因验证）。`EDITORIAL_SESSION` 硬编码仅出现在变异模板里，若契约改名会触发"变异未生效"自杀断言，方向不可反客为主。
2. **全等强度**：见 F-03/F-04/F-06——静态闸门弱于其宣称，但 Java 启动断言读的是**运行时生效值**，是更强的一层。
3. **断言覆盖面**：断言在 `identitySecurity` 组合根内、且位于 `env.matchesProfiles("prod")` 分支**之外**，故"所有 profile"成立；准确表述应为"identity 开关为 true 时的所有 profile"（类带 `@ConditionalOnProperty(editorial.identity.enabled=true)`，基础配置默认 false）。真实证据：`formal.py:115` 置 `EDITORIAL_IDENTITY_ENABLED='true'` 且 identity 套件应用成功启动，说明断言在真实容器内通过。`JSESSIONID` 回流扫描覆盖五源全文（含 Java 常量），`git grep JSESSIONID` 在非证据文件中仅命中台账/报告/闸门自身与 `FORBIDDEN` 常量 → 生产与测试代码 0 残留。改名但运行时仍发旧名的路径不存在：全仓无 `CookieSerializer`/`ServletWebServerFactory`/手写 `Set-Cookie`，容器默认名只由 `server.servlet.session.cookie.name` 决定，而该键同时被启动断言读取。
4. **反向控制有效性**：6 条变异全部是内存内（`copy = dict(sources)` + 字符串替换，无任何写盘；`--output` 存在即拒绝覆盖）；`if mutated == sources: raise "changed nothing"`（`check_session_cookie.py:181-182`）即"变异集非空"断言，我用二次替换验证其为 no-op 触发路径；循环后 `evaluate(sources)`（第 189 行）防"全坏也通过"。运行后我复核两契约 sha 未变，磁盘未被触碰。**但**：两条关键分支无任何控制（F-04），且闸门对断言本身盲视（F-02）。
5. **新未证明面**：见 F-05 与 §4。

## 3. 运行时与回归（读已入库证据，非我复跑）

- `r04-core-post-change-test-results`：12 类 / 75 项 / 0 失败，**其中没有 `T03PostgresTest`**，`fixationRotationAndLogout` 出现次数 = 0；`-Dtest` 白名单（`formal.py:135`）证实 core 套件不含 identity 域。
- `r04-session-cookie-test-results/TEST-…T03PostgresTest.xml`：15 项 / 6 失败；**`fixationRotationAndLogout` = PASS** — 这才是改名生效的直接证据（该用例现在要求 `Set-Cookie` 以 `EDITORIAL_SESSION=` 开头，且按名过滤 CookieStore 后 `orElseThrow()`，未改名必失败，非恒真）。
- 该套件的 `executedInputs` 把 `T03Configuration.java=56f4d50a…`、`T03PostgresTest.java=ecc2eaed…` 绑定为 **等于 `2512025` 且等于 HEAD**；`application.yml` 绑定为等于 `2512025`、**不等于 HEAD**（见 F-05）。
- 归因复核（不需 Maven）：`formal-all-domains-01` 由 `5413cf4` 引入，是 `2512025` 的祖先（`git merge-base --is-ancestor` 退出 0）。其 `T03PostgresTest` 15 项 / 6 失败的**方法名集合与整改后 identity 套件逐项相同**，且 `--suite all` 的 16 失败与它 `sets identical: True`；`fixationRotationAndLogout` 在两者均不在失败集 → `MULTI-DOMAIN-SUITE` 台账项与非回归归因成立。
- 注意 `evidence.mode = 'REAL_POSTGRES_REAL_HTTP_SESSION_CSRF'` 是 `formal.py:52` 的**硬编码字符串**，不是推导事实，不可当作"本套件跑了 T03 会话用例"的证据。

## 4. 发现

| id | 级别 | 发现与 requiredFix |
|---|---|---|
| **T03R5-F01** | P2 | **报告 §3 把运行时直接证据归给不含该用例的套件**。报告："运行时修复的直接证据是第 3 项里的 `fixationRotationAndLogout`"；但第 3 项（core，退出 0）无 `T03PostgresTest`（`Select-String` 命中 0），真实载体是第 4 项 `r04-session-cookie.json`（退出码 1）。`STATE.openItems[T07-R04].fixEvidence` 同样把 `r04-core-post-change.json（真实 PG+真实 HTTP Session/CSRF，12 类 75 项全通过…）` 列为运行时证据，读者会以为改名用例在那套绿色里。证据命令：C6/C7（退出 0）。requiredFix：改写报告 §3 与 `fixEvidence` 首条，明写"改名生效由 identity 套件（exit 1，6 项既有失败）中 `fixationRotationAndLogout` PASS 支持；core 75 项绿色不覆盖 T03 会话用例"，并说明 `mode` 为硬编码标签。 |
| **T03R5-F02** | P2 | **闸门对"守卫本身"盲视**。内存探针（C10，退出 0）：删除 `T03_COOKIE` 启动断言行 → ACCEPTED；把它阉割成 `if(false)` → ACCEPTED；让它读错的属性键（`…cookie.nam`）→ ACCEPTED；`T03PostgresTest.java` 根本不在 `SOURCES`（键仅 `frozenContract/additiveContract/config/configProd/code`），删掉那条 `Set-Cookie` 自证断言闸门毫无反应。即"五源全等"闸门只保证字符串相等，不保证改名被强制与自证。requiredFix：在闸门追加文本级守卫断言——`code` 源必须同时含 `SESSION_COOKIE_NAME.equals(env.getProperty("server.servlet.session.cookie.name"`、测试源必须含 `startsWith(T03Configuration.SESSION_COOKIE_NAME+"=")`——并把"删断言""阉割断言"作为第 7/8 条反向控制。 |
| **T03R5-F03** | P2 | **`config_cookie_name` 无路径锚定、只取首个命中**。探针：删掉真实 `server.servlet.session.cookie.name` 后把 `cookie:/name: EDITORIAL_SESSION` 放到 `spring.datasource:` 下 → ACCEPTED；追加 `---` 文档在 `server.servlet.session.cookie` 下把名字改成 `MYOTHERSESSION` → ACCEPTED（YAML 块扫描器不识别多文档，`application.yml` 现在也没有 `---`）。即结构变化可在"配置根本没设契约键"的情况下报 PASS。缓解：Spring 解析真实生效值，启动断言会拿到 `""` 或覆盖值而抛 `T03_COOKIE`，所以运行时不会静默错，弱的是闸门宣称的覆盖强度。requiredFix：按 `server→servlet→session→cookie` 祖先缩进链锚定、遇到重复键/多文档取后者并校验其 profile 激活条件，并把两个探针转成反向控制。 |
| **T03R5-F04** | P3 | **两条分支有代码无控制**：`configProd` 分支（`evaluate:146`）与 `main()` 的 `FORBIDDEN` 全文回流扫描都不在 6 条控制里。探针 E/F：prod 里加 `name: JSESSIONID` → 正确被拒；prod 显式写契约名 → 接受。当前 `prodOverride=null`（`application-prod.yml` 只加 `secure: true`，`2512025` 未碰它），故"第五源"实际只证明"缺失即继承"，不正向证明该值。协同改名探针：五源一起改成 `JSESSIONID` 时 `evaluate()` 接受，仅靠 `main()` 扫描兜底（命中 4 源）。requiredFix：新增 `configprod-drifts-name`、`coordinated-rename-to-default` 两条控制；台账措辞把"五源全等"改述为"四源正向相等 + prod 未覆盖（继承）"。 |
| **T03R5-F05** | P3 | **已入库证据不再绑定 HEAD 字节**。`tests/engineering/T03/evidence/session-cookie-r04.json:31` 记 `application.yml=fff6a718…`，HEAD 为 `42acb385…`（`b3a909d`/T08 加了 `editorial.cost.enabled`）；`r04-core`/`r04-session-cookie` 的 `executedInputs` 同样绑 `fff6a718`。结论：HEAD 字节的闸门我已在跑（PASS，新 sha 见 C1），但 **HEAD 字节的真实 HTTP 会话套件在本轮不存在**，依协议"复现主张必须绑定当前字节"，T03 批准时不得把 r04 会话证据表述为当前字节。requiredFix：以 `--output` 生成新名证据，并在台账标注继承轮次与绑定基线；T08 合入后在 HEAD 字节重跑 identity 套件。 |
| **T03R5-F06** | P3 | **扫描器"过严"面（方向安全）**：`name: "EDITORIAL_SESSION"`（带引号，语义等价）被拒；`cookie: {name: EDITORIAL_SESSION}` flow 风格被当作"没设 name"被拒；`additive-scheme-extra-key` 因字典全等拒绝合法的 `description` 键。均为 fail-closed，且与 T07-R03 已批准的"字典全等"条件一致 → 不算缺陷。requiredFix：在闸门 docstring 记明"只接受裸标量/严格字典全等"是有意的保守选择，并排除别名键（`"cookie":`）与注释值等语义等价写法继续产生假失败。 |
| **T03R5-F07** | P3 | 措辞精度：`application-dev.yml`/`application-mock.yml`（3/5 行）不含任何 `server|servlet|session|cookie` 键，因此 profile 面目前只有 prod 会追加属性；但闸门 `SOURCES` 只列 `application.yml` + `application-prod.yml`，dev/mock 若日后引入覆盖不会被发现。requiredFix：把 `application-*.yml` 全部纳入 FORBIDDEN 扫描（零依赖，glob 即可）。 |

## 5. 未被我（本轮）证明

1. 任何 Maven 侧事实：`mvn clean verify`、`formal.py` 全套、真实 PG 启动、`Set-Cookie`/401/登录成功回归——我只**读**已入库 surefire 并核对方法名与字节绑定，未复跑。
2. 启动断言在真实容器抛错的正面证据（配置缺失→`T03_COOKIE`）：无负向运行时变异，只有静态推理。
3. HEAD 字节（`42acb385` 的 `application.yml`）上的真实 HTTP 会话证据：不存在（F-05）。
4. prod profile 真实启动；`EDITORIAL_*` 与 `SERVER_SERVLET_SESSION_COOKIE_NAME` 环境变量覆盖顺序（静态推理：断言与容器读同一键，故覆盖会被拒启动，但未运行验证）。
5. 前端/生成客户端对 `EDITORIAL_SESSION` 的端到端消费（T12+ 范围，报告 §5 自述未做）。
6. `--suite identity` 基线对照我未复跑；我以祖先提交 `5413cf4` 引入的 `formal-all-domains-01` 已入库证据替代（同 15/6、同 16 失败集合），这是替代证明而非等价于主 agent 的 worktree 实跑。

判决词汇限于 PASS / CHANGES_REQUIRED / BLOCKED；本记录不构成采纳，采纳由主 agent 与人工批准决定。T03 独立批准（`T03-APPROVAL`）仍 OPEN，G1 仍不可宣布。
