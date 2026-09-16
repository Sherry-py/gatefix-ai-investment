"""Tests for the ai_investment case — the first case in this repo whose judgment
target is an investment DECISION (not an agent action): whether the evidence
for investing in an AI project is sufficient to authorize committing capital.

This is also the first case backed by a de-identified AI-project sample
whose evidence values come from public reporting + the company BP (both "to be
verified"), NOT a real internal due-diligence record — the honest-disclosure
stance is explicit about this. There is NO real investment decision behind
this case yet (n=0); the scoring field split and thresholds are a first pass,
to be tightened after real cases.

The intent of the committed evidence is to keep the sample's representative state — most
governance evidence unconfirmed, landing evidence with unclear contract
口径 (contract/framework/intent not separated), and a brain-pie track valuation
whose claimed 100 亿 sits in the "half-option" zone (above the financial ruler,
below the 200 亿 ticket) — so the gate routes the investment decision, the
landing level, and the track valuation all to ESCALATE (human review), never PASS.
The governance gap is marked externally-verifiable, but Q lands below
tau_repair, so it escalates straight to the investment committee without an
automated repair attempt (AUTO_REPAIR only fires inside [tau_repair, tau_pass)).
The track-valuation gap is also externally-verifiable but lands inside the repair
band, so it attempts AUTO_REPAIR and, because the premium cannot be repaired by
flipping bools, converges to ESCALATE."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine
from gate import GateConfig
from preconditions import ai_investment as ai_pre


EXPECTED_ROUTES = {
    "invest_decision": "ESCALATE",
    "valuation": "ESCALATE",
    "track_valuation": "ESCALATE",
    "aidc_track_valuation": "ESCALATE",
    "mna_exit_likelihood": "ESCALATE",
    "team_capability": "BYPASS_TO_HUMAN",
}


def test_ai_investment_case_reproduces_expected_routes():
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    assert len(records) == len(EXPECTED_ROUTES)
    routes = {r["commit_id"]: r["route"] for r in records}
    assert routes == EXPECTED_ROUTES


def test_ai_investment_governance_escalates_below_repair_band():
    """The sample's governance evidence is 0/6 confirmed — Q lands at 0.225,
    well below tau_repair — so it escalates straight to the investment
    committee without an automated repair attempt, even though the gap is
    marked externally-verifiable. This mirrors the "黄灯 → 人工终审" conclusion
    in the research notes, encoded deterministically."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "invest_decision")
    cfg = GateConfig()
    assert rec["Q"] < cfg.tau_repair
    assert rec["route"] == "ESCALATE"
    assert rec["dry_rounds"] == 0
    assert "AUTO_REPAIR" not in rec["notes"]
    assert "红线" in rec["notes"]


def test_ai_investment_landing_reports_verified_level():
    """The sample's landing evidence: deployment + industry embedding are present
    (2/5), but paid contracts / economic value / repeat orders are unverified —
    the verified landing level reports L1, with the L2 claim (N signed units)
    blocked on contract verification. The red line (deployment + verified paid
    contract) is not passed."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "valuation")
    assert rec["route"] == "ESCALATE"
    assert "L1" in rec["notes"]
    assert "红线" in rec["notes"]


def test_ai_investment_track_valuation_escalates_half_option():
    """The sample's track valuation is a brain-pie at 100 亿 with ~12 亿 cumulative
    funding and ~1.5 亿 revenue — the deterministic anchors put the financial ruler
    at [36,60] 亿 and the 200 亿 ticket above it, so 100 亿 lands in the half-option
    zone (premium vs financials, discount vs ticket). The red line (within financial
    ruler) fails and cannot be repaired by flipping bools → converges to ESCALATE."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "track_valuation")
    assert rec["route"] == "ESCALATE"
    assert "half_option" in rec["notes"]
    assert "金融尺子" in rec["notes"]
    assert "门票" in rec["notes"]
    assert "AUTO_REPAIR" in rec["notes"]  # it did attempt AUTO_REPAIR before escalating


