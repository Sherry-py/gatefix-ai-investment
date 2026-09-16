"""
preconditions/ai_investment.py —— "GateFix 方法（Xirui Lian Sherry 开发）· 中美绿色基金采用"（case=ai_investment）的
precondition 判定函数（Pᵢ(E,θᵢ) 的具体实现）

这是把判定对象从"某个 agent 动作能不能放行"换到"对某个 AI 项目的投资决策，证据
够不够格放行"的第 4 个 case。判定引擎（gate.py/engine.py）领域无关、零改动，本文件
只提供"AI 投资治理判断标准"这一领域的打分函数——沿用同一套引擎的结构（每个函数输入 evidence dict，输出 R/C/O/Ro/verifiable_ext/notes）。

判断标准分三层：
1. score_invest_governance（投资决策的治理闸门，管得住）：6 项治理证据
   —— 数据合规、备案资质、安全、可控、隐私、跨境合规。
2. score_landing_level（估值锁定的落地闸门，用得上）：5 项落地证据
   —— 生产部署、付费合同、复购、产业嵌入、可量化经济价值；
   落地等级 L0(叙事)→L3(规模复购) 由这 5 项覆盖度体现。
3. score_valuation_sanity（独立估值合理性闸门，值不值）：4 项估值证据
   —— 自报估值披露、估值方法、对标可查证、独立区间推导；
   红线 = 自报估值落在独立推导区间内（valuation_in_range 确定性计算，
   不经过 LLM）。见《GateFix赛道层与估值闸门_设计文档》§3.4。

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


VALUATION_TOLERANCE = 0.20  # ±20% 容忍带，吸收估值数值取整/口径差异


def valuation_in_range(claimed, low, high, tol=VALUATION_TOLERANCE):
    """确定性判定：自报估值是否落在独立推导的区间内（带 ±tol 容忍带）。
    数据缺失/非法/非正 → False（fail-closed，不静默当"合理"放行）。"""
    if claimed is None or low is None or high is None:
        return False
    try:
        claimed, low, high = float(claimed), float(low), float(high)
    except (TypeError, ValueError):
        return False
    if low <= 0 or high <= 0:
        return False
    return low * (1 - tol) <= claimed <= high * (1 + tol)


def score_valuation_sanity(evidence: dict) -> dict:
    """独立估值合理性证据闸门（值不值）。evidence 字段（4 项估值证据，每项
    True/False/缺省视为未提供）：
    claimed_valuation_disclosed（公司披露了自报估值/融资金额）、
    valuation_methodology_disclosed（估值方法/依据有披露）、
    comps_publicly_verifiable（对标公司数据可公开查证）、
    independent_range_derived（独立区间成功推导，且置信度不低）；
    红线 = valuation_within_independent_range（自报估值落在独立区间内，
    由 valuation_in_range() 确定性计算，不经过 LLM）；
    另有 independent_before_claimed（先独立推导、后比对自报的顺序）、
    valuation_source_verified（估值来源第三方 vs 自报）、
    valuation_gap_externally_verifiable（估值缺口能否靠外部核查补齐，决定
    AUTO_REPAIR）。
    显示字段（仅用于 notes，不参与打分）：claimed_value / range_low /
    range_high / vs_claimed。"""
    val_dims = [
        bool(evidence.get("claimed_valuation_disclosed")),
        bool(evidence.get("valuation_methodology_disclosed")),
        bool(evidence.get("comps_publicly_verifiable")),
        bool(evidence.get("independent_range_derived")),
    ]
    covered = sum(val_dims)
    C = covered / len(val_dims)  # Coverage：4 项估值证据的覆盖度

    # Relevance：自报估值落在独立区间内是"这估值站不站得住"的前提本身。
    red_line_ok = bool(evidence.get("valuation_within_independent_range"))
    R = 1.0 if red_line_ok else 0.2

    O = 1.0 if evidence.get("independent_before_claimed") else 0.4
    Ro = 1.0 if evidence.get("valuation_source_verified") else 0.3

    verifiable_ext = bool(evidence.get("valuation_gap_externally_verifiable", True))

    names = ["自报估值", "估值方法", "对标可查证", "独立区间"]
    detail = "/".join(
        ("✓" if val_dims[i] else "缺") + names[i] for i in range(len(names))
    )
    claimed = evidence.get("claimed_value")
    low = evidence.get("range_low")
    high = evidence.get("range_high")
    if claimed is not None and low is not None and high is not None:
        price_line = f"自报 {claimed} 亿 vs 独立区间 [{low},{high}] 亿"
    else:
        price_line = "自报/独立区间数据缺失"
    notes = (
        f"估值证据覆盖 {covered}/4（{detail}）；{price_line}；"
        f"红线（落在独立区间内）{'通过' if red_line_ok else '未通过'}；"
        f"数据来源{'第三方' if evidence.get('valuation_source_verified') else '自报'}；"
        f"顺序{'先独立推导后比对' if evidence.get('independent_before_claimed') else '未确认独立推导'}"
    )
    return dict(R=R, C=C, O=O, Ro=Ro, verifiable_ext=verifiable_ext, notes=notes)


def repair_valuation_sanity(evidence: dict) -> dict:
    """AUTO_REPAIR：对标数据可公开查证——模拟"去公开融资数据库补对标公司估值"。
    只补可外部核查的字段（对标可查证/数据来源第三方），绝不修改自报估值、
    独立区间或"落在区间内"的判定——真溢价不能靠翻 bool 修复，改数字等于做账。"""
    new_evidence = dict(evidence)
    new_evidence["comps_publicly_verifiable"] = True
    new_evidence["valuation_source_verified"] = True
    return new_evidence


# ============================================================
# 国内具身智能赛道估值法（赛道估值闸门 · 2026-08 校准）
# ============================================================
# 这是把"国内当前对这个赛道（具身智能）怎么估值"编码成确定性规则的层。
# 定价逻辑来源（2026-08 公开报道，见同名设计文档）：
#   《具身智能的大脑，200亿一张门票》(界面新闻, 2026-08-10)
#   《宇树4000亿之后，具身智能该如何定价》(第一财经, 2026-08-20)
#   《具身智能"200亿俱乐部"：8家、吸金千亿》(投中网, 2026-07-30)
#
# 国内对这个赛道的估值，本质是「三把尺子 + 一张门票 + 一道上市门槛」，
# 且同一估值对谁成立，取决于资本穿透（见《GateFix资本穿透层_思考逻辑v2》）。
#   ① 融资体量锚：估值 ≈ 累计融资额 × 大脑派倍数（3~5x）——"估值分层反映融了多少资"
#   ② 门票锚：大脑派"200亿一张门票"——加入"200亿俱乐部"的市场共识中枢
#   ③ PS 锚：估值 ≈ 年收入 × 24.7x——宇树发行基准，只对本体派/有营收者成立
#   ④ 上市门槛锚：港股 18C 未商业化 150 亿港元 ≈ 140 亿人民币——"上市门票"
# 与 score_valuation_sanity 的分工：san 是"自报估值 vs 外部 comps 区间"的通用价格闸；
# 本函数是"派别 × 锚"的国内赛道定价法，输出多锚对照 + 落在哪根尺子上。

# —— 校准常数（单位统一：亿元人民币；倍数经 2026-08 样本校准）——
TICKET_ANCHOR_BRAIN = 200.0      # 大脑派"200亿俱乐部"门票价（市场共识中枢）
# 港股 18C 未商业化门槛：2022 咨询稿 150 亿港元 → 2023 定稿 100 亿 → 2024-08 降门槛 80 亿港元。
# 此处按现行 80 亿港元 × 0.92 ≈ 73.6 亿人民币（与《18D》文章口径、hk18c_exit_upside 一致）。
EXIT_ANCHOR_HK18C = 80.0 * 0.92  # 港股 18C 未商业化门槛（现行 80 亿港元 ≈ 73.6 亿人民币）
PS_BODY_BENCHMARK = 24.7         # 宇树发行 PS 基准（发行 420 亿 / 2025 营收 16.99 亿）
# 大脑派"累计融资 → 估值"倍数（样本：银河通用 ~70亿→~210亿≈3.0x；千寻 ~50亿→~200亿≈4.0x；
# 星海图 两笔 30亿→~200亿≈6.7x，属高密度融资溢价样本）。稳健取 3x（低）/ 5x（高）。
FUNDING_MULTIPLE_LOW = 3.0
FUNDING_MULTIPLE_HIGH = 5.0

ARCHETYPES = ("body", "brain", "component")  # 本体派 / 大脑派 / 关键部件派


def _num(v):
    """安全转 float；None/非法/非正 → None（fail-closed，不拿坏数据当 0 算）。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def cn_embodied_ai_anchors(*, funding=None, revenue=None, archetype=None):
    """国内具身智能赛道估值法：由（累计融资额, 年收入, 派别）确定性推导四根锚。
    返回 dict，任一输入缺失/非法时对应锚为 None。单位：亿元人民币。"""
    f = _num(funding)
    r = _num(revenue)
    anchors = {
        "archetype": archetype if archetype in ARCHETYPES else None,
        "funding_anchor": None,   # (low, high) 融资体量锚
        "ticket_anchor": None,    # 门票锚（仅大脑/关键部件派）
        "ps_anchor": None,        # PS 锚（有营收才成立）
        "exit_anchor": EXIT_ANCHOR_HK18C,   # 上市门槛对全派别成立
        "financial_range": None,  # 金融尺子区间 = funding_anchor ∪ ps_anchor 的上下界
    }
    if anchors["archetype"] in ("brain", "component"):
        anchors["ticket_anchor"] = TICKET_ANCHOR_BRAIN
        if f is not None:
            anchors["funding_anchor"] = (f * FUNDING_MULTIPLE_LOW, f * FUNDING_MULTIPLE_HIGH)
    if r is not None:
        anchors["ps_anchor"] = r * PS_BODY_BENCHMARK
    bounds = []
    if anchors["funding_anchor"]:
        bounds.extend(anchors["funding_anchor"])
    if anchors["ps_anchor"]:
        bounds.append(anchors["ps_anchor"])
    if bounds:
        anchors["financial_range"] = (min(bounds), max(bounds))
    return anchors


def track_ruler_zone(claimed, anchors, tol=VALUATION_TOLERANCE):
    """确定性判定：自报估值落在国内赛道定价法的哪根尺子上。
    返回 (zone, price_rel_on_financial)：
      zone ∈ {"within_financial", "half_option", "at_ceiling", "above_ceiling", "indeterminate"}
      price_rel_on_financial ∈ {"折价","合理","溢价"}（相对金融尺子区间，可能 None）。
    语义：within_financial=金融尺子可解释；half_option=金融尺子之上、派别上限之下
    （半期权区，需资本穿透决定按落地锚还是金融退出锚看）；at_ceiling=站上派别上限
    （大脑/部件派=200亿门票价，本体派=PS锚）；above_ceiling=无锚溢价；indeterminate=锚推不出。"""
    c = _num(claimed)
    if c is None:
        return "indeterminate", None
    fin = anchors.get("financial_range")
    # 派别上限（"无锚溢价"的分界线）：大脑/部件派 = 门票价；本体派 = PS 锚
    ceiling = anchors.get("ticket_anchor") or anchors.get("ps_anchor")

    if fin is not None and c <= fin[1] * (1 + tol):
        rel = "折价" if c < fin[0] * (1 - tol) else "合理"
        return "within_financial", rel
    if ceiling is not None:
        if c < ceiling * (1 - tol):
            return "half_option", "溢价"
        if c <= ceiling * (1 + tol):
            return "at_ceiling", "合理"
        return "above_ceiling", "溢价"
    return "indeterminate", None   # 无金融尺子也无上限锚（数据不足）


