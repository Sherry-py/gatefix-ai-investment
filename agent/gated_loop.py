"""
agent/gated_loop.py —— 把 gate.py 的三态路由嵌进一个 agent loop：
reason → gate → (仅 PASS) act。

复用 gate.py 的 GateConfig 和 preconditions/<case>.py 的
REGISTRY/REPAIR_REGISTRY，不引入新的判定逻辑，也不调用任何模型/LLM——
本仓库设计上是 LLM-free 的确定性 demo（见 README「no LLM call needed」）。
tool_fn 返回的整数是抽象 action-cost 单位，不是 LLM token 计数——这个仓库
测不了 token 成本，不假装测。

Route → 二元映射（不新增 REFUSE，复用 gate.py 的 route 词汇表）：
    PASS                        → 放行，tool_fn 执行
    ESCALATE / BYPASS_TO_HUMAN  → 阻断，tool_fn 绝不执行
    AUTO_REPAIR                 → 不对外暴露。engine.py::run_case 证明这是
                                  "补证据后重新判定"的真实重试循环
                                  （while True + REPAIR_REGISTRY + k_dry），
                                  make_case_gate_fn 在适配层内部原样复刻，
                                  直到收敛成 PASS/ESCALATE 才返回。

没有 CLARIFY 态，也没有"非 PASS 但仍放行"的旁路开关：gate.py::route() 只
产出 PASS/AUTO_REPAIR/ESCALATE，engine.py 另加 BYPASS_TO_HUMAN（人情类
证据）。非 PASS 时 tool_fn 绝不会被调用——这是这个模块唯一的契约，不可
配置、不可放宽。
"""

from __future__ import annotations

import importlib
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from gate import (  # noqa: E402
    GateConfig, ReasonCode, classify_regular_reason_code, build_gate_contract,
    EXIT_CODE, EXIT_CODE_INTERNAL_ERROR, safe_score, safe_repair,
)
from engine import load_yaml  # noqa: E402


@dataclass
class GateResult:
    """一次 gate 判定的最终结果。route 只会是 PASS / ESCALATE /
    BYPASS_TO_HUMAN 之一——AUTO_REPAIR 已经在 make_case_gate_fn 内部收敛掉，
    不会出现在这里（和 engine.py 写进 gate_record.jsonl 的最终 route 一致）。
    """

    route: str
    R: float
    C: float
    O: float
    Ro: float
    Q: float
    verifiable_ext: bool = True
    dry_rounds: int = 0
    repair_attempts: int = 0
    reason: str = ""
    reason_code: str = ""

    @property
    def blocked(self) -> bool:
        return self.route != "PASS"

    def to_contract(self) -> dict:
        """任务 1：机器可判定的授权契约。下游只应该读 gate_state/
        reason_code/auto_repair_available 做决策，reason 只是给人看。"""
        return build_gate_contract(
            gate_state=self.route, R=self.R, C=self.C, O=self.O, Ro=self.Ro,
            reason_code=self.reason_code,
            auto_repair_available=self.repair_attempts > 0,
            human_readable=self.reason,
        )


@dataclass
class StepTelemetry:
    step: int
    tool: str
    route: str
    gate_latency_ms: float
    gate_tokens: int  # 抽象 action-cost 单位（见模块 docstring），不是 LLM token
    action_latency_ms: float = 0.0
    action_tokens: int = 0  # 同上，来自 tool_fn 的抽象 cost
    blocked: bool = False

    @property
    def total_latency_ms(self) -> float:
        return self.gate_latency_ms + self.action_latency_ms

    @property
    def total_tokens(self) -> int:
        return self.gate_tokens + self.action_tokens


@dataclass
class LoopTrace:
    steps: list = field(default_factory=list)
    final_output: Optional[str] = None
    halted_by_gate: bool = False

    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.steps)

    def total_latency_ms(self) -> float:
        return sum(s.total_latency_ms for s in self.steps)

    def gate_overhead_ratio(self) -> float:
        total = self.total_latency_ms()
        if total == 0:
            return 0.0
        return sum(s.gate_latency_ms for s in self.steps) / total