def test_ai_investment_aidc_track_valuation_escalates_red_flag_deadzone():
    """The sample's 算电协同 track is a power-pie at 12 亿 with ~0.8 亿 revenue
    (<1 亿 red-flag threshold) — the deterministic M&A-exit anchors put the
    financial ruler at [2.4, 6.4] 亿 (PS 3-8x) and the 20 亿 size ceiling above it,
    so 12 亿 triggers red_flag_deadzone (revenue <1 亿 AND valuation >8x revenue).
    The red line (within M&A-exit ruler) fails and cannot be repaired by flipping
    bools → converges to ESCALATE after AUTO_REPAIR dry rounds."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "aidc_track_valuation")
    assert rec["route"] == "ESCALATE"
    assert "red_flag_deadzone" in rec["notes"]
    assert "并购退路" in rec["notes"]
    assert "规模天花板" in rec["notes"]
    assert "AUTO_REPAIR" in rec["notes"]  # the premium cannot be repaired by flipping bools


def test_aidc_anchors_financial_ruler_ps_3_to_8():
    """Deterministic anchors: revenue 2 亿 → M&A-exit ruler [6, 16] 亿 (PS 3-8x),
    size ceiling 20 亿, red-flag-low-revenue False (revenue >= 1 亿)."""
    anchors = ai_pre.cn_aidc_energy_anchors(revenue=2.0, archetype="power")
    assert anchors["financial_range"] == (6.0, 16.0)
    assert anchors["size_ceiling"] == 20.0
    assert anchors["red_flag_low_revenue"] is False
    assert anchors["archetype"] == "power"


def test_aidc_ruler_zone_within_financial_passes():
    """A claimed 10 亿 valuation with 2 亿 revenue lands within the [6,16] 亿
    M&A-exit ruler → within_financial (合理), the PASS condition."""
    anchors = ai_pre.cn_aidc_energy_anchors(revenue=2.0, archetype="power")
    zone, rel = ai_pre.aidc_ruler_zone(10.0, anchors)
    assert zone == "within_financial"
    assert rel == "合理"


def test_aidc_ruler_zone_size_ceiling_breach():
    """A claimed 25 亿 valuation exceeds the 20 亿 重大资产重组 line → the most
    severe zone (A 股买方直接放弃), regardless of revenue."""
    anchors = ai_pre.cn_aidc_energy_anchors(revenue=2.0, archetype="power")
    zone, rel = ai_pre.aidc_ruler_zone(25.0, anchors)
    assert zone == "size_ceiling_breach"
    assert rel == "溢价"


def test_aidc_track_valuation_passes_with_all_green_evidence():
    """A power-pie at 10 亿 with 2 亿 revenue, AIDC-chain customer identified and
    marginal pricer identified → all 4 coverage dims true, red line within_financial
    → Q=1.0 → PASS."""
    evidence = {
        "archetype": "power",
        "archetype_identified": True,
        "annual_revenue": 2.0,
        "revenue_disclosed": True,
        "customer_identified": True,
        "marginal_pricer_identified": True,
        "claimed_valuation": 10.0,
        "anchors_before_claimed": True,
        "anchor_source_verified": True,
        "track_gap_externally_verifiable": True,
    }
    result = ai_pre.score_aidc_track_valuation(evidence)
    assert result["R"] == 1.0
    assert result["C"] == 1.0
    assert result["O"] == 1.0
    assert result["Ro"] == 1.0
    assert result["zone"] == "within_financial"


def test_ai_investment_mna_exit_likelihood_escalates_red_flag():
    """The sample's M&A-fit gate: 财务可并表 + 产业逻辑 partial, but the valuation
    (12 亿 at 0.8 亿 revenue) derives the red flag 估值>8x收入且收入<1亿, and the fit
    score lands below 65 → red line fails. The gap is externally verifiable but the
    derived valuation red flag cannot be repaired by flipping bools → ESCALATE."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "mna_exit_likelihood")
    assert rec["route"] == "ESCALATE"
    assert "并购适配度" in rec["notes"]
    assert "红旗" in rec["notes"]
    assert "8x" in rec["notes"]


def test_mna_fit_score_derives_valuation_red_flags():
    """A 12 亿 claim at 0.8 亿 revenue (<1 亿) must derive the 8x red flag and (since
    12 亿 < 20 亿) NOT the size-ceiling red flag — deterministic, no LLM."""
    ev = {
        "annual_revenue": 0.8,
        "claimed_valuation": 12.0,
    }
    fit = ai_pre.mna_fit_score(ev)
    flags = "、".join(fit["red_flags"])
    assert "8x" in flags
    assert "20亿" not in flags
    assert fit["score"] == 0  # no sub-items evidenced


