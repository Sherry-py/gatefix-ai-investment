"""
preconditions/ai_investment.py —— "GateFix 方法（Xirui Lian Sherry 开发）· 中美绿色基金采用"（case=ai_investment）的
precondition 判定函数（Pᵢ(E,θᵢ) 的具体实现）

这是把判定对象从"某个 agent 动作能不能放行"换到"对某个 AI 项目的投资决策，证据
够不够格放行"的第 4 个 case。判定引擎（gate.py/engine.py）领域无关、零改动，本文件
只提供"AI 投资治理判断标准"这一领域的打分函数——沿用同一套引擎的结构（每个函数输入 evidence dict，输出 R/C/O/Ro/verifiable_ext/notes）。

判断标准分两层：
1. score_invest_governance（投资决策的治理闸门，管得住）：6 项治理证据
   —— 数据合规、备案资质、安全、可控、隐私、跨境合规。
2. score_landing_level（估值锁定的落地闸门，用得上）：5 项落地证据
   —— 生产部署、付费合同、复购、产业嵌入、可量化经济价值；
   落地等级 L0(叙事)→L3(规模复购) 由这 5 项覆盖度体现。

如实说明：这是第一个把投资决策编码成确定性判定规则的 case，尚未经过真实投资
决策验证（n=0）。打分函数的字段划分与阈值是首版，待真实案例跑过后收紧。证据
真实性仍归取证层（人工核实/可信数据源），判定层只判"给定一组声称的证据，质量
够不够格"——这条边界与本仓库其他 case 一致。
"""


def score_invest_governance(evidence: dict) -> dict:
    """投资决策的治理证据闸门（管得住）。evidence 字段（6 项治理证据，每项 True/False/缺省视为未提供）：
    filing_license_verified（算法/大模型备案号可公开查询）、
    data_compliance_verified（训练数据来源合法且有授权）、
    safety_certified（安全认证/第三方检测）、
    controllability_data_present（远程介入率/故障率等可控性数据）、
    privacy_compliance_verified（数据采集隐私合规）、
    cross_border_compliance_verified（跨境数据/技术合规）；
    另有 compliance_before_operations（先合规后运营的顺序）、
    evidence_source_verified（证据来源第三方核验 vs 自报）、
    governance_gap_externally_verifiable（治理缺口能否靠外部核查补齐，决定 AUTO_REPAIR）。"""
    gov_dims = [
        bool(evidence.get("filing_license_verified")),
        bool(evidence.get("data_compliance_verified")),
        bool(evidence.get("safety_certified")),
        bool(evidence.get("controllability_data_present")),
        bool(evidence.get("privacy_compliance_verified")),
        bool(evidence.get("cross_border_compliance_verified")),
    ]
    covered = sum(gov_dims)
    C = covered / len(gov_dims)  # Coverage：6 项治理证据的覆盖度

    # Relevance：备案 + 数据合规是治理红线，缺失直接打低分——不是"证据填得全不全"，
    # 是"这个项目能不能被管住"的前提本身站不站得住。
    red_line_ok = bool(evidence.get("filing_license_verified")) and bool(
        evidence.get("data_compliance_verified")
    )
    R = 1.0 if red_line_ok else 0.2

    O = 1.0 if evidence.get("compliance_before_operations") else 0.4
    Ro = 1.0 if evidence.get("evidence_source_verified") else 0.3

    verifiable_ext = bool(evidence.get("governance_gap_externally_verifiable", True))

    names = ["备案", "数据合规", "安全", "可控", "隐私", "跨境"]
    detail = "/".join(
        ("✓" if gov_dims[i] else "缺") + names[i] for i in range(len(names))
    )
    notes = (
        f"治理证据覆盖 {covered}/6（{detail}）；"
        f"红线（备案+数据合规）{'通过' if red_line_ok else '未通过'}；"
        f"证据来源{'第三方核验' if evidence.get('evidence_source_verified') else '自报'}；"
        f"顺序{'先合规后运营' if evidence.get('compliance_before_operations') else '未确认先合规'}"
    )
    return dict(R=R, C=C, O=O, Ro=Ro, verifiable_ext=verifiable_ext, notes=notes)


