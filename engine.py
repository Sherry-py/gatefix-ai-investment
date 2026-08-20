"""
engine.py —— 运行时引擎：组装上下文 → Precondition 判定 → 三态路由 → 执行/升级人 → 写回

运行方式：
    python engine.py run --case=ai_investment
    python engine.py run --case=ai_investment --verbose

按 --case 动态加载四份场景配置（commits/<case>_commits.yaml、
bindings/<case>_bindings.yaml、evidence/<case>_evidence.yaml、
preconditions/<case>.py），engine.py 和 gate.py 本身不含任何场景特定逻辑。
当前场景为 ai_investment（GateFix 方法（Xirui Lian Sherry 开发）· 中美绿色基金采用）。
"""

import argparse
import json
import importlib
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import yaml

from gate import (
    GateConfig, GateRecord, ReasonCode, classify_regular_reason_code,
    EXIT_CODE, EXIT_CODE_INTERNAL_ERROR, safe_score, safe_repair,
    SCHEMA_VERSION,
)
from audit import append_gate_decision, build_audit_record, DEFAULT_AUDIT_LOG

BASE_DIR = Path(__file__).parent

# GitHub 是公开仓库，不展示案例的真实财务数字——value_tier 是 low/mid/high
# 三档，这里换算成代表性数字参与 λ·Value 判定。数字本身是假的，但换算后
# 每个 commit 之间的相对大小关系和真实数据一致，is_commit()/loop_mode() 的
# 判定结果不受影响（tests/test_admission_gate.py、tests/test_engine.py 里
# 断言的是 route，不是具体数字）。
VALUE_TIER_SCALE = {"low": 100.0, "mid": 1000.0, "high": 10000.0}


def _resolve_regular_commit(config, score_fn, repair_fn, evidence, verbose=False):
    """常规 commit 的三态路由 + AUTO_REPAIR 重试循环。从 run_case 抽成独立
    函数：一是不用为了测一个边界分支就构造一整个 case 的三份 yaml/py；二是
    修一个真实缺口——route=="AUTO_REPAIR" 但该 precondition_fn 没注册
    REPAIR_REGISTRY 补证函数时，原写法会让 AUTO_REPAIR 原样返回、从不收敛
    （route 只能是 PASS 或 ESCALATE，这不是合法终态）。ai_investment 案例里
    没有 commit 撞上这条路径，直到用真实但非案例内的 evidence 测 MCP
    server 的 authorize() 才发现。

    返回 (route, result, Q, dry_rounds, repair_attempts, reason_code)，route
    只会是 PASS / ESCALATE / BYPASS_TO_HUMAN（后者是 fail-closed
    兜底：score_fn/repair_fn 抛异常时的故障性失败，见 gate.py::safe_score/
    safe_repair）。reason_code 用 gate.py::classify_regular_reason_code
    从收敛后的最终状态反推。"""
    repair_fn_registered = repair_fn is not None
    dry_rounds = 0
    repair_attempts = 0
    while True:
        result, fault = safe_score(score_fn, evidence)
        if fault:
            print(f"  [FAIL-CLOSED] {result['notes']} → 收敛到 BYPASS_TO_HUMAN，不默认 PASS")
            return ("BYPASS_TO_HUMAN", result, 0.0, dry_rounds, repair_attempts,
                    ReasonCode.EVALUATOR_FAULT)

        Q = config.quality_score(result["R"], result["C"], result["O"], result["Ro"])
        route = config.route(Q, result["verifiable_ext"], dry_rounds)

        if verbose or route != "AUTO_REPAIR":
            print(f"  R={result['R']:.2f} C={result['C']:.2f} O={result['O']:.2f} "
                  f"Ro={result['Ro']:.2f} → Q={Q:.3f}  route={route}  "
                  f"(dry_rounds={dry_rounds})")
            print(f"  说明: {result['notes']}")

        if route == "AUTO_REPAIR" and repair_fn is not None:
            repair_attempts += 1
            print(f"  [AUTO_REPAIR] 缺口可外部验证，尝试补证（第 {repair_attempts} 轮）...")
            new_evidence, repair_fault = safe_repair(repair_fn, evidence)
            if repair_fault:
                print("  [FAIL-CLOSED] repair_fn 异常 → 收敛到 BYPASS_TO_HUMAN，不默认 PASS")
                return ("BYPASS_TO_HUMAN", result, Q, dry_rounds, repair_attempts,
                        ReasonCode.EVALUATOR_FAULT)
            if new_evidence == evidence:
                dry_rounds += 1  # 没有新证据
            else:
                evidence = new_evidence
                dry_rounds = 0  # 拿到新证据，重置计数
            if dry_rounds >= config.k_dry:
                route = "ESCALATE"
                print(f"  连续 {config.k_dry} 轮无新证据 → 强制 ESCALATE")
                break
            continue

        if route == "AUTO_REPAIR":
            # repair_fn 是 None：这个精度分数落进了"可以自动修"的区间，但这个
            # precondition_fn 没有注册对应的补证函数，没有自动化手段真的去
            # 补——不能停留在 AUTO_REPAIR 这个非终态，降级为 ESCALATE
            # （和 k_dry 耗尽时的处理方式一致）。
            route = "ESCALATE"
            print("  这个 precondition_fn 没有注册 REPAIR_REGISTRY 补证函数，"
                  "AUTO_REPAIR 无法自动执行 → 降级 ESCALATE")
        break

    reason_code = classify_regular_reason_code(
        route=route, Q=Q, tau_repair=config.tau_repair,
        verifiable_ext=result["verifiable_ext"], dry_rounds=dry_rounds,
        k_dry=config.k_dry, repair_attempts=repair_attempts,
        repair_fn_registered=repair_fn_registered,
    )
    return route, result, Q, dry_rounds, repair_attempts, reason_code


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_number(v):
    """yaml 里的 'inf' 要转成 float('inf')。"""
    if isinstance(v, str) and v.strip().lower() == "inf":
        return float("inf")
    return v


