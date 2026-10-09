# T02 第六轮整改（R06）

> 2026-10-09 集成说明：本文保留 R06 开发过程的历史读数；最终期望为结构 19、controls 223。222 是加入进程隔离断言前的中间版本，不能用作当前验收值。原文中“未 stage / 不写 STATE / 等待主 agent”描述的是交接时状态；本次将按 T02 单独提交、逐件核对证据的磁盘与索引字节，并同步 STATE。独立复审未完成，任务不提升为 PASS。

- 上游判决：`docs/execution/reviews/T02-round5/review.md`（**CHANGES_REQUIRED**：R5-1…R5-7 + §11 交回清单）
- 本轮实施：T02 第六轮整改（本文件）
- 开工基线：`HEAD = e4f0f3c`（主 agent 的 `.gitattributes` evidence `-text` 修复）
- 落盘优先：本文件在动工前建立骨架，每完成一节即写盘。判决词只用 PASS / CHANGES_REQUIRED / BLOCKED。

## 判决

- **本轮自判：CHANGES_REQUIRED**（不是 PASS）。理由分三层，逐层给可核对的读数：
  1. **R5-1…R5-6 六项全部落地且当场可复核**：`\b` 换成两侧封闭定界类后，复审 harness 的**改前 50 例标点邻接抑制**复现、**改后 0 例**（`evidence/r06-anchor-battery-{before,after}.json`）；11/11 精确值仍抑制、99/99 超串复报、44/44 单字符变异复报；aws 判据改成**三道门**并给出**整条 20 字符匹配串**为计量对象的翻转对；`T02-Revision-R05.md:19` 的字符类**就地改对**；canary 补出「合法 base32 + 低熵」第三角 ⇒ 三角形闭合；`T02-Revision-R02.md:163` 的「仍退出 1」就地标注并全文扫了同类残留。
  2. **仍判 CHANGES_REQUIRED 的原因不是没做，而是有两条我这边证不了的缺口留在台账上**：① `docs/execution/STATE.json` 的 `machineGates` 期望仍是旧数（**断言 88→139 已过期，现为 19 / 223**；`gitleaks.toml` 摘要期望需改为 `60e37e44e0429055` / 4,987 B），该文件属主 agent，我不写；② 新证据的字节保真只能等 `git add` 后用 `git show :<path>` 复算——我无权 stage，本轮用等价手段先证了一次（17 件 `git hash-object --path` 的 blob id == 磁盘字节 SHA-1，`would-rewrite: none`），并把入库后的复核命令交给你（§12 第 1 条）。
  3. **未证明清单如实留着**（§12 六条）：gitleaks 上游源码口径、Linux/CI 侧、复审 §11(D) 的 runner 尾款、`:` `,` `` ` `` 三字符的 span 语义（实测不产生命中，属推论）、按值豁免本身的长期风险、红控副本的寿命。**没有**任何一处用「应该」代替读数。
- 必跑矩阵七行**全 0**（§10），其中结构模式 **19/19**、controls **223/223、0 NOTE**；三条 AWS-shape 断言与 14 条 span 断言都在最终 223 里。矩阵在所有文件落盘后最后跑了一遍，所以它的 0 覆盖了本判决写进文件之后的正文状态（本判决落盘后仅剩 §11 计数微调，已复跑 `secret_scan.py` 与结构模式确认仍为 0）。
- 冻结三件收尾复算不变；临时根 7 处全部删净（`exists=False`）；`git status` 只有我的 5 改 + 1 新报告 + 8 新证据件。


## §0 基线自证（开工先读回）

| 项 | 期望 | 实测 | 判定 |
|---|---|---|---|
| `evidence/r01-integrity.json` = `1d18eef28322218a`/14783 | 不变 | `1d18eef28322218a` / 14,783 B | PASS |
| `evidence/r01-integrity-run.json` = `18be0c34fbc16ad1`/409 | 不变 | `18be0c34fbc16ad1` / 409 B | PASS |
| `evidence/gitleaks-findings.json` = `37517e5f3dc66819`/3 | 不变 | `37517e5f3dc66819` / 3 B | PASS |
| `gitleaks.toml` 开工 = `641c19b6b16282db`/3329 | 本轮允许变（需申报新摘要与新字节数） | 开工件复算 = `641c19b6b16282db` / 3,329 B（`git show HEAD:…` 同值）；本轮 R5-1 改写后 = **`60e37e44e0429055` / 4,987 B** | PASS（申报新摘要） |

- 本骨架文件自身继承校验：5,271 B / 114 行（`len(splitlines())`，同一串用 `count('\n')+1` 得 115，正是被点名的虚高口径）/ 59 个「待填」/ §0–§12 共 13 节标题（含大标题与判决共 15 个 heading）⇒ 四项与任务书一致，未覆盖他人内容。
- 开工时会话可见 `HEAD`：骨架建立时为 `e4f0f3c`，本轮动工瞬间 `git rev-parse --short HEAD` = **`533c0dc`**（并发会话在期间提交，本卡不含其内容）。
- 工具版本：python `3.12.14`；gitleaks `8.30.1`（`.tools/t02/gitleaks/gitleaks.exe version`）。
- 冻结三件在本轮结束时再各复算一次，见 §11。

## §1 R5-1（P2，主项）词界把豁免换宽 → 两侧封闭定界类

- 计划：先跑复审 `evidence/r5-harness-probe.py <临时目录> attack` 复现 50 例标点邻接抑制；再改 `gitleaks.toml` 为左界 `(?:^|[\x60'"=:\s])` / 右界 `(?:$|[\x60'"\s;])`（第 11 条保留 `[^0-9a-f]` 再接右界）；同步改 `check_gitleaks_allowlists.py` 的 `unwrap()` 与标签逻辑；给 super 三例补 `-`/`.`/`=` 邻接。
- 实测退出码：复审 harness 两次实跑（改前件 / 改后件）都 **0**（它只出读数，不做判定）；交付门结构模式 **0 / 19 条**、`--with-controls` **0 / 223 条**（其中 R5-1 相关：11 条逐值标签 + 99 条超串控制 + 14 条 span 控制 + 68 条反向电池）。
- 「改前 50 例 → 改后 0 例」：同一套攻击件、同一台机、同一份 gitleaks 8.30.1。改前 `suppressedPunctuation = 50`（另 1 例是 harness 自己造的 `api_key="…"` 邻例，我按对象写明 51，不混进 50）；改后 **`suppressedPunctuation = 0`**，且 89 例仍被报出。逐例读数存 `evidence/r06-anchor-battery-before.json`（`0f7296a2ce7ca01a` / 20,322 B）与 `evidence/r06-anchor-battery-after.json`（`ae63c17b854b2ea0` / 20,212 B）。
- 11/11 与超串复报：**11 条精确值仍然被抑制**（`unchanged value is still suppressed` 11/11 PASS）；**99/99 超串全部复报**（9 个邻接形状 × 11 值：字母数字前/后/嵌入、`_` 后缀、`-` 前缀、`-` 后缀、`.` 后缀、`=` 后缀、两侧都带 `-` 的中间态）；44/44 单字符变异仍复报。
- 同步改动（复审点名的陷阱）：`check_gitleaks_allowlists.py` 的 `unwrap()` 原来要求两侧是 `\b`，我改成要求**新的封闭定界类**，并把拒绝原因写成 `unanchored` / `truncated` / `literal` 三类；标签措辞同步为「以两侧封闭定界类锚定、无通配」。因此**退回 `\b` 会让标签直接变红**，而不是「只有旧写法红、新写法也不报」。这条反向半边在交付门内部（不只是 harness）实测：`pre-change-synced` 变体把 `LEFT`/`RIGHT` 同步改成 `\\b` 让 10/11 条标签保持绿，仍有 **50 条行为红**，形状正是 `-`/`.`/`=` 邻接（见 §10）。
- span 边界（裁定 2）：**没有为了让 0 例成立而放宽豁免**。第 11 条残例的 `[^0-9a-f]` 半开区间是既有的、已申报的写法，本轮保持原样（只把它的右界接进封闭类），并用 14 条 `span control` 把它变成可失败断言：实测「延续 Match span」的字符是 `-` `.` `=` `_` `/` `+` 与字母数字，「终止」的是 `;` `"` `'` `` ` `` 空白 `:` `,`。若哪天某个命中把 span 延伸到尾串（吞进更长 token），这 14 条里对应的一条**会红**。逐字符读数存 `evidence/r06-match-span-adjacency.json`（`73bc61c19c842065` / 3,703 B）。
- 良性半边：`wide-right-synced` 变体把右界放宽到允许 `-`（同步放宽门的常量，标签 11/11 仍绿）→ **退出 1、只剩 10 条行为红**，证明新控制不是配合新写法的摆设；同时交付配置下 4 条良性控制全绿（现场生成的 274 条指纹清单在不加任何 allowlist 时 0 命中）。
- 未证明：RE2 定界类是**我按实测字符集选的形状**，不是从 gitleaks 文档推出来的完备划分；`:` `,` `` ` `` 三个字符实测不产生命中，其 span 语义是推论而非观测（见 §12 第 4 条）。


## §2 R5-2（P2）第三个门：规则自带 `'''.+EXAMPLE$'''` 豁免

- 判据改写：撤「**当且仅当** base32 AND 熵」的两条合取，改成**三道门全过**（① 字母表 `A-Z2-7`；② `entropy = 3`，计量对象为整条 20 字符匹配串；③ 不落入规则自带 `[[rules.allowlists]]` `'''.+EXAMPLE$'''`）。落点三处：`T02-Revision-R02.md:165`（本条旧文的合取式，就地重写并写明「少写第三道门 ⇒ **高估检出率**」这一偏差方向）、`T02.md:70`（覆盖边界第 4 条）、`T02-Revision-R05.md` §0 顶部更正块与 §J-2 汇总行。
- 实测退出码：TEMP 探针 `aws_doors.py` → **0**；证据件 `evidence/r06-aws-three-doors.json`（`c9f8d8b940331f43` / 3,057 B，7 例逐条含 `defaultsFindings`/`deliveredFindings`）。交付门 `--with-controls` 中 `AWS-shape control` 3 条断言 **PASS**（见 §10 第 4 行）。
- 反向控制（第三道门独立存在，不是别的门在拦）：`AKIA`+`IOSFODNN7EXAMPLE` 字母表合法、后缀熵 3.6250、整串熵 3.6842（①② 全过）→ **0 命中**；**只把末位 `E` 改成 `F`**（①② 的读数一字不变）→ **1 命中**。同时 defaults-only 与交付配置两份读数完全相同（`deliveredFindings == defaultsFindings`，7 例全部如此）⇒ 该抑制来自上游规则自带豁免，与本轮 11 条按值例外无关。
- 良性半边：三道门之外规则照旧工作——活体 canary（`AKIA`+`ABCDEFGHIJKLMNOP`，整串熵 3.8842）在三份副本各命中 1 条，`aws-access-token` 总数恰为 **3**；整树 `scan_secrets.py` 仍退出 0（未新增任何豁免，见 §1 申报的新摘要）。
- 未证明：未读 gitleaks 上游源码确认 `EXAMPLE$` 的匹配对象是 Match 还是 Secret（本轮为行为实测）；`ASIA/ABIA/ACCA/A3T` 前缀簇未单独取数；Linux runner 未复现。

## §3 R5-3（P3）熵的单位与计量对象

- 写法：所有「约 3.0」补齐「**阈值精确 3.0 + 计量对象 = 整条 20 字符匹配串（含 `AKIA` 前缀）**」。落点 `T02-Revision-R05.md` §0 更正块与 :18/:20/:141、`T02-Revision-R02.md:165`、`T02.md` 覆盖边界第 4 条。
- 实测退出码：同上探针脚本 **0**；翻转对在证据件 `evidence/r06-aws-three-doors.json` 的 `flip-*` 两行。
- 反向控制（后缀口径本身会被同一组数据否证）：k=7 那条按**后缀**熵是 **2.7806 < 3.0**，若判据是「后缀熵 ≥ 3.0」它应当**不被抓**，实测**被抓**（1 命中）⇒ 「后缀口径 + 阈值 3.0」这个组合被同一条数据直接否证；k=6 整串 2.8282 < 3.0 实测**不被抓**、k=7 整串 3.0037 ≥ 3.0 实测**被抓** ⇒ 唯一同时解释两个翻转点的计量对象是整条匹配串。故复审给的 (2.561, 2.781] 与整串口径**不矛盾**，是同一数据的另一种单位读数，报告里两种都写出并标明谁是判据。
- 良性半边：`entropy = 3` 无环视、RE2 侧不可表达为「按后缀算熵」，本轮**没有**为绕开它改任何规则或配置（配置改动只在 §1 的例外定界类）。
- 未证明：熵的精确定义（是否以 8·log 计、是否含重复字符归一）未取源码核对；我只证到「阈值 3.0 精确、作用在整串」这一行为层面。

## §4 R5-4（P3）`T02-Revision-R05.md:19` 字符类写错

- 就地修订：原句「规则 `aws-access-token`（`AKIA[A-Z0-9]{16}` 形态 + `entropy` 门，RE2 引擎）」改为默认规则实际形态 `(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16}`，并写明 `0/1/8/9` 与 8、9 之外的字母**根本不在字符类里**——「字母表门」来自字符类本身，不是引擎另加的检查。同处保留 R05 原实测数据不动（只改错抄的形态），并在 §0 顶部更正块里点名「:19 原文抄错」。
- 实测退出码：文字修订无门可跑；用两条读数背书——① `AKIA`+`ABCDEFGH1IJKLMNO`（第 8 位为 `1`，整串熵 3.8842）实测 **0 命中**，与 `[A-Z2-7]` 一致、与旧的 `[A-Z0-9]` 写法矛盾（按旧写法它应当被抓）；② 全树 `secret_scan.py` / `scan_secrets.py` 在本文件改动后仍退出 **0**（见 §10）。
- 反向控制：若字符类真是 `[A-Z0-9]{16}`，则含 `1` 的样本会被抓——实测不抓 ⇒ 旧写法被否证。
- 良性半边：R05 本节其余结论（双门数据的两组熵区间重叠）不变，仅形态串与判据条数更正。
- 未证明：未从 gitleaks 二进制的规则清单导出正则（本轮正则来自实测行为 + 上游配置常识），Linux 侧未复现。

## §5 R5-5（P3）canary 补「合法 base32 + 低熵」近例

- 实施：`canary_block()` 由 4 条增至 **5 条**植入行——活体 `AKIA`+`ABCDEFGHIJKLMNOP`、字母表越界（第 8 位 `1`）、**新增合法 base32 低熵 `AKIA`+`ABCDABCDABCDABCD`（后缀熵 2.0 / 整串 2.3464）**、github-pat、private-key；配套 3 条断言：活体必抓、`aws-access-token` 命中恰为 3 且全为活体 id、低熵合法 base32 **不被抓（特性，不是缺陷）**。
- 实测退出码：`--with-controls` → **0**（§10 第 4 行）；三条 AWS-shape 断言全 PASS，独立 TEMP 探针同读数（`evidence/r06-aws-three-doors.json` 的 `door2-legal-base32-low-entropy` = 0 命中）。
- 反向控制：这条近例**必须不被抓**——若哪天熵门被放宽（或规则换了阈值），它会变红并指出是「规则侧变了」，而不是让「低熵合法 base32 被漏」重新变成一句没人查的口头话；同理它也和 §2 的 EXAMPLE 例一起把 Triangle 补成三角（活体抓 / 字母表越界不抓 / 合法低熵不抓 / EXAMPLE 结尾不抓）。
- 良性半边：新增这条**没有**改变「九条 canary 即全部命中」的断言（`extra []`，`aws-access-token` 仍是 3 条，每份副本 1 条活体）——低熵样本不产生命中，故无需新增任何豁免，也无需改那条「九条即全部」的措辞。
- 未证明：低熵样本的熵数是我按 shannon 口径自算（含重复字符归一），与 gitleaks 内部实现是否逐位一致未经源码核对。

## §6 R5-6（P2/P3）`T02-Revision-R02.md:163` 旧退出码未就地标注

- 就地标注：`:163` 原话一字不动，紧随其后加 `:164` 引用块，写明「写就时成立、现已不成立；第三轮 `EXEMPT_VALUES` 之后实测退出 **0**；R06 本轮再实测 `secret_scan.py` 退出 **0**、`--self-test` 退出 **0**」。
- 全文清扫（同类残留）：对 `docs/execution/reports/T02*.md` 用模式 `仍退出|现在退出|当前退出|退出码仍|必然失败|都会退出 1` 复扫，命中 7 处，逐条判读：`T02.md:30`（第五轮已就地注，含「当前退出 0」事实）、`T02.md:63`（「`check_contracts.py` 仍退出 0」为真，本轮实测仍 0 / 27 哈希）、`T02-Revision-R05.md:106`（注本身）、`T02-Revision-R05.md:179`（全树复扫仍退出 0，本轮复算成立）、`T02-Revision-R02.md:163/:164`（本条）、`T02-Revision-R02.md:166`（「T07 下游期望必然失败」——**该期望在 T07 域内、本卡不改也不复测**，列入 §12 需主 agent 代跑/裁决）。⇒ 未发现第二条「陈述为真但读数已失效」的退出码残留。
- 实测退出码：`secret_scan.py` **0**、`secret_scan.py --self-test` **0**（10 fixtures + 1 exemption）；`scan_secrets.py` 全树 **0**（43.46 MB、报告体 `[]`）。
- 反向控制（标注里最容易糊过去的一处）：本轮我自己的第一次 `secret_scan.py` 实跑是**退出 1**，命中就在我要写进 `T02-Revision-R05.md` §0 的连排 AKIA 形状（`AKIA` 后接 4 组 `ABCD` 拼成的 20 字符串）上。按「显示层脱敏、不得为此新增豁免」的规矩，我把文档里的 AKIA 形状改为 `AKIA`+16 位**分写**后复跑 → 退出 **0**；`EXEMPT_VALUES` 本轮未增条目（仍 1 条）。这条现场证明：「退出 0」不是抄来的，是被门逼出来的。**同一个坑本卡又踩了一次**：§6 叙述第一次命中时，我把那个形状连排写在了叙述里（`which_pattern.py` 定位到本卡正文一处），于是这条记录本身在收尾复跑时又让 `secret_scan.py` 变红一次——同样按拆写脱敏修掉，未加豁免。⇒ 「AKIA 形状一律拆写」必须是默认写法，而不是每次靠复扫补救；这也是本轮唯一一处「我自己写的正文被我自己交付的门抓住」发生了**两次**的条目。
- 良性半边：`--self-test` 仍断言近邻形状被抓（脱敏没有把模式串改宽）。
- 未证明：T07 域那条下游期望的现状（不属于我的可读写路径）。

## §7 R5-7（P3）`STATE.json:937` —— 由主 agent 自改

- 实施：**本轮未触碰** `docs/execution/STATE.json`（任务书明令禁写，且 R5-7 归主 agent）。全程只用读命令读工作树状态，未读写该文件任何一行。
- 自证：本轮 `git status --porcelain` 中 T02 相关只有 `M tests/engineering/T02/gitleaks.toml`、`M tests/engineering/T02/check_gitleaks_allowlists.py`、`?? docs/execution/reports/T02-Revision-R06.md` 与本节提到的新证据件；`STATE.json` 不在改动集内（并发会话的 T03/T08 条目不属于我，也未被我修改）。
- 其余四项（实测退出码 / 反向控制 / 良性半边 / 未证明）：不适用。

## §8 §3 结构弱点（P3）：断言总数未钉死 + `>= 40` 容忍带

- 断言总数守卫：新增 `count_guard()`，**两种模式各钉一条恰好值**——结构模式 **19**（5 配置形状 + 11 逐值标签 + 2 配对门 + 1 守卫自身），controls 模式最终为 **223**（并发 scratch 守卫加入前为 222）。判据是 `EMITTED + 1 == EXPECTED`（`check()` 自计数），**双向**收紧：条数变少（被静默剔除）与变多（灌水凑数）都红。
- **现场：这条守卫两次抓到我自己**（不是写完就绿）。失败输出原样保留为证据件 `evidence/r06-assertion-count-pin.txt`：
  - run 1：钉 195 / 实测 197 → 全跑只有这一条 FAIL，**退出 1**；
  - run 3：加完 14 条 span 控制仍钉 197 / 实测 211 → 又是只有这一条 FAIL，**退出 1**；
  - run 2 / run 4 / run 5 把钉值改成实测后分别 **197、211、222 条全绿、退出 0**；run 5（加第 9 个形状 `mdash` 后）的 222 是**按类别算出来后一次验证通过**——守卫不报错，说明预测与实测吻合。
- 新旧真实对比：**139（R05）→ 222（R06）**，构成 = **+66 邻接超串控制**（6 个新形状 × 11 值：`_` 后缀、`-` 前缀、`-` 后缀、`.` 后缀、`=` 后缀、两侧都带 `-` 的中间态）+**2 AWS 熵角控制** +**14 span 控制** +**1 总数守卫**；**未删任何一条既有断言**（11 逐值标签、44 单字符变异、R05 的 33 条字母数字超串、正/盲点/良性各条全部保留，只是标签措辞随 R5-1 换成定界类口径）。台账另存 `evidence/r06-assertion-count-ledger.json`。
- controls 222 条的逐类别分解（与门内注释同源，139+83=222）：18 结构行 + 1 scanner + 10 正向 + 3 AWS-shape + 3 盲点 + 68 反向电池（1 非空转 + 11 逐值存活 + 44 单字符变异 + 1 电池规模 + 11 精确值仍抑制）+ **99 超串控制（9 形状 × 11 值）** + 14 span + 4 良性 + 1 scratch + 1 守卫 = **222**，且 **0 条 NOTE（无空转探针）**。
- `>= 40` 收紧：变异电池断言改为 `mutation_total == MUTATION_BATTERY`（常量 **44**），并把逐值那条从「`>= 2` 个变异仍活」改为「**该值的全部 4 个变异位都仍活**」（11 条逐值 + 1 条电池规模）。空转探针不再静默扣数：仍打 `NOTE` 并从逐条断言里剔除，但**剔除会让总数掉下来**，从而被上一条守卫抓住。
- 反向控制（把总数改掉必须红）：变体 `tamper-pin`（只把钉值 222 改成 221）→ **退出 1，且唯一那条 FAIL 就是 `assertion count: controls mode emits exactly 221 assertions`**（现场在 `evidence/r06-assertion-count-pin.txt` 与 `evidence/r06-red-control-variants-final.json`）。⇒ 守卫不是装饰。
- 良性半边：同一批红控里两个未同步变体（`wide-right`/`wide-left`，把定界类改宽而门不改）各出 39 条 FAIL / 退出 1，**逐值标签 11 条全部变红**⇒ 计数守卫与宽度守卫互不遮蔽；两个**同步**变体（把门的 `LEFT`/`RIGHT` 一起放宽，标签因此保持绿）只剩行为半边红，见 §1 裁定 3 条。
- 未证明：钉值绑定「默认规则对这些探针都会命中」这一前提；若上游规则改动使某类探针变 void，总数会掉下来、门会红（这正是设计意图），但届时要人工判断是「规则变弱」还是「探针该换」。
- **本轮红控顺手抓出的第二个结构缺陷（并发互踩，已修并当场回归）**：门的 controls 模式把探针树固定写在 `.work/allowlist-controls`，起手就 `rmtree`。同一份工作树里**同时**跑两个实例（今天真实发生：我这边并发跑红控变体与矩阵，本仓另有 T03/T08 会话在跑）时，后起的那个把前一个的探针文件在半途删掉，受害者报出「默认规则不命中 ⇒ 空转探针 ⇒ 逐值存活断言红」——**矩阵因此假红过两轮**（第一轮我误判成配置/熵问题）。
  - 修法：`scratch = WORK / ('allowlist-controls-%d' % os.getpid())`，并加**一条断言把这个性质钉住**（`scratch is process-scoped, so a concurrent run cannot delete this run's probes`）⇒ 退回固定路径就会红。电池由 222 长为 **223**。
  - 回归实测：同一时刻并发起两条完整 controls 跑，两条都 **退出 0、223 PASS / 0 FAIL / 0 NOTE**，各自 scratch 目录名不同、跑完各自删净（读数在 `evidence/r06-assertion-count-pin.txt` 末段与 `evidence/r06-assertion-count-ledger.json` 的 `concurrencyDefect` 块）。
  - 代价如实写明：崩溃的跑会把自己的 `.work/allowlist-controls-<pid>` 留在 gitignored 树里；**不做前缀清扫**，因为清扫等于把竞态重新打开（留一个空目录比互踩便宜）。
  - 未证明：这条回归只覆盖「两个实例」；没做 N 实例压力测试，也没测同一台机器上不同用户对同一工作树的并发（权限差异未验）。
  - **同一缺陷的第二例，这次是我的错**：修好门之后，我把两条 close-out 脚本并发跑了一次，第二条报 **203 PASS / 17 FAIL / 1 NOTE**（值 10 的逐位存活、电池规模等）。查因不是门又坏了，而是**我的收尾脚本新加了一行 `.work/allowlist-controls-*` 通配清扫**——它把正在跑的那条实例的探针目录整个删了。⇒ 修法不是把通配改精确，而是**任何外部清扫都不许碰这个前缀**：门自己只删自己的 `<pid>` 目录；本轮的残目录留到最后一次实例结束之后单独手工删净（读数见 §11）。这条也解释了今天前两轮矩阵假红的真因。

## §9 A-9 配对门范围裁定

- 边界（用户已裁定，本轮不再辩论，只把边界写清并落进 `T02.md:61`）：`digest_records.violations()` 的「关键词与 32+ 位十六进制不得同行」判据**只约束经 `digest_records` 新写入的那一刻**（`dumps()`/`check()` 在序列化后自检并抛 `AssertionError`）；**不加全树配对扫描**，也不把该判据升级成 CI 门禁。
- 两个数（本轮 R06 用**门自己的判据**实测，脚本走 `git ls-files --cached --others --exclude-standard`，只读）：
  1. **`tests/engineering/T02/evidence/*.json` 今天 8 个文件会红**：`integration.json:13`、`r01-compose-final.json:9`、`r01-compose-fixed.json:9`、`r01-docker-availability.json:9`、`r01-empty-integration.json:13`、`r01-entrypoint-final.json:10`、**`r01-integrity.json:67,110,111,115,124,125`（冻结件，含复审点名的 :110/:111）**、`r01-upgrade-integration.json:13`。名单与复审 §11(C) 给的 8 个一致。
  2. 全仓口径：git 可见 JSON **733** 个里 **168** 个存在同行配对；只看 `*/evidence/` 目录 = **533 个里 142 个**（`docs/execution/reviews/**` 59 个属复审方只读区、`tests/fixtures/**` 3 个是冻结契约件）。复审 §11(C) 当时报的是「511 个证据 JSON 里 132 个」，与我今日 533/142 的差值是并发会话在期间新增证据所致，同一判据、不同快照。
- 结论（写进 `T02.md` 的原话）：把该判据做成全树扫描 ⇒ 门禁**今天就恒红**（168/733），而恒红的门等于没有门；历史证据不改写，旧文件只在被重新生成时自然迁移到分行记录格式。
- 实测退出码：A-9 读数脚本只读、不产出门禁；门的配对半边由 controls 模式的两条断言钉（`pairing gate: digest_records refuses a path+digest written on one line` / `... a correctly split record is accepted (guard is not over-eager)`），本轮 **2/2 PASS**（含在最终 223 里）。
- 反向控制：第二条断言是「不过度饥饿」半边——把 `path` 与 `sha256` 拆行的正确记录必须**被接受**；若哪天有人把守卫改成「任何含 32+ 位十六进制的文件都拒」，第二条会红。
- 良性半边：`benign control` 4 条 PASS——`revision_integrity.py` 现场生成的清单（本轮实测 274 条交付指纹）在**完全不加 allowlist** 下仍 0 命中、`digest_records` 无同行配对。
- 未证明：168/733 的配对里有多少是真凭据形态、多少是文档摘要——未逐条判读（本轮也不改它们）；把该判据用于**新**证据时的 CI 侧强制（现在只在门的 2 条断言里，不在 workflow）。

## §10 必跑矩阵（逐条真实退出码）

`$py` = `C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`，工作目录 = 仓库根；每条命令后立刻取 `$LASTEXITCODE`（外层 pwsh 退出 0 不代表内层成功，本轮全部按内层读数记账）。

| # | 命令 | 期望 | 实测退出码 | 输出要点（真实读数） |
|---|---|---|---|---|
| 1 | `$py tests/engineering/T02/secret_scan.py --self-test` | 0 | **0** | `secret_scan self-test: 10 fixtures and 1 exemptions agree` |
| 2 | `$py tests/engineering/T02/secret_scan.py` | 0 | **0** | `Secret pattern scan: no matches`。本轮它**真实变红过两次，两次都是我自己的文档**：第一次命中在写进 `T02-Revision-R05.md` §0 的连排 AKIA 形状，第二次命中在本卡 §6 叙述第一次的那一行里（我把同一个形状又连排写了一遍）。两次都按「显示层脱敏」拆写成 `AKIA`+16 位形式修掉，**未新增豁免**（详见 §6） |
| 3 | `$py tests/engineering/T02/check_gitleaks_allowlists.py` | 0 | **0** | `GITLEAKS ALLOWLIST POLICY: PASSED (structure only)`，**19/19** 断言（5 配置形状 + 11 逐值标签 + 2 配对门 + 1 总数守卫） |
| 4 | `$py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe` | 0 | **0** | `PASSED`，**223/223** 断言、0 NOTE（无空转探针）；对比 R05 的 **139** 条 = +66 邻接超串控制（6 个新形状 × 11 值）+2 熵角 +14 span +1 进程隔离 +1 守卫，未删断言 |
| 5 | `$py tests/engineering/T02/check_contracts.py` | 0 | **0** | `Approved T00 rc.3: 27 hashes verified, no regeneration`（27 个冻结契约哈希一致） |
| 6 | `$py tests/engineering/T02/digest_records.py` | 0 | **0** | 无输出——该模块**没有 `__main__` 自检入口**，运行它只证明可导入；配对判据的真实半边在第 3/4 行的 2 条 `pairing gate` 断言里（此点如实标注，不当成已通过） |
| 7 | `$py tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe --report <TEMP>\r06diag\tree-report.json` | 0 | **0** | `no leaks found`，`scanned ~43,459,684 bytes (43.46 MB)`，报告体 `[]` 写在 TEMP，未覆写仓库内 `evidence/gitleaks-findings.json`（哈希仍 `37517e5f3dc66819`/3） |

上表七行来自**单独串行那一次**收尾实跑（所有文档与证据落盘之后），由 Python 驱动逐条取子进程退出码（不用 PS 的 `*>`，它写 UTF-16；也不用 `Out-File -Encoding utf8`，它加 BOM——本轮被这两个坑各吃掉一个读数）：`1=0 2=0 3=0(19/19 PASS) 4=0(223/223 PASS、0 NOTE) 5=0 6=0 7=0`。判决与 §11 微调之后又复跑了第 1、2、3 行，仍为 **0**。**必须串行**这一点不是洁癖：并发跑那一次第二条实例报了 203 PASS / 17 FAIL / 1 NOTE，真因是我自己的收尾脚本加了 `.work/allowlist-controls-*` 通配清扫，把正在跑的兄弟实例的探针目录删了——与刚修完的互踩同形，处置与教训写在 §8 末条。

红控批次（预期变红，逐条真实退出码；副本都在 gitignored `.work/r06-repro-final/`，读数存 `evidence/r06-red-control-variants-final.json`，首轮 8 变体存 `evidence/r06-red-control-variants.json`）：

**历史最终红控批（9 形状 / 钉值 222；此后进程隔离守卫使交付门变为 223）**

| 变体 | 改了什么 | 退出码 | PASS/FAIL | 红点 |
|---|---|---|---|---|
| `pre-change-synced` | 把 `LEFT`/`RIGHT` 两个常量换成 `\\b`、配置退回改前那份 ⇒ **11 条标签里 10 条仍绿**、探针取的是真值 | **1** | 150 / **58** | **50 条超串控制红**，形状恰为 `pdash`/`sdash`/`sdot`/`seq`/`mdash` 各 10 条；另 3 条反向控制 + 3 条 span + 1 条标签（第 11 条截断形态）+ 1 条总数守卫 |
| `wide-right-synced` | 只把右界放宽到允许 `-`，并把门的 `RIGHT` 常量同步放宽 ⇒ **11 条标签全绿** | **1** | 212 / **10** | 10 条全是 `substring control: super-string sdash for value 00…09` ⇒ **纯行为**抓到「`-` 后缀被吞」 |
| `tamper-pin` | 只把钉值 222 改成 221 | **1** | 221 / **1** | **唯一红就是断言总数守卫** ⇒ 守卫不空转，也不是靠删断言凑出来的 |

**首轮批（8 形状期，读数以 `evidence/r06-red-control-variants.json` 为准）**：`pre-change` 170/28、`wide-right` 29/39、`wide-left` 29/39、`unanchor-one` 33/1（这一跑暴露了 GBK 崩溃）、`substring-synced`（设计缺陷：`LEFT`/`RIGHT` 清零后探针取值退化成空串，只跑 36 行，**不能当证据用**，已弃）、`wide-right-synced` 201/10、`wide-left-synced` 200/11（这两条当时已在 8 形状电池上证明「同步放宽 ⇒ 只剩行为红」，最终批用 9 形状重跑了右界那条）。

- 裁定 3 要的反向半边成立，而且是**两半都成立**：① 「退回旧写法 ⇒ 门红」不只是标签红——把标签半边人为按住（10/11 条仍绿）后，`pre-change-synced` 仍有 **50 条行为红**，形状正是 `-`/`.`/`=` 邻接；② 「把新定界类改宽 ⇒ 门红」同理（`wide-right-synced` 标签全绿、10 条行为红）。⇒ 新加的标点邻接控制是**承重**的，不是配合新写法摆设。
- 顺带抓出并修掉一个真缺陷：`check()` 打印 gitleaks 日志里的 `µs` 时，GBK 控制台抛 `UnicodeEncodeError` 把整门打断（首轮 `unanchor-one`/`substring-synced` 两跑都因此没跑完）。修法是在模块载入时把 stdout/stderr `reconfigure(encoding='utf-8', errors='backslashreplace')`，已计入交付脚本——这条也是「红控不只是表演」的实证：它抓到了作者自己的工具。


## §11 清理与自证

- **字节保真自证（未 `git add` 也能证）**：本会话被禁止 `git add`，而未入库的文件在索引里没有条目，`git show :<path>` 直接失败——所以用等价的 `git hash-object --path <rel> <file>`：它按 `.gitattributes` 施加与将来 `git add` **完全相同**的转换，把得到的 blob id 与磁盘字节的 SHA-1 逐件比对。**17 件**（5 件 T02 脚本 + `gitleaks.toml` + 4 份报告 + 8 件 r06 证据，其中 3 件脚本本轮未改也一并核）**全部一致**，`would-rewrite: none`，无 CRLF、无 BOM ⇒ 入库不会被改写。留给你在 `git add` 后代跑的等价校验见 §12。
- 属性实测：evidence 目录 = `text: unset`（即 `-text`，不转换）；`gitleaks.toml`/脚本/`T02.md` = `text: set, eol: lf`（磁盘已是 LF，故转换是恒等）；其余 `T02-Revision-*.md` = `text: unset`。
- **本卡收尾自证**：交付时 **224 行**（`len(splitlines())`；同一串用 `count('\n')+1` 会得 225，正是被点名的虚高口径，本轮不用它）；正文直角引号 **60** 处；**代码围栏与行内码之外 ASCII 双引号 0 处**（`quote_check.py` 逐行核，含 `"` 的 16 行全在代码/表格单元里）。字节数与占位字样残余数**只写在交付消息里**——写进本卡会让这两个读数自我矛盾：填数的那一次写盘本身就改变它们。其余三份报告无未填内容；本卡里「待填」这三个字只出现在**对自身骨架计数的引用**中，没有一处是未填的占位。
- **临时根清理（实测读数）**：以下 7 处收尾全部 `exists=False` —— `tests/engineering/T02/.work/r06-repro`、`.work/r06-repro-final`、`.work/allowlist-controls`、`%TEMP%\r06probe`、`%TEMP%\r06probe-before`、`%TEMP%\r06probe-after`、`%TEMP%\r06-prechange`（同一脚本还顺手确认门自己的 `scratch tree deleted before exit` 断言在每次跑里成立）。留到交付后才删的只有 `%TEMP%\r06diag`（本卡 §10 收尾脚本与其日志），删除后 `Test-Path` 亦为 False，读数在本轮交付消息里。
- **新增证据 8 件（只新增，未覆写任何既有件）**，磁盘 sha256[:16] / 字节：
  | 文件 | sha256[:16] | 字节 | 内容 |
  |---|---|---|---|
  | `evidence/r06-anchor-battery-before.json` | `0f7296a2ce7ca01a` | 20,322 | 改前攻击集逐例读数（标点抑制 51 例，含 50 例复审口径） |
  | `evidence/r06-anchor-battery-after.json` | `ae63c17b854b2ea0` | 20,212 | 改后同一攻击集（标点抑制 **0** 例、reported 89） |
  | `evidence/r06-aws-three-doors.json` | `c9f8d8b940331f43` | 3,057 | 三门独立实测 + 熵两口径翻转对 |
  | `evidence/r06-match-span-adjacency.json` | `73bc61c19c842065` | 3,703 | 逐拼接符 span 延续/终止实测表（裁定 2 的边界证据） |
  | `evidence/r06-assertion-count-ledger.json` | `399a7cc21de4fa9d` | 4,267 | 139→197→211→222→223 台账、逐类别构成、5 次改钉历史 |
  | `evidence/r06-assertion-count-pin.txt` | `c4795f754d2708ea` | 3,550 | **守卫抓到作者的现场**（195/197 与 197/211 两次 FAIL 逐字原文 + 197/211/222 三次绿跑原文） |
  | `evidence/r06-red-control-variants.json` | `d6b0b0dfc616529b` | 4,809 | 首轮 8 变体逐组红点 + 顺带抓出的 GBK 崩溃缺陷（两个变体因该缺陷没跑完，原样保留） |
  | `evidence/r06-red-control-variants-final.json` | `e93a9752cad09b93` | 3,620 | 最终批 3 变体（`pre-change-synced` 50 条行为红 / `wide-right-synced` 10 条 / `tamper-pin` 唯一红是守卫），值前缀一律掩到 4 位 |
  - 前两件是我本轮早期写的，写完后电池又长了一次（超串形状 8→9），当时尚未交付、也尚未被任何复审读过，所以**按完整历史重发**而不是留一份数字过时的件；其余既有证据件一律未动。
  - 脱敏：证据件里**没有任何 token 文本、没有 Match 原文、没有豁免值**（`mask_evidence.py` 只留探针名/计数/熵值；`r06-aws-three-doors.json` 只留长度与熵）。新增后全树扫描仍退出 0（§10 第 7 行），未为此新增任何豁免。
- **冻结三件本轮结束复算**（与 §0 开工读数一致）：`evidence/r01-integrity.json` = `1d18eef28322218a` / 14,783 B；`evidence/r01-integrity-run.json` = `18be0c34fbc16ad1` / 409 B；`evidence/gitleaks-findings.json` = `37517e5f3dc66819` / 3 B。
- **临时根清理**：TEMP 下 `%TEMP%\r06probe`、`%TEMP%\r06probe-before`、`%TEMP%\r06probe-after`、`%TEMP%\r06-prechange`、`%TEMP%\r06diag` 与仓库内 gitignored `.work\r06-repro`、`.work\r06-repro-final`、`.work\allowlist-controls`（门自己的 scratch）在收尾时删除，`Test-Path` 逐一为 **False**（读数见本轮交付消息；门自己的 `scratch tree deleted before exit` 断言也在每次跑里钉这条）。矩阵必须**最后**跑，因为报告正文本身在被扫的树里——事实如此发生过：正文里一处连排 AKIA 形状让收尾复跑变红，按拆写脱敏修掉后才绿（§6）。
- **未使用**：`git add` / `git commit` / `mvn`；未写 `docs/execution/STATE.json`；未读写 `tests/engineering/{T03,T07,T08}/**`、`tests/engineering/integration/**`、`backend/**`、`.github/workflows/**`、`docs/execution/reviews/**`（只读跑过复审方的 `r5-harness-probe.py`，未改它一个字）；未批量 `--renormalize`；`.work/r06-repro-final/` 下的红控副本含豁免值全文，**只存在于 gitignored 目录、绝不入证据树**，收尾已删净。

## §12 仍未证明清单 / 需主 agent 代跑

**仍未证明（不粉饰）**

1. gitleaks 上游源码层面：`entropy` 的实现口径、`EXAMPLE$` 豁免匹配的是 Match 还是 Secret、`A3T/ASIA/ABIA/ACCA` 前缀簇的行为——本轮全部是**二进制行为实测**，未读源码、未测前缀簇。
2. Linux / GitHub Actions 侧：本机是 Windows + PowerShell 5.1 + gitleaks 8.30.1 exe；`.github/workflows/**` 属禁改路径，YAML 未动也未跑，**不能宣称 CI 通过**。
3. 复审 §11(D) 的 runner 侧尾款（需要 `/bin/bash`、pyyaml、Linux tarball）本机跑不了，未冒充跑过。
4. 第 11 条「散文截断」形态（`<16hex>...` + 单个非十六进制字符收口）仍按值豁免。裁定 2 要的「会变红」探针已交付且方向精确：`span control` 用默认规则实测——若某个拼接符把 Match span **延伸到尾串**（即豁免有机会吞掉更长 token），该条红；实测 14 条里「延续」的 7 个字符（`-` `.` `=` `_` `/` `+` 字母数字）全绿、「终止」的 7 个（`;` `"` `'` `` ` `` 空白 `:` `,`）也全绿。仍未证明的是：`:` `,` `` ` `` 这几个**实测不产生命中**（0 findings）的字符，其 span 语义是我从「无命中 ⇒ 无豁免可吞」推出来的，而不是直接观测到 span 在那里断开。
5. 豁免值本身的风险不变：按值豁免精确到值，同一值日后出现在真实凭据位置仍会被静默抑制（第四轮 C-5 已确证 1→0）；本轮未新增任何豁免来掩盖这点（`EXEMPT_VALUES` 仍 1 条，allowlist 仍 11 条）。
6. 红控副本的寿命：`.work/r06-repro-final/` 里的变体脚本随临时根删除而消失，重放需要按 §10 描述的三处补丁重建（`LEFT`/`RIGHT`/钉值）。红点读数本身已在两份 `r06-red-control-variants*.json` 里留档。

**需你代跑 / 代裁（给精确命令与期望值）**

1. 证据字节保真（我无权 `git add`）——把 **8 件**新证据加入索引后逐件比对：
   ```powershell
   cd E:\project\codex\wxAgent
   $py = 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
   $names = 'r06-anchor-battery-before.json','r06-anchor-battery-after.json','r06-aws-three-doors.json',
            'r06-match-span-adjacency.json','r06-assertion-count-ledger.json','r06-assertion-count-pin.txt',
            'r06-red-control-variants.json','r06-red-control-variants-final.json'
   foreach ($n in $names) {
     $rel = "tests/engineering/T02/evidence/$n"
     git add -- $rel
     $disk = (Get-FileHash -Algorithm SHA256 $rel).Hash.ToLower()
     $idx  = (git show ":$rel" | $py -c "import sys,hashlib;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())")
     "{0,-40} disk={1} index={2} {3}" -f $n, $disk.Substring(0,16), $idx.Substring(0,16), $(if ($disk -eq $idx) {'SAME'} else {'DIFF'})
   }
   ```
   期望：8 行全 `SAME`；`diff` 名单里**不应**出现 `r01-integrity.json`/`r01-integrity-run.json`/`gitleaks-findings.json`（它们 sha256 仍应分别是 `1d18eef28322218a`/`18be0c34fbc16ad1`/`37517e5f3dc66819`）。注意 `git show :<path>` 走管道时内容不受编码影响，但**不要**用 `Out-File` 落盘（PS 5.1 会加 BOM，本轮就是被这个坑过一次计数）。
2. 必跑矩阵复核（期望退出码全 0，第 4 行断言数应为 **223**，第 3 行 **19**）：
   ```powershell
   cd E:\project\codex\wxAgent
   $env:PYTHONDONTWRITEBYTECODE='1'
   $py = 'C:/Users/eie04/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
   & $py tests/engineering/T02/secret_scan.py --self-test; "1=$LASTEXITCODE"
   & $py tests/engineering/T02/secret_scan.py;               "2=$LASTEXITCODE"
   & $py tests/engineering/T02/check_gitleaks_allowlists.py; "3=$LASTEXITCODE"
   & $py tests/engineering/T02/check_gitleaks_allowlists.py --with-controls --gitleaks .tools/t02/gitleaks/gitleaks.exe
   "4=$LASTEXITCODE"
   & $py tests/engineering/T02/check_contracts.py;           "5=$LASTEXITCODE"
   & $py tests/engineering/T02/digest_records.py;            "6=$LASTEXITCODE"
   & $py tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe --report "$env:TEMP\r06-matrix-report.json"
   "7=$LASTEXITCODE"
   ```
3. 台账口径需要你的两处改数（我不动 `STATE.json`）：`machineGates` 里旧期望 **88→139** 应改为 **19（结构模式）/ 223（含控制）**；`gitleaks.toml` 的期望摘要应改为 **`60e37e44e0429055` / 4,987 B**（原 `641c19b6b16282db` / 3,329 B）。
4. 裁决项（我不擅自扩大范围）：`T02-Revision-R02.md:166` 的「T07 下游期望必然失败」属 T07 域文件（我禁改），现状未复测；`digest_records.py` 无 `__main__` 入口——若你希望矩阵第 6 行是「真自检」而非「可导入」，需要有人给它加自检（本轮加即越界，未做）。
