# T02 第三轮独立复审（R02 专项）

- 复审日期：2026-10-06（Asia/Hong_Kong）。对象：工作区当前字节，`git diff HEAD -- tests/engineering/T02/evidence` 为空（原件未动）。
- 工具：Gitleaks 8.30.1（`.tools/t02/gitleaks/gitleaks.exe version` 退出 0）；`check_contracts.py` 退出 0，27 哈希一致。
- 扫描包装器 [run_checks.py](run_checks.py) 只把 `scan_secrets.py` 的报告/work 路径改到本目录，扫描输入、配置、规则、退出码不变。
- 配置字节：`tests/engineering/T02/gitleaks.toml` sha256 `66e1fc1c…3ceed9`，例外 3 条。

## 判决：CHANGES_REQUIRED

**F-01 [P1] R02 未闭合：CI 等价全量扫描仍退出 1，命中 7 条。**
复现：`python docs/execution/reviews/T02-round3/run_checks.py` → `scanExit 1`，`gitleaks-findings.json` 7 条，全为 `generic-api-key`，全部落在**已跟踪**文件：
`docs/execution/reviews/T03-round5/evidence/checks.json:11,12,20`、`docs/execution/reviews/T07-round4/checks.json:91,93`、`tests/engineering/T03/evidence/session-cookie-r04.json:29,30`。
7 条值经重算核实为相应文件 SHA-256（`docs/api/openapi.yaml`=`e285471760a5dce4…`、`docs/api/diff-pages-v1.1.openapi.yaml`=`0db04ea086c2c563…`；L20 为叙述行含同一指纹的 16 位前缀）→ 属误报，但与 R02 同一根因、同一失败模式，已跨轮扩散到 3 个新文件。原 6 项 `r01-integrity.json` 命中已被例外抑制，故 R02 验收第 2 条"全部证据生成完毕后扫描退出 0"未满足。`docs/execution/reports/T02.md:94` 记录的退出 0 只对当时输入集成立。

