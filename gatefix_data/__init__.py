"""
gatefix_data —— GateFix 的数据地基（2026-09 快照）

把《具身智能产业链投资调研.xlsx》里的调研数据，转成 GateFix 可查表的确定性常量，
补齐"算法强、模型够用、数据薄"的短板。三块数据：

  1. EMBODIED_TARGETS   标的库（20 家：产业链五层 × 制造属性 × 财务 × 退出概率）
  2. BACKER_GRAPH       机构资本图谱（33 家机构 × 被投公司，喂给 backer_profile）
  3. POLICY_EXIT_ATTITUDE / EXIT_CHANNELS  政策规则库（2027 政策态度 + 退出门槛）

本包只提供【数据 + 简单查表】；复杂判定函数（classify_value_chain /
backer_profile / exit_probability）放在 preconditions/ai_investment.py，
与本包解耦——数据一处更新、全量生效。

如实说明：数据来自 2026-08/09 公开报道，非穷尽、非投资建议；None 表示"未披露/
口径不清"而非"为 0"（fail-closed 语义）。
"""

from .embodied_targets import EMBODIED_TARGETS, target_by_name, targets_by_archetype
from .backer_graph import BACKER_GRAPH, backer_by_name, backers_of, backers_by_type
from .policy_exit import POLICY_EXIT_ATTITUDE, EXIT_CHANNELS, exit_attitude_for

__all__ = [
    "EMBODIED_TARGETS",
    "target_by_name",
    "targets_by_archetype",
    "BACKER_GRAPH",
    "backer_by_name",
    "backers_of",
    "backers_by_type",
    "POLICY_EXIT_ATTITUDE",
    "EXIT_CHANNELS",
    "exit_attitude_for",
]
