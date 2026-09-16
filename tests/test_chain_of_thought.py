"""Tests for agent/chain_of_thought.py —— GateFix agent 的 8 步显式思维链。

验证目标（对应「更准确判断项目状态 + 预判发展前景」）：
  1. 思维链是 8 步、有序、确定性（LLM-free），前一步结论喂后一步；
  2. 项目状态卡不把"营收未披露"误判成"纯叙事"（帕西尼有产业客户 → 有商业化验证）；
  3. 发展前景卡由 退出概率×接盘×状态×周期 合成，分档 高/中/低；
  4. 退出概率：标的库 exit_prob（研究推导，body 分 高/中/低）优先于政策表二分；
  5. 估值锚选择：body×intelligent → 回归制造业锚（宇树腰斩教训）；
  6. 未收录标的 → fail-closed（退出低、前景低、状态未披露）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.chain_of_thought import (  # noqa: E402
    ANCHOR_SELECTION,
    embodied_chain_of_thought,
    render_chain_trace,
)


def _chain(name, evidence=None):
    return embodied_chain_of_thought(name, evidence)


def test_chain_has_eight_ordered_steps():
    """思维链必须是 8 步，且标题顺序固定（产业链→制造→估值锚→周期→退出→接盘→状态→前景）。"""
    c = _chain("极智嘉")
    assert len(c["steps"]) == 8
    titles = [s["title"] for s in c["steps"]]
    assert titles == ["产业链五层定位", "制造属性判定", "估值锚选择", "产业周期定位",
                      "政策态度 + 退出概率", "机构接盘画像", "项目状态判定", "发展前景预判"]


def test_project_status_distinguishes_commercial_from_narrative():
    """项目状态卡：营收未披露 ≠ 纯叙事。帕西尼（component，比亚迪产业客户，exit_prob 高）
    应为「有商业化验证/出货」；章鱼动力（无规模化应用，exit_prob 低）应为「纯叙事」。"""
    pax = _chain("帕西尼感知")
    assert pax["project_status"]["grade"] == 1
    assert "有商业化验证" in pax["project_status"]["summary"]

    zy = _chain("章鱼动力")
    assert zy["project_status"]["grade"] == 0
    assert "纯叙事" in zy["project_status"]["summary"]


def test_project_status_reports_profit_and_listing():
    """宇树：已上市 + 已盈利（营收 16.99 / 净利 2.78）。"""
    y = _chain("宇树科技")
    assert y["project_status"]["grade"] == 3
    assert "已上市" in y["project_status"]["summary"]
    assert "已盈利" in y["project_status"]["summary"]


def test_exit_probability_prefers_library_over_policy_bifurcation():
    """退出概率：智元是 body 未盈利，政策表二分会给「低」，但标的库研究推导给「中」
    （有产业方背书）。思维链应采信标的库「中」而非政策表「低」。"""
    zy = _chain("智元机器人")
    assert zy["exit"]["probability"] == "中"
    assert zy["exit"]["attitude"] == "有条件欢迎"  # 与"中"一致，而非政策表的"收紧"


def test_prospect_high_for_scenario_and_component():
    """发展前景：极智嘉（场景派·已上市·有规模化营收）→ 高；帕西尼（零部件·产业接盘）→ 高。"""
    assert _chain("极智嘉")["prospect"]["prospect"] == "高"
    assert _chain("帕西尼感知")["prospect"]["prospect"] == "高"


def test_prospect_low_for_pure_narrative_brain():
    """发展前景：章鱼动力（纯模型·无规模化应用）→ 低。"""
    assert _chain("章鱼动力")["prospect"]["prospect"] == "低"


def test_valuation_anchor_body_intelligent_regresses_to_manufacturing():
    """估值锚选择：body×intelligent → 回归制造业锚（宇树腰斩教训）。
    宇树在标的库里 mfg_profile=manufacturing（正确），故直接断言 ANCHOR_SELECTION 表。"""
    assert "回归制造业锚" in ANCHOR_SELECTION[("body", "intelligent")]
    assert "制造业锚" in _chain("宇树科技")["valuation_anchor"]


def test_unknown_target_fails_closed():
    """未收录标的 → fail-closed：层级未识别、退出低、前景低、状态未披露。"""
    c = _chain("不存在的标的")
    assert c["in_library"] is False
    assert c["exit"]["probability"] == "低"
    assert c["prospect"]["prospect"] == "低"
    assert c["project_status"]["grade"] == -1


def test_render_chain_trace_outputs_markdown():
    """渲染：Markdown 含 8 步、项目状态卡、发展前景卡。"""
    md = render_chain_trace(_chain("极智嘉"))
    assert "思维链" in md
    assert "项目状态卡" in md
    assert "发展前景卡" in md
    assert "关键观察点" in md