def score_track_valuation(evidence: dict) -> dict:
    """国内赛道估值合理性闸门（赛道定价法）。evidence 覆盖字段（4 项，bool）：
    archetype_identified（派别已识别：body/brain/component）、
    cumulative_funding_disclosed（累计融资额已披露）、
    revenue_disclosed（年收入已披露）、
    marginal_pricer_identified（边际定价者/资本性质已识别，接资本穿透层）；
    红线 = valuation_within_financial（自报估值落在金融尺子内——融资体量锚∪PS锚的区间，
    由 track_ruler_zone() 确定性计算，不经过 LLM）。超出金融尺子（half_option/at_ceiling/
    above_ceiling）即"金融定价不成立"，需资本穿透层决定换哪把尺子（落地锚/战略期权/门票）；
    另有 anchors_before_claimed（先推导锚、后比对自报，按构造 True）、
    anchor_source_verified（锚数据来源第三方 vs 自报）、
    track_gap_externally_verifiable（缺口能否外部核查，决定 AUTO_REPAIR）。
    显示字段（仅用于 notes，不参与打分）：archetype / cumulative_funding / annual_revenue /
    claimed_valuation / ticket_anchor / exit_anchor / financial_range_low / financial_range_high。"""
    track_dims = [
        bool(evidence.get("archetype_identified")),
        bool(evidence.get("cumulative_funding_disclosed")),
        bool(evidence.get("revenue_disclosed")),
        bool(evidence.get("marginal_pricer_identified")),
    ]
    covered = sum(track_dims)
    C = covered / len(track_dims)  # Coverage：4 项赛道定价证据的覆盖度

    archetype = evidence.get("archetype")
    anchors = cn_embodied_ai_anchors(
        funding=evidence.get("cumulative_funding"),
        revenue=evidence.get("annual_revenue"),
        archetype=archetype,
    )
    zone, price_rel = track_ruler_zone(evidence.get("claimed_valuation"), anchors)

    # Relevance 红线：自报估值落在金融尺子内（金融定价成立）。half_option/at_ceiling/
    # above_ceiling 都是"金融尺子之外的溢价"——需要换尺子（落地锚/战略期权/门票），
    # 由资本穿透层接续判定；indeterminate（锚推不出）fail-closed 记未通过。
    red_line_ok = zone == "within_financial"
    R = 1.0 if red_line_ok else 0.2

    O = 1.0 if evidence.get("anchors_before_claimed") else 0.4
    Ro = 1.0 if evidence.get("anchor_source_verified") else 0.3
    verifiable_ext = bool(evidence.get("track_gap_externally_verifiable", True))

    names = ["派别", "累计融资", "收入", "边际定价者"]
    detail = "/".join(
        ("✓" if track_dims[i] else "缺") + names[i] for i in range(len(names))
    )
    claimed = evidence.get("claimed_valuation")
    fin = anchors["financial_range"]
    line = []
    if fin:
        line.append(f"金融尺子[{fin[0]:g},{fin[1]:g}]亿")
    if anchors["ticket_anchor"]:
        line.append(f"门票{anchors['ticket_anchor']:g}亿")
    line.append(f"上市门槛{anchors['exit_anchor']:g}亿")
    if claimed is not None:
        # 相对门票价的位置（门票尺子是"大脑派200亿俱乐部"的市场共识锚）
        ticket = anchors["ticket_anchor"]
        ticket_rel = ""
        if ticket is not None:
            if claimed < ticket * (1 - VALUATION_TOLERANCE):
                ticket_rel = "，相对门票折价"
            elif claimed > ticket * (1 + VALUATION_TOLERANCE):
                ticket_rel = "，相对门票溢价"
            else:
                ticket_rel = "，站在门票价"
        line.append(f"自报{claimed:g}亿→{zone}{ticket_rel}")
    notes = (
        f"赛道定价证据覆盖 {covered}/4（{detail}）；"
        f"{'，'.join(line)}；"
        f"红线（落在金融尺子内）{'通过' if red_line_ok else '未通过'}；"
        f"锚数据{'第三方' if evidence.get('anchor_source_verified') else '自报'}；"
        f"顺序{'先推导锚后比对' if evidence.get('anchors_before_claimed') else '未确认先推导'}"
    )
    return dict(R=R, C=C, O=O, Ro=Ro, verifiable_ext=verifiable_ext, notes=notes,
                zone=zone, price_rel=price_rel, anchors=anchors)


def repair_track_valuation(evidence: dict) -> dict:
    """AUTO_REPAIR：锚数据可公开查证——模拟"去公开融资库/工商/港股规则补对标数据"。
    只补可外部核查的字段（累计融资/收入可查证、锚来源第三方），绝不修改自报估值、
    派别或锚推导结果——真溢价不能靠翻 bool 修复，改数字等于做账。"""
    new_evidence = dict(evidence)
    new_evidence["cumulative_funding_disclosed"] = True
    new_evidence["revenue_disclosed"] = True
    new_evidence["anchor_source_verified"] = True
    return new_evidence


# 具身智能"大脑/关键部件"派的估值线对标（2026-08 公开样本，单位：亿元）
# 用途：把"这家公司落在哪根尺子上"升级成"它要求的隐含融资倍数是赛道的几倍"。
EMBODIED_REFERENCE = [
    {"name": "银河通用", "funding": 70.0, "valuation": 210.0, "archetype": "brain", "note": "融资体量锚 3.0x"},
    {"name": "千寻智能", "funding": 50.0, "valuation": 200.0, "archetype": "brain", "note": "融资体量锚 4.0x"},
    {"name": "星海图", "funding": 30.0, "valuation": 200.0, "archetype": "brain", "note": "高密度融资溢价 6.7x"},
    {"name": "宇树(本体派)", "funding": None, "valuation": 420.0, "archetype": "body", "note": "PS 锚 24.7x（发行基准）"},
]


def embodied_implied_multiple(funding, claimed):
    """隐含融资倍数 = 自报估值 / 累计融资。缺失/非法 → None（fail-closed）。"""
    f = _num(funding)
    c = _num(claimed)
    if f is None or c is None:
        return None
    return c / f


# 港股 18C 退出门槛（用于"叙事阶段"倒算；2024-08 联交所+证监会联合降门槛后的现行口径）
# 注：2023-03 原规则为 已商业化 60 / 未商业化 100 亿港元；2024-08 降门槛 → 40 / 80。
# 与《18D》文章口径一致。GateFix 旧设计文档的"150 亿港元≈140 亿人民币"是 2022 咨询稿，
# 已过时——此处以 40/80 为准，倒算更保守（门槛更低 = 退出空间更小 = 更早判"叙事阶段"）。
HK18C_THRESHOLDS_HKD = {"commercial": 40.0, "pre_commercial": 80.0}
HKD_TO_CNY = 0.92  # 近似汇率（人民币计价统一用）


def hk18c_exit_upside(current_valuation_cny, *, pre_commercial=True):
    """18C 退出倒算：当前投后估值（人民币）→ 18C 门槛/当前估值 = 至少退出倍数。
    倍数 < 1.5 → 叙事阶段（18C 倒算不成立，只能赌上市后再涨）；
    1.5~3 → 退出空间收窄（安全边际薄）；≥3 → 退出锚定价成立（至少 3x 退出空间）。
    缺数据/非法 → None（fail-closed）。"""
    cur = _num(current_valuation_cny)
    if cur is None or cur <= 0:
        return None
    threshold_hkd = HK18C_THRESHOLDS_HKD["pre_commercial" if pre_commercial else "commercial"]
    threshold_cny = threshold_hkd * HKD_TO_CNY
    multiple = threshold_cny / cur
    if multiple >= 3.0:
        stage = "退出锚定价（18C 倒算 ≥3x）"
    elif multiple >= 1.5:
        stage = "退出空间收窄（1.5~3x，安全边际薄）"
    else:
        stage = "叙事阶段（18C 倒算不成立，只能赌上市后再涨）"
    return dict(threshold_hkd=threshold_hkd, threshold_cny=threshold_cny,
                multiple=multiple, stage=stage)


def render_embodied_ruler(evidence: dict, name: str = "") -> str:
    """确定性输出「具身智能估值线」（标尺表达）。把赛道四锚 + 自报估值 + 隐含融资
    倍数画成一条可读的标尺，并对照赛道已验证的 3~5x 融资倍数区间。LLM-free。"""
    title = name or evidence.get("target_name") or evidence.get("archetype") or "（未命名标的）"
    funding = evidence.get("cumulative_funding")
    claimed = evidence.get("claimed_valuation")
    anchors = cn_embodied_ai_anchors(
        funding=funding, revenue=evidence.get("annual_revenue"),
        archetype=evidence.get("archetype"),
    )
    zone, price_rel = track_ruler_zone(claimed, anchors)
    mult = embodied_implied_multiple(funding, claimed)
    upside = hk18c_exit_upside(claimed, pre_commercial=True)

    fin = anchors["financial_range"]
    fin_line = f"{fin[0]:g} ~ {fin[1]:g} 亿（融资体量锚 {FUNDING_MULTIPLE_LOW:g}~{FUNDING_MULTIPLE_HIGH:g}x）" if fin else "推不出（数据缺失）"
    ticket = anchors["ticket_anchor"]
    exit_a = anchors["exit_anchor"]

    # 标尺：金融尺子下界/上界 → 上市门槛 → 门票
    ruler_parts = []
    if fin:
        ruler_parts.append(f"金融尺子 [{fin[0]:g} — {fin[1]:g}] 亿")
    if exit_a:
        ruler_parts.append(f"上市门槛 {exit_a:g} 亿")
    if ticket:
        ruler_parts.append(f"门票 {ticket:g} 亿")
    ruler_line = "  <  ".join(ruler_parts) if ruler_parts else "（锚推不出）"

    mult_line = ""
    if mult is not None:
        band = f"赛道稳健 {FUNDING_MULTIPLE_LOW:g}~{FUNDING_MULTIPLE_HIGH:g}x，最激进星海图 {200/30:.1f}x"
        verdict = "落在区间内" if FUNDING_MULTIPLE_LOW <= mult <= FUNDING_MULTIPLE_HIGH else ("溢价" if mult > FUNDING_MULTIPLE_HIGH else "折价")
        mult_line = f"隐含融资倍数：**{claimed:g} / {funding:g} = {mult:.1f}x**（{band} → {verdict}）"
    else:
        mult_line = "隐含融资倍数：数据缺失，推不出"

    upside_line = ""
    if upside is not None:
        upside_line = (f"18C 退出倒算：{upside['threshold_hkd']:g} 亿港元门槛 ≈ "
                       f"{upside['threshold_cny']:.1f} 亿人民币 / {claimed:g} 亿 = "
                       f"**{upside['multiple']:.2f}x** → {upside['stage']}")
    else:
        upside_line = "18C 退出倒算：数据缺失，推不出"

    # 赛道对标表
    ref_rows = []
    for r in EMBODIED_REFERENCE:
        if r["funding"] is None:
            m = "—"
        else:
            m = f"{r['valuation'] / r['funding']:.1f}x"
        ref_rows.append(f"| {r['name']} | {r['funding'] if r['funding'] is not None else '—'} | {r['valuation']:g} | {m} | {r['note']} |")
    ref_table = "\n".join(ref_rows)

    return (
        f"# {title} · 具身智能估值线（标尺）\n\n"
        f"## 标尺（自报估值落点）\n\n{ruler_line}\n\n"
        f"- 自报/目标：**{claimed:g} 亿** → **{zone}**（{price_rel or '—'}）\n"
        f"- {mult_line}\n"
        f"- {upside_line}\n\n"
        f"## 赛道估值线对照\n\n"
        f"| 公司 | 累计融资(亿) | 估值(亿) | 隐含倍数 | 说明 |\n|---|---|---|---|---|\n"
        f"{ref_table}\n"
    )


# ============================================================
# 算电协同 / AIDC能源 赛道估值法（并购退路定价法 · 2026-09 校准）
# ============================================================
# 这是把"国内当前对算电协同 / AIDC 能源这条赛道怎么估值"编码成确定性规则的层。
# 与具身智能（融资体量/门票/PS/上市门槛四根锚）不同：这一格有真实收入和真实客户、
# 退出走并购（IPO 只占约 5%），因此锚是「并购退路 + 规模天花板 + 二级可比」三根。
# 定价逻辑来源（2026-09 公开报道 + AI赛道投资研究报告，见同名报告）：
#   《AI赛道投资研究报告_202609》（上篇 §6 估值闸门、下篇并购退出推演 §4 评分卡）
#   国联民生证券《科华数据：多产品矩阵充分受益于AIDC基建浪潮》（可比 PE 27/20/16）
# 关键结论（AI赛道投资研究报告原文，全部有据可查）：
#   ① 并购退路锚：产业买方/央国企并购价 PS 3~8x（买方C 央国企 3-5x；阶段一硬件补链期 3-8x）
#   ② 规模天花板：估值 > 20 亿 → 对 A 股买方构成重大资产重组（评分卡红旗#6）
#   ③ 红旗：上一轮投后估值 > 8x 收入 且 收入 < 1 亿 → 并购定价谈不拢（评分卡红旗#1）
#   ④ 二级可比天花板：英维克/麦格米特/盛弘/科华数据 PE 带 16~27x（仅对盈利者成立）
# 与 score_track_valuation（具身智能）的分工：那是"一级市场融资体量/门票定价"；
# 本函数是"并购退路 + 二级可比定价"——同一格一级项目，尺子不同。
# 与 score_valuation_sanity（通用 comps 区间）的分工：sanity 是"自报 vs 外部 comps
# 区间"的通用价格闸；本函数是"派别 × 并购退路锚"的国内赛道定价法。

# —— 校准常数（单位统一：亿元人民币；倍数经 2026-09 样本校准）——
MNA_EXIT_PS_LOW = 3.0           # 并购退路锚下限：央国企买方并购价 PS 3-5x 的下沿
MNA_EXIT_PS_HIGH = 8.0          # 并购退路锚上限：硬件补链期并购价 PS 3-8x 的上沿
MNA_SIZE_CEILING = 20.0         # 估值规模天花板：>20 亿触发重大资产重组（评分卡红旗#6）
MNA_LOW_REVENUE_REDFLAG = 1.0   # 红旗#1 收入阈值：<1 亿（单位：亿元）
LISTED_PE_LOW = 16.0            # 二级可比 2026E PE 下沿（科华数据研报：2024/2025/2026 = 27/20/16）
LISTED_PE_HIGH = 27.0           # 二级可比 2024 PE 上沿（同上，仅对盈利者成立）