def run_case(case: str, verbose: bool = False, audit_log_path: Optional[Path] = None):
    commits_path = BASE_DIR / "commits" / f"{case}_commits.yaml"
    bindings_path = BASE_DIR / "bindings" / f"{case}_bindings.yaml"
    evidence_path = BASE_DIR / "evidence" / f"{case}_evidence.yaml"

    commits = load_yaml(commits_path)["commits"]
    bindings = load_yaml(bindings_path)["bindings"]
    all_evidence = load_yaml(evidence_path)

    # 场景特定的打分函数模块——preconditions/<case>.py 必须导出 REGISTRY
    # （必须）和 REPAIR_REGISTRY（可选）。这是"engine.py 不含场景逻辑"的
    # 落地方式：新场景只需要新增这个模块，不需要改这里的 import。
    precondition_module = importlib.import_module(f"preconditions.{case}")
    REGISTRY = precondition_module.REGISTRY
    REPAIR_REGISTRY = getattr(precondition_module, "REPAIR_REGISTRY", {})

    config = GateConfig()
    records = []

    print("=" * 78)
    print(f"GateFix engine.py —— case: {case}")
    print(f"GateConfig: tau_pass={config.tau_pass} tau_repair={config.tau_repair} "
          f"k_dry={config.k_dry} lambda={config.lambda_value} beta={config.beta_fix_cost}")
    print("=" * 78)

    total_certain_cost = 0.0
    total_risk_ext = 0.0

    for commit in commits:
        cid = commit["id"]
        name = commit["name_cn"]
        cost_reverse = parse_number(commit.get("cost_reverse"))
        value = VALUE_TIER_SCALE.get(commit.get("value_tier"), 0.0)
        cost_fix = parse_number(commit.get("cost_fix", 0))
        binding = bindings.get(cid, {})
        evidence = dict(all_evidence.get(cid, {}))

        is_commit = config.is_commit(cost_reverse, value)
        loop_mode = config.loop_mode(cost_reverse, value, cost_fix)

        print(f"\n--- Commit: {name} ({cid}) ---")
        print(f"  不可逆性: {commit.get('irreversibility')}")
        print(f"  IsCommit(a)={is_commit}  LoopMode(a)={loop_mode}  "
              f"执行器={binding.get('executor', '未绑定')}")

        # ---------- 分支 1：人情类，直接旁路给人 ----------
        if commit.get("bypass_to_human"):
            notes = commit.get("bypass_reason", "")
            # 有的 bypass_to_human commit 同时带 precondition_fn：不是走常规三态
            # 路由（那是分支 3 的事），是一个独立的预检阶段——比如
            # friend_compensation 现实里是"先承诺分账、后来分账落空改现金/实物
            # 补偿"两阶段合成的一个 commit，承诺阶段有客观可查的可行性证据，
            # 值得单独跑一次 expectation_gate 记录在案；但预检结果不会、也不能
            # 决定最终路由——补偿这件事人情类证据机器不可组装，终态永远是
            # BYPASS_TO_HUMAN（mcp_server/server.py 里专门测试保证这条不会被
            # 外部 client 误当成"预检 PASS = 已授权"绕开）。
            if commit.get("precondition_fn"):
                score_fn = REGISTRY[commit["precondition_fn"]]
                pre, pre_fault = safe_score(score_fn, evidence)
                # pre_fault 不改变最终 route——这条分支的终态本来就恒为
                # BYPASS_TO_HUMAN，预检从来不能决定 route（见上面的注释）；
                # 这里只是不让预检本身的异常把整个 run_case 崩掉。
                if pre_fault:
                    print(f"  [阶段一·承诺 expectation_gate] [FAIL-CLOSED] {pre['notes']}")
                    stage_note = f"承诺阶段：预检异常（{pre['notes']}），未影响最终旁路人工的判定"
                else:
                    pre_allowed = config.expectation_gate(
                        pre.get("contains_promise", True),
                        pre.get("has_feasibility_evidence", False),
                    )
                    pre_route = "PASS" if pre_allowed else "ESCALATE"
                    print(f"  [阶段一·承诺 expectation_gate] {pre['notes']}")
                    print(f"  Send(msg) 被允许={pre_allowed} → {pre_route}"
                          "（仅记录，不影响最终 route——最终仍是 BYPASS_TO_HUMAN）")
                    stage_note = f"承诺阶段：{pre_route}——{pre['notes']}"
                if evidence.get("actual_settlement_tier") is not None:
                    stage_note += (
                        f"；实付阶段：{evidence.get('actual_settlement_form', '')}结清"
                        f"（金额量级：{evidence['actual_settlement_tier']}，"
                        f"{evidence.get('settlement_reason', '')}）"
                    )
                notes = f"{stage_note}　{notes}"
            print(f"  [阶段二·旁路] {commit.get('bypass_reason')}")
            print("  → 最终决定不进入 4D-CQ 计算，直接呈人定夺（Human_Gate(a) 定义域之外）")
            rec = GateRecord(
                commit_id=cid, commit_name=name, R=0, C=0, O=0, Ro=0, Q=0,
                route="BYPASS_TO_HUMAN", is_commit=is_commit, loop_mode=loop_mode,
                verifiable_ext=False, dry_rounds=0,
                notes=notes, bypassed_to_human=True,
                reason_code=ReasonCode.BYPASS_HUMAN_JUDGMENT_REQUIRED,
            )
            records.append(rec)
            continue

        # ---------- 分支 2：软 commit，走 expectation_gate ----------
        if commit.get("soft_commit"):
            score_fn = REGISTRY[commit["precondition_fn"]]
            result, fault = safe_score(score_fn, evidence)
            if fault:
                # fail-closed：软 commit 也不例外，evaluator 异常
                # 绝不能被 expectation_gate 悄悄当成"没有 promise"而放行。
                print(f"  [软 commit / expectation gate] [FAIL-CLOSED] {result['notes']}")
                rec = GateRecord(
                    commit_id=cid, commit_name=name, R=0, C=0, O=0, Ro=0, Q=0,
                    route="BYPASS_TO_HUMAN", is_commit=is_commit, loop_mode=loop_mode,
                    verifiable_ext=False, dry_rounds=0, notes=result["notes"],
                    reason_code=ReasonCode.EVALUATOR_FAULT,
                )
                records.append(rec)
                continue
            allowed = config.expectation_gate(
                result.get("contains_promise", True),
                result.get("has_feasibility_evidence", False),
            )
            route = "PASS" if allowed else "ESCALATE"
            print(f"  [软 commit / expectation gate] {result['notes']}")
            print(f"  Send(msg) 被允许 = {allowed}  → route={route}")
            rec = GateRecord(
                commit_id=cid, commit_name=name,
                R=result["R"], C=result["C"], O=result["O"], Ro=result["Ro"],
                Q=config.quality_score(result["R"], result["C"], result["O"], result["Ro"]),
                route=route, is_commit=is_commit, loop_mode=loop_mode,
                verifiable_ext=result["verifiable_ext"], dry_rounds=0,
                notes=result["notes"],
                reason_code=(ReasonCode.SOFT_COMMIT_PROMISE_SUPPORTED if allowed
                             else ReasonCode.SOFT_COMMIT_PROMISE_UNSUPPORTED),
            )
            records.append(rec)
            if route == "PASS":
                total_certain_cost += value
            continue

        # ---------- 分支 3：常规 commit，走三态路由（可能带 AUTO_REPAIR 循环） ----------
        score_fn = REGISTRY[commit["precondition_fn"]]
        repair_fn = REPAIR_REGISTRY.get(commit["precondition_fn"])

        route, result, Q, dry_rounds, repair_attempts, reason_code = _resolve_regular_commit(
            config, score_fn, repair_fn, evidence, verbose=verbose,
        )

        rec = GateRecord(
            commit_id=cid, commit_name=name,
            R=result["R"], C=result["C"], O=result["O"], Ro=result["Ro"], Q=Q,
            route=route, is_commit=is_commit, loop_mode=loop_mode,
            verifiable_ext=result["verifiable_ext"], dry_rounds=dry_rounds,
            notes=result["notes"] + (f"　[经过 {repair_attempts} 轮 AUTO_REPAIR]" if repair_attempts else ""),
            reason_code=reason_code,
        )
        rec.repair_attempts = repair_attempts

        # ---------- 外部或有闸门（如有）：不影响 route，只报告 ----------
        risk_ext_cfg = commit.get("risk_ext")
        if risk_ext_cfg:
            r = config.expected_external_risk(
                risk_ext_cfg["p_inspect"], risk_ext_cfg["loss_if_inspected"]
            )
            rec.risk_ext = r
            total_risk_ext += r
            print(f"  [外部或有闸门] p_inspect={risk_ext_cfg['p_inspect']} × "
                  f"Loss={risk_ext_cfg['loss_if_inspected']} → Risk_ext={r:.1f}  "
                  f"({risk_ext_cfg.get('note', '')})")
            print(f"  注意：route={route} 不代表这条风险已清零，Total_Cost = Cost_certain + Risk_ext")

        if route == "PASS":
            total_certain_cost += value
        elif route == "ESCALATE":
            print(f"  → 升级给人：{binding.get('executor', '委托人本人')} 终审")

        records.append(rec)

    # ---------- 写 Gate Record（JSONL，最近一次 run 的快照，覆盖写） ----------
    out_path = BASE_DIR / "gate_record.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            entry = rec.to_dict()
            entry["case"] = case
            entry["timestamp"] = datetime.now(timezone.utc).isoformat()
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ---------- 写审计日志（JSONL，append-only） ----------
    # 这是真正的历史留痕，和上面 gate_record.jsonl 的"最近一次快照"是两回事
    # （见 audit.py 模块 docstring）。诚实的失败语义：审计写入失败不会撤销
    # 已经生效的判定（rec 已经在 records 里了），只是分开报告——见下面汇总
    # 里的 audit_failures。
    audit_path = audit_log_path or DEFAULT_AUDIT_LOG
    audit_failures = []
    for rec in records:
        audit_record = build_audit_record(
            action_id=rec.commit_id, gate_state=rec.route,
            reason_code=rec.reason_code,
            cq_scores={"relevance": rec.R, "coverage": rec.C,
                       "ordering": rec.O, "robustness": rec.Ro},
            schema_version=SCHEMA_VERSION,
            thresholds={"tau_pass": config.tau_pass, "tau_repair": config.tau_repair},
            case=case,
        )
        write_result = append_gate_decision(audit_record, audit_path)
        if not write_result.ok:
            audit_failures.append((rec.commit_id, write_result.error))

    # ---------- 汇总 ----------
    n_pass = sum(1 for r in records if r.route == "PASS")
    n_escalate = sum(1 for r in records if r.route in ("ESCALATE", "BYPASS_TO_HUMAN"))
    n_repair = sum(1 for r in records if getattr(r, "repair_attempts", 0) > 0)

    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)
    print(f"  Commit 总数: {len(records)}")
    print(f"  PASS: {n_pass}   ESCALATE/旁路人工: {n_escalate}   经过 AUTO_REPAIR: {n_repair}")
    print(f"  Total_Cost_certain（已确定成本量级，仅 PASS 的 value_tier 换算求和，代表性单位非真实金额）: {total_certain_cost:.0f}")
    print(f"  Total_Risk_ext（外部或有闸门期望敞口，Commit=True 之后仍未清零，代表性单位）: {total_risk_ext:.1f}")
    print(f"  Gate Record 已写入: {out_path}")
    if audit_failures:
        print(f"  [审计] {len(audit_failures)}/{len(records)} 条判定的审计写入失败"
              "（判定本身仍然有效，未回滚）：")
        for commit_id, error in audit_failures:
            print(f"    - {commit_id}: {error}")
    else:
        print(f"  [审计] {len(records)}/{len(records)} 条判定已写入 {audit_path}（append-only）")
    print("=" * 78)

    return records


