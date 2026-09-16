"""
gatefix_data/embodied_targets.py —— 具身智能标的库（2026-09 快照）

把调研里的明星公司 + 场景派样本，转成 GateFix 可查表的确定性标的库。
字段：
  name         标的名称
  archetype    产业链五层定位（component/brain/data/body/scenario）
  mfg_profile  制造属性（manufacturing/intelligent/platform）
  funding      累计融资额（亿元；None=未披露/口径不清）
  valuation    最新估值或市值（亿元；None=未披露）
  revenue      年收入（亿元；None=未披露）
  profit       净利润（亿元；None=未披露或亏损）
  listed       上市状态（None=未上市）
  exit_prob    退出概率（高/中/低，按 2027 政策态度 + 商业化验证推导）
  note         一句话说明

五层口径（本调研推导）：
  component = 上游零部件（卖零件给造机器人的）
  brain     = 中游大脑（卖模型/算法）
  data      = 中游数据（卖数据/仿真/评测基础设施）
  body      = 下游整机（造机器人卖产品）
  scenario  = 下游场景（用机器人卖结果）

制造属性口径：
  manufacturing = 制造型（卖硬件，壁垒在工艺/良率/供应链）→ 制造业估值
  intelligent   = 智能型（卖模型/算法，壁垒在模型/数据）→ 智能估值
  platform      = 平台型（卖数据/基础设施，对标"数据英伟达"）→ 平台估值
"""