AIDC_ARCHETYPES = ("power", "cooling", "storage_green", "software")


def cn_aidc_energy_anchors(*, revenue=None, archetype=None):
    """算电协同 / AIDC能源 赛道估值法：由（年收入, 派别）确定性推导三根锚。
    返回 dict，任一输入缺失/非法时对应锚为 None。单位：亿元人民币。
    派别：power（电源/HVDC/供配电）、cooling（液冷/温控）、
    storage_green（数据中心储能/绿电直供）、software（能效算法/EMS/调度）。"""
    r = _num(revenue)
    anchors = {
        "archetype": archetype if archetype in AIDC_ARCHETYPES else None,
        "mna_anchor": None,              # (low, high) 并购退路锚 PS 3-8x
        "size_ceiling": MNA_SIZE_CEILING,  # 规模天花板（重大资产重组线，全派别成立）
        "listed_pe_band": (LISTED_PE_LOW, LISTED_PE_HIGH),  # 二级可比 PE 带（仅对盈利者成立）
        "red_flag_low_revenue": None,    # 红旗#1：收入 < 1 亿 且 估值 > 8x 收入
        "financial_range": None,         # 金融尺子 = 并购退路锚区间
    }
    if r is not None:
        anchors["mna_anchor"] = (r * MNA_EXIT_PS_LOW, r * MNA_EXIT_PS_HIGH)
        anchors["financial_range"] = anchors["mna_anchor"]
        anchors["red_flag_low_revenue"] = r < MNA_LOW_REVENUE_REDFLAG
    return anchors


def aidc_ruler_zone(claimed, anchors, tol=VALUATION_TOLERANCE):
    """确定性判定：自报估值落在算电协同赛道定价法的哪根尺子上。
    返回 (zone, price_rel_on_financial)：
      zone ∈ {"within_financial", "above_financial", "size_ceiling_breach",
              "red_flag_deadzone", "indeterminate"}
      price_rel_on_financial ∈ {"折价","合理","溢价"}（相对并购退路金融尺子，可能 None）。
    语义：within_financial=落在并购退路 PS 3-8x 内（产业买方接得住）；
    above_financial=超过 8x 收入但 < 20 亿（并购定价谈不拢，需二级天花板/战略期权解释）；
    size_ceiling_breach=超过 20 亿（重大资产重组，A 股买方直接放弃）；
    red_flag_deadzone=收入 < 1 亿 且 估值 > 8x 收入（评分卡红旗#1，双重死区）；
    indeterminate=锚推不出。"""
    c = _num(claimed)
    if c is None:
        return "indeterminate", None
    fin = anchors.get("financial_range")
    ceiling = anchors.get("size_ceiling")
    if fin is None:
        return "indeterminate", None
    # ① 规模天花板优先：>20 亿 → 重大资产重组，A 股买方直接放弃（红旗#6）
    if ceiling is not None and c > ceiling * (1 + tol):
        return "size_ceiling_breach", "溢价"
    # ② 红旗#1：收入 < 1 亿 且 估值 > 8x 收入 → 并购定价谈不拢
    if anchors.get("red_flag_low_revenue") and c > fin[1] * (1 + tol):
        return "red_flag_deadzone", "溢价"
    # ③ 金融尺子：并购退路 PS 3-8x
    if c <= fin[1] * (1 + tol):
        rel = "折价" if c < fin[0] * (1 - tol) else "合理"
        return "within_financial", rel
    # ④ 超过 8x 收入但 < 20 亿 → 并购定价谈不拢
    return "above_financial", "溢价"


def score_aidc_track_valuation(evidence: dict) -> dict:
    """算电协同 / AIDC能源 赛道估值合理性闸门（并购退路定价法）。evidence 覆盖
    字段（4 项，bool）：
    archetype_identified（派别已识别：power/cooling/storage_green/software）、
    revenue_disclosed（年收入已披露）、
    customer_identified（客户是 AIDC 链主已识别：浪潮/工业富联/万国数据等）、
    marginal_pricer_identified（边际定价者/资本性质已识别，接资本穿透层）；
    红线 = valuation_within_financial（自报估值落在并购退路 PS 3-8x 内，
    由 aidc_ruler_zone() 确定性计算，不经过 LLM）。超出金融尺子
    （above_financial/size_ceiling_breach/red_flag_deadzone）即"并购退路不成立"，
    需二级天花板/战略期权/资本穿透层决定换哪把尺子；
    另有 anchors_before_claimed（先推导锚、后比对自报，按构造 True）、
    anchor_source_verified（锚数据来源第三方 vs 自报）、
    track_gap_externally_verifiable（缺口能否外部核查，决定 AUTO_REPAIR）。
    显示字段（仅用于 notes，不参与打分）：archetype / annual_revenue /
    claimed_valuation / mna_anchor / size_ceiling / listed_pe_band。"""
    track_dims = [
        bool(evidence.get("archetype_identified")),
        bool(evidence.get("revenue_disclosed")),
        bool(evidence.get("customer_identified")),
        bool(evidence.get("marginal_pricer_identified")),
    ]
    covered = sum(track_dims)
    C = covered / len(track_dims)  # Coverage：4 项赛道定价证据的覆盖度

    archetype = evidence.get("archetype")
    anchors = cn_aidc_energy_anchors(
        revenue=evidence.get("annual_revenue"),
        archetype=archetype,
    )
    zone, price_rel = aidc_ruler_zone(evidence.get("claimed_valuation"), anchors)

    # Relevance 红线：自报估值落在并购退路内（金融定价成立）。above_financial/
    # size_ceiling_breach/red_flag_deadzone 都是"并购退路之外的溢价"——需要换
    # 尺子（二级天花板/战略期权/资本穿透）；indeterminate（锚推不出）fail-closed 记未通过。
    red_line_ok = zone == "within_financial"
    R = 1.0 if red_line_ok else 0.2

    O = 1.0 if evidence.get("anchors_before_claimed") else 0.4
    Ro = 1.0 if evidence.get("anchor_source_verified") else 0.3
    verifiable_ext = bool(evidence.get("track_gap_externally_verifiable", True))

    names = ["派别", "收入", "AIDC客户", "边际定价者"]
    detail = "/".join(
        ("✓" if track_dims[i] else "缺") + names[i] for i in range(len(names))
    )
    claimed = evidence.get("claimed_valuation")
    fin = anchors["financial_range"]
    pe = anchors["listed_pe_band"]
    line = []
    if fin:
        line.append(f"并购退路[{fin[0]:g},{fin[1]:g}]亿")
    line.append(f"规模天花板{anchors['size_ceiling']:g}亿")
    if pe:
        line.append(f"二级PE{pe[0]:g}~{pe[1]:g}x")
    if claimed is not None:
        line.append(f"自报{claimed:g}亿→{zone}")
    notes = (
        f"赛道定价证据覆盖 {covered}/4（{detail}）；"
        f"{'，'.join(line)}；"
        f"红线（落在并购退路内）{'通过' if red_line_ok else '未通过'}；"
        f"锚数据{'第三方' if evidence.get('anchor_source_verified') else '自报'}；"
        f"顺序{'先推导锚后比对' if evidence.get('anchors_before_claimed') else '未确认先推导'}"
    )
    return dict(R=R, C=C, O=O, Ro=Ro, verifiable_ext=verifiable_ext, notes=notes,
                zone=zone, price_rel=price_rel, anchors=anchors)


def repair_aidc_track_valuation(evidence: dict) -> dict:
    """AUTO_REPAIR：收入/客户可公开查证——模拟"去招投标公告/上市公司供应商名录/
    公开融资库补收入与 AIDC 客户数据"。只补可外部核查的字段（收入可查证、锚来源
    第三方），绝不修改自报估值、派别或锚推导结果——真溢价不能靠翻 bool 修复，
    改数字等于做账。"""
    new_evidence = dict(evidence)
    new_evidence["revenue_disclosed"] = True
    new_evidence["anchor_source_verified"] = True
    return new_evidence


# ============================================================
# 并购退出可能性闸门（M&A Exit Likelihood · 2026-09 校准）
# ============================================================
# 把《AI赛道投资研究报告》下篇 §4「并购适配度评分卡」编码成确定性规则。
# 评分卡来源（研究原文，满分 100，六维度 + 六红旗 + 四级分级）：
#   维度一 财务可并表性 25 ｜ 维度二 产业逻辑单一性 20 ｜ 维度三 股权可交割性 20★
#   维度四 技术可整合性 15 ｜ 维度五 客户可继承性 10 ｜ 维度六 估值可谈性 10★
#   红旗（任一即暂停）6 条；分级：≥80 高确定性 / 65-79 可投需锁条款 / 50-64 仅IPO成立 / <50 不成立
# 与 score_aidc_track_valuation（算电协同赛道估值法）联动：两条估值红旗
# （>8x收入 且 收入<1亿；>20亿重大资产重组）由赛道锚确定性推导，本闸门复用，
# 命中即自动计入红旗，无需重复填。
# 与 score_aidc_track_valuation 的分工：那是"并购退路 PS 3-8x / 规模天花板"的
# 价格轴；本闸门是"这单并购整体成不成立"的适配度轴（六维度 + 红旗）。

# —— 六维度权重（子项 → 分值），满分 100 ——
MNA_FIT_DIMS = [
    ("财务可并表性", [
        ("auditable_revenue", 10, "真实收入可审计"),
        ("gross_margin_not_dilutive", 5, "毛利率不拖累买方"),
        ("profitable_or_near", 10, "已盈利或18个月内可盈利"),
    ]),
    ("产业逻辑单一性", [
        ("acquisition_logic_one_liner", 10, "一句话说清买方为什么必须买"),
        ("buyer_updownstream_fit", 10, "与买方构成上下游或同业"),
    ]),
    ("股权结构可交割性", [
        ("shareholder_count_lt_20", 5, "股东数量<20"),
        ("soe_shareholder_exitable", 5, "无国资股东或国资有退出授权"),
        ("no_repurchase_conflict", 5, "无对赌/回购条款冲突"),
        ("founder_accepts_stock", 5, "创始人持股>25%且接受股票对价"),
    ]),
    ("技术可整合性", [
        ("modular_tech", 8, "技术模块化可插入"),
        ("not_founder_dependent", 7, "不依赖单一创始人"),
    ]),
    ("客户可继承性", [
        ("institutional_customers", 5, "客户是机构关系"),
        ("no_customer_conflict", 5, "客户与买方不冲突"),
    ]),
    ("估值可谈性", [
        ("valuation_below_buyer_bid", 10, "上一轮估值低于买方能给的对价"),
    ]),
]

# 红旗（显式 bool；估值两条红旗由 mna_fit_score 从赛道锚派生）
MNA_REDFLAG_ITEMS = {
    "redflag_soe_gt_30": "国资股东合计>30%且无退出授权",
    "redflag_founder_ipo_only": "创始人只接受IPO退出",
    "redflag_thirdparty_ip": "核心技术依赖第三方授权IP，无法随资产转移",
    "redflag_vie": "存在未清理的红筹/VIE结构",
}

# 标的画像 → 潜在买方 + 并购时间窗（来自研究下篇 §5，确定性查表，供报告输出用）
MNA_TRACK_MAP = {
    "power": ("英维克/麦格米特/盛弘股份/科华数据/欧陆通/阳光电源/宁德时代", "2028–2029"),
    "cooling": ("英维克/高澜股份/申菱环境/川润股份", "2028–2029"),
    "storage_green": ("阳光电源/科华数据/宁德时代", "2028–2029"),
    "software": ("英维克/盛弘股份/科华数据/朗新集团", "2028–2030"),
    "sic": ("紫光国微/士兰微/斯达半导/时代电气/闻泰科技/基本半导体", "2026–2027"),
    "grid_ai": ("国电南瑞/国网信通/朗新集团/四方股份 + 电力央企", "2026–2030"),
    "embodied": ("优必选/越疆/地平线 + 三花智控/拓普集团/汇川技术/绿的谐波", "2027–2028"),
}


def mna_fit_score(evidence: dict) -> dict:
    """并购适配度评分卡（确定性，满分 100）。输入 14 个子项 bool + 4 条显式红旗
    bool；两条估值红旗从（年收入, 自报估值）经赛道锚确定性派生。返回
    score / grade / red_flags / dims（逐维度明细）。"""
    score = 0
    dims = []
    n_items = 0
    n_present = 0
    for dim_name, items in MNA_FIT_DIMS:
        dim_score = 0
        dim_items = []
        for field, weight, label in items:
            n_items += 1
            ok = bool(evidence.get(field))
            if ok:
                score += weight
                dim_score += weight
                n_present += 1
            dim_items.append({"field": field, "label": label, "weight": weight, "ok": ok})
        dims.append({"name": dim_name, "score": dim_score, "items": dim_items})

    red_flags = []
    for field, label in MNA_REDFLAG_ITEMS.items():
        if evidence.get(field):
            red_flags.append(label)
    # 派生估值红旗（复用赛道锚，与 score_aidc_track_valuation 同源）
    rev = _num(evidence.get("annual_revenue"))
    claimed = _num(evidence.get("claimed_valuation"))
    if rev is not None and claimed is not None:
        if rev < MNA_LOW_REVENUE_REDFLAG and claimed > rev * MNA_EXIT_PS_HIGH * (1 + VALUATION_TOLERANCE):
            red_flags.append("上一轮投后估值>8x收入 且 收入<1亿（并购定价谈不拢）")
        if claimed > MNA_SIZE_CEILING * (1 + VALUATION_TOLERANCE):
            red_flags.append("标的估值>20亿（对A股买方构成重大资产重组）")

    if score >= 80:
        grade = "并购退出高确定性"
    elif score >= 65:
        grade = "可投，需在TS中锁定并购触发条款"
    elif score >= 50:
        grade = "仅在IPO路径同时成立时考虑"
    else:
        grade = "并购退出不成立，除非有明确战略买方已表态"

    return dict(score=score, grade=grade, red_flags=red_flags, dims=dims,
                n_items=n_items, n_present=n_present)


