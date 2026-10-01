# GateFix · AI Investment Governance

[简体中文](README.md) ｜ **English**

[![CI](https://github.com/Sherry-py/gatefix-ai-investment/actions/workflows/ci.yml/badge.svg)](https://github.com/Sherry-py/gatefix-ai-investment/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

> **License:** this repository is **dual-licensed AGPL-3.0 + commercial**. Open-source use (self-hosting, research, internal tooling) is governed by [AGPL-3.0](LICENSE). If you want to integrate the decision engine into a closed-source product or service without taking on AGPL's source-sharing obligations, obtain an exemption via a [commercial license](DUAL-LICENSE.md). See [DUAL-LICENSE.md](DUAL-LICENSE.md).

> **One-line positioning:** whether an AI project is investable — and what it is worth — does not turn on how well it tells its story. It turns on whether the evidence qualifies. This standard fixes the discipline of pre-investment judgement — governance evidence (*can it be governed*) plus traction evidence (*can it be used*) — into deterministic, auditable, reproducible rules, so every AI investment decision has grounds and a paper trail.

```
$ python engine.py run --case=ai_investment

--- Commit: AI project investment decision (governance evidence gate) ---
  R=0.20 C=0.00 O=0.40 Ro=0.30 -> Q=0.225  route=ESCALATE
  note: governance evidence covers 0/6 (no filing / no data compliance / no safety /
        no controllability / no privacy / no cross-border); red line not passed
  -> escalate to human: investment team -> IC final review

--- Commit: Valuation lock (traction evidence gate) ---
  R=0.20 C=0.40 O=0.40 Ro=0.30 -> Q=0.325  route=ESCALATE
  note: traction evidence covers 2/5 (deployed / no paid contract / embedded in industry /
        no quantified economic value / no repeat orders); landing level ~ L1
  -> escalate to human: investment team -> IC final review
```

The same evidence rules apply throughout: incomplete governance evidence escalates the investment decision to IC final review; an unclear traction record escalates the valuation to IC final review. What it produces is not a subjective verdict on whether a project is "good", but a deterministic judgement on whether a given set of due-diligence materials qualifies to support an irreversible investment. The standard is written into the rules — it does not move with the person or the mood.

## What this is

A **deterministic investment-decision gate for AI projects** — sitting between "what the founder says it is worth" and "what the IC actually wires", it adds a layer that looks at nothing but evidence. It fixes the discipline an IC applies to any deal — is the evidence sufficient, is it compliant, does it land — into reproducible rules.

It answers the question an IC cares about most: when irreversible capital is about to go into an AI project, what justifies going forward, and when should we stop?

1. Can this action (the investment) **be undone** — once the capital is in, can it be pulled back?
2. Is the evidence sufficient — do the **governance evidence** (*can it be governed*) and **traction evidence** (*can it be used*) clear the thresholds across the 4D-CQ dimensions?
3. Even if it passes, how much external risk is left that we cannot shed?

## The standard: two gates

### Gate 1 — Governance (*can it be governed*): "will this project die?"

Six items of governance evidence; the red line is filing + data compliance.

| Dimension | Question |
|---|---|
| Filing | Is the algorithm / LLM filing publicly verifiable? |
| Data compliance | Is training data lawfully sourced and licensed? |
| Safety | Safety certification / third-party testing |
| Controllability | Remote-intervention rate, failure rate, and similar |
| Privacy | Is data collection privacy-compliant? |
| Cross-border | Cross-border data / technology compliance |

### Gate 2 — Traction (*can it be used*): "will this project live, and what is it worth?"

Five items of traction evidence; the red line is deployment + paid contract. Coverage maps to a landing level.

| Landing level | Coverage | Meaning |
|---|---|---|
| L3 Scale repeat | 5/5 | Deployment + contract + industry embedment + economic value + repeat orders |
| L2 Application | 3–4/5 | Real paid contracts, embedded in the industry, quantifiable economic value |
| L1 Engineered | 2/5 | In production, but no paid repeat business |
| L0 Narrative | 0–1/5 | Model / paper / demo, no production deployment |

A third gate — team command of the business — is a **judgement call about people**. The machine does not assemble it and does not decide it: it goes straight to `BYPASS_TO_HUMAN`.

## 4D-CQ and four-state routing

Each gate scores the evidence along 4D-CQ (every dimension in [0,1]; a weighted sum yields Q):

- **R (Relevance)** — does the evidence bear on *this* project and *this* decision point? A missing red-line item drives this down.
- **C (Coverage)** — are all required dimensions covered?
- **O (Ordering)** — is the sequence right? (Compliance before operations; delivery before claiming repeat orders.)
- **Ro (Robustness)** — is the evidence third-party verified, or self-reported?

Four-state routing (`tau_pass=0.85` / `tau_repair=0.50`):

- **PASS** — Q ≥ 0.85: release.
- **AUTO_REPAIR** — 0.50 ≤ Q < 0.85 and the gap is externally checkable: collect the evidence once more and re-judge (converges internally; never exposed as a terminal state).
- **ESCALATE** — the evidence gap cannot be closed automatically: hand to human final review.
- **BYPASS_TO_HUMAN** — people-type evidence, or an evaluator fault (fail-closed): force to human.

> **On scoring granularity, plainly:** in this case the scores are **discrete** — R/C/O/Ro mostly take binary values (red line passed = 1.0, failed = 0.2, and so on), so Q takes only a handful of distinct values. In substance it is a rule table of "did the red line pass, and how many items are covered", not a continuous quality spectrum. 4D-CQ is the framework and supports continuous scores in future; but in investment decisions, evidence like "is there a filing" is inherently binary, and discrete fits the business better. Also note that `cost_reverse` / `value_tier` do **not** participate in routing in this case (an investment is irreversibly committed, so `is_commit` is always true); they appear only in the aggregated cost magnitude. Do not read the code for the first time and assume the ticket size feeds the judgement.

## How to run

```bash
pip install pyyaml   # the only core dependency
python engine.py run --case=ai_investment
python engine.py run --case=ai_investment --verbose
```

```bash
pip install pytest
pytest -v
```

## Embodied-AI chain of thought (8 deterministic steps)

`agent/chain_of_thought.py` fixes eight reasoning steps — value-chain position → manufacturing profile → valuation anchor → industry cycle → policy stance & exit probability → institutional backers → project state → outlook — into an **explicit, ordered chain in which each step feeds the next**, for a more accurate read on where a project stands and where it is heading. It is entirely LLM-free: the data comes from three tables under `gatefix_data/` (target library / institutional graph / policy rules), and the LLM is used only to extract evidence fields from due-diligence materials.

```bash
python agent/chain_of_thought.py 极智嘉      # run a single chain (Markdown output)
python agent/chain_of_thought.py 章鱼动力
```

| Step | Question | Where the conclusion comes from |
|---|---|---|
| 1. Five-layer value-chain position | Selling parts, models, data, machines, or outcomes? | Target library first + `classify_value_chain` |
| 2. Manufacturing profile | Manufacturing / intelligence / platform? | Target library first + `classify_manufacturing` |
| 3. Valuation anchor | Which ruler should measure this? | Layer x manufacturing profile lookup |
| 4. Industry cycle | Where in the solar-style curve, past the demand inflection? | `cn_embodied_cycle` + commercial validation |
| 5. Policy stance + exit probability | Policy welcoming or tightening? | Target library `exit_prob` first + policy table cross-check |
| 6. Institutional backer profile | Who invests, who buys the next round? | Reverse look-up through `BACKER_GRAPH` |
| 7. Project state card | Where does the project stand today? | Listed / profitable / revenue / funding, four states combined |
| 8. Outlook card | Where is it heading? | Exit x backers x state x cycle, weighted |

Core discipline: **when the target library has the company, its fields win; missing data fails closed (never a silent guess); exit probability follows the library's research, and the binary policy table is only a cross-check** — so that an unprofitable hardware maker with industrial backing is not misread as pure narrative.

## MCP: an interface for external partners

`mcp_server/server.py` exposes the same judgement as MCP tools, callable by any MCP client (Claude Desktop, other agent frameworks). This is the **live-evidence** version, not a case replay:

```bash
pip install "mcp==1.23.1"   # only needed to run the MCP server
python mcp_server/server.py   # stdio transport
```

Two tools:

- **`list_precondition_functions(case="ai_investment")`** — lists the judgeable standards (the governance and traction scoring functions) together with the evidence fields each expects.
- **`authorize(case, precondition_fn, evidence)`** — runs a real judgement over **live evidence** supplied by the caller, returning `route` (PASS / ESCALATE / BYPASS_TO_HUMAN), `authorized`, `R/C/O/Ro/Q`, and `reason_code`.

**Core contract: when `route != "PASS"`, the caller must never treat the investment as authorized.**

## About the sample (modelled on a fund's portfolio)

The evidence values in `evidence/ai_investment_evidence.yaml` describe a **de-identified example AI project** and represent no specific target's due-diligence conclusion. It deliberately preserves the typical state of "a lot of governance evidence still unconfirmed + an unclear traction record", to verify that the gate routes to ESCALATE rather than defaulting to PASS:

- Governance evidence 0/6 confirmed -> `invest_decision` ESCALATE (governance gate not passed)
- Traction evidence 2/5 (deployed + embedded in industry), paid-contract record unclear -> `valuation` ESCALATE, landing level ~ L1
- Team command of the business -> BYPASS_TO_HUMAN

**Stated plainly:** this is the first case to encode investment decisions as deterministic rules, and it has **not** been validated against real investment decisions (n=0). The scoring fields and thresholds are a first version, to be tightened once real cases have run through it. The sample can be any project a fund has backed — fill its due-diligence materials into the evidence file using the same fields.

## Boundaries (the honest state of things)

**This standard judges the quality of evidence, not its truthfulness.** If a caller (or a lazy, or compromised, MCP client) passes `filing_license_verified: true` when no filing exists, the gate will treat it as filed. Evidentiary truth belongs to the **evidence-collection layer** (human verification, trusted sources). This standard is the **decision layer**: it guarantees only that, given a set of claimed evidence, the judgement logic is deterministic, reproducible and auditable.

**This is not an investment-principles document; it is a code-level standard.** Feed the same evidence in and you get the same result out, every time — auditable, reproducible, covered by regression tests. It is not the kind of thing anyone can say ("we stick to value investing and care about compliance") and that cannot judge a specific project.

## Repository layout

```
gate.py                            # engine core: GateConfig (thresholds) + 4D-CQ scoring + four-state routing + machine-decidable contract
engine.py                          # CLI runtime: load config by --case -> score -> route -> write back
audit.py                           # append-only audit log (no free text stored)
agent/gated_loop.py                # reason -> gate -> act loop + resolve_precondition() (also called by the MCP server)
agent/chain_of_thought.py          # 8-step deterministic chain: value chain -> project state -> outlook (LLM-free)
gatefix_data/                      # data foundation: target library / institutional graph / policy rules (2026-09 snapshot)
mcp_server/server.py               # MCP server: list_precondition_functions / authorize
commits/ai_investment_commits.yaml # decision gates: investment decision / valuation lock / team command
preconditions/ai_investment.py     # the standards: 6 governance + 5 traction + value-chain layer / exit probability (deterministic scoring functions)
evidence/ai_investment_evidence.yaml # evidence snapshot (de-identified sample)
bindings/ai_investment_bindings.yaml # who executes (investment team -> IC final review)
tests/test_ai_investment_case.py   # regression tests (case routing + value chain / exit dimensions)
tests/test_chain_of_thought.py     # chain-of-thought regression tests (8 steps / state separation / outlook tiers / fail-closed)
```

## Using it for another project

Adding a project `<project>` takes three files: `evidence/<project>_evidence.yaml`; optionally `commits/<project>_commits.yaml` (leave it alone if you reuse the ai_investment gate definitions); optionally `preconditions/<project>.py` (only needed if the standards differ). The engine loads dynamically by `--case`, and the decision core does not change at all.
