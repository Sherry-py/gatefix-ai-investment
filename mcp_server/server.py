"""
mcp_server/server.py —— 把 GateFix 的 4D-CQ gate 包成一个 MCP server。

暴露三个 tool，显式分成读/写两类（读写工具分离）——MCP_TOOL_CATEGORIES 是这个分类的唯一
真源，新增 tool 时要求同步登记，tests/test_mcp_server.py 有一条测试断言
这个字典和 mcp 实际注册的 tool 集合完全对上：

  只读：
  - list_precondition_functions(case="ai_investment")：列出这个 case 里有哪些
    precondition_fn 可以被 authorize() 调用，每个附带对应 commit 的名字、
    是否 soft_commit、有没有 AUTO_REPAIR，以及打分函数的 docstring（里面
    写了这个函数期望什么样的 evidence 字段）。
  - gate_history_get(case=None, gate_state=None, action_id=None)：查询
    audit.py 记录下来的历史判定，不产生新判定，也不写任何东西。

  有副作用（写）：
  - authorize(case, precondition_fn, evidence)：对调用方传入的 evidence
    做真实判定——调用的是 preconditions.<case>.REGISTRY[precondition_fn]，
    走 agent/gated_loop.py 里 resolve_precondition() 那套真实三态路由 +
    AUTO_REPAIR 重试循环（soft_commit 型走 expectation_gate）。返回的
    route 只会是 PASS / ESCALATE / BYPASS_TO_HUMAN 之一。副作用：每次调用
    都会追加一条 append-only 审计记录（见 audit.py），这正是它被归为
    "写"工具、而不是和 list_precondition_functions 归在一起的原因。

这是"活证据"版本，不是案例回放：evidence 由调用方（任何 MCP client）在每
次调用时提供，不读 evidence/ai_investment_evidence.yaml 里的静态数据，所以
能真的挡在别的 agent 动作前面——前提是那个动作的证据形状匹配
preconditions/ai_investment.py 里某个已有的打分函数；只认得这 2 个可独立
授权的，不是能判断任意领域动作的通用 gate。

bypass_to_human 的 commit（如 friend_compensation）不会出现在
list_precondition_functions 里，也没法通过 authorize() 判定——即使它自己
也带一个 precondition_fn（friend_compensation 的 score_expectation_setting
是承诺阶段的内部预检，只在 CLI/agent-loop/LangGraph 里用，给最终人工决定
当参考），那个预检结果也不能被外部 client 当成"已授权"绕开人工审核，所以
_case_precondition_index() 显式把它排除在外，authorize() 也会拒绝调用它。
人情类的最终决定本来就该直接交给人，预检只是参考，不是判定。

仍然是 LLM-free、确定性：不调用任何模型/外部 API，判定过程和 CLI/agent
loop 完全一样可审计、可复现。

stdout 纪律：这个文件里没有一处裸 print()——stdout 只留给 MCP 协议本身用
（FastMCP 走 stdio transport），任何诊断信息都不该往 stdout 写，会污染协议
帧。tests/test_mcp_server.py 有一条静态检查断言这一点。

故意不做的事，如实说明（不是漏做，是评估过的边界）：这个 gate 的判定是
纯 Python 确定性计算（4D-CQ 加权求和 + 阈值比较），微秒级，不调用任何
网络/LLM API——"立即返回 job_id + 轮询"
异步模式是为真正耗时的操作设计的，套在一个瞬时完成的本地计算上只会
多一次轮询往返、不会更快，属于给不存在的问题上方案。如果未来 gate 判定
真的接了会阻塞的外部依赖（比如需要调一个真实的第三方核验 API），这个
决定要重新评估，不是永久豁免。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from gate import GateConfig  # noqa: E402
from engine import load_yaml  # noqa: E402
from agent.gated_loop import resolve_precondition  # noqa: E402
from audit import append_gate_decision, build_audit_record, query_gate_decisions  # noqa: E402

mcp = FastMCP("gatefix-gate")

# 读/写分类的唯一真源——见模块 docstring。
MCP_TOOL_CATEGORIES = {
    "list_precondition_functions": "read",
    "gate_history_get": "read",
    "authorize": "write",
}


def _case_precondition_index(case: str) -> dict:
    """precondition_fn -> {commit_id, name_cn, soft_commit} 的映射，从
    commits/<case>_commits.yaml 里真实读出来（不是编的）。commit 没有
    precondition_fn 字段的自然不进这个索引；commit 带 bypass_to_human 的
    也显式排除——即使它同时带了 precondition_fn（比如 friend_compensation
    的承诺阶段预检），那也只是内部参考，不能被外部 MCP client 当成可以
    独立 authorize() 的东西，绕过人工审核。"""
    commits_path = BASE_DIR / "commits" / f"{case}_commits.yaml"
    commits = load_yaml(commits_path)["commits"]
    index = {}
    for c in commits:
        fn_name = c.get("precondition_fn")
        if fn_name and not c.get("bypass_to_human"):
            index[fn_name] = {
                "commit_id": c["id"],
                "name_cn": c["name_cn"],
                "soft_commit": bool(c.get("soft_commit")),
            }
    return index


@mcp.tool()
def list_precondition_functions(case: str = "ai_investment") -> list[dict]:
    """列出 <case> 里所有可被 authorize() 调用的 precondition_fn，附带
    对应 commit 的名字、是否 soft_commit、有没有 AUTO_REPAIR，以及打分
    函数的 docstring（说明期望的 evidence 字段）。调用 authorize() 之前
    应该先调这个，搞清楚要传什么样的 evidence。"""
    module = importlib.import_module(f"preconditions.{case}")
    index = _case_precondition_index(case)
    repair_registry = getattr(module, "REPAIR_REGISTRY", {})
    out = []
    for fn_name, meta in index.items():
        fn = module.REGISTRY[fn_name]
        out.append({
            "precondition_fn": fn_name,
            "commit_id": meta["commit_id"],
            "commit_name": meta["name_cn"],
            "soft_commit": meta["soft_commit"],
            "has_auto_repair": fn_name in repair_registry,
            "doc": (fn.__doc__ or "").strip(),
        })
    return out


@mcp.tool()
def authorize(case: str, precondition_fn: str, evidence: dict) -> dict:
    """对调用方提交的 evidence 做真实的 4D-CQ 判定。

    返回值是机器可判定契约（gate_state/schema_version/
    cq_scores/reason_code/auto_repair_available/human_readable），外加为了
    不破坏既有调用方而保留的旧字段：route（=gate_state）、
    authorized（route=="PASS" 的布尔值）、R/C/O/Ro/Q、verifiable_ext、
    repair_attempts。

    核心契约：route/gate_state != "PASS" 时，调用这个 tool 的 agent 绝不能
    把对应的动作当作已授权去执行——这和 agent/gated_loop.py 里
    GatedAgentLoop 的契约完全一样，只是这次判定发生在 MCP 协议边界的
    另一侧。机器决策应该读 gate_state/reason_code，不要 parse human_readable。
    """
    module = importlib.import_module(f"preconditions.{case}")
    index = _case_precondition_index(case)
    if precondition_fn not in module.REGISTRY:
        raise ValueError(
            f"unknown precondition_fn={precondition_fn!r} for case={case!r}; "
            "call list_precondition_functions first to see what's available"
        )
    if precondition_fn not in index:
        raise ValueError(
            f"{precondition_fn!r} belongs to a bypass_to_human commit and "
            "cannot be authorized via evidence alone — call "
            "list_precondition_functions first; that commit must go through "
            "human review, this tool will not approve it for you"
        )

    meta = index[precondition_fn]
    score_fn = module.REGISTRY[precondition_fn]
    repair_fn = getattr(module, "REPAIR_REGISTRY", {}).get(precondition_fn)

    config = GateConfig()
    result = resolve_precondition(
        config, score_fn, evidence,
        repair_fn=repair_fn,
        soft_commit=meta.get("soft_commit", False),
    )
    contract = result.to_contract()

    # 副作用：追加一条审计记录。诚实的失败语义——审计写入失败
    # 不影响这次判定的返回值，只把失败情况附加进 human_readable，不吞掉
    # 也不假装成功；client 依然拿到真实、完整的 gate_state。
    audit_record = build_audit_record(
        action_id=meta["commit_id"], gate_state=result.route,
        reason_code=result.reason_code,
        cq_scores={"relevance": result.R, "coverage": result.C,
                   "ordering": result.O, "robustness": result.Ro},
        schema_version=contract["schema_version"],
        thresholds={"tau_pass": config.tau_pass, "tau_repair": config.tau_repair},
        case=case,
    )
    write_result = append_gate_decision(audit_record)
    if not write_result.ok:
        contract["human_readable"] += f"　[AUDIT WRITE FAILED: {write_result.error}]"

    return {
        **contract,
        "route": result.route,
        "authorized": result.route == "PASS",
        "R": result.R, "C": result.C, "O": result.O, "Ro": result.Ro, "Q": result.Q,
        "verifiable_ext": result.verifiable_ext,
        "repair_attempts": result.repair_attempts,
        "reason": result.reason,
        "audit_write_ok": write_result.ok,
    }


@mcp.tool()
def gate_history_get(case: Optional[str] = None, gate_state: Optional[str] = None,
                      action_id: Optional[str] = None) -> list[dict]:
    """只读工具：查询 audit.py 记录的历史判定，用于复盘"当初
    为什么放行/拦截"。不产生新判定，不写任何东西——和 authorize() 是两个
    独立的 tool，MCP client 不该把这个当成能触发判定的入口。

    参数都是可选过滤条件；不传就返回全部历史（可能很大，调用方自己控制
    要不要传窄一点的过滤条件）。"""
    records = query_gate_decisions(action_id=action_id, gate_state=gate_state)
    if case is not None:
        records = [r for r in records if r.get("case") == case]
    return records


if __name__ == "__main__":
    mcp.run()