def score_mna_exit_likelihood(evidence: dict) -> dict:
    """并购退出可能性证据闸门（4D-CQ 同构）。Coverage = 评分卡 14 个子项覆盖度；
    红线 = 无红旗 且 适配度≥65（并购退出的"前提"成立）；Ordering = 先做适配度、后
    谈估值；Robustness = 第三方核验。
    显示字段（仅用于 notes/报告，不参与打分）：target_name / track / archetype /
    annual_revenue / claimed_valuation。"""
    fit = mna_fit_score(evidence)
    C = fit["n_present"] / fit["n_items"]  # Coverage：14 子项覆盖度

    red_line_ok = (not fit["red_flags"]) and fit["score"] >= 65
    R = 1.0 if red_line_ok else 0.2

    O = 1.0 if evidence.get("mna_fit_before_valuation") else 0.4
    Ro = 1.0 if evidence.get("mna_source_verified") else 0.3
    verifiable_ext = bool(evidence.get("mna_gap_externally_verifiable", True))

    redflag_text = "、".join(fit["red_flags"]) if fit["red_flags"] else "无"
    notes = (
        f"并购适配度 {fit['score']}/100（{fit['grade']}）；"
        f"证据覆盖 {fit['n_present']}/{fit['n_items']}；"
        f"红旗：{redflag_text}；"
        f"红线（无红旗且≥65）{'通过' if red_line_ok else '未通过'}；"
        f"数据{'第三方' if evidence.get('mna_source_verified') else '自报'}；"
        f"顺序{'先适配度后估值' if evidence.get('mna_fit_before_valuation') else '未确认先适配度'}"
    )
    return dict(R=R, C=C, O=O, Ro=Ro, verifiable_ext=verifiable_ext, notes=notes,
                fit=fit)


def repair_mna_exit_likelihood(evidence: dict) -> dict:
    """AUTO_REPAIR：财务可并表性/股权可交割性可外部核查——模拟"去工商/审计/招投标
    公告补可交割性与可并表性证据"。只补可外部核查的子项，绝不修改红旗判定、估值
    或适配度结论——改数字等于做账。"""
    new_evidence = dict(evidence)
    new_evidence["auditable_revenue"] = True
    new_evidence["shareholder_count_lt_20"] = True
    new_evidence["mna_source_verified"] = True
    return new_evidence


def render_mna_exit_report(evidence: dict) -> str:
    """确定性输出「并购退出可能性分析报告」（Markdown 字符串）。LLM-free：所有数字
    来自 mna_fit_score / 赛道锚确定性计算，买方与时间窗来自 MNA_TRACK_MAP 查表。"""
    fit = mna_fit_score(evidence)
    target = evidence.get("target_name") or "（未命名标的）"
    track_key = evidence.get("track") or evidence.get("archetype")
    buyers, window = MNA_TRACK_MAP.get(track_key, ("（需按标的画像人工补买方名单）", "（待定）"))

    # 赛道落点（如有收入/估值，用并购退路锚确定性推导）
    zone_line = ""
    rev = _num(evidence.get("annual_revenue"))
    claimed = _num(evidence.get("claimed_valuation"))
    if rev is not None and claimed is not None:
        anchors = cn_aidc_energy_anchors(revenue=rev, archetype=evidence.get("archetype"))
        zone, price_rel = aidc_ruler_zone(claimed, anchors)
        fin = anchors["financial_range"]
        zone_line = (f"赛道落点：自报 {claimed:g} 亿 → **{zone}**"
                     f"（并购退路[{fin[0]:g},{fin[1]:g}]亿，规模天花板{anchors['size_ceiling']:g}亿）")

    # 六维度明细表
    dim_rows = []
    for d in fit["dims"]:
        dim_max = sum(it["weight"] for it in d["items"])
        marks = " ".join(("✓" if it["ok"] else "✗") + it["label"] for it in d["items"])
        dim_rows.append(f"| {d['name']} | **{d['score']}/{dim_max}** | {marks} |")
    dim_table = "\n".join(dim_rows)

    red_flag_lines = ("\n".join(f"- 🚩 {r}" for r in fit["red_flags"])
                      if fit["red_flags"] else "- 无红旗")

    exit_paths = " / ".join(hk_exit_paths_for(evidence.get("track"), evidence.get("archetype")))

    verdict = ("建议按并购路径设计条款（领售权/并购优先分配/接受股票对价）。"
               if fit["score"] >= 65 and not fit["red_flags"]
               else "入价纪律即退出保障：先清红旗、重谈估值，再议并购退出。")

    return (
        f"# {target} · 并购退出可能性分析报告\n\n"
        f"## 结论速览\n\n"
        f"- 并购适配度：**{fit['score']}/100**（{fit['grade']}）\n"
        f"- 证据覆盖：{fit['n_present']}/{fit['n_items']} 项\n"
        f"- {zone_line or '赛道落点：数据不足，无法推导'}\n"
        f"- 潜在买方：{buyers}\n"
        f"- 并购时间窗：{window}\n"
        f"- 港股退出路径：{exit_paths}\n\n"
        f"## 六维度适配度评分\n\n"
        f"| 维度 | 得分 | 子项（✓已满足 / ✗未满足） |\n|---|---|---|\n"
        f"{dim_table}\n\n"
        f"## 红旗\n\n{red_flag_lines}\n\n"
        f"## 判定结论\n\n{fit['grade']}。{verdict}\n"
    )


# ============================================================
# 港股退出路径谱系（2026-09）· 对应估值分析
# ============================================================
# 把港股全部退出路径（含拟设的 18D）编码成确定性查表：每条路径 → 适用对象 / 门槛 /
# 对应估值锚（GateFix 赛道估值法）。"先选道、再定价"。
# 来源：《港股AI退出通道图谱》+ 18D 改革（南华早报/媒体披露，拟议方案，非生效规则）。

# 18D 上市门槛锚：市值+营收+经营现金流组合测试，具体标准待公众咨询确认。
# 定位在 18C（商业化 40 亿 / 未商业化 80 亿港元）之下，是"未达独角兽体量"的中小成长型通道。
EXIT_ANCHOR_HK18D = None   # 待定（媒体披露拟议，2026 年底公众咨询 / 2027 落地）

HK_EXIT_PATHS = [
    {
        "path": "传统主板·第八章",
        "status": "已生效",
        "applies": "成熟盈利企业",
        "threshold": "市值≥5亿港元；三年累计盈利≥8000万港元",
        "valuation_anchor": "PE 锚（盈利 × 可比 PE）",
        "gatefix_fn": "score_valuation_sanity",
    },
    {
        "path": "18A·未盈利生物科技",
        "status": "2018 生效",
        "applies": "创新药临床阶段",
        "threshold": "市值≥15亿港元；核心产品到临床里程碑",
        "valuation_anchor": "临床里程碑 + BD 授权锚（基金 AI 赛道不适用）",
        "gatefix_fn": None,
    },
    {
        "path": "18B·SPAC",
        "status": "2022 生效",
        "applies": "特殊需求",
        "threshold": "募资≥10亿港元；24 个月内 De-SPAC",
        "valuation_anchor": "De-SPAC 交易定价（流程复杂，不建议首选）",
        "gatefix_fn": None,
    },
    {
        "path": "18C·大型未盈利特专科技",
        "status": "2023 生效",
        "applies": "AI/机器人/自动驾驶大体量硬科技独角兽",
        "threshold": "商业化市值≥40亿港元；未商业化≥80亿港元",
        "valuation_anchor": "融资体量锚 + 门票锚（具身智能，18C 未商业化门槛≈140 亿人民币）",
        "gatefix_fn": "score_track_valuation",
    },
    {
        "path": "18D·中小成长型（拟设）",
        "status": "拟议，2027 落地（待公众咨询）",
        "applies": "有技术、有收入、有增长，未达独角兽体量",
        "threshold": "市值+营收+经营现金流组合测试（具体标准待定）",
        "valuation_anchor": "二级可比 PS/PE 锚（算电协同/AIDC能源，18D 门槛待定）",
        "gatefix_fn": "score_aidc_track_valuation",
    },
    {
        "path": "并购退出（非 IPO）",
        "status": "持续",
        "applies": "中小硬科技（IPO 只占约 5%）",
        "threshold": "产业买方/央国企并购价 PS 3-8x；>20 亿触发重大资产重组",
        "valuation_anchor": "并购退路锚（PS 3-8x）+ 并购适配度评分卡",
        "gatefix_fn": "score_mna_exit_likelihood",
    },
]

# 标的画像 → 适用退出路径（确定性映射；并购恒成立，18D 对中小成长型，18C 对大脑/本体大体量）
_EXIT_PATH_TRACK_MAP = {
    "power": ["并购退出（非 IPO）", "18D·中小成长型（拟设）"],
    "cooling": ["并购退出（非 IPO）", "18D·中小成长型（拟设）"],
    "storage_green": ["并购退出（非 IPO）", "18D·中小成长型（拟设）"],
    "software": ["并购退出（非 IPO）", "18D·中小成长型（拟设）"],
    "sic": ["并购退出（非 IPO）", "18D·中小成长型（拟设）"],
    "grid_ai": ["并购退出（非 IPO）", "18D·中小成长型（拟设）"],
    "brain": ["并购退出（非 IPO）", "18C·大型未盈利特专科技"],
    "body": ["并购退出（非 IPO）", "18C·大型未盈利特专科技"],
    "embodied": ["并购退出（非 IPO）"],
    "component": ["并购退出（非 IPO）"],
}


def hk_exit_paths_for(track=None, archetype=None):
    """给定标的画像，返回适用的港股退出路径（确定性查表）。并购退出对所有中小
    硬科技恒成立；18D（拟）对算电协同/三代半导体/电网算法等中小成长型成立；18C
    对具身智能"大脑/本体"大体量独角兽成立。"""
    key = track or archetype
    return list(_EXIT_PATH_TRACK_MAP.get(key, ["并购退出（非 IPO）"]))


def render_hk_exit_spectrum() -> str:
    """确定性输出「港股退出路径全谱系 + 对应估值分析」Markdown 表格。LLM-free。"""
    rows = []
    for p in HK_EXIT_PATHS:
        fn = p["gatefix_fn"] or "（不接 GateFix，人工/其他口径）"
        rows.append(f"| {p['path']} | {p['status']} | {p['applies']} | {p['threshold']} | {p['valuation_anchor']} | `{fn}` |")
    header = ("| 退出路径 | 状态 | 适用对象 | 门槛 | 对应估值锚 | GateFix 闸门 |\n"
              "|---|---|---|---|---|---|")
    return header + "\n" + "\n".join(rows)


# ============================================================
# 境内退出路径谱系（A股 / 科创板 / 北交所 · 2026-09 调研）
# ============================================================
# 与上面的 HK_EXIT_PATHS（港股全谱系）互补，补齐 GateFix「退出通道全景」研究维度。
# 港股回答"能不能去香港退"；本表回答"能不能在境内（沪深北）退"，并附退出周期与资金额。
# 来源：A股/科创板/港股18C上市退出调研（2024-2025 全年数据 + 2026 初，见同名调研报告/设计文档）。
# 关键口径（全部有据可查）：
#   ① A股盈利底线：近两年净利累计≥5000万（创业板/科创板标准一）——达不到则境内盈利型 IPO 无望
#   ② 科创板标准五（未盈利）：市值≥40亿 + 医药II期临床（2025-07 重启，扩围 AI/商业航天/低空）
#   ③ 境内 2025 全年 116 家上市、募资 1317 亿；科创板 19 家、募资 380.6 亿（平均≈20 亿/家）
# 注意：本表与港股 18C 的"已商业化 40 / 未商业化 80 亿港元"（2024-08 降门槛后现行口径）并列，
# 共同构成"同一标的可同时对照境内/境外两个退出入口"的全景视图。

