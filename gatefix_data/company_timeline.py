"""
gatefix_data/company_timeline.py —— 公司业务布局时间库（2026-09 快照）

把 key 标的的【业务布局年份】编码成确定性查表，喂给 policy_alignment()
判断"业务布局 vs 政策发布"的先后（先知 vs 跟风）。替代 LLM 凭记忆猜公司成立年份。

字段：
  name         公司名
  layout_year  业务布局年份（以成立年份为代理；混合业务的公司以最早核心业务为准）
  sector       所属赛道
  keywords     匹配关键词（LLM 提取的公司名模糊匹配用）
  note         一句话说明

如实说明：年份来自公开报道，快照非穷尽；未收录的公司 → lookup 返回 None（fail-closed）。
混合业务（如中科类脑"能源AI→算电协同"）的布局年份以【最早核心业务】为准，
政策相关的细分业务线时间由 business_lines 层单独处理。
"""

COMPANY_TIMELINE = [
    # ============ 新能源 / 电池 / 光伏 ============
    {"name": "宁德时代", "layout_year": 2011, "sector": "动力电池",
     "keywords": ["宁德时代", "CATL", "宁德"],
     "note": "2011年成立，动力电池龙头"},
    {"name": "比亚迪", "layout_year": 1995, "sector": "新能源车",
     "keywords": ["比亚迪", "BYD"],
     "note": "1995年成立，2003年进入汽车，2008年推电动车"},
    {"name": "阳光电源", "layout_year": 1997, "sector": "光伏逆变器/储能",
     "keywords": ["阳光电源", "阳光"],
     "note": "1997年成立，光伏逆变器+储能龙头"},
    {"name": "隆基绿能", "layout_year": 2000, "sector": "光伏",
     "keywords": ["隆基", "隆基绿能"],
     "note": "2000年成立，单晶硅片龙头"},
    # ============ 算电协同 / 能源AI ============
    {"name": "中科类脑", "layout_year": 2017, "sector": "类脑智能/能源AI",
     "keywords": ["中科类脑", "类脑"],
     "note": "2017年成立，能源AI起家，后转算电协同"},
    {"name": "协鑫能科", "layout_year": 1992, "sector": "热电/新能源",
     "keywords": ["协鑫能科", "协鑫"],
     "note": "协鑫集团1992年起，热电/光伏/算电协同"},
    # ============ 大模型 / AI应用 ============
    {"name": "商汤科技", "layout_year": 2014, "sector": "AI/计算机视觉",
     "keywords": ["商汤", "SenseTime"],
     "note": "2014年成立，AI视觉起家"},
    {"name": "第四范式", "layout_year": 2014, "sector": "企业AI",
     "keywords": ["第四范式", "4Paradigm"],
     "note": "2014年成立，决策类AI"},
    {"name": "智谱AI", "layout_year": 2019, "sector": "大模型",
     "keywords": ["智谱", "智谱AI", "GLM", "ChatGLM"],
     "note": "2019年成立，清华系大模型"},
    {"name": "月之暗面", "layout_year": 2023, "sector": "大模型",
     "keywords": ["月之暗面", "Moonshot", "Kimi"],
     "note": "2023年成立，Kimi大模型"},
    {"name": "零一万物", "layout_year": 2023, "sector": "大模型",
     "keywords": ["零一万物", "01.AI", "李开复"],
     "note": "2023年成立，李开复创立，后转ToB"},
    {"name": "阶跃星辰", "layout_year": 2023, "sector": "大模型",
     "keywords": ["阶跃星辰", "StepFun"],
     "note": "2023年成立，阶跃大模型"},
    # ============ 芯片 / 算力 ============
    {"name": "海光信息", "layout_year": 2014, "sector": "国产CPU/DCU",
     "keywords": ["海光", "海光信息"],
     "note": "2014年成立，国产CPU+DCU"},
    {"name": "天数智芯", "layout_year": 2015, "sector": "国产GPU",
     "keywords": ["天数智芯"],
     "note": "2015年成立，国产GPGPU"},
    {"name": "寒武纪", "layout_year": 2016, "sector": "AI芯片",
     "keywords": ["寒武纪", "Cambricon"],
     "note": "2016年成立，AI芯片龙头"},
    {"name": "燧原科技", "layout_year": 2018, "sector": "AI芯片",
     "keywords": ["燧原", "燧原科技"],
     "note": "2018年成立，云端AI训练芯片，腾讯绑定"},
    {"name": "壁仞科技", "layout_year": 2019, "sector": "GPU",
     "keywords": ["壁仞", "壁仞科技"],
     "note": "2019年成立，通用GPU"},
    {"name": "摩尔线程", "layout_year": 2020, "sector": "GPU",
     "keywords": ["摩尔线程", "Moore Threads"],
     "note": "2020年成立，全功能GPU"},
    {"name": "沐曦", "layout_year": 2020, "sector": "GPU",
     "keywords": ["沐曦", "沐曦股份"],
     "note": "2020年成立，GPU"},
    # ============ 具身智能 / 机器人 ============
    {"name": "优必选", "layout_year": 2012, "sector": "人形机器人",
     "keywords": ["优必选", "UBTECH"],
     "note": "2012年成立，人形机器人第一股"},
    {"name": "宇树科技", "layout_year": 2016, "sector": "机器人",
     "keywords": ["宇树", "宇树科技", "Unitree"],
     "note": "2016年成立，四足/人形机器人"},
    {"name": "智元机器人", "layout_year": 2023, "sector": "具身智能",
     "keywords": ["智元机器人", "智元"],
     "note": "2023年成立，具身智能整机"},
    {"name": "银河通用", "layout_year": 2023, "sector": "具身智能",
     "keywords": ["银河通用", "Galbot"],
     "note": "2023年成立，具身智能"},
    {"name": "穹彻智能", "layout_year": 2023, "sector": "具身智能大脑",
     "keywords": ["穹彻", "穹彻智能"],
     "note": "2023年成立，具身智能大脑/世界模型"},
    # ============ 2026-09 扩充：储能 / 电池 / 氢能 / 补充大模型 ============
    {"name": "中创新航", "layout_year": 2007, "sector": "动力电池",
     "keywords": ["中创新航", "中航锂电"],
     "note": "2007年成立(原中航锂电)，动力电池"},
    {"name": "蜂巢能源", "layout_year": 2018, "sector": "动力电池",
     "keywords": ["蜂巢能源"],
     "note": "2018年成立，长城汽车孵化的电池公司"},
    {"name": "海辰储能", "layout_year": 2019, "sector": "储能电池",
     "keywords": ["海辰储能", "海辰"],
     "note": "2019年成立，厦门储能独角兽，IPO二度折戟"},
    {"name": "瑞浦兰钧", "layout_year": 2017, "sector": "动力电池/储能",
     "keywords": ["瑞浦兰钧", "青山集团"],
     "note": "2017年成立，青山集团旗下电池"},
    {"name": "卫蓝新能源", "layout_year": 2016, "sector": "固态电池",
     "keywords": ["卫蓝新能源", "卫蓝"],
     "note": "2016年成立，固态电池龙头"},
    {"name": "亿华通", "layout_year": 2012, "sector": "氢燃料电池",
     "keywords": ["亿华通"],
     "note": "2012年成立，氢燃料电池"},
    {"name": "国鸿氢能", "layout_year": 2015, "sector": "氢能",
     "keywords": ["国鸿氢能", "国鸿"],
     "note": "2015年成立，氢能"},
    {"name": "重塑能源", "layout_year": 2015, "sector": "氢能",
     "keywords": ["重塑能源", "重塑"],
     "note": "2015年成立，氢燃料电池系统"},
    {"name": "MiniMax", "layout_year": 2021, "sector": "大模型",
     "keywords": ["MiniMax", "稀宇科技", "海螺AI"],
     "note": "2021年成立，大模型+端侧"},
    {"name": "百川智能", "layout_year": 2023, "sector": "大模型",
     "keywords": ["百川智能", "百川", "王小川"],
     "note": "2023年成立，王小川创立"},
    {"name": "面壁智能", "layout_year": 2022, "sector": "大模型",
     "keywords": ["面壁智能", "面壁"],
     "note": "2022年成立，端侧模型"},
]


def lookup_company_year(company_name):
    """按公司名模糊匹配业务布局年份。未命中返回 None（fail-closed）。"""
    if not company_name:
        return None
    name = str(company_name)
    for c in COMPANY_TIMELINE:
        if name in c["name"] or c["name"] in name:
            return c["layout_year"]
        for kw in c["keywords"]:
            if kw in name:
                return c["layout_year"]
    return None


def lookup_company(company_name):
    """按公司名查整条记录。未命中返回 None。"""
    if not company_name:
        return None
    name = str(company_name)
    for c in COMPANY_TIMELINE:
        if name in c["name"] or c["name"] in name:
            return c
        for kw in c["keywords"]:
            if kw in name:
                return c
    return None