EMBODIED_TARGETS = [
    # ===== 上游零部件 component（硬科技+国产替代，政策欢迎，退出概率高）=====
    {
        "name": "帕西尼感知",
        "archetype": "component", "mfg_profile": "manufacturing",
        "funding": 35.0, "valuation": 100.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "高",
        "note": "多维触觉传感器+触觉芯片；比亚迪超亿元战略投资 → 硬科技+产业接盘方",
    },
    {
        "name": "因时机器人",
        "archetype": "component", "mfg_profile": "manufacturing",
        "funding": None, "valuation": None, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "高",
        "note": "灵巧手+微型伺服电缸(自研丝杠)；神骐/深创投/北京AI产业基金等",
    },
    {
        "name": "灵心巧手",
        "archetype": "component", "mfg_profile": "manufacturing",
        "funding": None, "valuation": 100.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "高",
        "note": "灵巧手(腱绳/直驱/连杆全覆盖)；蚂蚁/红杉/中金，估值超百亿",
    },
    {
        "name": "诺仕机器人",
        "archetype": "component", "mfg_profile": "manufacturing",
        "funding": None, "valuation": None, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "高",
        "note": "行星滚柱丝杠+微型直线执行器；顺为领投，国产替代核心件",
    },
    # ===== 中游大脑 brain（智能型，需"规模化应用"才能退，退出概率中）=====
    {
        "name": "自变量机器人",
        "archetype": "brain", "mfg_profile": "intelligent",
        "funding": 20.0, "valuation": 200.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "VLA+世界模型；唯一集齐美团/阿里云/字节三大厂，估值破200亿",
    },
    {
        "name": "千寻智能",
        "archetype": "brain", "mfg_profile": "intelligent",
        "funding": 50.0, "valuation": 200.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "VLA；顺为(雷军)/云锋(马云)领投，3个月近50亿",
    },
    {
        "name": "星海图",
        "archetype": "brain", "mfg_profile": "intelligent",
        "funding": 30.0, "valuation": 200.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "VLA+世界模型(配轮式双臂整机)；蚂蚁独家领投A轮，估值超200亿",
    },
    {
        "name": "章鱼动力",
        "archetype": "brain", "mfg_profile": "intelligent",
        "funding": 10.0, "valuation": None, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "低",
        "note": "世界模型/手脑一体；2026.1成立4个月3轮，尚无规模化应用 → 第五套红线",
    },
    # ===== 中游数据 data（平台型基础设施，退出概率中高）=====
    {
        "name": "光轮智能",
        "archetype": "data", "mfg_profile": "platform",
        "funding": None, "valuation": 150.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中高",
        "note": "数据+仿真+评测基础设施（对标「数据英伟达」）；两周两轮20亿，估值超150亿",
    },
    {
        "name": "觅蜂科技",
        "archetype": "data", "mfg_profile": "platform",
        "funding": None, "valuation": None, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "具身数据平台(智元系拆分)；中国电信领投Pre-A，为蚂蚁灵波供训练数据",
    },
    # ===== 下游整机 body（卖硬件，制造型估值；有盈利/出货验证者退出概率高，纯叙事者低）=====
    {
        "name": "宇树科技",
        "archetype": "body", "mfg_profile": "manufacturing",
        "funding": 30.0, "valuation": 1929.0, "revenue": 16.99, "profit": 2.78,
        "listed": "科创板688836", "exit_prob": "高",
        "note": "人形出货全球第一+四足3.3万台+盈利；已上市，估值从智能回归制造业(4449亿→1929亿)",
    },
    {
        "name": "智元机器人",
        "archetype": "body", "mfg_profile": "manufacturing",
        "funding": None, "valuation": 150.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "人形整机；腾讯/比亚迪/上汽/TCL等产业方，估值约150亿(2025.3)",
    },
    {
        "name": "银河通用",
        "archetype": "body", "mfg_profile": "manufacturing",
        "funding": 24.0, "valuation": 210.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "轮式双臂+具身大模型；天使轮18家机构，累计融资超24亿",
    },
    {
        "name": "傅利叶智能",
        "archetype": "body", "mfg_profile": "manufacturing",
        "funding": None, "valuation": 80.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "康复起家转人形(GR系)；软银愿景+沙特阿美Prosperity7背书",
    },
    {
        "name": "星动纪元",
        "archetype": "body", "mfg_profile": "manufacturing",
        "funding": 34.0, "valuation": 100.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "清华交叉院孵化；红杉/IDG/阿里/顺丰/中国联通，拟赴港IPO募8-10亿美元",
    },
    {
        "name": "星尘智能",
        "archetype": "body", "mfg_profile": "manufacturing",
        "funding": None, "valuation": 100.0, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中",
        "note": "绳驱人形/具身；蚂蚁+锦秋领投A/A+，估值破百亿",
    },
    # ===== 下游场景 scenario（卖结果，规模化应用+复购，政策欢迎，退出概率高）=====
    {
        "name": "极智嘉",
        "archetype": "scenario", "mfg_profile": "manufacturing",
        "funding": None, "valuation": 135.0, "revenue": 31.97, "profit": None,
        "listed": "港股", "exit_prob": "高",
        "note": "全球AMR第一(连续7年)，营收31.97亿/复购78%/70%海外，PS仅3.7倍被低估",
    },
    {
        "name": "优艾智合",
        "archetype": "scenario", "mfg_profile": "manufacturing",
        "funding": None, "valuation": 20.8, "revenue": None, "profit": None,
        "listed": "冲刺港股", "exit_prob": "中高",
        "note": "工业移动机器人；蓝驰/真格股东，估值20.8亿",
    },
    {
        "name": "云迹科技",
        "archetype": "scenario", "mfg_profile": "manufacturing",
        "funding": None, "valuation": None, "revenue": None, "profit": None,
        "listed": "港股02670", "exit_prob": "高",
        "note": "酒店/楼宇配送服务机器人，已上市",
    },
    {
        "name": "海柔创新",
        "archetype": "scenario", "mfg_profile": "manufacturing",
        "funding": None, "valuation": None, "revenue": None, "profit": None,
        "listed": None, "exit_prob": "中高",
        "note": "箱式仓储机器人(ACR)；源码资本投资",
    },
]


def target_by_name(name):
    """按名称查标的；未命中返回 None（fail-closed）。"""
    for t in EMBODIED_TARGETS:
        if t["name"] == name:
            return t
    return None


def targets_by_archetype(archetype):
    """按五层定位过滤标的列表。"""
    return [t for t in EMBODIED_TARGETS if t["archetype"] == archetype]