CN_EXIT_PATHS = [
    {
        "path": "上交所主板",
        "status": "注册制已生效",
        "applies": "成熟期·规模盈利企业",
        "threshold": "近三年净利均为正累计≥1.5亿，最近一年≥6000万；近三年经营现金流累计≥1亿或营收累计≥10亿",
        "valuation_anchor": "PE 锚（盈利 × 可比 PE）",
        "gatefix_fn": "score_valuation_sanity",
    },
    {
        "path": "深交所主板",
        "status": "注册制已生效",
        "applies": "成熟期·规模盈利企业",
        "threshold": "同主板标准（近三年净利累计≥1.5亿、最近一年≥6000万等）",
        "valuation_anchor": "PE 锚",
        "gatefix_fn": "score_valuation_sanity",
    },
    {
        "path": "创业板",
        "status": "注册制已生效",
        "applies": "成长型创新企业",
        "threshold": "近两年净利均为正累计≥5000万；或市值≥10亿+近一年净利为正+营收≥1亿",
        "valuation_anchor": "PE/PS 锚",
        "gatefix_fn": "score_valuation_sanity",
    },
    {
        "path": "科创板·标准一（盈利）",
        "status": "2019 生效",
        "applies": "硬科技·已盈利",
        "threshold": "市值≥10亿；近两年净利均为正累计≥5000万，或近一年净利为正+营收≥1亿",
        "valuation_anchor": "PE 锚",
        "gatefix_fn": "score_valuation_sanity",
    },
    {
        "path": "科创板·标准二~四（研发/现金流/营收）",
        "status": "2019 生效",
        "applies": "有营收未盈利硬科技",
        "threshold": "市值15~30亿；营收2~3亿；近三年研发合计≥营收15%（或经营现金流累计≥1亿）",
        "valuation_anchor": "PS / 研发投入锚",
        "gatefix_fn": "score_aidc_track_valuation",
    },
    {
        "path": "科创板·标准五（未盈利）",
        "status": "2019 生效 · 2025-07 重启扩围",
        "applies": "未盈利硬科技：医药/AI/商业航天/低空",
        "threshold": "市值≥40亿；医药需至少一项核心产品获准II期临床；AI等需明显技术优势",
        "valuation_anchor": "融资体量锚 + 门票锚（与港股18C未商业化同构）",
        "gatefix_fn": "score_track_valuation",
    },
    {
        "path": "北交所",
        "status": "2021 生效",
        "applies": "专精特新中小企业",
        "threshold": "市值≥2亿；净利≥1500万（或市值+营收+现金流组合测试）",
        "valuation_anchor": "PE 锚（规模小、流动性弱）",
        "gatefix_fn": None,
    },
]

# 境内退出的"三条可行性红线"（倒推：项目要退，必须达到的水平）
CN_EXIT_REDLINES = [
    {"id": "R1", "name": "盈利型底线", "level": "年净利 5000万~1亿（营收 3~10亿）",
     "channel": "A股主板/创业板/科创板标准一", "note": "达不到则境内盈利型 IPO 无望"},
    {"id": "R2", "name": "硬科技未盈利底线", "level": "融资估值 40~80亿（人民币/港元）",
     "channel": "科创板标准五 / 港股18C未商业化", "note": "不看利润，看融资估值+研发+赛道成色"},
    {"id": "R3", "name": "中间地带（最现实）", "level": "营收≥2.5亿港元(≈2.3亿人民币)+市值40亿港元+研发占比15%",
     "channel": "港股18C已商业化", "note": "有收入未盈利硬科技门槛最低、确定性最高的路径"},
]

# 退出周期（研究维度：周期）
EXIT_CYCLE = {
    "avg_holding_years": 3.37,          # 单项目平均持有期（2021 全市场退出项目口径）
    "seed_to_ipo_years": (15, 17),      # 种子/天使轮投到 IPO（专精特新样本倒推）
    "fund_liquidation_rate": 0.1797,    # 人民币私募股权/创投基金累计清算率 17.97%
    "ipo_exit_revenue_share": 0.6255,   # 境内 IPO 退出收益占比 62.55%（2021）
    "rmb_fund_life_years": (7, 10),     # 人民币基金典型存续期
}

# 退出资金额（研究维度：资金额；单位：亿元人民币，港股标港元）
EXIT_CAPITAL = {
    "star_market_avg_cny": 20.0,        # 科创板 2025 平均募资（19 家 380.6 亿）
    "star_market_std5_avg_cny": 21.4,   # 科创板第五套 20 家平均募资（428.71 亿）
    "a_share_avg_cny": 11.4,            # A股 2025 平均募资（116 家 1317 亿）
    "hk18c_range_hkd": (8.0, 16.0),     # 港股 18C 单家募资区间（晶泰≈11 / 黑芝麻拟16）
    "hk_ipo_2025_total_hkd": 2858.0,    # 港股 2025 全年募资（重登全球榜首）
}


def cn_exit_paths_for(*, profitable=None, revenue_cny=None, valuation_cny=None):
    """给定财务状态，返回适用的境内退出路径（确定性查表，LLM-free）。
    境内 IPO 通道由财务状态（盈利/营收/估值）决定，而非赛道——这是与
    hk_exit_paths_for（赛道画像驱动）的根本区别。
    盈利 → 主板/创业板/科创板标准一；
    未盈利但营收≥3亿 → 科创板标准二~四；
    未盈利硬科技且估值≥40亿 → 科创板标准五；
    均不满足/缺数据 → 境内 IPO 不成立（fail-closed，转港股18C/并购）。"""
    paths = []
    if profitable is True:
        paths += ["科创板·标准一（盈利）", "创业板", "深交所主板", "上交所主板"]
    else:
        rev = _num(revenue_cny)
        val = _num(valuation_cny)
        if rev is not None and rev >= 3.0:
            paths += ["科创板·标准二~四（研发/现金流/营收）"]
        if val is not None and val >= 40.0:
            paths += ["科创板·标准五（未盈利）"]
    if not paths:
        return ["境内 IPO 不成立（营收/估值未达门槛 → 港股18C / 并购退出）"]
    return paths


def render_cn_exit_spectrum() -> str:
    """确定性输出「境内退出路径全谱系」Markdown 表格。LLM-free。"""
    rows = []
    for p in CN_EXIT_PATHS:
        fn = p["gatefix_fn"] or "（不接 GateFix，人工/其他口径）"
        rows.append(f"| {p['path']} | {p['status']} | {p['applies']} | {p['threshold']} | {p['valuation_anchor']} | `{fn}` |")
    header = ("| 退出路径 | 状态 | 适用对象 | 门槛 | 对应估值锚 | GateFix 闸门 |\n"
              "|---|---|---|---|---|---|")
    return header + "\n" + "\n".join(rows)


def render_exit_panorama() -> str:
    """确定性输出「退出通道全景」：港股全谱系 + 境内全谱系 + 三条红线 + 周期 + 资金额。
    LLM-free，把两套退出路径谱系与退出周期/资金额合并成一个可复现的退出研究维度报告。"""
    red_rows = "\n".join(
        f"| {r['id']} {r['name']} | {r['level']} | {r['channel']} | {r['note']} |"
        for r in CN_EXIT_REDLINES
    )
    cycle = EXIT_CYCLE
    cap = EXIT_CAPITAL
    return (
        f"# 退出通道全景（GateFix 退出研究维度）\n\n"
        f"## 一、港股退出路径\n\n{render_hk_exit_spectrum()}\n\n"
        f"## 二、境内退出路径（A股 / 科创板 / 北交所）\n\n{render_cn_exit_spectrum()}\n\n"
        f"## 三、三条可行性红线（倒推：项目要退，必须达到的水平）\n\n"
        f"| 红线 | 必须达到 | 通道 | 说明 |\n|---|---|---|---|\n{red_rows}\n\n"
        f"## 四、退出周期\n\n"
        f"- 单项目平均持有期：**{cycle['avg_holding_years']:g} 年**\n"
        f"- 种子/天使轮投到 IPO：**{cycle['seed_to_ipo_years'][0]}~{cycle['seed_to_ipo_years'][1]} 年**\n"
        f"- 人民币基金累计清算率：**{cycle['fund_liquidation_rate']*100:g}%**（退出难是核心矛盾）\n"
        f"- 境内 IPO 退出收益占比：**{cycle['ipo_exit_revenue_share']*100:g}%**\n"
        f"- 人民币基金存续期：**{cycle['rmb_fund_life_years'][0]}~{cycle['rmb_fund_life_years'][1]} 年**\n\n"
        f"## 五、退出资金额\n\n"
        f"- 科创板平均募资：**{cap['star_market_avg_cny']:g} 亿人民币/家**（2025）\n"
        f"- 科创板第五套（未盈利）平均募资：**{cap['star_market_std5_avg_cny']:g} 亿/家**\n"
        f"- A股整体平均募资：**{cap['a_share_avg_cny']:g} 亿/家**（2025）\n"
        f"- 港股18C 单家募资区间：**{cap['hk18c_range_hkd'][0]:g}~{cap['hk18c_range_hkd'][1]:g} 亿港元**\n"
        f"- 港股 2025 全年募资：**{cap['hk_ipo_2025_total_hkd']:g} 亿港元**（重登全球榜首）\n\n"
        f"## 六、换锚方法论（gap = 外生锚 − 内生锚）\n\n"
        f"上市前估值上涨 = 定价锚从「内生锚（融资体量/门票）」切到「外生锚（二级 PS/PE）」。\n"
        f"- 内生锚 = 上一轮融资估值（自指，无外部底）\n"
        f"- 外生锚 = PE × 利润（{LISTED_PE_LOW:g}~{LISTED_PE_HIGH:g}x）或 PS × 营收（{LISTED_PS_LOW:g}~{LISTED_PS_HIGH:g}x）\n"
        f"- gap =（外生锚 − 内生锚）/ 内生锚；> +{SWITCH_TOLERANCE*100:.0f}% 换轨成功（涨），< −{SWITCH_TOLERANCE*100:.0f}% 换轨失败（破发），无收入无利润 = 无锚可切（最高风险）\n"
        f"- 单项目分析用 `anchor_switch_analysis(revenue, profit, last_round_valuation, scarcity)`\n"
    )


# ============================================================
# 换锚分析（上市前估值上涨逻辑 · 2026-09）
# ============================================================
# 核心洞察（《GateFix退出通道全景_研究维度_设计文档》+ 中网投分析）：
#   上市前估值上涨的本质 = 定价锚从「内生锚（融资体量/门票）」切换到「外生锚（二级 PS/PE）」。
#   换轨成功（外生锚 > 内生锚）→ 涨幅；换轨失败（外生锚 < 内生锚 或 无锚可切）→ 破发。
#   内生锚 = 上一轮融资估值（自指：融资者自己付的钱，没有外部底）
#   外生锚 = PE × 利润（有利润最扎实）或 PS × 营收（有收入）——有真实收入/利润做地板
# 与六维度 D1「锚的性质」同源：内生锚共识逆转时没有底，换轨失败 = 共识逆转。
# 桥 = 收入/利润：无收入→只能停在内生锚（二级用市梦率叙事，切不动）；有收入→PS；有利润→PE。

# —— 二级可比倍数（硬科技成长股，模块级常数，可按赛道校准）——
LISTED_PS_LOW = 10.0     # 硬科技成长股二级 PS 下沿（倍）
LISTED_PS_HIGH = 25.0    # 上沿（宇树发行 24.7x 在此附近）
LISTED_PE_LOW = 25.0     # 盈利硬科技二级 PE 下沿（倍）
LISTED_PE_HIGH = 45.0    # 上沿
SWITCH_TOLERANCE = 0.20  # gap 容忍带 ±20%（吸收倍数取整误差）


def anchor_switch_analysis(*, revenue=None, profit=None,
                           last_round_valuation=None, scarcity=None):
    """换锚分析：判断 Pre-IPO 公司「内生锚 → 外生锚」换轨成败（确定性，LLM-free）。
    输入（单位：亿元人民币）：
      revenue —— 最近一年营收（撑 PS 锚）
      profit  —— 最近一年净利润（撑 PE 锚；未盈利/亏损传 None 或 <=0）
      last_round_valuation —— 上一轮投后估值（内生锚）
      scarcity —— 赛道稀缺性：True（第一股/稀缺）/ False（同质竞争）/ None（未知）
    返回 dict：endogenous_anchor / exogenous_anchor / exo_method / gap_ratio /
      switch（success|fail|borderline|no_anchor|indeterminate）/ scarcity_note / expected。
    """
    rev = _num(revenue)
    prof = _num(profit)
    last = _num(last_round_valuation)

    # 外生锚：优先 PE（有利润最扎实），否则 PS（有收入），否则 None（无锚可切）
    exo = None
    exo_method = None
    if prof is not None and prof > 0:
        exo = prof * ((LISTED_PE_LOW + LISTED_PE_HIGH) / 2)
        exo_method = "PE"
    elif rev is not None and rev > 0:
        exo = rev * ((LISTED_PS_LOW + LISTED_PS_HIGH) / 2)
        exo_method = "PS"

    if exo is None:
        return dict(endogenous_anchor=last, exogenous_anchor=None, exo_method=None,
                    gap_ratio=None, switch="no_anchor", scarcity=scarcity,
                    scarcity_note="", expected="无收入/无利润 → 二级无锚可切，只能用市梦率叙事，换轨失败风险最高")

    if last is None or last <= 0:
        return dict(endogenous_anchor=None, exogenous_anchor=exo, exo_method=exo_method,
                    gap_ratio=None, switch="indeterminate", scarcity=scarcity,
                    scarcity_note="", expected=f"缺上一轮估值（内生锚）→ 无法算 gap；外生锚≈{exo:g} 亿（{exo_method}）")

    gap = (exo - last) / last

    if scarcity is True:
        scarcity_note = "稀缺/第一股 → 换轨后还有情绪抢筹空间，涨幅可再放大"
    elif scarcity is False:
        scarcity_note = "同质竞争 → 二级不抢，缺口收窄甚至打折"
    else:
        scarcity_note = "稀缺性未知 → 按中性处理"

    if gap >= SWITCH_TOLERANCE:
        switch = "success"
        expected = f"+{gap*100:.0f}% 起（外生锚 {exo:g} 亿 > 内生锚 {last:g} 亿）"
        if scarcity is True:
            expected += "，稀缺抢筹可再放大"
    elif gap <= -SWITCH_TOLERANCE:
        switch = "fail"
        expected = f"破发约 {gap*100:.0f}%（外生锚 {exo:g} 亿 < 内生锚 {last:g} 亿，一级已透支）"
    else:
        switch = "borderline"
        expected = (f"gap 在 ±{SWITCH_TOLERANCE*100:.0f}% 内，换轨临界"
                    f"（外生锚 {exo:g} vs 内生锚 {last:g} 亿），方向未定")

    return dict(endogenous_anchor=last, exogenous_anchor=exo, exo_method=exo_method,
                gap_ratio=gap, switch=switch, scarcity=scarcity,
                scarcity_note=scarcity_note, expected=expected)


