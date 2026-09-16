"""
agent/chain_of_thought.py —— GateFix agent 的显式思维链（chain-of-thought）

把「产业链五层定位 → 制造属性 → 估值锚 → 产业周期 → 政策/退出概率 →
机构接盘 → 项目状态 → 发展前景」这 8 步确定性推理，固化成一条**显式、有序、
前一步结论喂给后一步**的思维链。目标是：更准确地判断项目当前状态（Step 7
项目状态卡）、预判发展前景（Step 8 发展前景卡）。

与 gated_loop.py 的 reason_fn 明确分工：
  gated_loop.reason_fn = 按 commits/<case>_commits.yaml 顺序产"下一个待授权动作"，
                         不是 planner（见其 docstring）。
  本模块 = 真正的思维链——每一步回答一个产业问题，答案由 Python 确定性算出，
           且存在 feed-forward：估值锚 ← 层级+制造属性；退出概率 ← 层级+商业验证；
           发展前景 ← 退出概率+接盘+状态+周期合成。

LLM-free：与 preconditions/ai_investment.py 的 classify_value_chain /
classify_manufacturing / exit_probability / cn_embodied_cycle / backer_profile
同一套确定性纪律，数据地基是 gatefix_data 三张表（标的库 EMBODIED_TARGETS /
机构图谱 BACKER_GRAPH / 政策规则库 POLICY_EXIT_ATTITUDE）。LLM 只负责从尽调
材料提取证据字段（archetype、commercial_validation 等），本链只判定与合成，
缺数据 fail-closed，不静默猜。

数据快照：2026-09（来自《具身智能产业链投资调研 2.xlsx》9 Sheet 的确定性转写）。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from preconditions.ai_investment import (  # noqa: E402
    classify_value_chain,
    classify_manufacturing,
    exit_probability,
    cn_embodied_cycle,
    backer_profile,
)
from gatefix_data import target_by_name  # noqa: E402


# ---------------------------------------------------------------------------
# Step 3 估值锚选择：由「产业链层级 × 制造属性」→ 用哪把尺子（确定性查表）
# ---------------------------------------------------------------------------
ANCHOR_SELECTION = {
    ("component", "manufacturing"): "制造业锚（PS + 国产替代 + 学习曲线）——卖零件，壁垒在工艺/良率/规模降本",
    ("component", "intelligent"): "制造业锚为主（触觉/感知芯片含智能溢价，但仍以硬件出货为锚）",
    ("component", "platform"): "制造业锚 + 平台溢价（标准化模组复售）",
    ("brain", "intelligent"): "融资体量锚 + 门票锚（200 亿俱乐部）——卖模型，看泛化与规模化应用",
    ("brain", "manufacturing"): "融资体量锚为主，制造属性为辅（模型带动整机出货）",
    ("brain", "platform"): "融资体量锚 + 平台基础设施锚（模型即平台）",
    ("data", "platform"): "平台基础设施锚（复售率/PS，对标「数据英伟达」）——卖数据，看复用",
    ("data", "intelligent"): "平台基础设施锚（数据/仿真/评测，稀缺供给溢价）",
    ("data", "manufacturing"): "平台基础设施锚（数据采集硬件带动，但估值看数据复用）",
    ("body", "manufacturing"): "制造业锚（PS 3~8x + PE，需盈利/出货验证）——卖硬件",
    ("body", "intelligent"): "⚠️ 需回归制造业锚（宇树腰斩教训：智能估值→制造业估值，PS 37x→回归）",
    ("body", "platform"): "制造业锚 + 平台溢价（整机×场景平台化）",
    ("scenario", "manufacturing"): "场景锚（PS 3~8x + 复购 + 现金流）——卖结果，看一年回本 ROI",
    ("scenario", "intelligent"): "场景锚 + 智能溢价（场景数据闭环）——卖结果，看复购",
    ("scenario", "platform"): "场景锚 + 平台溢价（场景运营平台化）",
}

# ---------------------------------------------------------------------------
# Step 7 项目状态卡：上市/盈利/营收/融资 四态 → 当前状态（确定性）
# ---------------------------------------------------------------------------
STATUS_GRADE_LABELS = {
    3: "已盈利",
    2: "有规模化营收（未盈利/盈利未披露）",
    1: "有商业化验证/出货（营收未披露）",
    0: "纯叙事（无规模化应用）",
    -1: "未披露（fail-closed）",
}


def _num(v) -> Optional[float]:
    """把 None/非法值转 float，非法返回 None（fail-closed 语义）。"""
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _project_status(target_name: str, evidence: dict, commercial_validation: bool) -> dict:
    """项目状态卡（确定性）。优先标的库（target_by_name 命中），否则按 evidence 信号。
    返回：listed / profit / revenue / funding / valuation / commercial_validation /
    grade（3 已盈利 / 2 规模化营收 / 1 出货验证 / 0 纯叙事 / -1 未披露）/ summary。"""
    t = target_by_name(target_name)
    listed = (t or {}).get("listed")
    profit = _num((t or {}).get("profit"))
    revenue = _num((t or {}).get("revenue"))
    funding = _num((t or {}).get("funding"))
    valuation = _num((t or {}).get("valuation"))

    # evidence 兜底（LLM 提取的财务/商业验证信号，仅当标的库未披露时补充）
    if profit is None:
        profit = _num(evidence.get("profit"))
    if revenue is None:
        revenue = _num(evidence.get("revenue"))
    if funding is None:
        funding = _num(evidence.get("cumulative_funding") or evidence.get("funding"))
    if valuation is None:
        valuation = _num(evidence.get("claimed_valuation") or evidence.get("valuation"))

    commercial = bool(commercial_validation or (revenue is not None and revenue > 0))

    # 上市状态
    if listed:
        listed_cn = ("已上市（" + str(listed) + "）" if not str(listed).startswith("冲刺")
                     else "冲刺 IPO（" + str(listed) + "）")
    else:
        listed_cn = "未上市" if t is not None else "未披露"

    # 成熟度 grade。营收/盈利未披露时，用标的库 exit_prob 兜底（它已编码商业验证判断：
    #   高/中高 = 已验证（盈利/规模化/硬科技+产业接盘）；中 = 部分验证（有出货/规模化应用）；
    #   低 = 未验证（纯叙事/无规模化应用）——避免把"营收未披露"误判成"纯叙事"。
    lib_exit = (t or {}).get("exit_prob")
    if profit is not None and profit > 0:
        grade = 3
    elif revenue is not None and revenue > 0:
        grade = 2
    elif commercial:
        grade = 1
    elif lib_exit in ("高", "中高", "中"):
        grade = 1  # 有商业化验证/出货（营收未披露）
    elif lib_exit == "低":
        grade = 0  # 纯叙事（无规模化应用）
    elif t is not None:
        grade = 0
    else:
        grade = -1

    summary = (f"{listed_cn} · {STATUS_GRADE_LABELS[grade]}"
               + (f"（营收 {revenue:g} 亿 / 净利 {profit:g} 亿）" if revenue is not None and profit is not None else
                  f"（营收 {revenue:g} 亿）" if revenue is not None else
                  f"（净利 {profit:g} 亿）" if profit is not None else "")
               + (f" · 累计融资 {funding:g} 亿" if funding is not None else "")
               + (f" · 估值 {valuation:g} 亿" if valuation is not None else ""))
    return dict(listed=listed_cn, profit=profit, revenue=revenue, funding=funding,
                valuation=valuation, commercial_validation=commercial,
                grade=grade, summary=summary, source=("标的库" if t else "证据信号"))


# ---------------------------------------------------------------------------
# Step 8 发展前景卡：退出概率 × 接盘 × 状态 × 周期 → 前景（确定性加权合成）
# ---------------------------------------------------------------------------
PROSPECT_WEIGHTS = {"exit": 0.40, "liquidity": 0.25, "maturity": 0.20, "timing": 0.15}

EXIT_SCORE = {"高": 1.0, "中高": 0.8, "中": 0.6, "低": 0.2}
# 退出概率 → 政策态度（同一判断的两个标签；标的库 exit_prob 研究推导比政策表更细，
# body 的"中"=有产业方背书/部分验证，态度应为"有条件欢迎"而非政策表 body 二分里的"收紧"）
EXIT_PROB_TO_ATTITUDE = {"高": "欢迎", "中高": "有条件欢迎", "中": "有条件欢迎", "低": "收紧"}
MATURITY_SCORE = {3: 1.0, 2: 0.8, 1: 0.5, 0: 0.2, -1: 0.3}
TIMING_SCORE = {"consolidation": 1.0, "startup": 0.7, "bubble": 0.5,
                "shakeout_eve": 0.3, "shakeout": 0.2, "indeterminate": 0.5}


def _development_prospect(exitp: dict, bp: dict, status: dict, cycle: dict) -> dict:
    """发展前景卡（确定性）。4 维加权合成（与 4D-CQ 加权同纪律），阈值映射 高/中/低：
      exit(0.40) 政策/财务退出概率 + liquidity(0.25) 接盘流动性 + maturity(0.20) 成熟度
      + timing(0.15) 周期时序。
    阈值：score ≥ 0.70 → 高；0.45 ≤ score < 0.70 → 中；< 0.45 → 低。
    每维分数显式给出，可审计。"""
    exit_s = EXIT_SCORE.get(exitp.get("probability"), 0.2)
    if bp.get("has_industrial_backer"):
        liq_s = 1.0
    elif bp.get("has_soe_backer"):
        liq_s = 0.7
    elif bp.get("backers"):
        liq_s = 0.4  # 纯财务 VC → 二级流动性依赖
    else:
        liq_s = 0.3  # 未收录 → fail-closed
    mat_s = MATURITY_SCORE.get(status["grade"], 0.3)
    tim_s = TIMING_SCORE.get(cycle.get("stage"), 0.5)

    score = (PROSPECT_WEIGHTS["exit"] * exit_s + PROSPECT_WEIGHTS["liquidity"] * liq_s
             + PROSPECT_WEIGHTS["maturity"] * mat_s + PROSPECT_WEIGHTS["timing"] * tim_s)
    if score >= 0.70:
        prospect = "高"
    elif score >= 0.45:
        prospect = "中"
    else:
        prospect = "低"

    # 关键观察点（未来要盯的信号，feed-forward 给投后）
    watch = []
    if status["grade"] <= 0:
        watch.append("商业化验证（付费合同/复购/经济价值）是否落地")
    if exitp.get("probability") in ("低", "中"):
        watch.append("交易所政策口径是否收紧（人形初创 IPO）")
    if bp.get("backers") and not bp.get("has_industrial_backer") and not bp.get("has_soe_backer"):
        watch.append("解禁潮/二级流动性（纯财务 VC 无产业接盘方）")
    if cycle.get("stage") in ("shakeout_eve", "shakeout"):
        watch.append("需求锚拐点（机器人成本 < 人工成本）是否到来")
    if status["listed"].startswith("已上市"):
        watch.append("解禁潮与估值锚回归（对标宇树腰斩）")

    reason = (f"退出概率 {exitp.get('probability')} × 接盘{('产业资本' if bp.get('has_industrial_backer') else '国资' if bp.get('has_soe_backer') else '财务VC' if bp.get('backers') else '未知')} "
              f"× 状态{STATUS_GRADE_LABELS[status['grade']]} × 周期{cycle.get('stage_cn')} → 前景【{prospect}】")
    return dict(prospect=prospect, score=round(score, 3),
                exit_score=exit_s, liquidity_score=liq_s, maturity_score=mat_s, timing_score=tim_s,
                reason=reason, key_watch=watch)


# ---------------------------------------------------------------------------
# 思维链本体：8 步确定性推理
# ---------------------------------------------------------------------------
@dataclass
class ChainStep:
    step: int
    title: str
    question: str
    conclusion: str
    basis: str
    source: str = ""


def embodied_chain_of_thought(target_name: str, evidence: Optional[dict] = None) -> dict:
    """显式思维链：8 步确定性推理，从产业链定位到发展前景预判。

    evidence 可携带 LLM 提取的信号（archetype/mfg_profile/sells_*/commercial_validation/
    profitable/player_count/price_war_started/demand_validated/累计融资/营收/估值等）；
    标的库命中（target_by_name）时，标的库字段优先（确定性地基），evidence 兜底。
    缺数据 → 对应步 fail-closed，不静默猜。

    返回 dict：target_name / steps(8 × ChainStep) / project_status / prospect。"""
    evidence = evidence or {}
    t = target_by_name(target_name)

    steps: list[ChainStep] = []

    # ---- Step 1 产业链五层定位 ----
    if t:
        vc = classify_value_chain({"archetype": t["archetype"]})
        vc["note"] = "标的库收录（直接采信）"
        s1_src = "标的库 EMBODIED_TARGETS"
    else:
        vc = classify_value_chain(evidence)
        s1_src = "证据信号推断" if vc["archetype"] else "fail-closed"
    steps.append(ChainStep(1, "产业链五层定位", "它在产业链哪一层（卖零件/模型/数据/整机/结果）？",
                           vc["layer"], vc["note"], s1_src))

    # ---- Step 2 制造属性判定 ----
    if t:
        mfg = classify_manufacturing({"mfg_profile": t["mfg_profile"]})
        mfg["note"] = "标的库收录（直接采信）"
        s2_src = "标的库 EMBODIED_TARGETS"
    else:
        mfg = classify_manufacturing(evidence)
        s2_src = "证据信号推断" if mfg["mfg_profile"] else "fail-closed"
    steps.append(ChainStep(2, "制造属性判定", "制造型（卖硬件）还是智能型（卖模型）还是平台型（卖数据）？",
                           mfg["profile"], mfg["note"], s2_src))

    # ---- Step 3 估值锚选择（feed-forward：层级 × 制造属性） ----
    anchor = ANCHOR_SELECTION.get((vc["archetype"], mfg["mfg_profile"]))
    if anchor is None:
        if vc["archetype"]:
            anchor = classify_value_chain({"archetype": vc["archetype"]}).get("valuation_anchor") or "未识别"
            s3_src = "按层级默认锚"
        else:
            anchor = "未识别（层级缺失）"
            s3_src = "fail-closed"
    else:
        s3_src = "层级 × 制造属性 查表"
    steps.append(ChainStep(3, "估值锚选择", "该用哪把尺子量它？",
                           anchor, "由 Step1 层级 × Step2 制造属性 推导", s3_src))

    # ---- Step 4 产业周期定位（赛道快照 + 项目是否已跨需求锚） ----
    cycle = cn_embodied_cycle(
        player_count=evidence.get("player_count", 300),
        capital_inflow=evidence.get("capital_inflow"),
        price_war_started=evidence.get("price_war_started", True),
        demand_validated=evidence.get("demand_validated", False),
    )
    commercial = bool(
        (evidence.get("commercial_validation"))
        or (t is not None and t.get("revenue") is not None and t["revenue"] > 0)
        or (t is not None and t.get("profit") is not None and t["profit"] > 0)
    )
    proj_position = ("本项目已有规模化应用/盈利 → 已跨过「需求锚」验证"
                     if commercial else
                     "本项目尚无规模化应用 → 未跨过「需求锚」，赌拐点（风险高于光伏洗牌）")
    steps.append(ChainStep(4, "产业周期定位", "赛道在光伏周期的哪一段，项目自身跨过需求拐点了吗？",
                           f"{cycle['stage_cn']}；{proj_position}", cycle["note"], "赛道快照 2026-09"))

    # ---- Step 5 政策态度 + 退出概率（feed-forward：层级 × 商业验证） ----
    # 优先级：标的库 exit_prob（研究推导，body 分 高/中/低，已计入产业方背书） >
    # 政策表 exit_probability（body 仅分 盈利=欢迎高 / 纯叙事=收紧低 两档，较粗）。
    # 政策表交叉核对时，态度仍取自政策表（欢迎/收紧），概率以标的库为准。
    policy_exitp = exit_probability(archetype=vc["archetype"],
                                    profitable=(_num((t or {}).get("profit")) is not None
                                                and _num((t or {}).get("profit")) > 0) or bool(evidence.get("profitable")),
                                    commercial_validation=commercial)
    lib_exit_prob = (t or {}).get("exit_prob")
    if lib_exit_prob:
        exitp = dict(policy_exitp)
        exitp["probability"] = lib_exit_prob
        exitp["attitude"] = EXIT_PROB_TO_ATTITUDE.get(lib_exit_prob, policy_exitp["attitude"])
        exitp["basis"] = (f"标的库标注 exit_prob={lib_exit_prob}（研究推导）；政策表交叉核对："
                          f"{policy_exitp['probability']}/{policy_exitp['attitude']}——{policy_exitp['basis']}")
        s5_src = "标的库 exit_prob 优先 + 政策表交叉核对"
    else:
        exitp = policy_exitp
        s5_src = "POLICY_EXIT_ATTITUDE 查表"
    steps.append(ChainStep(5, "政策态度 + 退出概率", "2027 政策欢迎还是收紧，退出概率高/中/低？",
                           f"{exitp['attitude']} · 退出概率【{exitp['probability']}】", exitp["basis"], s5_src))

    # ---- Step 6 机构接盘画像 ----
    bp = backer_profile(target_name)
    if bp["backers"]:
        s6_ccl = "、".join(bp["backers"]) + " → " + bp["exit_liquidity"]
    else:
        s6_ccl = bp["exit_liquidity"]
    steps.append(ChainStep(6, "机构接盘画像", "谁在投，退出时谁接盘？",
                           s6_ccl, bp["exit_liquidity"], "BACKER_GRAPH 反向穿透"))

    # ---- Step 7 项目状态卡（feed-forward 汇总） ----
    status = _project_status(target_name, evidence, commercial)
    steps.append(ChainStep(7, "项目状态判定", "项目当前处于什么状态（上市/盈利/营收/融资）？",
                           status["summary"], STATUS_GRADE_LABELS[status["grade"]], status["source"]))

    # ---- Step 8 发展前景卡（feed-forward 合成） ----
    prospect = _development_prospect(exitp, bp, status, cycle)
    steps.append(ChainStep(8, "发展前景预判", "综合 5 步结论，预判发展前景？",
                           prospect["reason"], "关键观察点：" + "；".join(prospect["key_watch"]) if prospect["key_watch"] else "—",
                           "退出×接盘×状态×周期 加权合成"))

    return {
        "target_name": target_name,
        "in_library": t is not None,
        "steps": [s.__dict__ for s in steps],
        "value_chain": vc,
        "manufacturing": mfg,
        "valuation_anchor": anchor,
        "cycle": cycle,
        "exit": exitp,
        "backer": bp,
        "project_status": status,
        "prospect": prospect,
    }


# ---------------------------------------------------------------------------
# Markdown 渲染（供调试 / 独立出报告 / 测试断言）
# ---------------------------------------------------------------------------
def render_chain_trace(chain: dict) -> str:
    """把思维链渲染成 Markdown：8 步逐条 + 项目状态卡 + 发展前景卡。"""
    name = chain.get("target_name") or "（未命名标的）"
    lib = "（标的库收录）" if chain.get("in_library") else "（标的库未收录，证据信号推断）"
    out = [f"# {name} · GateFix 思维链（8 步确定性推理） {lib}\n"]
    for s in chain["steps"]:
        out.append(f"### {s['title']}\n")
        out.append(f"- 问：{s['question']}\n")
        out.append(f"- 答：**{s['conclusion']}**\n")
        out.append(f"- 依据：{s['basis']}　`{s['source']}`\n")
    st = chain["project_status"]
    pr = chain["prospect"]
    out.append("## 项目状态卡\n")
    out.append(f"- {st['summary']}\n")
    out.append("## 发展前景卡\n")
    out.append(f"- 前景：**{pr['prospect']}**（score={pr['score']}，"
               f"退出{pr['exit_score']}×接盘{pr['liquidity_score']}×状态{pr['maturity_score']}×周期{pr['timing_score']}）\n")
    out.append(f"- {pr['reason']}\n")
    if pr["key_watch"]:
        out.append("- 关键观察点：\n")
        for w in pr["key_watch"]:
            out.append(f"  - {w}\n")
    return "\n".join(out)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run the GateFix embodied chain-of-thought")
    parser.add_argument("target", help="标的名称（如 极智嘉 / 宇树科技 / 章鱼动力 / 帕西尼感知）")
    args = parser.parse_args()
    print(render_chain_trace(embodied_chain_of_thought(args.target)))


if __name__ == "__main__":
    main()