def test_mna_fit_score_full_green_is_high_certainty():
    """All 14 sub-items True, no red flags, valuation within M&A-exit ruler →
    score 100, grade 并购退出高确定性, red line passes."""
    ev = {
        "target_name": "算电协同·电源派标的（全绿）",
        "track": "power",
        "archetype": "power",
        "annual_revenue": 2.0,
        "claimed_valuation": 10.0,
        "auditable_revenue": True, "gross_margin_not_dilutive": True, "profitable_or_near": True,
        "acquisition_logic_one_liner": True, "buyer_updownstream_fit": True,
        "shareholder_count_lt_20": True, "soe_shareholder_exitable": True,
        "no_repurchase_conflict": True, "founder_accepts_stock": True,
        "modular_tech": True, "not_founder_dependent": True,
        "institutional_customers": True, "no_customer_conflict": True,
        "valuation_below_buyer_bid": True,
        "redflag_soe_gt_30": False, "redflag_founder_ipo_only": False,
        "redflag_thirdparty_ip": False, "redflag_vie": False,
        "mna_fit_before_valuation": True, "mna_source_verified": True,
    }
    fit = ai_pre.mna_fit_score(ev)
    assert fit["score"] == 100
    assert fit["red_flags"] == []
    assert fit["grade"] == "并购退出高确定性"
    result = ai_pre.score_mna_exit_likelihood(ev)
    assert result["R"] == 1.0 and result["C"] == 1.0


def test_render_mna_exit_report_outputs_markdown():
    """The report renderer is a pure deterministic function: given evidence it emits
    a Markdown string containing the score, the grade, the buyers and the red flags."""
    ev = {
        "target_name": "算电协同·电源派标的",
        "track": "power",
        "archetype": "power",
        "annual_revenue": 2.0,
        "claimed_valuation": 10.0,
        "auditable_revenue": True, "gross_margin_not_dilutive": True, "profitable_or_near": True,
        "acquisition_logic_one_liner": True, "buyer_updownstream_fit": True,
        "shareholder_count_lt_20": True, "soe_shareholder_exitable": True,
        "no_repurchase_conflict": True, "founder_accepts_stock": True,
        "modular_tech": True, "not_founder_dependent": True,
        "institutional_customers": True, "no_customer_conflict": True,
        "valuation_below_buyer_bid": True,
        "mna_fit_before_valuation": True, "mna_source_verified": True,
    }
    md = ai_pre.render_mna_exit_report(ev)
    assert "并购退出可能性分析报告" in md
    assert "100/100" in md
    assert "并购退出高确定性" in md
    assert "英维克" in md  # buyers from MNA_TRACK_MAP["power"]
    assert "2028–2029" in md  # time window from MNA_TRACK_MAP["power"]


def test_hk_exit_paths_for_maps_tracks_to_paths():
    """算电协同/三代半导体/电网算法 → 并购 + 18D；具身智能大脑 → 并购 + 18C；
    具身智能单点 → 仅并购。确定性查表，不经过 LLM。"""
    assert ai_pre.hk_exit_paths_for(track="power") == ["并购退出（非 IPO）", "18D·中小成长型（拟设）"]
    assert ai_pre.hk_exit_paths_for(track="sic") == ["并购退出（非 IPO）", "18D·中小成长型（拟设）"]
    assert ai_pre.hk_exit_paths_for(track="brain") == ["并购退出（非 IPO）", "18C·大型未盈利特专科技"]
    assert ai_pre.hk_exit_paths_for(track="embodied") == ["并购退出（非 IPO）"]
    assert ai_pre.hk_exit_paths_for(track="unknown") == ["并购退出（非 IPO）"]


def test_render_hk_exit_spectrum_covers_all_six_paths():
    """The spectrum table renders every HK exit path with its valuation anchor."""
    md = ai_pre.render_hk_exit_spectrum()
    for path in ("传统主板·第八章", "18A·未盈利生物科技", "18B·SPAC",
                 "18C·大型未盈利特专科技", "18D·中小成长型（拟设）", "并购退出（非 IPO）"):
        assert path in md
    assert "18D" in md and "待定" in md  # 18D 门槛待公众咨询确认


