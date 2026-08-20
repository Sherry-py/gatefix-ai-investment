# GateFix · AI 投资治理方法（Xirui Lian Sherry 开发）

> **品牌归属：** 本方法由Xirui Lian Sherry 独立开发，知识产权归其所有；中美绿色基金采用本方法进行 AI 投资判断。本开源仓库为公开的"判定骨架"，评分阈值、估值锚算法与真实案例不在此仓库中。

[![CI](https://github.com/Sherry-py/gatefix-ai-investment/actions/workflows/ci.yml/badge.svg)](https://github.com/Sherry-py/gatefix-ai-investment/actions/workflows/ci.yml)

> **一句话定位：** 判断一个 AI 项目能不能投、值多少，靠的不是它讲得怎么样，是证据够不够格。这套标准把投前判断的纪律——治理证据（管得住）+ 落地证据（用得上）——固化成确定性、可审计、可复现的规则，让每一笔 AI 投资决策都有据可依、有迹可循。

```
$ python engine.py run --case=ai_investment

--- Commit: AI 项目投资决策（治理证据闸门） ---
  R=0.20 C=0.00 O=0.40 Ro=0.30 → Q=0.225  route=ESCALATE
  说明: 治理证据覆盖 0/6（缺备案/缺数据合规/缺安全/缺可控/缺隐私/缺跨境）；红线未通过
  → 升级给人：投资团队 → 投委会终审

--- Commit: 估值锁定（落地证据闸门） ---
  R=0.20 C=0.40 O=0.40 Ro=0.30 → Q=0.325  route=ESCALATE
  说明: 落地证据覆盖 2/5（✓部署/缺付费合同/✓产业嵌入/缺经济价值/缺复购）；落地等级≈L1
  → 升级给人：投资团队 → 投委会终审
```

同一套证据判定规则：治理证据不全 → 投资决策升级投委会终审；落地证据口径不清 → 估值升级投委会终审。它做的不是"项目好不好"的主观评价，而是"给定一组尽调材料，它够不够格支撑这笔不可逆的投资"的确定性判断——判断标准写死在规则里，不随人、不随情绪变。

## 这是什么

一个**确定性的 AI 项目投资决策闸门**——在"项目方主张它值多少"和"投委会真正投出去"之间，补一道**只看证据的判定层**。它把投委会看项目时的那条纪律——证据够不够格、合不合规、落不落地——固化成可复现的规则。

它回答投委会最关心的那个问题：一笔不可逆的资本要投进一个 AI 项目，凭什么往下走、什么时候该停？

1. 这个动作（投资）**能不能反悔**——资本一旦投入，能否撤回；
2. 证据够不够充分——**治理证据（管得住）+ 落地证据（用得上）**在 4D-CQ 四维上是否过阈值；
3. 就算放行了，还剩多少甩不掉的外部风险。

## 判断标准：两道闸门

### 第一道：治理闸门（管得住）——「这个项目会不会死」

6 项治理证据，红线 = 备案 + 数据合规：

| 维度 | 问什么 |
|---|---|
| 备案资质 | 算法/大模型备案号可公开查询 |
| 数据合规 | 训练数据来源合法且有授权 |
| 安全 | 安全认证 / 第三方检测 |
| 可控 | 远程介入率 / 故障率等可控性数据 |
| 隐私 | 数据采集隐私合规 |
| 跨境 | 跨境数据 / 技术合规 |

### 第二道：落地闸门（用得上）——「这个项目会不会活、值多少」

5 项落地证据，红线 = 部署 + 付费合同；覆盖度映射落地等级：

| 落地等级 | 覆盖度 | 含义 |
|---|---|---|
| L3 规模复购 | 5/5 | 部署+合同+产业嵌入+经济价值+复购 |
| L2 应用落地 | 3–4/5 | 有真实付费合同、嵌入产业、可量化经济价值 |
| L1 工程化 | 2/5 | 有生产部署，无付费复购 |
| L0 叙事 | 0–1/5 | 有模型/论文/demo，无生产部署 |

第三道（团队驾驭能力）是**人情类判断**，机器不组装、不拍板——直接 `BYPASS_TO_HUMAN` 给投委会。

## 4D-CQ 与四态路由

每个闸门对证据做 4D-CQ 打分（每个维度 ∈ [0,1]，加权求和得 Q）：

- **R（Relevance）**：证据是否针对这个项目、这个决策点（红线项缺失直接打低分）；
- **C（Coverage）**：是否覆盖所有必需维度；
- **O（Ordering）**：顺序对不对（先合规后运营、先交付后声称复购）；
- **Ro（Robustness）**：证据来源第三方核验 vs 自报。

四态路由（`tau_pass=0.85` / `tau_repair=0.50`）：

- **PASS** = Q ≥ 0.85，放行；
- **AUTO_REPAIR** = 0.50 ≤ Q < 0.85 且缺口可外部核查，补一次证据再判（内部收敛，不作为终态暴露）；
- **ESCALATE** = 证据缺口不可自动闭合，转人工终审；
- **BYPASS_TO_HUMAN** = 人情类证据，或评估器故障（fail-closed），强制转人工。

> **如实说明打分粒度**：当前这个 case 的打分是**离散**的——R/C/O/Ro 大多取二值（红线过 = 1.0 / 不过 = 0.2 这类），Q 只有少数离散取值，本质是一张"红线过没过 + 覆盖了几项"的规则表，不是连续质量谱。4D-CQ 是框架，支持未来把证据写成连续分；而投资决策里"有没有备案"这类证据本来就是二值，离散更贴业务。另外 `cost_reverse`/`value_tier` 在这个 case 不参与路由（投资天然不可逆，`is_commit` 恒真），它们只在汇总的成本量级里出现，第一次读代码不要误以为投资金额参与了判定。

## 怎么跑

```bash
pip install pyyaml   # 唯一核心依赖
python engine.py run --case=ai_investment
python engine.py run --case=ai_investment --verbose
```

```bash
pip install pytest
pytest -v
```

## MCP：给外部合作伙伴的接口

`mcp_server/server.py` 把同一套判定暴露成 MCP tool，任何 MCP client（Claude Desktop、其他 agent 框架）都能调——这是「活证据」版本，不是案例回放：

```bash
pip install "mcp==1.23.1"   # 只有跑 MCP server 才需要
python mcp_server/server.py   # stdio transport
```

两个 tool：

- **`list_precondition_functions(case="ai_investment")`**：列出可判定的判断标准（治理/落地两个打分函数），附带期望的 evidence 字段。
- **`authorize(case, precondition_fn, evidence)`**：对调用方传入的**活证据**做真实判定，返回 `route`（PASS/ESCALATE/BYPASS_TO_HUMAN）、`authorized`、`R/C/O/Ro/Q`、`reason_code`。

**核心契约：`route != "PASS"` 时，调用方绝不能把「投资」当作已授权去执行。**

## 样本说明（以中美绿色基金已投项目为例）

`evidence/ai_investment_evidence.yaml` 里的证据取值是一个**已脱敏的示例 AI 项目**，不代表任何具体标的的尽调结论。它刻意保留"治理证据大量待确认 + 落地证据口径不清"的典型状态，验证 gate 会不会正确路由到 ESCALATE 而不是默认 PASS：

- 治理证据 0/6 已确认 → `invest_decision` ESCALATE（治理闸门未过）；
- 落地证据 2/5（部署 + 产业嵌入），付费合同口径不清 → `valuation` ESCALATE，落地等级≈L1；
- 团队驾驭能力 → BYPASS_TO_HUMAN。

**如实说明**：这是第一个把投资决策编码成确定性判定规则的 case，尚未经过真实投资决策验证（n=0）；打分字段与阈值是首版，待真实案例跑过后收紧。样本可以是基金已投的任何项目——把它的尽调材料按同样字段填进 evidence 文件即可。

## 边界（诚实的现状）

**这套标准判证据的质量，不判证据的真伪。** 如果调用方（或一个偷懒/被攻破的 MCP client）传 `filing_license_verified: true` 但实际根本没备案，闸门照样按"已备案"算。证据真实性归**取证层**（人工核实、可信数据源），这套标准是**判定层**，只保证"给定一组声称的证据，判定逻辑确定性、可复现、可审计"。

**这不是投资原则文档，是代码级标准。** 同一个证据喂进去，每次输出一样的结果，可审计、可复现、有回归测试——不是"我们坚持价值投资、注重合规"这种人人能说、判断不了具体项目的话。

## 项目结构

```
gate.py                            # 引擎核心：GateConfig（阈值）+ 4D-CQ 打分 + 四态路由 + 机器可判定契约
engine.py                          # CLI 运行时：按 --case 加载配置 → 打分 → 路由 → 写回
audit.py                           # append-only 审计日志（不存自由文本）
agent/gated_loop.py                # reason → gate → act 循环 + resolve_precondition()（MCP server 也调用）
mcp_server/server.py               # MCP server：list_precondition_functions / authorize
commits/ai_investment_commits.yaml # 决策闸门：投资决策 / 估值锁定 / 团队驾驭
preconditions/ai_investment.py     # 判断标准：治理 6 项 + 落地 5 项（确定性打分函数）
evidence/ai_investment_evidence.yaml # 证据快照（脱敏示例样本）
bindings/ai_investment_bindings.yaml # 谁执行（投资团队 → 投委会终审）
tests/test_ai_investment_case.py   # 回归测试
```

## 换一个项目怎么用

新增一个项目 `<project>` 需要三份文件：`evidence/<project>_evidence.yaml`、可选 `commits/<project>_commits.yaml`（复用 ai_investment 的闸门定义时可不改）、可选 `preconditions/<project>.py`（判断标准不同才需要）。引擎按 `--case` 动态加载，判定核心零改动。