def worst_case_exit_code(records) -> int:
    """退出码约定（0=PASS, 1=ESCALATE, 2=BYPASS, 3=内部错误）应用到
    engine.py 的批量 CLI 形态：一次 run 处理多个 commit，没有单一 route 可
    映射，所以取"这批里最需要人工介入的那个结果"——BYPASS_TO_HUMAN 比
    ESCALATE 更需要人工，ESCALATE 比 PASS 更需要人工，谁的退出码数字大就
    以谁为准。全 PASS 才是 0，调用方（CI/脚本）可以直接看退出码知道这次
    run 有没有东西卡在人工那关，不用去 parse 打印文本或 gate_record.jsonl。"""
    worst = 0
    for r in records:
        worst = max(worst, EXIT_CODE.get(r.route, EXIT_CODE_INTERNAL_ERROR))
    return worst


def main():
    parser = argparse.ArgumentParser(description="GateFix engine")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="运行一个 case")
    run_parser.add_argument("--case", default="ai_investment", help="case 名（决定加载 commits/bindings/evidence/preconditions 四处的哪一套配置）")
    run_parser.add_argument("--verbose", action="store_true", help="打印每一轮 AUTO_REPAIR 的详情")

    args = parser.parse_args()
    if args.command == "run":
        try:
            records = run_case(args.case, verbose=args.verbose)
        except Exception as exc:  # noqa: BLE001 — fail-closed 兜底
            print(f"internal error running case {args.case!r}: {exc}", file=sys.stderr)
            sys.exit(EXIT_CODE_INTERNAL_ERROR)
        sys.exit(worst_case_exit_code(records))


if __name__ == "__main__":
    main()