def test_cn_exit_paths_for_maps_financial_state_to_paths():
    """境内 IPO 通道由财务状态决定（盈利/营收/估值），而非赛道。确定性查表。"""
    assert ai_pre.cn_exit_paths_for(profitable=True) == [
        "科创板·标准一（盈利）", "创业板", "深交所主板", "上交所主板"]
    assert ai_pre.cn_exit_paths_for(profitable=False, revenue_cny=5.0) == [
        "科创板·标准二~四（研发/现金流/营收）"]
    assert ai_pre.cn_exit_paths_for(profitable=False, valuation_cny=45.0) == [
        "科创板·标准五（未盈利）"]
    assert ai_pre.cn_exit_paths_for(profitable=False, revenue_cny=1.0) == [
        "境内 IPO 不成立（营收/估值未达门槛 → 港股18C / 并购退出）"]
    assert ai_pre.cn_exit_paths_for() == [
        "境内 IPO 不成立（营收/估值未达门槛 → 港股18C / 并购退出）"]


def test_render_cn_exit_spectrum_covers_mainland_paths():
    """The mainland spectrum renders every CN exit path with its gate mapping."""
    md = ai_pre.render_cn_exit_spectrum()
    for path in ("上交所主板", "深交所主板", "创业板",
                 "科创板·标准一（盈利）", "科创板·标准二~四（研发/现金流/营收）",
                 "科创板·标准五（未盈利）", "北交所"):
        assert path in md
    assert "市值≥40亿" in md  # 科创板标准五门槛


def test_render_exit_panorama_merges_hk_cn_cycle_capital():
    """The panorama merges HK + CN spectra plus redlines, cycle, and capital amounts."""
    md = ai_pre.render_exit_panorama()
    assert "18C·大型未盈利特专科技" in md     # 港股
    assert "科创板·标准五（未盈利）" in md     # 境内
    assert "三条可行性红线" in md
    assert "3.37" in md                        # 单项目平均持有期
    assert "2858" in md                        # 港股 2025 全年募资（亿港元）
    assert "换锚方法论" in md                    # 六、gap = 外生锚 − 内生锚


def test_anchor_switch_analysis_success_fail_noanchor():
    """换锚分析：有利润→PE 锚（正 gap→success）；有收入无利润→PS 锚（负 gap→fail）；
    无收入无利润→no_anchor；缺上一轮估值→indeterminate。确定性，LLM-free。"""
    # 有利润：外生锚 = 2.0 × 35 = 70 亿；gap = (70-40)/40 = +75% → success
    ok = ai_pre.anchor_switch_analysis(profit=2.0, last_round_valuation=40.0)
    assert ok["switch"] == "success"
    assert ok["exo_method"] == "PE"
    assert ok["gap_ratio"] > 0.5

    # 有收入无利润：外生锚 = 2.0 × 17.5 = 35 亿；gap = (35-50)/50 = -30% → fail
    bad = ai_pre.anchor_switch_analysis(revenue=2.0, last_round_valuation=50.0)
    assert bad["switch"] == "fail"
    assert bad["exo_method"] == "PS"
    assert bad["gap_ratio"] < -0.2

    # 无收入无利润 → no_anchor
    assert ai_pre.anchor_switch_analysis()["switch"] == "no_anchor"

    # 缺上一轮估值 → indeterminate
    assert ai_pre.anchor_switch_analysis(revenue=5.0)["switch"] == "indeterminate"


def test_anchor_switch_scarcity_and_render():
    """稀缺性 True 会标注抢筹空间；render 输出换轨结论。"""
    r = ai_pre.anchor_switch_analysis(revenue=3.0, last_round_valuation=35.0, scarcity=True)
    assert r["switch"] == "success"
    assert "稀缺" in r["scarcity_note"]
    md = ai_pre.render_anchor_switch(revenue=3.0, last_round_valuation=35.0,
                                     scarcity=True, name="某硬科技")
    assert "换锚分析" in md
    assert "换轨成功（涨）" in md