def score_landing_level(evidence: dict) -> dict:
    """估值锁定的落地证据闸门（用得上）。evidence 字段（5 项落地证据，每项 True/False/缺省视为未提供）：
    production_deployed（生产环境部署/上线记录，L1 工程化的门槛）、
    paying_contracts_verified（盖章付费合同已核实，L2 应用落地的红线之一）、
    industry_embedded（嵌入真实产业环节，L2）、
    economic_value_quantified（可量化经济价值：收入/成本节约，L2）、
    repeat_orders（复购/续约，L3 规模复购的门槛）；
    另有 delivery_before_repeat_claim（先交付后声称复购的顺序）、
    contract_evidence_verified_third_party（合同证据第三方核实 vs 自报）、
    landing_gap_externally_verifiable（落地缺口能否靠外部核查补齐）。

    落地等级由覆盖度体现：5/5≈L3 规模复购；3-4/5≈L2 应用落地；2/5≈L1 工程化；
    0-1/5≈L0 叙事。"""
    land_dims = [
        bool(evidence.get("production_deployed")),
        bool(evidence.get("paying_contracts_verified")),
        bool(evidence.get("industry_embedded")),
        bool(evidence.get("economic_value_quantified")),
        bool(evidence.get("repeat_orders")),
    ]
    covered = sum(land_dims)
    C = covered / len(land_dims)  # Coverage：5 项落地证据的覆盖度

    # Relevance：真实部署 + 已核实的付费合同，是"落地"的两条红线。
    red_line_ok = bool(evidence.get("production_deployed")) and bool(
        evidence.get("paying_contracts_verified")
    )
    R = 1.0 if red_line_ok else 0.2

    O = 1.0 if evidence.get("delivery_before_repeat_claim") else 0.4
    Ro = 1.0 if evidence.get("contract_evidence_verified_third_party") else 0.3

    verifiable_ext = bool(evidence.get("landing_gap_externally_verifiable", True))

    level = "L3" if covered == 5 else ("L2" if covered >= 3 else ("L1" if covered == 2 else "L0"))
    names = ["部署", "付费合同", "产业嵌入", "经济价值", "复购"]
    detail = "/".join(
        ("✓" if land_dims[i] else "缺") + names[i] for i in range(len(names))
    )
    notes = (
        f"落地证据覆盖 {covered}/5（{detail}）；"
        f"落地等级(已核验)≈{level}；"
        f"红线（部署+付费合同）{'通过' if red_line_ok else '未通过'}；"
        f"合同证据{'第三方核实' if evidence.get('contract_evidence_verified_third_party') else '自报'}"
    )
    return dict(R=R, C=C, O=O, Ro=Ro, verifiable_ext=verifiable_ext, notes=notes)


def repair_invest_governance(evidence: dict) -> dict:
    """AUTO_REPAIR：备案/数据合规缺口可外部核查——模拟"去查一遍公开备案系统/索要数据
    授权证明"。只补可外部核查的字段，不碰安全认证/可控性等需要现场核实的字段。"""
    new_evidence = dict(evidence)
    new_evidence["filing_license_verified"] = True
    new_evidence["data_compliance_verified"] = True
    new_evidence["evidence_source_verified"] = True
    return new_evidence


def repair_landing_level(evidence: dict) -> dict:
    """AUTO_REPAIR：付费合同缺口可外部核查——模拟"要求项目方提供盖章合同原件"。
    只补合同核实，不碰复购/经济价值等需要时间验证的字段。"""
    new_evidence = dict(evidence)
    new_evidence["paying_contracts_verified"] = True
    new_evidence["contract_evidence_verified_third_party"] = True
    return new_evidence


# 供 engine.py 动态查找函数名用
REGISTRY = {
    "score_invest_governance": score_invest_governance,
    "score_landing_level": score_landing_level,
}

REPAIR_REGISTRY = {
    "score_invest_governance": repair_invest_governance,
    "score_landing_level": repair_landing_level,
}
