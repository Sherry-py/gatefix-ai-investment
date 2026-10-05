"""
paired_log_summary.py —— 读 paired_log.jsonl，汇总知行脱节的被试内测量。

    python paired_log_summary.py                    # 汇总
    python paired_log_summary.py --list             # 列出每条记录
    python paired_log_summary.py --set RUN_ID --decision 暂缓 --outcome "B轮后估值腰斩"

主测量：P(无约束臂建议推进 | LLM 诊断出缺陷)，附 Wilson 95% 区间；
两臂对比给出 McNemar 精确检验的不一致对数与 p 值。同一项目多次运行只取最新一条。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "paired_log.jsonl"


def load(path=LOG_PATH):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def latest_per_project(rows):
    by = {}
    for r in rows:
        if r.get("error"):
            continue
        by[r.get("project")] = r  # 文件按时间追加，后者覆盖前者
    return list(by.values())


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b, c):
    """双侧精确二项检验：b、c 为两种不一致对的数量。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def conditional(rows, defect_key):
    sub = [r for r in rows if r["derived"][defect_key]]
    n = len(sub)
    u = sum(r["derived"]["unconstrained_proceeds"] for r in sub)
    c = sum(r["derived"]["constrained_proceeds"] for r in sub)
    # 不一致对：b = 无约束推进而受约束不推进；c = 反之
    b = sum(r["derived"]["unconstrained_proceeds"] and not r["derived"]["constrained_proceeds"] for r in sub)
    cc = sum(r["derived"]["constrained_proceeds"] and not r["derived"]["unconstrained_proceeds"] for r in sub)
    return n, u, c, b, cc


def summarize(rows):
    rows = latest_per_project(rows)
    print(f"项目数（去重、去失败）：{len(rows)}")
    if not rows:
        return
    for key, label in (("defect_primary", "主口径：叙事筛选判排除"),
                       ("defect_broad", "宽口径：排除/硬伤/闸门未放行")):
        n, u, c, b, cc = conditional(rows, key)
        print(f"\n[{label}] 诊断出缺陷的项目 n={n}")
        if n == 0:
            continue
        lo, hi = wilson(u, n)
        print(f"  无约束臂仍建议推进：{u}/{n} = {u/n:.0%}  (Wilson 95% CI {lo:.0%}–{hi:.0%})")
        lo, hi = wilson(c, n)
        print(f"  受约束臂建议推进：  {c}/{n} = {c/n:.0%}  (Wilson 95% CI {lo:.0%}–{hi:.0%})")
        print(f"  McNemar 不一致对 b={b}, c={cc}, 精确 p={mcnemar_exact(b, cc):.3g}")
    decided = [r for r in rows if r.get("human_decision")]
    print(f"\n已填写人工决定：{len(decided)}/{len(rows)}；已填写结局：{sum(bool(r.get('outcome')) for r in rows)}/{len(rows)}")


def list_rows(rows):
    for r in rows:
        d, g = r["derived"], r.get("gate_routes", {})
        print(f"{r['run_id']}  {r['project'][:16]:<16}  叙事={r['diagnosis'].get('narrative_verdict')}  "
              f"治理={g.get('governance')}  无约束={r['arm_unconstrained']['class']}  "
              f"受约束={r['arm_constrained']['class']}  人工={r.get('human_decision') or '-'}"
              + ("  [失败]" if r.get("error") else ""))


def set_fields(run_id, decision=None, outcome=None, path=LOG_PATH):
    rows = load(path)
    hit = False
    for r in rows:
        if r.get("run_id") == run_id:
            if decision is not None:
                r["human_decision"] = decision
            if outcome is not None:
                r["outcome"] = outcome
            hit = True
    if not hit:
        raise SystemExit(f"未找到 run_id={run_id}")
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"已更新 {run_id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--set", metavar="RUN_ID")
    ap.add_argument("--decision")
    ap.add_argument("--outcome")
    a = ap.parse_args()
    if a.set:
        set_fields(a.set, a.decision, a.outcome)
    elif a.list:
        list_rows(load())
    else:
        summarize(load())


if __name__ == "__main__":
    main()