def test_local_landing_contributions_map_six_kpis():
    """The 标的 evidence maps onto the six local-government KPIs deterministically."""
    ev = {
        "capex_scale": 2.0, "output_value_scale": 3.0, "tax_scale": 1500,
        "employment_count": 120, "listed_status": "pre_ipo", "chain_role": "专精特新",
    }
    rows = ai_pre.local_landing_contributions(ev)
    assert len(rows) == 6
    fields = {r["field"]: r for r in rows}
    assert fields["capex_scale"]["display"] == "2.0 亿元"
    assert fields["listed_status"]["display"] == "pre_ipo"
    assert fields["chain_role"]["display"] == "专精特新"


def test_render_local_landing_plan_captures_core_logic():
    """The landing-plan report surfaces the core logic: 统计口径 vs 投资额,
    确定性>规模, 拟上市企业>投资额, 返投口径写死, 年底缺固投筹码最大."""
    ev = {
        "target_name": "算电协同·服务器电源标的",
        "listed_status": "pre_ipo",
        "can_setup_local_entity": True,
        "capex_scale": 2.0, "output_value_scale": 3.0, "tax_scale": 1500,
        "employment_count": 120, "chain_role": "专精特新",
        "investment_amount": 1.5, "return_invest_ratio": 2.0,
        "return_invest_definition": "实际经营和纳税在本地",
        "govt_most_needed_metric": "固投",
    }
    md = ai_pre.render_local_landing_plan(ev)
    assert "地方落地方案" in md
    assert "统计口径" in md
    assert "确定性" in md
    assert "拟上市企业" in md
    assert "返投" in md and "写死" in md
    assert "年底缺固投" in md


def test_render_local_landing_plan_flags_pure_equity_as_low_certainty():
    """纯股权投资（不设本地实体）→ 低确定性：不进统计口径，地方视同签约不落地."""
    ev = {"target_name": "某标的", "can_setup_local_entity": False}
    md = ai_pre.render_local_landing_plan(ev)
    assert "低确定性" in md
    assert "统计口径" in md


def test_price_model_presets_match_three_tracks():
    """六维度速查：绿电/核电 6/6 全过；算力/大模型 3/6 且 D1 内生；具身智能 2/6 且 D1 内生."""
    green = ai_pre.score_price_model(ai_pre.PRICE_MODEL_PRESETS["绿电/核电"])
    assert green["health"] == 1.0
    assert "六项全过" in green["verdict"]

    compute = ai_pre.score_price_model(ai_pre.PRICE_MODEL_PRESETS["算力/大模型"])
    assert compute["d1_ok"] is False
    assert "内生锚" in compute["verdict"]

    embodied = ai_pre.score_price_model(ai_pre.PRICE_MODEL_PRESETS["具身智能"])
    assert embodied["health"] == 2 / 6
    assert embodied["d1_ok"] is False


def test_price_model_d1_endogenous_caps_verdict():
    """D1 内生是红线：即使其余五维全绿，结论仍封顶「内生锚结构脆弱」."""
    ev = {"d1_anchor_exogenous": False, "d2_scissors": True, "d3_physical_constraint": True,
          "d4_measurable_unit": True, "d5_term_match": True, "d6_benchmark": True}
    sc = ai_pre.score_price_model(ev)
    assert sc["health"] == 5 / 6
    assert "内生锚" in sc["verdict"]


def test_render_price_model_outputs_table():
    md = ai_pre.render_price_model(ai_pre.PRICE_MODEL_PRESETS["绿电/核电"], name="绿电/核电")
    assert "六维度价格模型判定" in md
    assert "6/6" in md
    assert "D1 锚的性质" in md


def test_price_model_tristate_and_qiongche_case():
    """三态模型跑真实公司：穹彻 D1偏外生(绿) D2正向(绿) D3正对(绿) D4正在造(黄)
    D5待观察(黄) D6未到(红) → 4/6，区别于具身智能赛道平均(2/6)与绿电(6/6)。"""
    qc = ai_pre.score_price_model(ai_pre.QIONGCHE_CASE)
    assert qc["health"] == 4.0 / 6
    assert qc["d1_ok"] is True  # D1 偏外生（药房夜班人力成本）
    assert qc["dims"][3]["state"] == "yellow"  # D4 正在造
    assert qc["dims"][5]["state"] == "red"     # D6 未到

    md = ai_pre.render_price_model(ai_pre.QIONGCHE_CASE, name="穹彻智能")
    assert "穹彻智能" in md
    assert "4/6" in md
    assert "△" in md  # 黄标记（正在造/待观察）


