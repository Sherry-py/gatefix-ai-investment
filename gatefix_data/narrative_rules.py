"""
gatefix_data/narrative_rules.py —— Layer 0 叙事筛选规则表（2026-09 校准）

把八轮新能源×AI 调研收敛出的叙事筛选规则，编码成确定性常量：
  1. NARRATIVE_RED_FLAGS    八条财务红旗（任一命中即"财务逻辑不成立"）
  2. ARCHETYPES             四原型（AI 创造 alpha 的四个位置）
  3. CAPITAL_ROLES          三种钱（链主/国资/财务）
  4. ARCHETYPE_CAPITAL_TIER 原型 × 资本角色 → 风险档（确定性查表）

判定函数 narrative_screen / score_narrative_screen 在
preconditions/ai_investment.py，与本包解耦——数据一处更新、全量生效。

方法论来源：2026-09 新能源×AI 调研（粤电力/协鑫能科/中科类脑/五环绿能等真实样本）
+ NVIDIA Ian Buck《tokens per MW 判据》（AI Infra Summit 2026）。
"""

# —— 八条财务红旗（bool，任一命中即红线条目）——
NARRATIVE_RED_FLAGS = [
    ("redflag_revenue_share_low", "AI/算力收入占营收<5%，但对外叙事中AI占比≥50%"),
    ("redflag_unit_economics", "AI 业务 ROIC < 资金成本（投入 vs 产出对不上）"),
    ("redflag_cashflow_mismatch", "利润表有AI收入，经营现金流无对应增量（应收/补贴/关联）"),
    ("redflag_related_party", "AI 收入来自关联方/同一控制人/链内互采"),
    ("redflag_rd_disguise", "研发费用实为项目交付/集成成本（把实施当研发）"),
    ("redflag_customer_concentration", "收入靠少数大客户/政府示范项目，非分散付费"),
    ("redflag_capex_divergence", "宣布AI转型后capex暴增，但收入/现金流不跟"),
    ("redflag_valuation_divergence", "市值/估值靠AI标签拿高倍，基本面不支撑"),
]

# —— 四原型（AI 创造 alpha 的四个位置）——
ARCHETYPES = ("labor_substitute", "physical_optimize", "new_supply", "certification")
ARCHETYPE_LABELS = {
    "labor_substitute": "替代稀缺人力（判断型）",
    "physical_optimize": "优化物理系统（可对账型）",
    "new_supply": "创造新供给（产品型）",
    "certification": "认证/信任/合规（裁判型）",
}

# —— 三种钱（资本角色）——
CAPITAL_ROLES = ("chain_master", "soe", "financial")
CAPITAL_ROLE_LABELS = {
    "chain_master": "链主（买供应链位置/订单）",
    "soe": "国资（买政策账：落地/就业/税收）",
    "financial": "财务（买IRR）",
}

# —— 原型 × 资本角色 → 风险档（确定性查表）——
# alpha_high = 最守得住（认证不能自证，谁买都稳）；alpha = 可对账；
# beta = 壁垒中等；beta_weak = 最弱（产品型+财务方，大厂可碾压，财务方最危险）。
ARCHETYPE_CAPITAL_TIER = {
    ("certification", "chain_master"): "alpha_high",
    ("certification", "soe"): "alpha_high",
    ("certification", "financial"): "alpha_high",
    ("physical_optimize", "chain_master"): "alpha",
    ("physical_optimize", "soe"): "alpha",
    ("physical_optimize", "financial"): "alpha",
    ("labor_substitute", "chain_master"): "alpha",
    ("labor_substitute", "soe"): "alpha",
    ("labor_substitute", "financial"): "beta",
    ("new_supply", "chain_master"): "beta",
    ("new_supply", "soe"): "beta",
    ("new_supply", "financial"): "beta_weak",
}