GateFn = Callable[[str, dict], GateResult]
ToolFn = Callable[[dict], "tuple[str, int]"]
ReasonFn = Callable[[dict], "tuple[dict, int]"]


class GatedAgentLoop:
    """核心契约：gate_fn 每步只返回 PASS 或阻断（ESCALATE/BYPASS_TO_HUMAN
    已在适配层收敛为非 PASS）；非 PASS 时 tool_fn 绝不被调用。没有开关能
    关掉这条——这是这个类存在的全部意义。

    fail-closed 兜底（任务 2）：gate_fn 是调用方传进来的，可以是
    make_case_gate_fn 那种内置实现，也可以是任何自定义函数——这里是所有
    动作执行前的唯一收口点，所以在这一层再加一道兜底：gate_fn 本身抛出的
    任何异常都收敛成阻断（BYPASS_TO_HUMAN），不会被异常冒泡绕过、变成
    "gate 没判定就默认放行"。make_case_gate_fn/resolve_precondition 内部
    已经对 score_fn/repair_fn 做了 fail-closed（见 gate.py::safe_score/
    safe_repair），这里是给"gate_fn 自己就有 bug"这类更外层的故障上的
    第二道保险，两者不是重复：内层管的是 evaluator 的故障，这里管的是
    gate_fn 整体（包括适配层自己的代码）的故障。"""

    def __init__(self, gate_fn: GateFn, tool_fn: ToolFn, reason_fn: ReasonFn,
                 max_steps: int = 6):
        self.gate_fn = gate_fn
        self.tool_fn = tool_fn
        self.reason_fn = reason_fn
        self.max_steps = max_steps

    def run(self, context: str, initial_state: dict) -> LoopTrace:
        trace = LoopTrace()
        state = dict(initial_state)
        for step in range(1, self.max_steps + 1):
            action, _reason_tokens = self.reason_fn(state)
            if action.get("type") == "finish":
                trace.final_output = action.get("output")
                return trace

            tool_name = action.get("tool", "unknown")
            t0 = time.perf_counter()
            try:
                gate = self.gate_fn(context, action)
            except Exception as exc:  # noqa: BLE001 — fail-closed 兜底，见类 docstring
                gate = GateResult(
                    route="BYPASS_TO_HUMAN", R=0, C=0, O=0, Ro=0, Q=0,
                    verifiable_ext=False,
                    reason=f"gate_fn raised {type(exc).__name__}: {exc}",
                    reason_code=ReasonCode.EVALUATOR_FAULT,
                )
            gate_ms = (time.perf_counter() - t0) * 1000
            gate_cost = _gate_cost_estimate(gate)

            tel = StepTelemetry(step=step, tool=tool_name, route=gate.route,
                                 gate_latency_ms=gate_ms, gate_tokens=gate_cost)

            if gate.blocked:
                tel.blocked = True
                trace.steps.append(tel)
                trace.halted_by_gate = True
                trace.final_output = (
                    f"BLOCKED[{gate.route}]: {gate.reason or 'gate did not authorize this action'}"
                )
                return trace

            t1 = time.perf_counter()
            output, action_cost = self.tool_fn(action)
            tel.action_latency_ms = (time.perf_counter() - t1) * 1000
            tel.action_tokens = action_cost
            trace.steps.append(tel)
            state = _advance_state(state, action, output)

        trace.final_output = state.get("last_output")
        return trace


def _gate_cost_estimate(gate: GateResult) -> int:
    """抽象 action-cost：这个仓库的 gate 是确定性 Python 计算（quality_score
    对 R/C/O/Ro 四个维度加权求和），不调用任何计费 API，没有真实"token"
    概念。这里按"评估了 4 个维度"计 4 个抽象 cost 单位——描述的是计算量的
    形状，不是编造出来的 LLM 用量数字。"""
    return 4


def _advance_state(state: dict, action: dict, output: str) -> dict:
    new = dict(state)
    new["last_output"] = output
    new.setdefault("history", []).append({"action": action, "output": output})
    return new