def render_anchor_switch(*, revenue=None, profit=None,
                         last_round_valuation=None, scarcity=None, name=""):
    """确定性输出「换锚分析」Markdown。LLM-free。"""
    r = anchor_switch_analysis(revenue=revenue, profit=profit,
                               last_round_valuation=last_round_valuation,
                               scarcity=scarcity)
    title = name or "（未命名标的）"
    exo_line = (f"{r['exogenous_anchor']:g} 亿（{r['exo_method']} 锚）"
                if r['exogenous_anchor'] is not None else "无（无收入/无利润）")
    endo_line = f"{r['endogenous_anchor']:g} 亿" if r['endogenous_anchor'] else "未披露"
    gap_line = f"{r['gap_ratio']*100:+.0f}%" if r['gap_ratio'] is not None else "—"
    switch_cn = {"success": "换轨成功（涨）", "fail": "换轨失败（破发）",
                 "borderline": "换轨临界", "no_anchor": "无锚可切（最高风险）",
                 "indeterminate": "数据不足"}[r["switch"]]
    return (
        f"# {title} · 换锚分析（上市前估值上涨逻辑）\n\n"
        f"| 项 | 值 |\n|---|---|\n"
        f"| 内生锚（上一轮估值） | {endo_line} |\n"
        f"| 外生锚（二级可比） | {exo_line} |\n"
        f"| gap（外生−内生）/内生 | {gap_line} |\n"
        f"| 换轨结论 | **{switch_cn}** |\n"
        f"| 预期 | {r['expected']} |\n"
        f"| 稀缺性 | {r['scarcity_note'] or '—'} |\n"
    )


# ---------------------------------------------------------------------------
# 资本穿透层（v2）：同一估值，对谁成立。
# 资本性质 → 考核周期 → 目标函数 → 估值尺度，全部确定性枚举查表，不经过 LLM。
# ---------------------------------------------------------------------------
CAPITAL_NATURES = ("地方国资", "央企", "金融机构", "产业资本", "市场化VC", "主权资本")
OBJECTIVES = ("财务回报", "落地", "供应链/场景", "战略卡位")

# 资本性质 → 目标函数（穿透后最终出资人的确定性映射）
CAPITAL_OBJECTIVE_MAP = {
    "地方国资": "落地",
    "央企": "战略卡位",
    "金融机构": "财务回报",
    "产业资本": "供应链/场景",
    "市场化VC": "财务回报",
    "主权资本": "战略卡位",
}

# 估值含义矩阵：价格轴（溢价/合理/折价）× 目标函数（资本要什么）→ 含义。
# 核心纪律：红只出现在「财务回报 × 溢价」这一格；其余溢价是黄（换尺子看，不是不能投）。
MEANING_MATRIX = {
    ("财务回报", "溢价"): ("红", "退出倍数不成立 → 金融定价不成立，建议按独立区间重谈"),
    ("财务回报", "合理"): ("绿", "金融定价成立"),
    ("财务回报", "折价"): ("绿", "安全边际"),
    ("落地", "溢价"): ("黄", "落地锚：看落地兑现度与非现金对价结构"),
    ("落地", "合理"): ("绿", "落地锚成立"),
    ("落地", "折价"): ("黄", "警惕落地绑架估值（低估=贱卖数据/场景）"),
    ("供应链/场景", "溢价"): ("黄", "战略期权：看产业方跟投比例与排他/订单承诺"),
    ("供应链/场景", "合理"): ("绿", "战略期权成立"),
    ("供应链/场景", "折价"): ("黄", "警惕战略资产被低估"),
    ("战略卡位", "溢价"): ("黄", "看稀缺性/不可复制性"),
    ("战略卡位", "合理"): ("绿", "卡位定价成立"),
    ("战略卡位", "折价"): ("黄", "警惕卡位价值被低估"),
}


def _objective(v):
    """把 LLM 可能返回的中英混写目标函数规整成四分类枚举，识别不出返回 None。"""
    s = str(v or "").strip()
    if s in ("财务回报", "回报", "退出回报", "IRR/MOIC", "财务"):
        return "财务回报"
    if s in ("落地", "政绩", "产业落地", "数据资产"):
        return "落地"
    if s in ("供应链/场景", "供应链", "场景", "供应链场景", "战略期权"):
        return "供应链/场景"
    if s in ("战略卡位", "卡位", "战略回报", "国产替代", "出海"):
        return "战略卡位"
    return None


def objective_from_nature(nature):
    """资本性质 → 目标函数的确定性映射（LLM 已判定 objective_function 时优先采信 LLM）。"""
    return CAPITAL_OBJECTIVE_MAP.get(nature)


def valuation_meaning(price_rel, objective):
    """确定性查表：价格关系 × 目标函数 → 估值含义（颜色 + 一句话）。
    价格关系必须来自确定性计算（track_ruler_zone 的 price_rel），不经过 LLM。"""
    if objective is None or price_rel is None:
        return ("灰", "数据不足，无法判定估值含义")
    return MEANING_MATRIX.get((objective, price_rel), ("灰", "数据不足，无法判定估值含义"))


def score_capital_attribution(evidence: dict) -> dict:
    """资本穿透证据闸门（资本轴）。evidence 覆盖字段（4 项，bool）：
    marginal_pricer_identified（边际定价者已识别）、
    capital_pierced_to_ultimate_owner（穿透到最终出资人层级）、
    assessment_horizon_disclosed（考核周期已披露）、
    objective_function_disclosed（目标函数已判定：财务回报/落地/供应链场景/战略卡位）；
    红线 = marginal_pricer_identified ∧ capital_pierced_to_ultimate_owner
    （边际定价者的钱穿透清楚，估值含义才谈得上）；
    另有 capital_before_valuation（先穿透资本后判估值，按构造 True）、
    capital_source_verified_third_party（穿透结论第三方可核 vs 自报）、
    capital_gap_externally_verifiable（缺口能否外部核查，决定 AUTO_REPAIR）。
    显示字段（仅用于 notes，不参与打分）：marginal_pricer / capital_nature /
    objective_function / assessment_horizon。"""
    dims = [
        bool(evidence.get("marginal_pricer_identified")),
        bool(evidence.get("capital_pierced_to_ultimate_owner")),
        bool(evidence.get("assessment_horizon_disclosed")),
        bool(evidence.get("objective_function_disclosed")),
    ]
    C = sum(dims) / len(dims)

    red_line_ok = bool(evidence.get("marginal_pricer_identified")) and bool(
        evidence.get("capital_pierced_to_ultimate_owner")
    )
    R = 1.0 if red_line_ok else 0.2

    O = 1.0 if evidence.get("capital_before_valuation") else 0.4
    Ro = 1.0 if evidence.get("capital_source_verified_third_party") else 0.3
    verifiable_ext = bool(evidence.get("capital_gap_externally_verifiable", True))

    names = ["边际定价者", "穿透到最终出资人", "考核周期", "目标函数"]
    detail = "/".join(("✓" if dims[i] else "缺") + names[i] for i in range(len(names)))
    notes = (
        f"资本穿透证据覆盖 {sum(dims)}/4（{detail}）；"
        f"红线（边际定价者的钱穿透清楚）{'通过' if red_line_ok else '未通过'}；"
        f"穿透结论{'第三方可核' if evidence.get('capital_source_verified_third_party') else '自报'}；"
        f"顺序{'先穿透资本后判估值' if evidence.get('capital_before_valuation') else '未确认先穿透'}"
    )
    return dict(R=R, C=C, O=O, Ro=Ro, verifiable_ext=verifiable_ext, notes=notes)


def repair_capital_attribution(evidence: dict) -> dict:
    """AUTO_REPAIR：工商/基金备案可公开查证——模拟"去企查查/基金业协会/国资公告补穿透数据"。
    只补可外部核查的字段（穿透到最终出资人、来源第三方），绝不修改目标函数判定——
    穿透结论错了靠翻 bool 修不回来，改结论等于做账。"""
    new_evidence = dict(evidence)
    new_evidence["capital_pierced_to_ultimate_owner"] = True
    new_evidence["capital_source_verified_third_party"] = True
    return new_evidence


# ============================================================
# 地方落地方案（地方招商引资考核逻辑 · 2026-09）
# ============================================================
# 核心一句话：地方要的不是"投资额"，是"能计入本地统计口径、能持续、能被考核"的东西。
# 理解钥匙：地方官员被考核什么，就要什么。本模块把"地方考核逻辑"编码成确定性规则，
# 输出单标的的「地方落地方案」——落地锚（地方国资要"落地"）的谈判工具。

# —— 六项考核（地方官员被考核什么，就要什么）——
LOCAL_GOV_KPIS = [
    {"kpi": "固定资产投资", "why": "年度硬考核，当年见数", "requirement": "买地/厂房/设备", "field": "capex_scale", "unit": "亿元"},
    {"kpi": "规上工业产值/GDP", "why": "统计口径必须落本地", "requirement": "本地生产实体", "field": "output_value_scale", "unit": "亿元"},
    {"kpi": "税收（地方留成）", "why": "可持续财政来源", "requirement": "本地纳税主体，非分支机构", "field": "tax_scale", "unit": "万元"},
    {"kpi": "就业", "why": "社会稳定+政绩", "requirement": "数量，近年更看质量", "field": "employment_count", "unit": "人"},
    {"kpi": "上市企业培育数", "why": "权重快速上升，多数 GP 低估", "requirement": "拟上市企业落地", "field": "listed_status", "unit": ""},
    {"kpi": "链主落地", "why": "链主带一串配套=招商背书", "requirement": "龙头/专精特新", "field": "chain_role", "unit": ""},
]

# 地方最怕三件事（按发生频率排）——确定性 > 规模
LOCAL_GOV_FEARS = [
    "签约不落地（框架协议签完没下文，指标要人背）",
    "落地不达产（厂房建了产值没有，土地补贴打水漂）",
    "拿了补贴就走（返投期未满迁走或注销）",
]

# 地方"给"的能力从"给钱"转向（招商引资鼓励/禁止清单下的新筹码）
LOCAL_GOV_OFFERS = [
    "应用场景与订单（国企/公共部门采购）",
    "产业配套（上下游在本地）",
    "要素成本（电价/绿电指标/算力）",
    "行政效率（审批速度/能耗指标/环评）",
    "人才与教育医疗配套",
]

# 返投认定口径（各地差别极大，同一笔投资可能算 100% 也可能算 0%）
RETURN_INVEST_DEFINITIONS = [
    "被投企业注册地在本地",
    "实际经营和纳税在本地",
    "认投资金额 vs 认企业数量",
    "投资发生在出资之后（之前投的不算）",
]


def local_landing_contributions(evidence: dict) -> list:
    """确定性：把标的证据映射到六项考核的"贡献值"（含能否进统计口径）。"""
    rows = []
    for kpi in LOCAL_GOV_KPIS:
        val = evidence.get(kpi["field"])
        if kpi["unit"]:
            display = f"{val} {kpi['unit']}" if val is not None else "未提供"
        else:
            display = str(val) if val else "未提供"
        rows.append({**kpi, "value": val, "display": display})
    return rows


