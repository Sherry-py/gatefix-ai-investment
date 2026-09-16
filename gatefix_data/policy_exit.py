"""
gatefix_data/policy_exit.py —— 退出政策规则库（2027 政策动态 + 退出门槛，2026-09 快照）

把 2026 交易所政策（科创板第五套扩至 AI、行业目录新增"机器人"、传收紧人形
机器人初创 IPO）编码成确定性查表，喂给 exit_probability()。与 preconditions
里的 CN_EXIT_PATHS / HK_EXIT_PATHS（静态财务门槛）互补：那是"够不够格到哪一档"，
这里是"政策欢迎还是收紧 → 大概率/小概率退"。

来源：
  《事关AI大模型企业科创板上市标准，上交所发布最新指引》(证券时报, 2026-06-17)
  《动态完善上市标准体系…A股市场打造境内优质企业上市首选地》(中国证券报, 2026-09-14)
  《传内地收紧人形机械人初创IPO》(星岛头条, 2026-09-10)
"""

# 政策态度 × 退出概率 查表（按"层级/形态"匹配，喂给 exit_probability）
# key 的分支语义：
#   component           上游零部件（硬科技/国产替代）
#   scenario            下游场景（规模化应用/商业化验证）
#   data                中游数据（平台基础设施）
#   body_profitable     下游整机·已盈利或有出货验证（宇树样本）
#   body_narrative      下游整机·未盈利纯叙事（收紧对象）
#   brain_scaled        中游大脑·有规模化应用（第五套放行）
#   brain_unscaled      中游大脑·无规模化应用（第五套红线）
POLICY_EXIT_ATTITUDE = [
    {"key": "component",        "attitude": "欢迎",       "probability": "高",   "basis": "科创板行业目录新增'机器人'(高端装备)、补短板"},
    {"key": "scenario",         "attitude": "欢迎",       "probability": "高",   "basis": "规模化应用/商业化验证是政策硬指标"},
    {"key": "data",             "attitude": "有条件欢迎", "probability": "中高", "basis": "第五套扩至AI，需'产品上线+规模化应用'"},
    {"key": "body_profitable",  "attitude": "欢迎",       "probability": "高",   "basis": "宇树样本：盈利+出货验证(非纯叙事)"},
    {"key": "body_narrative",   "attitude": "收紧",       "probability": "低",   "basis": "传内地收紧人形机器人初创IPO(纯叙事/未商业化)"},
    {"key": "brain_scaled",     "attitude": "有条件欢迎", "probability": "中",   "basis": "第五套需'产品上线+规模化应用'"},
    {"key": "brain_unscaled",   "attitude": "收紧",       "probability": "低",   "basis": "第五套'规模化应用'红线，纯模型不退"},
]

# 退出门槛（版本化快照，监管变更一处更新）
EXIT_CHANNELS = {
    "version": "2026-09",
    "科创板": {
        "标准一(盈利)": "市值≥10亿 + 净利累计≥5000万",
        "标准二~四": "市值15~30亿 + 营收2~3亿 + 研发占比15%",
        "标准五(未盈利, 2026扩至AI)": "市值≥40亿 + AI大模型'产品上线+规模化应用'",
        "行业目录(2026新增)": "高端装备新增'机器人'; +量子/氢能/脑机接口/生物制造",
        "科创成长层": "未盈利硬科技的通道(2026设立)",
    },
    "港股18C": {
        "已商业化": "市值≥40亿港元 + 收益2.5亿港元",
        "未商业化": "市值≥80亿港元",
    },
    "创业板": {
        "盈利标准": "近两年净利累计≥5000万",
        "第三套(未盈利)": "2026启用",
        "第四套": "2026增设",
    },
    "北交所": "市值≥2亿 + 净利≥1500万",
    "收紧信号": "2026-09 传内地收紧人形机器人初创IPO(纯叙事/未商业化)",
}


def exit_attitude_for(key):
    """按 key 查政策态度；未命中返回 fail-closed 默认（收紧/低概率）。"""
    for p in POLICY_EXIT_ATTITUDE:
        if p["key"] == key:
            return p
    return {"key": key, "attitude": "未知", "probability": "低",
            "basis": "未收录，fail-closed（不静默当'欢迎'）"}