# ---------------------------------------------------------------------------
# 真实接线：把上面的 GateFn / ReasonFn / ToolFn 接到 ai_investment 这个
# case 的数据和代码上——不是占位，是 engine.py 同一套 commits/bindings/
# evidence/preconditions 四处配置的复用。
# ---------------------------------------------------------------------------


def make_case_gate_fn(case: str) -> GateFn:
    """真正接到 preconditions/<case>.py 的 REGISTRY/REPAIR_REGISTRY 和
    evidence/<case>_evidence.yaml、commits/<case>_commits.yaml 上的
    gate_fn 工厂。忠实复刻 engine.py::run_case 里的三条分支（bypass_to_human /
    soft_commit / 常规三态路由 + AUTO_REPAIR 重试循环），只是把结果收敛成
    单次调用返回的 GateResult，供 GatedAgentLoop 使用。"""
    config = GateConfig()
    precondition_module = importlib.import_module(f"preconditions.{case}")
    registry = precondition_module.REGISTRY
    repair_registry = getattr(precondition_module, "REPAIR_REGISTRY", {})

    commits_path = BASE_DIR / "commits" / f"{case}_commits.yaml"
    evidence_path = BASE_DIR / "evidence" / f"{case}_evidence.yaml"
    commits_by_id = {c["id"]: c for c in load_yaml(commits_path)["commits"]}
    all_evidence = load_yaml(evidence_path)

    def gate_fn(context: str, action: dict) -> GateResult:
        commit_id = action["commit_id"]
        commit = commits_by_id[commit_id]
        evidence = dict(all_evidence.get(commit_id, {}))

        # ---- 分支 1：人情类，直接旁路给人（engine.py 分支 1 的等价物） ----
        if commit.get("bypass_to_human"):
            reason = commit.get("bypass_reason", "")
            # 同 engine.py：precondition_fn（若有）只是承诺阶段的预检，记录在
            # reason 里，不影响最终恒为 BYPASS_TO_HUMAN 的路由。
            if commit.get("precondition_fn"):
                score_fn = registry[commit["precondition_fn"]]
                pre, pre_fault = safe_score(score_fn, evidence)
                # 同 engine.py：预检异常不改变这条分支恒为 BYPASS_TO_HUMAN
                # 的终态，只是不让异常冒泡崩掉整个 gate_fn 调用。
                if pre_fault:
                    reason = f"承诺阶段：预检异常（{pre['notes']}）　{reason}"
                else:
                    pre_allowed = config.expectation_gate(
                        pre.get("contains_promise", True),
                        pre.get("has_feasibility_evidence", False),
                    )
                    pre_route = "PASS" if pre_allowed else "ESCALATE"
                    reason = f"承诺阶段：{pre_route}——{pre['notes']}　{reason}"
            return GateResult(
                route="BYPASS_TO_HUMAN", R=0, C=0, O=0, Ro=0, Q=0,
                verifiable_ext=False,
                reason=reason,
                reason_code=ReasonCode.BYPASS_HUMAN_JUDGMENT_REQUIRED,
            )

        score_fn = registry[commit["precondition_fn"]]
        repair_fn = repair_registry.get(commit["precondition_fn"])

        return resolve_precondition(
            config, score_fn, evidence,
            repair_fn=repair_fn,
            soft_commit=bool(commit.get("soft_commit")),
        )

    return gate_fn