def render_local_landing_plan(evidence: dict) -> str:
    """确定性输出「地方落地方案」（Markdown）。把地方考核逻辑落到单标的的落地谈判上，
    输出：六项考核映射 / 确定性评估 / 筹码排序 / 返投口径 / 谈判时机。LLM-free。"""
    target = evidence.get("target_name") or "（未命名标的）"
    rows = local_landing_contributions(evidence)

    # 六项考核映射表
    kpi_rows = []
    for r in rows:
        kpi_rows.append(f"| {r['kpi']} | {r['why']} | {r['display']} | {r['requirement']} |")
    kpi_table = "\n".join(kpi_rows)

    # 确定性评估：能否设本地实体 → 缓解"三怕"里的前两怕
    can_entity = bool(evidence.get("can_setup_local_entity"))
    if can_entity:
        certainty = ("✅ 高确定性：设本地子公司/生产实体，同时产生固投+产值+税收+就业四项，"
                     "直接对冲「签约不落地」「落地不达产」两怕。")
    else:
        certainty = ("⚠️ 低确定性：纯股权投资不进任何统计口径，地方视同「签约不落地」，"
                     "筹码近乎为零——先想清楚能给的到底是钱，还是能进统计口径的实体。")

    # 筹码排序：拟上市企业 > 投资额
    listed = str(evidence.get("listed_status") or "").strip()
    is_pre_ipo = listed in ("listed", "pre_ipo", "拟上市", "已报")
    if is_pre_ipo:
        leverage = ("「我们能带一家拟上市企业落地」的价值 > 「我们能带 N 亿投资」——"
                    "上市公司数量是长期政绩、可写进五年规划，投资额是一次性的。")
    else:
        leverage = ("无拟上市身份时，退而求其次用「固投+产值+税收+就业」组合去谈，"
                     "不要单谈投资额——纯股权投资对地方几乎零价值。")

    # 返投口径 checklist（最多 GP 吃亏的地方）
    ri_def = evidence.get("return_invest_definition") or "未明确（必须写死）"
    ri_ratio = evidence.get("return_invest_ratio") or "1.5–2"
    return_lines = "\n".join(f"- {d}" for d in RETURN_INVEST_DEFINITIONS)

    # 谈判时机
    metric = evidence.get("govt_most_needed_metric") or "（未识别）"
    timing = (f"谈之前先问清楚今年最缺哪项指标（当前标的侧：**{metric}**）。"
              "缺固投的年份和缺税收的年份，能谈的条件完全不同；"
              "**年底缺固投时筹码最大**——一个能立刻形成投资额的项目，地方愿意给的条件明显松动。")

    offers = "、".join(LOCAL_GOV_OFFERS)

    return (
        f"# {target} · 地方落地方案\n\n"
        f"## 核心判断\n\n"
        f"地方要的不是「投资额」，是「能计入本地统计口径、能持续、能被考核」的东西。"
        f"理解钥匙：**地方官员被考核什么，就要什么。**\n\n"
        f"## 六项考核映射（本标的能贡献什么）\n\n"
        f"| 考核项 | 为什么重要 | 本标的贡献 | 对项目的要求 |\n|---|---|---|---|\n"
        f"{kpi_table}\n\n"
        f"## 确定性评估（地方最怕的三件事）\n\n"
        f"按发生频率：① {LOCAL_GOV_FEARS[0]}；② {LOCAL_GOV_FEARS[1]}；③ {LOCAL_GOV_FEARS[2]}。\n\n"
        f"{certainty}\n\n"
        f"> 推论：**规模小但确定性高的项目，对地方的实际价值经常高于规模大但飘的项目**——这跟很多 GP 的直觉相反。\n\n"
        f"## 筹码排序\n\n{leverage}\n\n"
        f"## 地方「给」的能力匹配（场景换份额天然对齐）\n\n"
        f"地方能拿出的已从「给钱」转向：{offers}。基金原本就要用场景换份额，"
        f"现在地方也只剩场景可给，**筹码同一种、谈判语言天然对齐**。\n\n"
        f"## 返投口径（必须写进协议，逐条写死）\n\n"
        f"返投义务通常 {ri_ratio} 倍，但「什么算返投」各地口径差别极大，同一笔投资可能算 100% 也可能算 0%。"
        f"当前标的口径：**{ri_def}**。认定标准、认定时点、认定机构逐条写死，别信口头承诺——经办人会换，协议不会：\n\n"
        f"{return_lines}\n\n"
        f"## 谈判时机\n\n{timing}\n"
    )


# ============================================================
# 六维度价格模型（可复用资产定价框架 · 2026-09）
# ============================================================
# 把前面几轮的定价框架收拢成一个可复用模型：任何资产定价，问六个问题。
# D1 锚内生/外生（最重要：内生锚共识逆转时没有底）｜D2 投入产出剪刀差｜
# D3 物理约束层｜D4 可交易计量单位｜D5 期限匹配｜D6 标尺（第一家盈利者）。

PRICE_MODEL_DIMS = [
    {"id": "D1", "name": "锚的性质", "question": "锚是内生还是外生？定价者是否同时是买方/融资方？", "field": "d1_anchor_exogenous", "note": "内生=自指/共识定价；外生=实体供需/监管定价（内生锚共识逆转时没有底）"},
    {"id": "D2", "name": "投入产出剪刀差", "question": "投入品与产出品价格方向？", "field": "d2_scissors", "note": "投入涨/产出跌 → 中间层必被挤压"},
    {"id": "D3", "name": "物理约束", "question": "物理瓶颈在哪一层？", "field": "d3_physical_constraint", "note": "物理约束不随融资额缓解，是唯一诚实的估值下限"},
    {"id": "D4", "name": "可交易计量单位", "question": "有没有可交易的产出计量单位？", "field": "d4_measurable_unit", "note": "无计量单位的资产只能靠共识定价"},
    {"id": "D5", "name": "期限匹配", "question": "资产/回报期限与资金期限匹配吗？", "field": "d5_term_match", "note": "错配=钱等不到收成 / 资产死在负债前面"},
    {"id": "D6", "name": "标尺", "question": "有没有第一家真正盈利者作标尺？", "field": "d6_benchmark", "note": "标尺出现的那一刻，就是分化开始的那一刻"},
]

# 三条赛道的六维度速查（预计算，来自 2026-09 分析）
PRICE_MODEL_PRESETS = {
    "算力/大模型": {"d1_anchor_exogenous": False, "d2_scissors": False, "d3_physical_constraint": True, "d4_measurable_unit": True, "d5_term_match": False, "d6_benchmark": True},
    "具身智能": {"d1_anchor_exogenous": False, "d2_scissors": False, "d3_physical_constraint": True, "d4_measurable_unit": False, "d5_term_match": False, "d6_benchmark": True},
    "绿电/核电": {"d1_anchor_exogenous": True, "d2_scissors": True, "d3_physical_constraint": True, "d4_measurable_unit": True, "d5_term_match": True, "d6_benchmark": True},
}

# 穹彻智能案例（2026-09 深度拆解）：具身智能赛道里的"偏外生"特例。
# 三态：True=绿 / None=黄(正在造·待观察) / False=红。
# 关键差异：药房场景给了它一个外部锚（夜班人力成本），把 D1 从"内生"掰成"偏外生"；
# RoboPocket 在"造"计量单位（有效训练信号），正对 D4 的根因——D4 从"无"（黄）走到
# "正在造"（黄），区别于赛道平均的"无"（红）。但 D6 标尺未到（百套 vs 宇树 5500 台）。
QIONGCHE_CASE = {
    "d1_anchor_exogenous": True,    # 偏外生：药房夜班人力成本是真实外部价格
    "d2_scissors": True,            # 正向：采集成本降（数据从成本变副产品），产出(件/小时)可计价
    "d3_physical_constraint": True, # 正面对准：力控直击 sim2real gap 的成因（接触物理）
    "d4_measurable_unit": None,     # 正在造：有效训练信号（待行业标准化）——差异化，但未兑现
    "d5_term_match": None,          # 待观察：药房回收周期未披露
    "d6_benchmark": False,          # 未到：百套 vs 宇树 5500 台，差一个数量级
}


def score_price_model(evidence: dict) -> dict:
    """六维度价格模型打分（三态：True=绿/None=黄/False=红）。D1 是红线：内生锚
    （D1=False）→ 结构脆弱，一票封顶「警惕」；D1=None（待观察）不计入红线。
    返回 health（0-1）/ verdict / dims 明细 / d1_ok。"""
    dims = []
    total = 0.0
    for d in PRICE_MODEL_DIMS:
        v = evidence.get(d["field"])
        if v is None:
            state, score = "yellow", 0.5   # 正在造/待观察
        elif bool(v):
            state, score = "green", 1.0
        else:
            state, score = "red", 0.0
        total += score
        dims.append({**d, "state": state})
    health = total / len(PRICE_MODEL_DIMS)
    d1 = evidence.get("d1_anchor_exogenous")
    d1_ok = bool(d1)
    if health >= 1.0:
        verdict = "六项全过——唯一同时具备需求刚性 + 政策豁免 + 期限匹配 + 物理约束下限的位置"
    elif d1 is False:
        verdict = "内生锚——共识逆转时没有底，结构脆弱（警惕/避开）"
    elif health >= 0.5:
        verdict = "部分通过——需补足未过维度再定价"
    else:
        verdict = "多项不通过——不具备可复用的定价基础"
    return dict(health=health, verdict=verdict, dims=dims, d1_ok=d1_ok)


def render_price_model(evidence: dict, name: str = "") -> str:
    """确定性输出「六维度价格模型判定」（Markdown）。三态：✓绿 / △黄(正在造·待观察) / ✗红。"""
    sc = score_price_model(evidence)
    title = name or evidence.get("track") or "（未命名资产）"
    marks = {"green": "✓", "yellow": "△", "red": "✗"}
    rows = []
    for d in sc["dims"]:
        rows.append(f"| {d['id']} {d['name']} | {marks[d['state']]} | {d['note']} |")
    table = "\n".join(rows)
    score_display = f"{sc['health'] * 6:g}/6"
    return (
        f"# {title} · 六维度价格模型判定\n\n"
        f"健康度：**{score_display}** ｜ 结论：**{sc['verdict']}**\n\n"
        f"| 维度 | 判定 | 说明 |\n|---|---|---|\n{table}\n"
    )


# ============================================================
# 中美绿色合规边界（行政令14105 + 关税 · 2026-09）
# ============================================================
# 决定性法律事实：美国对华投资限制（行政令14105，2024-10-28 最终规则，2025-01-02 生效）
# 只覆盖三个领域——半导体与微电子、量子信息技术、人工智能。清洁能源不在受限名单。
# → AI 的电力底座同时享有 AI 需求刚性 + 绿色投资政策豁免。
# 货物贸易：投资通道开着，货物通道基本封了（光伏 50% 关税、锂电 25%、多晶硅调查、光伏退税取消）。

US_CHINA_COMPLIANCE = {
    "semiconductor": ("受限", "行政令14105：半导体与微电子"),
    "quantum": ("受限", "行政令14105：量子信息技术"),
    "ai_software": ("受限", "行政令14105：人工智能"),
    "clean_energy": ("豁免", "清洁能源不在 14105 受限名单"),
    "nuclear_smr": ("豁免", "核电/SMR 属清洁能源，不在受限名单"),
    "grid": ("豁免", "电网是纯工程/资本问题，几乎不可能被政治化"),
    "long_duration_storage": ("豁免", "长时储能属清洁能源"),
    "liquid_cooling": ("豁免", "数据中心能效，不触及受限三领域"),
    "industrial_energy_efficiency": ("豁免", "工业能效/余热利用，不触及受限三领域"),
    "solar_component": ("关税暴露", "光伏电池片关税 50% + 出口退税取消 + 产能过剩"),
    "lithium_battery": ("关税暴露", "锂电加征 25% 关税"),
    "polysilicon": ("关税暴露", "中国对美太阳能级多晶硅发起调查"),
}


def compliance_exposure(field: str) -> tuple:
    """给定领域 → 合规判定 (status, reason)。status ∈ {受限, 豁免, 关税暴露, 未知}。确定性查表。"""
    return US_CHINA_COMPLIANCE.get(field, ("未知", "需按最新政策逐案核实"))


# ============================================================
# 产业链分层 + 退出概率维度（2026-09 设计文档落地）
# ============================================================
# 把《GateFix产业链分层与退出概率维度_设计文档》的 5 个确定性函数实现出来，
# 数据来自 gatefix_data 包（标的库/机构图谱/政策规则库）。
# 五层：component(上游零部件)/brain(中游大脑)/data(中游数据)/body(下游整机)/scenario(下游场景)。
# 制造属性：manufacturing(制造型)/intelligent(智能型)/platform(平台型)。
# 核心纪律：LLM 只产证据字段，本层全 Python 确定性计算，缺数据 fail-closed。
# 与既有三派 ARCHETYPES(body/brain/component，供具身估值法) 不冲突：五层是产业链定位
# 维度，三派是具身智能估值法自己的定价口径——本层新增 data/scenario 两层的估值锚。

# —— 数据地基（gatefix_data 包，2026-09 快照）；未部署则降级空表、函数 fail-closed ——
try:
    from gatefix_data import (
        EMBODIED_TARGETS, BACKER_GRAPH, POLICY_EXIT_ATTITUDE, EXIT_CHANNELS,
        target_by_name, targets_by_archetype, backers_of, backer_by_name,
        exit_attitude_for,
    )
    _GATEFIX_DATA_READY = True