def test_compliance_exposure_maps_14105_and_tariffs():
    """行政令14105：半导体/量子/AI 受限；清洁能源/核电/电网 豁免；光伏/锂电 关税暴露."""
    assert ai_pre.compliance_exposure("semiconductor")[0] == "受限"
    assert ai_pre.compliance_exposure("quantum")[0] == "受限"
    assert ai_pre.compliance_exposure("ai_software")[0] == "受限"
    assert ai_pre.compliance_exposure("nuclear_smr")[0] == "豁免"
    assert ai_pre.compliance_exposure("grid")[0] == "豁免"
    assert ai_pre.compliance_exposure("solar_component")[0] == "关税暴露"
    assert ai_pre.compliance_exposure("lithium_battery")[0] == "关税暴露"
    assert ai_pre.compliance_exposure("unknown_field")[0] == "未知"


def test_embodied_implied_multiple_and_ruler():
    """隐含融资倍数：穹彻 100/12=8.3x 远超赛道 3~5x → 溢价；渲染标尺含四锚+倍数对照."""
    assert abs(ai_pre.embodied_implied_multiple(12.0, 100.0) - 100 / 12) < 1e-9
    assert ai_pre.embodied_implied_multiple(None, 100.0) is None

    ev = {"target_name": "穹彻智能", "archetype": "brain",
          "cumulative_funding": 12.0, "annual_revenue": 1.5, "claimed_valuation": 100.0}
    md = ai_pre.render_embodied_ruler(ev)
    assert "具身智能估值线" in md
    assert "half_option" in md
    assert "8.3x" in md          # 隐含倍数
    assert "3~5x" in md or "3～5x" in md
    assert "银河通用" in md and "星海图" in md  # 对标表
    assert "溢价" in md


def test_hk18c_exit_upside_backward_calc():
    """18C 退出倒算：穹彻 100 亿 → 0.74x(叙事阶段)；50 亿 → 1.47x(叙事边缘)；
    30 亿 → 2.45x(退出空间收窄)；20 亿 → 3.68x(退出锚定价)。"""
    u100 = ai_pre.hk18c_exit_upside(100.0, pre_commercial=True)
    assert abs(u100["multiple"] - 80 * 0.92 / 100) < 1e-9
    assert "叙事阶段" in u100["stage"]

    u50 = ai_pre.hk18c_exit_upside(50.0)
    assert abs(u50["multiple"] - 80 * 0.92 / 50) < 1e-9
    assert "叙事阶段" in u50["stage"]  # 1.47x < 1.5x

    u30 = ai_pre.hk18c_exit_upside(30.0)
    assert "退出空间收窄" in u30["stage"]

    u20 = ai_pre.hk18c_exit_upside(20.0)
    assert abs(u20["multiple"] - 80 * 0.92 / 20) < 1e-9
    assert "退出锚定价" in u20["stage"]

    assert ai_pre.hk18c_exit_upside(None) is None