def resolve_precondition(
    config: GateConfig,
    score_fn: Callable[[dict], dict],
    evidence: dict,
    *,
    repair_fn: Optional[Callable[[dict], dict]] = None,
    soft_commit: bool = False,
) -> GateResult:
    """给定一个真实的打分函数 + 一份证据，解出最终 GateResult。这是
    engine.py::run_case 里"软 commit 走 expectation_gate / 常规 commit 走
    三态路由 + AUTO_REPAIR 重试循环"这两条分支的原样复刻，抽成独立函数是
    因为它现在有两个真实调用方：make_case_gate_fn（case+commit_id，读静态
    evidence yaml）和 mcp_server/server.py（precondition_fn+外部传入的活
    evidence，供任意 MCP client 调用）——两者必须走同一份判定逻辑，不能
    各写一份、慢慢长歪。

    soft_commit 分支：不看 R/C/O/Ro 阈值，改看 contains_promise /
    has_feasibility_evidence 这两个布尔量（expectation_gate）。
    常规分支：AUTO_REPAIR 只在这个函数内部出现，循环收敛后只会返回
    PASS 或 ESCALATE——调用方永远只看到二态结果。任务 2（fail-closed）：
    score_fn/repair_fn 抛异常时的第三种终态是 BYPASS_TO_HUMAN，不是
    PASS，也不是普通的 ESCALATE——见 gate.py::safe_score/safe_repair。"""
    if soft_commit:
        result, fault = safe_score(score_fn, evidence)
        if fault:
            return GateResult(
                route="BYPASS_TO_HUMAN", R=0, C=0, O=0, Ro=0, Q=0,
                verifiable_ext=False, reason=result["notes"],
                reason_code=ReasonCode.EVALUATOR_FAULT,
            )
        allowed = config.expectation_gate(
            result.get("contains_promise", True),
            result.get("has_feasibility_evidence", False),
        )
        return GateResult(
            route="PASS" if allowed else "ESCALATE",
            R=result["R"], C=result["C"], O=result["O"], Ro=result["Ro"],
            Q=config.quality_score(result["R"], result["C"], result["O"], result["Ro"]),
            verifiable_ext=result["verifiable_ext"],
            reason=result.get("notes", ""),
            reason_code=(ReasonCode.SOFT_COMMIT_PROMISE_SUPPORTED if allowed
                         else ReasonCode.SOFT_COMMIT_PROMISE_UNSUPPORTED),
        )

    repair_fn_registered = repair_fn is not None
    ev = dict(evidence)
    dry_rounds = 0
    repair_attempts = 0
    while True:
        result, fault = safe_score(score_fn, ev)
        if fault:
            return GateResult(
                route="BYPASS_TO_HUMAN", R=0, C=0, O=0, Ro=0, Q=0,
                verifiable_ext=False, dry_rounds=dry_rounds,
                repair_attempts=repair_attempts, reason=result["notes"],
                reason_code=ReasonCode.EVALUATOR_FAULT,
            )
        Q = config.quality_score(result["R"], result["C"], result["O"], result["Ro"])
        route = config.route(Q, result["verifiable_ext"], dry_rounds)

        if route == "AUTO_REPAIR" and repair_fn is not None:
            repair_attempts += 1
            new_evidence, repair_fault = safe_repair(repair_fn, ev)
            if repair_fault:
                return GateResult(
                    route="BYPASS_TO_HUMAN", R=result["R"], C=result["C"],
                    O=result["O"], Ro=result["Ro"], Q=Q,
                    verifiable_ext=result["verifiable_ext"], dry_rounds=dry_rounds,
                    repair_attempts=repair_attempts,
                    reason="repair_fn raised — fail-closed to BYPASS_TO_HUMAN",
                    reason_code=ReasonCode.EVALUATOR_FAULT,
                )
            if new_evidence == ev:
                dry_rounds += 1
            else:
                ev = new_evidence
                dry_rounds = 0
            if dry_rounds >= config.k_dry:
                route = "ESCALATE"
                break
            continue

        if route == "AUTO_REPAIR":
            # repair_fn 是 None：这个精度分数落进了"可以自动修"的区间，但这个
            # precondition_fn 没有注册对应的补证函数，没有自动化手段真的去
            # 补——不能停留在 AUTO_REPAIR 这个非终态，降级为 ESCALATE
            # （和 k_dry 耗尽时的处理方式一致）。发现过程：用真实但非案例内的
            # evidence 测试 MCP server 的 authorize() 时，score_air_freight_dispatch
            # 落进 AUTO_REPAIR 区间但没有 repair_fn，暴露了这条路径。
            route = "ESCALATE"
        break

    reason_code = classify_regular_reason_code(
        route=route, Q=Q, tau_repair=config.tau_repair,
        verifiable_ext=result["verifiable_ext"], dry_rounds=dry_rounds,
        k_dry=config.k_dry, repair_attempts=repair_attempts,
        repair_fn_registered=repair_fn_registered,
    )
    return GateResult(
        route=route, R=result["R"], C=result["C"], O=result["O"], Ro=result["Ro"], Q=Q,
        verifiable_ext=result["verifiable_ext"], dry_rounds=dry_rounds,
        repair_attempts=repair_attempts, reason=result.get("notes", ""),
        reason_code=reason_code,
    )