except ImportError:  # gatefix_data 未部署 → 空表降级，全部 fail-closed
    EMBODIED_TARGETS, BACKER_GRAPH = [], []
    POLICY_EXIT_ATTITUDE, EXIT_CHANNELS = [], {}

    def target_by_name(name):
        return None

    def targets_by_archetype(archetype):
        return []

    def backers_of(name):
        return []

    def backer_by_name(name):
        return None

    def exit_attitude_for(key):
        return {"key": key, "attitude": "未知", "probability": "低",
                "basis": "gatefix_data 未部署，fail-closed"}

    _GATEFIX_DATA_READY = False

# —— 五层口径 + 估值锚 ——
VALUE_CHAIN_LAYERS = {
    "component": "上游零部件（卖零件给造机器人的）",
    "brain": "中游大脑（卖模型/算法）",
    "data": "中游数据（卖数据/仿真/评测基础设施）",
    "body": "下游整机（造机器人卖产品）",
    "scenario": "下游场景（用机器人卖结果）",
}

VALUE_CHAIN_ANCHORS = {
    "component": "制造业锚（PS + 国产替代 + 学习曲线）",
    "brain": "融资体量锚 + 门票锚（200亿俱乐部）",
    "data": "平台基础设施锚（复售率/PS，对标「数据英伟达」）",
    "body": "制造业锚（PS，需先判制造型/智能型）",
    "scenario": "场景锚（PS 3~8x + 复购 + 现金流）",
}

MANUFACTURING_PROFILES = {
    "manufacturing": "制造型（卖硬件，壁垒在工艺/良率/供应链）→ 制造业估值",
    "intelligent": "智能型（卖模型/算法，壁垒在模型/数据）→ 智能估值",
    "platform": "平台型（卖数据/基础设施）→ 平台估值",
}

CYCLE_STAGES = ("startup", "bubble", "shakeout_eve", "shakeout", "consolidation")


def classify_value_chain(evidence: dict) -> dict:
    """产业链五层定位（确定性，LLM-free）。
    优先采信 evidence['archetype']（若已在五层内）；否则按信号推断：
      sells_solution_service → scenario；sells_model_or_data → brain/data
      （sells_data_infrastructure 再分 data）；sells_components → component；
      sells_robot_product → body。
    缺数据/识别不出 → archetype=None（fail-closed，不猜）。
    返回 dict：archetype / layer / valuation_anchor / note。"""
    archetype = evidence.get("archetype")
    if archetype in VALUE_CHAIN_LAYERS:
        return {"archetype": archetype, "layer": VALUE_CHAIN_LAYERS[archetype],
                "valuation_anchor": VALUE_CHAIN_ANCHORS[archetype], "note": "直接采信"}
    if evidence.get("sells_solution_service"):
        a = "scenario"
    elif evidence.get("sells_model_or_data"):
        a = "data" if evidence.get("sells_data_infrastructure") else "brain"
    elif evidence.get("sells_components"):
        a = "component"
    elif evidence.get("sells_robot_product"):
        a = "body"
    else:
        a = None
    if a is None:
        return {"archetype": None, "layer": "未识别", "valuation_anchor": None,
                "note": "信号缺失，fail-closed（不猜）"}
    return {"archetype": a, "layer": VALUE_CHAIN_LAYERS[a],
            "valuation_anchor": VALUE_CHAIN_ANCHORS[a], "note": "由信号推断"}


def classify_manufacturing(evidence: dict) -> dict:
    """制造属性判定（确定性，LLM-free）。优先采信 evidence['mfg_profile']；
    否则按信号推断：platform_business → platform；moat_in_algorithm_data 或
    sells_model_or_data → intelligent；hardware_revenue_dominant 或
    sells_components/sells_robot_product → manufacturing。
    缺数据 → mfg_profile=None（fail-closed）。"""
    mfg = evidence.get("mfg_profile")
    if mfg in MANUFACTURING_PROFILES:
        return {"mfg_profile": mfg, "profile": MANUFACTURING_PROFILES[mfg], "note": "直接采信"}
    if evidence.get("platform_business"):
        m = "platform"
    elif evidence.get("moat_in_algorithm_data") or evidence.get("sells_model_or_data"):
        m = "intelligent"
    elif (evidence.get("hardware_revenue_dominant") or evidence.get("sells_components")
          or evidence.get("sells_robot_product")):
        m = "manufacturing"
    else:
        m = None
    if m is None:
        return {"mfg_profile": None, "profile": "未识别", "note": "信号缺失，fail-closed（不猜）"}
    return {"mfg_profile": m, "profile": MANUFACTURING_PROFILES[m], "note": "由信号推断"}


def backer_profile(target_name: str) -> dict:
    """机构接盘画像（确定性）。查 gatefix_data.BACKER_GRAPH 反向穿透，返回：
      backers（谁在投）、has_industrial_backer（有产业资本 → 并购退出上调）、
      has_soe_backer（有国资 → IPO 护航但并购交接受限）、
      industrial/soe/financial_vc（分类型名单）、exit_liquidity（退出流动性一句话）。
    无记录/查不到 → backers=[]，has_* 全 False（fail-closed）。"""
    backers = backers_of(target_name)
    industrial = [b for b in backers if b["type"] == "产业资本"]
    soe = [b for b in backers if b["type"] == "国资/政府基金"]
    fin_vc = [b for b in backers if b["type"] == "财务VC"]
    has_industrial = bool(industrial)
    has_soe = bool(soe)
    if not backers:
        liquidity = "未收录于机构图谱 → 退出接盘方未知（fail-closed）"
    elif has_industrial:
        liquidity = "有产业资本接盘方 → 并购退出概率上调"
    elif has_soe:
        liquidity = "有国资护航 → IPO 确定性高，但并购交接受限（国资退出需授权）"
    else:
        liquidity = "纯财务VC → 退出全靠二级流动性，解禁潮风险最高"
    return dict(backers=[b["name"] for b in backers],
                has_industrial_backer=has_industrial,
                has_soe_backer=has_soe,
                industrial=[b["name"] for b in industrial],
                soe=[b["name"] for b in soe],
                financial_vc=[b["name"] for b in fin_vc],
                exit_liquidity=liquidity)


def exit_probability(*, archetype=None, profitable=None,
                     commercial_validation=None) -> dict:
    """退出概率（确定性）。按 archetype + 商业验证 → 查 gatefix_data.POLICY_EXIT_ATTITUDE。
    分支：body 分盈利(body_profitable 欢迎/高)/纯叙事(body_narrative 收紧/低)；
    brain 分有/无规模化应用(brain_scaled 有条件欢迎/中 vs brain_unscaled 收紧/低)；
    其余（component/scenario/data）按 archetype 直查。
    缺 archetype/未识别 → fail-closed 返回 收紧/低。返回 dict：key/attitude/probability/basis。"""
    if archetype not in VALUE_CHAIN_LAYERS:
        return {"key": "unknown", "attitude": "未知", "probability": "低",
                "basis": "产业链层级未识别，fail-closed（不静默当'欢迎'）"}
    if archetype == "body":
        # 商业化验证（付费合同/复购/经济价值）即"非纯叙事"；盈利是更强信号
        key = "body_profitable" if (profitable or commercial_validation) else "body_narrative"
    elif archetype == "brain":
        key = "brain_scaled" if commercial_validation else "brain_unscaled"
    else:
        key = archetype
    return exit_attitude_for(key)

EXIT_SPECTRUM_LABELS = {
    "component": "上游零部件（减速器/丝杠/灵巧手/芯片）",
    "scenario": "下游场景（物流/工业/能源解决方案）",
    "data": "中游数据（数据/仿真/评测基础设施）",
    "body_profitable": "下游整机·有盈利/出货验证",
    "body_narrative": "下游整机·纯叙事/未商业化",
    "brain_scaled": "中游大脑·有规模化应用",
    "brain_unscaled": "中游大脑·无规模化应用",
}


def exit_probability_spectrum():
    """确定性：上中下游成功率全景（查 POLICY_EXIT_ATTITUDE）。返回 list[dict]。"""
    return [{"key": p["key"], "label": EXIT_SPECTRUM_LABELS.get(p["key"], p["key"]),
             "probability": p["probability"], "attitude": p["attitude"], "basis": p["basis"]}
            for p in POLICY_EXIT_ATTITUDE]


def render_exit_probability_spectrum(highlight=None):
    """确定性输出「上中下游成功率全景」Markdown 表（高亮目标层）。LLM-free。"""
    rows = []
    for s in exit_probability_spectrum():
        mark = " ← 目标" if (highlight and (s["key"] == highlight or s["key"].startswith(highlight + "_"))) else ""
        rows.append(f"| {s['label']}{mark} | {s['probability']} | {s['attitude']} |")
    return ("| 产业链位置 | 成功率 | 政策态度 |\n|---|---|---|\n" + "\n".join(rows)
            + "\n\n> 规律：**两头（上游零部件、下游场景）高，中间（纯整机、纯大脑）低** —— 两头卡位、跳过中间。")


def cn_embodied_cycle(*, player_count=None, capital_inflow=None,
                      price_war_started=None, demand_validated=None) -> dict:
    """产业周期定位（确定性，光伏类比）。四信号 → 阶段。
    阈值（2026-09 快照）：player_count≥200=玩家过剩；price_war_started=True=洗牌前夜；
    demand_validated=False=需求锚缺失（机器替代人拐点未到）。
    缺数据/非法 → stage=indeterminate（fail-closed）。返回 dict：stage/stage_cn/note。"""
    if price_war_started is None or demand_validated is None:
        return {"stage": "indeterminate", "stage_cn": "数据不足",
                "note": "周期信号缺失，fail-closed"}
    pc = _num(player_count)
    if pc is None:
        return {"stage": "indeterminate", "stage_cn": "数据不足",
                "note": "玩家数缺失/非法，fail-closed"}
    over_capacity = pc >= 200
    if over_capacity and price_war_started:
        stage, cn = "shakeout_eve", "洗牌前夜（玩家过剩 + 价格战已开打）"
    elif over_capacity:
        stage, cn = "bubble", "泡沫期（玩家过剩，价格战未开打）"
    else:
        stage, cn = "startup", "启动期（玩家尚少）"
    note = cn
    if not demand_validated:
        note += "；需求锚缺失（机器替代人拐点未到）——洗牌将比光伏更惨烈（无需求托底）"
    return {"stage": stage, "stage_cn": cn, "note": note}


def render_value_chain_exit_report(evidence: dict) -> str:
    """确定性输出「产业链定位 + 退出概率」Markdown 报告。LLM-free：所有结论来自
    classify_value_chain / classify_manufacturing / cn_embodied_cycle /
    exit_probability 的确定性计算，标的库命中时交叉核对 exit_prob。"""
    name = evidence.get("target_name") or "（未命名标的）"
    vc = classify_value_chain(evidence)
    mfg = classify_manufacturing(evidence)
    cycle = cn_embodied_cycle(
        player_count=evidence.get("player_count"),
        capital_inflow=evidence.get("capital_inflow"),
        price_war_started=evidence.get("price_war_started"),
        demand_validated=evidence.get("demand_validated"),
    )
    exitp = exit_probability(
        archetype=vc["archetype"],
        profitable=evidence.get("profitable"),
        commercial_validation=evidence.get("commercial_validation"),
    )
    lib_note = ""
    if name and name != "（未命名标的）":
        t = target_by_name(name)
        if t:
            lib_note = f"（标的库收录：archetype={t['archetype']}，exit_prob={t['exit_prob']}）"
    return (
        f"# {name} · 产业链定位 + 退出概率 {lib_note}\n\n"
        f"## 一、产业链五层定位\n\n"
        f"- 层级：**{vc['layer']}**\n"
        f"- 估值锚：{vc['valuation_anchor'] or '未识别'}\n"
        f"- {vc['note']}\n\n"
        f"## 二、制造属性\n\n- **{mfg['profile']}**（{mfg['note']}）\n\n"
        f"## 三、产业周期（光伏类比）\n\n- **{cycle['stage_cn']}**\n- {cycle['note']}\n\n"
        f"## 四、退出概率（2027 政策）\n\n"
        f"- 政策态度：**{exitp['attitude']}**\n"
        f"- 退出概率：**{exitp['probability']}**\n"
        f"- 依据：{exitp['basis']}\n\n"
        f"## 五、上中下游成功率全景（两头卡位、跳过中间）\n\n"
        f"{render_exit_probability_spectrum(vc['archetype'])}\n"
    )


# 供 engine.py 动态查找函数名用
REGISTRY = {
    "score_invest_governance": score_invest_governance,
    "score_landing_level": score_landing_level,
    "score_valuation_sanity": score_valuation_sanity,
    "score_track_valuation": score_track_valuation,
    "score_aidc_track_valuation": score_aidc_track_valuation,
    "score_mna_exit_likelihood": score_mna_exit_likelihood,
    "score_capital_attribution": score_capital_attribution,
}

REPAIR_REGISTRY = {
    "score_invest_governance": repair_invest_governance,
    "score_landing_level": repair_landing_level,
    "score_valuation_sanity": repair_valuation_sanity,
    "score_track_valuation": repair_track_valuation,
    "score_aidc_track_valuation": repair_aidc_track_valuation,
    "score_mna_exit_likelihood": repair_mna_exit_likelihood,
    "score_capital_attribution": repair_capital_attribution,
}
