"""
gatefix_data/policy_timeline.py —— 政策时间线库（2026-09 快照）

把关键产业政策的【发布时间】编码成确定性查表，喂给 policy_alignment()
判断"业务布局 vs 政策发布"的先后（先知 vs 跟风）。替代 LLM 凭记忆猜年份。

字段：
  name       政策名称
  issue_year 发布/首次提出年份
  ptype      environment(放水养鱼·环境型) / subsidy(定点支持·补贴型) / regulatory(监管/准入)
  keywords   匹配关键词（LLM 提取的政策名模糊匹配用）
  note       一句话说明

如实说明：年份来自公开报道，快照非穷尽；未收录的政策 → lookup 返回 None（fail-closed）。
"""

POLICY_TIMELINE = [
    {"name": "双碳目标(30·60)", "issue_year": 2020, "ptype": "environment",
     "keywords": ["双碳", "碳达峰", "碳中和", "30·60", "3060"],
     "note": "碳达峰碳中和，催生新能源/绿电/碳市场/储能"},
    {"name": "东数西算", "issue_year": 2022, "ptype": "environment",
     "keywords": ["东数西算", "算力枢纽", "国家枢纽节点"],
     "note": "8大算力枢纽，催生数据中心西迁与绿电直连"},
    {"name": "算电协同", "issue_year": 2026, "ptype": "environment",
     "keywords": ["算电协同", "算力电力协同", "算随电动", "电随算动"],
     "note": "2026首次写入政府工作报告，列为新基建工程"},
    {"name": "新型电力系统", "issue_year": 2021, "ptype": "environment",
     "keywords": ["新型电力系统", "以电代煤", "源网荷储"],
     "note": "中央财经委第九次会议提出，新能源消纳/调度/储能"},
    {"name": "人工智能+行动", "issue_year": 2024, "ptype": "environment",
     "keywords": ["人工智能+", "AI+行动", "AI赋能"],
     "note": "2024政府工作报告首次提出'人工智能+'，产业数字化"},
    {"name": "人形机器人/具身智能", "issue_year": 2023, "ptype": "environment",
     "keywords": ["人形机器人", "具身智能", "机器人产业"],
     "note": "工信部《人形机器人创新发展指导意见》(2023-10)"},
    {"name": "生成式AI管理(大模型备案)", "issue_year": 2023, "ptype": "regulatory",
     "keywords": ["大模型备案", "生成式AI", "生成式人工智能", "算法备案"],
     "note": "《生成式人工智能服务管理暂行办法》2023-08施行"},
    {"name": "动力电池白名单", "issue_year": 2015, "ptype": "subsidy",
     "keywords": ["动力电池白名单", "电池规范条件", "动力电池目录"],
     "note": "《汽车动力蓄电池行业规范条件》，扶持国产电池"},
    {"name": "专精特新", "issue_year": 2021, "ptype": "subsidy",
     "keywords": ["专精特新", "小巨人", "单项冠军"],
     "note": "工信部专精特新'小巨人'认定，扶持硬科技中小企业"},
    {"name": "数据要素×", "issue_year": 2023, "ptype": "environment",
     "keywords": ["数据要素", "数据要素×", "数据二十条", "数据资产"],
     "note": "'数据要素×'三年行动计划，数据资产化/交易"},
    {"name": "绿电交易/绿证", "issue_year": 2021, "ptype": "environment",
     "keywords": ["绿电交易", "绿证", "绿电直供", "绿电直连", "可再生能源消纳"],
     "note": "绿电交易试点启动(2021-09)，绿证全覆盖"},
    {"name": "源网荷储一体化", "issue_year": 2021, "ptype": "environment",
     "keywords": ["源网荷储", "风光储一体化", "多能互补"],
     "note": "国家发改委/能源局指导意见，源网荷储一体化"},
    {"name": "港股18C", "issue_year": 2023, "ptype": "regulatory",
     "keywords": ["18C", "特专科技", "港股18C"],
     "note": "联交所特专科技公司上市机制(2023-03)，未盈利硬科技"},
    {"name": "以旧换新/设备更新", "issue_year": 2024, "ptype": "subsidy",
     "keywords": ["以旧换新", "设备更新", "两新政策"],
     "note": "《推动大规模设备更新和消费品以旧换新行动方案》(2024-03)"},
    {"name": "新能源车购置税减免", "issue_year": 2014, "ptype": "subsidy",
     "keywords": ["购置税减免", "新能源车补贴", "新能源车政策"],
     "note": "新能源车购置税减免，催生电动车产业链"},
    {"name": "电力现货市场", "issue_year": 2017, "ptype": "environment",
     "keywords": ["电力现货", "现货市场", "电力市场化交易"],
     "note": "首批现货试点(2017)，2021扩大，催生虚拟电厂/售电"},
]


def lookup_policy_year(policy_name):
    """按政策名模糊匹配发布时间年份。未命中返回 None（fail-closed）。"""
    if not policy_name:
        return None
    name = str(policy_name)
    for p in POLICY_TIMELINE:
        # 精确名或关键词命中
        if name in p["name"] or p["name"] in name:
            return p["issue_year"]
        for kw in p["keywords"]:
            if kw in name:
                return p["issue_year"]
    return None


def lookup_policy(name):
    """按政策名查整条记录。未命中返回 None。"""
    if not name:
        return None
    for p in POLICY_TIMELINE:
        if name in p["name"] or p["name"] in name:
            return p
        for kw in p["keywords"]:
            if kw in name:
                return p
    return None