**F-02 [P1] 例外实际是"整文件豁免"，不是主 agent 声称的"同文件路径且同完整示例值"。**
最小复现（[verify_r02.py](verify_r02.py)，全部在 gitignore 的 `.work/` 内做副本，未回写任何仓库配置）：把两条默认可检凭证（GitHub PAT、AWS secret 形态）写进 `tests/engineering/T02/evidence/r01-integrity.json` 同路径副本 → 交付配置 exit 0 / 0 命中 / gitleaks 自报 `scanned ~0 bytes (0)`（文件根本没被读）；删掉该 allowlist 块 → exit 1 / 2 命中 / 115 bytes；把 `regexes` 换成不可能命中的 `ZZZ_IMPOSSIBLE_VALUE_ZZZ` → 仍 exit 0 / 0 bytes。**值条件不起作用，只有路径条件生效。**
反向控制：把被豁免的 6 个指纹任一改一位（`…ec99`→`…ec90`）→ 同路径仍 0 命中（应报 1）；把同一清单挪到 `elsewhere/copied-manifest.json` → 立即报 6 条。三条 allowlist（SRS、T04 integration、T02 R02）行为完全一致 [evidence/verify.json](evidence/verify.json) `attribution.*_valueInert / *_shipped / *_minusBlock`。
后果：真实凭证若被提交进这 3 个文件（含 16.5 万字节、仍在演进的 SRS 规格文档）将被 CI 静默跳过。[T02.md:115](../../reports/T02.md#L115) 的"未豁免目录或真实密钥"与实测行为不符；R02 验收第 1 条的意图（范围精确）未达成。

**F-03 [P2] 根因未修，逐值例外不可持续。**
[revision_integrity.py:35](../../../tests/engineering/T02/revision_integrity.py#L35) 仍以"路径作键 + SHA-256 作值"同行输出。良性探针：键为中性路径的纯哈希清单 → 0 命中；仅把键换成含 `api` 的路径 → 1 命中。故触发条件是"关键词路径与高熵值同行"，与文件内容真伪无关 → 每份新指纹清单都要新增一条例外，已实际复发 3 次。整改提交为 `5413cf4`（且夹在 T03-T07 集成提交里，非独立可核对的 R02 修复）。

**F-04 [P2] 例外改动使 T07 交付门自身失效。**
[tests/engineering/T07/verify_delivery.py:52-53](../../../tests/engineering/T07/verify_delivery.py#L52-L53) 硬编码断言"命中恰 6 条且全在 `r01-integrity.json`"，当前为 7 条且全在其他文件 → 该脚本必记 `secret scan differs from known T02 six findings` 并非零退出（静态推导 + 本轮命中集）。R02 整改未同步这处跨任务期望。

**F-05 [P3] `scan_secrets.py` 把报告写进被跟踪的证据原件。**
[scan_secrets.py:29](../../../tests/engineering/T02/scan_secrets.py#L29) 固定输出 `tests/engineering/T02/evidence/gitleaks-findings.json`（`git ls-files` 命中）→ 按 CI 原样复跑即覆盖交付证据原件（该文件 mtime 16:42:03 晚于同批 15:00:00，说明已被覆盖过一次，当前内容 `[]` 与 HEAD 相同）。建议加 `--report` 参数，复审方一律内存改写输出路径。

**F-06 [P2] 同一 CI 步骤的第一条命令也已失败：`secret_scan.py` 退出 1。**
复现：`python tests/engineering/T02/secret_scan.py` → `Secret pattern scan: FAILED: backend/src/test/java/com/example/editorial/storage/S3ProtocolRegressionTest.java`（L16 为 AWS 文档示例键对，非真实凭证）。该命令是 [ci.yml:54](../../../.github/workflows/ci.yml#L54) 密钥步骤的第一条，先于 L55 的 Gitleaks → R02 验收第 2 条"完整密钥扫描退出 0"在两个命令上都不成立。T02 报告与第二轮记录中"简化密钥模式扫描 PASS 退出 0"（`evidence/secret-patterns-final.json`）只对当时的输入集成立。

## 正向与良性控制（本会话新协议）

- 正向控制**未全部被抓**：GitHub PAT、AWS secret 形态、64 位十六进制私钥形态、PEM 头 → 交付配置与**无配置默认规则**命中集完全相同（各 1 条）；单独一行 `AKIA[0-9A-Z]{16}`、`password=`/`DB_PASSWORD=` 明文 → 两种配置下均 0 命中。故漏报归因于 Gitleaks 8.30.1 规则覆盖，而非例外体系过宽；例外体系的过宽由 F-02 单独证明。
- 良性探针"合法文件不该红"已成立（中性路径哈希清单 0 命中）；"该红的必须红"在非豁免路径成立（`tests/engineering/T05/evidence/*` 新清单 1 命中）。全红/全绿本身不作为结论依据。
- 临时 scratch `docs/execution/reviews/T02-round3/scratch/` 已删除（`Test-Path` False）；`.work/` 控制副本随 `verify_r02.py` 结束清理。
- 复审自身产物也在扫描输入集内（`scan_secrets.py` 用 `git ls-files --others`）：初版证据文件因原文引用例外里的 UUID/哈希而多出 2 条命中，截断后基线回到 7；下一轮复审请把凭证形态写成运行时拼接或截断字面量。

## R02 是否闭合

**未闭合。** 依据：F-01 退出码 1 违反验收第 2 条；F-02/F-03 违反验收第 1 条（例外未做到范围精确，根因也未按建议改清单格式）；验收第 3 条的"报告绑定最终成功扫描"不可能成立，因为尚不存在退出 0 的全量扫描。另 F-04 显示整改破坏了下游期望。

## 附注（非 T02 议题）

1. 工作树卫生：`docs/execution/reviews/T04-round1..3` 合计 241,977,524 字节（其中 `.work/` 239,988,466）、`T07-round1..4` 合计 346,364,261 字节（`.work/` 342,629,882），含 `backend/target/` 整仓副本。全部被 `.gitignore:21 **/.work/` 忽略 → 属"已忽略但污染工作树"，未删除，仅报告。
2. CI 等价性：[.github/workflows/ci.yml:35-37](../../../.github/workflows/ci.yml#L35-L37) 固定 8.30.1 linux 包（sha256 `551f6fc8…`），L55 调 `scan_secrets.py --gitleaks .tools/t02/gitleaks`，配置由脚本 L32 硬编码 → 与本地同版本、同配置；仓库根无 `.gitleaks.toml`，不存在第二套配置漂移。差异仅在输入集来源：本轮 7 条命中文件均已跟踪，CI checkout 后同样命中。

## 未证明清单

- Gitleaks 8.30.1 中 `paths`+`regexes`/`condition=AND` 的求值粒度是否为上游有意设计：本机网络不可用（`web_search` 401、`web_fetch` 失败），本轮只给行为证据，未取上游文档/源码。
- 未在真实 GitHub Actions runner 上复跑；CI 结论为"同版本同配置 + 已跟踪命中文件"的静态推导。
- 未验证 T04/T06 是否也隐含同一"6 条"期望（只核到 T07）。mvn、前端构建、容器路径本轮未跑。

## 需主 agent 代跑

1. `python tests/engineering/T02/scan_secrets.py --gitleaks .tools/t02/gitleaks/gitleaks.exe`（会覆盖 F-05 所述原件，复跑前请先 `git show HEAD:...` 留存或加 `--report`）。
2. `python tests/engineering/T07/verify_delivery.py --evidence-name r03-gate-recheck`（验证 F-04）。
3. 有网环境取 Gitleaks 8.30.1 allowlist 语义文档，确认 F-02 是上游粒度还是配置写法问题。
4. 修复方向建议：改指纹输出为分行记录（`{"path":…,"sha256":…}`）后**删除**这 3 条按文件路径的例外；若保留，须在配置与报告中明写"按路径整文件豁免"，并为这 3 个文件加独立凭证形态哨兵检查。
