"""
tests/test_narrative_screen.py —— Layer 0 叙事筛选三态判定 + 业务线拆分 + 政策关联 的回归测试。

预注册 5 个真实样本（2026-09 调研），每个断言确定性 verdict。用 pytest 或
直接 python3 跑（见文件底部 main）。注意：本文件只测【确定性判定层】，不测
LLM 提取层（LLM 提取的证据字段由人工/取证层核实，见 README 边界）。
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from preconditions.ai_investment import narrative_screen, policy_alignment  # noqa: E402


def test_case_1_yuedianli():
    """粤电力A：算力收入0.02%，火电换皮 → NARRATIVE_RED_FLAG（纯叙事）。"""
    ev = {
        "stripped_business_viable": False,  # 删掉"算力"，本质是火电，但火电亏损
        "final_buyer_external": False,      # 算力收入微乎其微，主业火电无链外真实AI买家
        "redflag_revenue_share_low": True,  # 算力收入0.02%
        "redflag_unit_economics": True,     # 1亿投资赚7万利润
    }
    r = narrative_screen(ev, "粤电力A")
    assert r["verdict"] == "NARRATIVE_RED_FLAG", f"粤电力应排除，实得 {r['verdict']}"


def test_case_2_xiexin():
    """协鑫能科：售电/虚拟电厂是真业务，但"算力生态"是叙事 → 混合，需拆线。"""
    ev = {
        "business_lines": [
            {"name": "售电/虚拟电厂", "stripped_business_viable": True,
             "final_buyer_external": True, "redflags": [], "revenue_share": 0.7},
            {"name": "算力生态/算电协同", "stripped_business_viable": False,
             "final_buyer_external": False, "redflags": ["redflag_revenue_share_low"], "revenue_share": 0.3},
        ],
    }
    r = narrative_screen(ev, "协鑫能科")
    assert r["verdict"] == "MIXED", f"协鑫应是 MIXED，实得 {r['verdict']}"
    assert "售电/虚拟电厂" in r["true_lines"]


def test_case_3_zhongke():
    """中科类脑：能源AI老业务是真，算电协同是叙事 → MIXED。"""
    ev = {
        "business_lines": [
            {"name": "能源AI(变电站运维)", "stripped_business_viable": True,
             "final_buyer_external": True, "redflags": [], "revenue_share": 0.5},
            {"name": "算电协同/Token工厂", "stripped_business_viable": False,
             "final_buyer_external": False, "redflags": ["redflag_capex_divergence"], "revenue_share": 0.5},
        ],
    }
    r = narrative_screen(ev, "中科类脑")
    assert r["verdict"] == "MIXED", f"中科类脑应是 MIXED，实得 {r['verdict']}"
    assert r["has_next_buyer"] is True  # 中移动+中车 = 产业方接盘
    assert "中国移动(中移资本)" in r["industrial_backers"]


def test_case_4_wuhuan():
    """五环绿能：全球风机位置数据，裸数据不成立，本质工程咨询 → 包装B。"""
    ev = {
        "stripped_business_viable": False,  # 裸数据不值钱，需封装进可研/技改/回收服务
        "final_buyer_external": False,      # 数据在链内自己用，无链外真实付费买家
        "redflag_valuation_divergence": True,  # 数据资产估值靠"AI大数据"叙事
    }
    r = narrative_screen(ev, "五环绿能")
    assert r["verdict"] == "NARRATIVE_RED_FLAG", f"五环绿能应排除，实得 {r['verdict']}"


def test_case_5_guangchusan():
    """7.5MW 光储算一体化：光储是真（链外业主付费），算力是叙事 → MIXED。"""
    ev = {
        "business_lines": [
            {"name": "光储(光伏+储能)", "stripped_business_viable": True,
             "final_buyer_external": True, "redflags": [], "revenue_share": 0.8},
            {"name": "算力(Token)", "stripped_business_viable": False,
             "final_buyer_external": False, "redflags": ["redflag_cashflow_mismatch"], "revenue_share": 0.2},
        ],
    }
    r = narrative_screen(ev, "光储算项目")
    assert r["verdict"] == "MIXED", f"光储算应是 MIXED，实得 {r['verdict']}"
    assert "光储(光伏+储能)" in r["true_lines"]


def test_policy_architect_wrapper():
    """政策-业务关联：宁德(先知+产业链)=architect；粤电力(跟风+无链)=wrapper。"""
    r1 = policy_alignment({"policy_name": "双碳", "policy_usage_mode": "architect",
                           "has_chain_architecture": True}, "宁德时代")
    assert r1["verdict"] == "architect", f"宁德应 architect，实得 {r1['verdict']}"
    assert r1["policy_year_source"] == "查表"  # 政策年份查表，非 LLM
    assert r1["business_layout_time"] == 2011  # 公司布局年份查表

    r2 = policy_alignment({"policy_name": "东数西算", "policy_usage_mode": "wrapper",
                           "has_chain_architecture": False}, "粤电力A")
    assert r2["verdict"] == "wrapper", f"粤电力应 wrapper，实得 {r2['verdict']}"


def test_fail_closed():
    """数据缺失 → fail-closed：不判 PASS，不静默放行。"""
    assert narrative_screen({})["verdict"] == "NARRATIVE_RED_FLAG"
    assert policy_alignment({})["verdict"] == "indeterminate"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} 通过")
    sys.exit(0 if passed == len(tests) else 1)