def make_case_reason_fn(case: str) -> ReasonFn:
    """最小实现，且如实注明：这不是一个真正的 planner / LLM 推理步骤——本
    仓库里没有这样的组件（README 写明这是 LLM-free 的确定性 demo）。这里
    只是按 commits/<case>_commits.yaml 里声明的顺序，一次产出一个真实
    commit 作为下一步待授权的动作，直到所有 commit 都被处理过（或被 gate
    拦下、循环提前结束）为止。"""
    commits_path = BASE_DIR / "commits" / f"{case}_commits.yaml"
    ordered_ids = [c["id"] for c in load_yaml(commits_path)["commits"]]

    def reason_fn(state: dict):
        processed = {h["action"].get("commit_id") for h in state.get("history", [])}
        remaining = [cid for cid in ordered_ids if cid not in processed]
        if not remaining:
            return {"type": "finish", "output": "all commits processed"}, 0
        next_id = remaining[0]
        return {"type": "tool", "tool": next_id, "commit_id": next_id}, 0

    return reason_fn


def make_case_tool_fn() -> ToolFn:
    """最小实现，且如实注明：这个 demo 没有真实的外部副作用可执行（不连
    任何真实业务系统——）。tool_fn 能做的真实事情就是记录"这个 commit 已放行执行"，
    cost 是每次调用固定 1 个抽象单位，不是编造出来冒充 token 的数字。"""

    def tool_fn(action: dict):
        return f"executed {action['commit_id']}", 1

    return tool_fn


def _print_trace(case: str, trace: LoopTrace) -> None:
    print("=" * 78)
    print(f"agent/gated_loop.py —— pre-action authorization demo, case: {case}")
    print("=" * 78)
    for s in trace.steps:
        status = "BLOCKED" if s.blocked else "OK"
        print(f"  step {s.step}: tool={s.tool!r} route={s.route} [{status}] "
              f"gate_latency={s.gate_latency_ms:.3f}ms action_latency={s.action_latency_ms:.3f}ms "
              f"cost={s.total_tokens}")
    print(f"\n  halted_by_gate={trace.halted_by_gate}")
    print(f"  final_output={trace.final_output!r}")
    print(f"  total steps={len(trace.steps)}  total cost={trace.total_tokens()}  "
          f"total latency={trace.total_latency_ms():.3f}ms  "
          f"gate_overhead_ratio={trace.gate_overhead_ratio():.3f}")
    print("=" * 78)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the gated agent loop against a real GateFix case")
    parser.add_argument("--case", default="ai_investment",
                         help="case 名（复用 commits/bindings/evidence/preconditions 四处真实配置）")
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args()

    loop = GatedAgentLoop(
        gate_fn=make_case_gate_fn(args.case),
        tool_fn=make_case_tool_fn(),
        reason_fn=make_case_reason_fn(args.case),
        max_steps=args.max_steps,
    )
    trace = loop.run(context=args.case, initial_state={})
    _print_trace(args.case, trace)

    # 任务 1 退出码约定：这个 CLI 一次只跑一条 loop，天然对应单一最终
    # route——被 gate 挡下就是挡它的那个 route，跑完没被挡就是 PASS。
    final_route = trace.steps[-1].route if trace.halted_by_gate else "PASS"
    sys.exit(EXIT_CODE.get(final_route, EXIT_CODE_INTERNAL_ERROR))


if __name__ == "__main__":
    main()