def test_ai_investment_team_capability_bypasses_to_human():
    """Team capability (能不能把技术落地) is a relationship/execution judgment
    the machine cannot assemble — it must bypass straight to the investment
    committee, never entering 4D-CQ scoring."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "team_capability")
    assert rec["route"] == "BYPASS_TO_HUMAN"
    assert rec["bypassed_to_human"] is True
    assert rec["R"] == 0 and rec["C"] == 0 and rec["Q"] == 0


# ============ 产业链分层 + 退出概率维度（2026-09）============

def test_classify_value_chain_five_layers():
    """五层定位：直接 archetype 优先采信；信号推断；缺数据 fail-closed（不猜）。"""
    assert ai_pre.classify_value_chain({"archetype": "scenario"})["archetype"] == "scenario"
    assert ai_pre.classify_value_chain({"archetype": "data"})["archetype"] == "data"
    assert ai_pre.classify_value_chain({"sells_components": True})["archetype"] == "component"
    assert ai_pre.classify_value_chain({"sells_solution_service": True})["archetype"] == "scenario"
    assert ai_pre.classify_value_chain({"sells_model_or_data": True})["archetype"] == "brain"
    assert ai_pre.classify_value_chain(
        {"sells_model_or_data": True, "sells_data_infrastructure": True})["archetype"] == "data"
    assert ai_pre.classify_value_chain({"sells_robot_product": True})["archetype"] == "body"
    assert ai_pre.classify_value_chain({})["archetype"] is None  # fail-closed


def test_classify_manufacturing_three_profiles():
    """制造属性三态：mfg_profile 优先；信号推断；缺数据 fail-closed。"""
    assert ai_pre.classify_manufacturing({"mfg_profile": "platform"})["mfg_profile"] == "platform"
    assert ai_pre.classify_manufacturing({"platform_business": True})["mfg_profile"] == "platform"
    assert ai_pre.classify_manufacturing({"moat_in_algorithm_data": True})["mfg_profile"] == "intelligent"
    assert ai_pre.classify_manufacturing({"hardware_revenue_dominant": True})["mfg_profile"] == "manufacturing"
    assert ai_pre.classify_manufacturing({})["mfg_profile"] is None  # fail-closed


def test_backer_profile_industrial_soe_financial():
    """机构接盘画像：有产业资本→并购上调；有国资→IPO护航；纯财务→二级流动性风险；
    未收录→fail-closed。"""
    p = ai_pre.backer_profile("帕西尼感知")
    assert p["has_industrial_backer"] is True  # 比亚迪(产业) + 奇绩(财务)
    assert "并购退出概率上调" in p["exit_liquidity"]

    u = ai_pre.backer_profile("宇树科技")
    assert u["has_industrial_backer"] is True  # 美团/蚂蚁/顺为
    assert u["has_soe_backer"] is True         # 中网投/北京机器人产业基金

    x = ai_pre.backer_profile("不存在的标的")
    assert x["backers"] == []
    assert x["has_industrial_backer"] is False
    assert "未知" in x["exit_liquidity"]


def test_exit_probability_policy_attitude():
    """退出概率：component/scenario 欢迎高；body 分盈利/叙事；brain 分应用；缺层 fail-closed。"""
    assert ai_pre.exit_probability(archetype="component")["probability"] == "高"
    assert ai_pre.exit_probability(archetype="scenario")["probability"] == "高"
    assert ai_pre.exit_probability(archetype="body", profitable=True)["probability"] == "高"
    assert ai_pre.exit_probability(archetype="body", profitable=False)["probability"] == "低"
    assert ai_pre.exit_probability(archetype="brain", commercial_validation=True)["probability"] == "中"
    assert ai_pre.exit_probability(archetype="brain", commercial_validation=False)["probability"] == "低"
    assert ai_pre.exit_probability(archetype="unknown")["probability"] == "低"  # fail-closed


def test_cn_embodied_cycle_stage_and_demand_anchor():
    """产业周期：玩家过剩+价格战→洗牌前夜；过剩无价格战→泡沫；缺数据→indeterminate。"""
    ev = ai_pre.cn_embodied_cycle(player_count=300, price_war_started=True, demand_validated=False)
    assert ev["stage"] == "shakeout_eve"
    assert "需求锚缺失" in ev["note"]

    ev2 = ai_pre.cn_embodied_cycle(player_count=300, price_war_started=False, demand_validated=True)
    assert ev2["stage"] == "bubble"

    ev3 = ai_pre.cn_embodied_cycle(player_count=50, price_war_started=False, demand_validated=True)
    assert ev3["stage"] == "startup"

    assert ai_pre.cn_embodied_cycle()["stage"] == "indeterminate"  # fail-closed


def test_render_value_chain_exit_report_outputs_markdown():
    """渲染函数：五维报告含层级/制造属性/周期/退出概率，标的库命中交叉核对。"""
    ev = {
        "target_name": "极智嘉",
        "archetype": "scenario",
        "mfg_profile": "manufacturing",
        "player_count": 300, "price_war_started": True, "demand_validated": True,
        "profitable": None, "commercial_validation": True,
    }
    md = ai_pre.render_value_chain_exit_report(ev)
    assert "产业链五层定位" in md
    assert "下游场景" in md
    assert "制造属性" in md
    assert "产业周期" in md
    assert "退出概率" in md
    assert "高" in md
    assert "标的库收录" in md  # 极智嘉在标的库，交叉核对
