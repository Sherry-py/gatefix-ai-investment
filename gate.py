"""
gate.py —— GateFix 的判定核心（对应"系统设计公式与可调参数表.md"里的核心公式 + 六条子公式）

这个文件只做一件事：判定。不碰 evidence 怎么收集（engine.py 管），
不碰某个 commit 具体怎么打分（preconditions/*.py 管）。

核心不变式（对应 Commit(a,E) = Human_Gate(a) ∧ ⋀ᵢ Pᵢ(E,θᵢ)）：
    一个动作能不能放行 = 人是否已批准 ∧ 证据在 R/C/O/Ro 四个维度上是否都过阈值。

授权强度分级（REVISION_BRIEF.md 任务 5，借鉴 MyClaw 的 session / step-up /
confirmation phrase 三级授权思路，落到这个仓库自己的四态词汇表）——四态
和"干预强度"是显式绑定的，不是四个平级的分类标签：
    PASS            = 自动放行（高频默认，agent 不停顿）
    AUTO_REPAIR     = 先给一次自愈机会（补证据后重新判定，类比 nudge，
                      不是放行，也不是拒绝）
    ESCALATE        = 需要人确认才能继续（阻断，但不是终局判断）
    BYPASS_TO_HUMAN = 强制转人工（人情类证据机器不可组装、或 evaluator
                      本身故障——见 ReasonCode.EVALUATOR_FAULT——这两类都
                      直接跳过自动判定，最不可逆/最没把握的动作走这里）
四态从上到下自主度递减、人工介入递增；README「四态自主度谱系」一节是
这条分级的可视化版本，这里是权威的文字定义。
"""

from dataclasses import dataclass, field
from typing import Optional
import re

# ---------- 机器可判定的授权契约 (REVISION_BRIEF.md 任务 1) ----------
#
# schema_version 独立于代码版本演进——下游 agent/MCP client/CI 靠这个字段
# 判断契约形状是否变化，不是靠 parse 人类可读文本。改了 REASON_CODE_* 的
# 集合或 to_contract() 的字段结构才需要碰这个数字。
SCHEMA_VERSION = "1"

# CLI 退出码约定（对应任务 1 的验收标准）。AUTO_REPAIR 不出现在这里——
# 它在 gate.py 上游（resolve_precondition / _resolve_regular_commit）已经
# 收敛成 PASS 或 ESCALATE，从不作为终态暴露给调用方。
EXIT_CODE = {
    "PASS": 0,
    "ESCALATE": 1,
    "BYPASS_TO_HUMAN": 2,
}
EXIT_CODE_INTERNAL_ERROR = 3


class ReasonCode:
    """稳定的 reason_code 词汇表——机器决策依赖这些字符串，不依赖解析
    human_readable 里的自然语言。这里只列真正由判定逻辑本身产出的原因：
    gate.route() 只对聚合后的 Q 做阈值判断，不单独判断某一维度，所以故意
    没有 COVERAGE_BELOW_THRESHOLD 这种按维度归因的码——那会假装系统做了
    它实际没做的事（按维度定位失败原因）。"""

    PASS_ABOVE_THRESHOLD = "PASS_ABOVE_THRESHOLD"
    QUALITY_BELOW_REPAIR_THRESHOLD = "QUALITY_BELOW_REPAIR_THRESHOLD"
    GAP_NOT_EXTERNALLY_VERIFIABLE = "GAP_NOT_EXTERNALLY_VERIFIABLE"
    AUTO_REPAIR_DRY_ROUNDS_EXHAUSTED = "AUTO_REPAIR_DRY_ROUNDS_EXHAUSTED"
    AUTO_REPAIR_UNAVAILABLE_NO_REPAIR_FN = "AUTO_REPAIR_UNAVAILABLE_NO_REPAIR_FN"
    SOFT_COMMIT_PROMISE_UNSUPPORTED = "SOFT_COMMIT_PROMISE_UNSUPPORTED"
    SOFT_COMMIT_PROMISE_SUPPORTED = "SOFT_COMMIT_PROMISE_SUPPORTED"
    BYPASS_HUMAN_JUDGMENT_REQUIRED = "BYPASS_HUMAN_JUDGMENT_REQUIRED"
    ORDERING_PRECONDITION_UNMET = "ORDERING_PRECONDITION_UNMET"
    # 任务 2（fail-closed）用：evaluator 本身抛异常，不是证据不够格。
    EVALUATOR_FAULT = "EVALUATOR_FAULT"


def classify_regular_reason_code(*, route: str, Q: float, tau_repair: float,
                                  verifiable_ext: bool, dry_rounds: int,
                                  k_dry: int, repair_attempts: int,
                                  repair_fn_registered: bool) -> str:
    """常规 commit（非 bypass、非 soft_commit）分支的 reason_code 分类，用
    收敛后的最终状态反推走的是哪条子路径。engine.py::_resolve_regular_commit
    和 agent/gated_loop.py::resolve_precondition 复用同一份——
    resolve_precondition 的 docstring 已经点名"两者必须走同一份判定逻辑，
    不能各写一份、慢慢长歪"，reason_code 的分类同样适用这条约束。"""
    if route == "PASS":
        return ReasonCode.PASS_ABOVE_THRESHOLD
    if Q >= tau_repair and not verifiable_ext:
        return ReasonCode.GAP_NOT_EXTERNALLY_VERIFIABLE
    if repair_attempts > 0 and dry_rounds >= k_dry:
        return ReasonCode.AUTO_REPAIR_DRY_ROUNDS_EXHAUSTED
    if Q >= tau_repair and not repair_fn_registered:
        return ReasonCode.AUTO_REPAIR_UNAVAILABLE_NO_REPAIR_FN
    return ReasonCode.QUALITY_BELOW_REPAIR_THRESHOLD


# ---------- 敏感物纪律 (REVISION_BRIEF.md 任务 5) ----------
#
# 门控核心本身不需要、也不接收任何凭据——evidence 字段是案例领域数据
# （证件是否已处理、退款账户名是否匹配之类），不是 API key/token。这里
# 防的是第二道防线：某个 precondition_fn 的 notes 或调用方传入的 evidence
# 里意外带了凭据形状的字符串，不能让它原样流进审计日志或对外的契约里。
_SECRET_PATTERN = re.compile(
    r"\b(api[_-]?key|access[_-]?key|token|secret|password|passwd|credentials?)"
    r"s?\s*[:=]\s*\S+"
    r"|\bsk-[A-Za-z0-9]{10,}\b"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\bbearer\s+[A-Za-z0-9\-_.]{10,}\b",
    re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """把看起来像 API key/token/密码/凭据的片段替换成 [REDACTED]。启发式
    匹配，不是万无一失的 DLP——真正的边界是"核心不接收凭据"这条设计约束
    本身（见 README「安全边界」），这个函数是防意外泄露的第二道防线。"""
    if not text:
        return text
    return _SECRET_PATTERN.sub("[REDACTED]", text)


# ---------- fail-closed 语义 (REVISION_BRIEF.md 任务 2) ----------
#
# 区分两类失败：
#   实质性拒绝（CQ 前置条件不满足）——score_fn 正常返回，只是分数不够格，
#     走上面 classify_regular_reason_code 的正常路径，终态是 ESCALATE。
#   故障性失败（评估器本身异常：超时/依赖缺失/代码 bug）——score_fn/
#     repair_fn 抛异常，下面这两个函数兜住，不让异常冒泡到"默认放行"，
#     终态固定 BYPASS_TO_HUMAN，reason_code=EVALUATOR_FAULT，明确标注这是
#     故障不是证据问题。


def safe_score(score_fn, evidence: dict) -> "tuple[dict, bool]":
    """返回 (result, fault)。fault=True 时 result 是一个 fail-closed 占位
    分数（全 0、verifiable_ext=False）——就算调用方忘记检查 fault 标志，
    quality_score()/route() 算出来的也绝不可能是 PASS。"""
    try:
        return score_fn(evidence), False
    except Exception as exc:  # noqa: BLE001 — fail-closed 就是要兜住任何异常
        return {
            "R": 0.0, "C": 0.0, "O": 0.0, "Ro": 0.0, "verifiable_ext": False,
            "notes": f"[FAIL-CLOSED] evaluator raised {type(exc).__name__}: {exc}",
        }, True


def safe_repair(repair_fn, evidence: dict) -> "tuple[Optional[dict], bool]":
    """返回 (new_evidence, fault)。fault=True 时 new_evidence 是 None——
    调用方必须把这当成"补证失败"处理，不能当成"没有新证据"（dry round）
    悄悄吞掉，两者要能被区分开。"""
    try:
        return repair_fn(evidence), False
    except Exception as exc:  # noqa: BLE001
        return None, True


def build_gate_contract(*, gate_state: str, R: float, C: float, O: float,
                         Ro: float, reason_code: str,
                         auto_repair_available: bool,
                         human_readable: str) -> dict:
    """任务 1 要求的结构化契约——见 REVISION_BRIEF.md 任务 1 的 JSON 示例。
    下游只应该读 gate_state/reason_code/auto_repair_available 这些结构化
    字段做决策，human_readable 仅供人看，绝不参与机器判断。human_readable
    在这里统一过一遍 redact_secrets()（任务 5）——这是唯一的出口，所有
    GateRecord/GateResult 的 to_contract() 都走这里，不需要每个调用点各自
    记得脱敏。"""
    return {
        "gate_state": gate_state,
        "schema_version": SCHEMA_VERSION,
        "cq_scores": {
            "relevance": R, "coverage": C, "ordering": O, "robustness": Ro,
        },
        "reason_code": reason_code,
        "auto_repair_available": auto_repair_available,
        "human_readable": redact_secrets(human_readable),
    }


@dataclass
class GateConfig:
    """可调参数表的代码化版本——改这里的数字，整个系统的判定行为就变。"""

    tau_pass: float = 0.85        # ① 放行阈值
    tau_repair: float = 0.50      # ① 自动修复区间下界
    w_relevance: float = 0.25     # ① 4D-CQ 四个维度权重，Σw = 1
    w_coverage: float = 0.25
    w_ordering: float = 0.25
    w_robustness: float = 0.25
    lambda_value: float = 1.0     # ③ 可逆性判定的价值倍数
    beta_fix_cost: float = 50.0   # ④ on/in-loop 划界的修复成本上限
    k_dry: int = 3                # ② AUTO_REPAIR 连续无新证据的轮数上限（loop-until-dry）

    # ---------- ① 4D-CQ 质量分 ----------
    def quality_score(self, R: float, C: float, O: float, Ro: float) -> float:
        return (
            self.w_relevance * R
            + self.w_coverage * C
            + self.w_ordering * O
            + self.w_robustness * Ro
        )

    # ---------- ② 三态路由函数 ----------
    def route(self, q: float, verifiable_ext: bool, dry_rounds: int = 0) -> str:
        if q >= self.tau_pass:
            return "PASS"
        if self.tau_repair <= q < self.tau_pass and verifiable_ext:
            if dry_rounds >= self.k_dry:
                return "ESCALATE"  # 连续 k_dry 轮无新证据，不再自动重试
            return "AUTO_REPAIR"
        return "ESCALATE"

    # ---------- ③ Commit 判定（可逆性分类） ----------
    def is_commit(self, cost_reverse: float, value: float) -> bool:
        """cost_reverse 用 float('inf') 表示完全不可逆。"""
        if cost_reverse == float("inf"):
            return True
        return cost_reverse > self.lambda_value * value

    # ---------- ④ On/In-the-loop 划界 ----------
    def loop_mode(self, cost_reverse: float, value: float, cost_fix: float) -> str:
        if (not self.is_commit(cost_reverse, value)) and cost_fix <= self.beta_fix_cost:
            return "ON_THE_LOOP"
        return "IN_THE_LOOP"

    # ---------- ⑤ 软 commit 门（expectation gate） ----------
    @staticmethod
    def expectation_gate(contains_promise: bool, has_feasibility_evidence: bool) -> bool:
        """Send(msg) 被允许 ⟺ ¬ContainsPromise(msg) ∨ HasFeasibilityEvidence(msg)"""
        return (not contains_promise) or has_feasibility_evidence

    # ---------- ⑥ 外部或有闸门（新增，海关抽查风险场景） ----------
    @staticmethod
    def expected_external_risk(p_inspect: float, loss_if_inspected: float) -> float:
        """Risk_ext(a) = p_inspect(a) · Loss(a∣inspected)
        这不是放行判定的一部分——Commit(a,E)=True 之后这条风险依然存在，
        只用于 Total_Cost 核算，提醒"放行"和"成本已确定"是两件事。"""
        return p_inspect * loss_if_inspected


@dataclass
class GateRecord:
    """对应案例里的 Gate Record：JSONL·批准人·事后结果——留痕，不是为了合规负担，是结算期权。"""

    commit_id: str
    commit_name: str
    R: float
    C: float
    O: float
    Ro: float
    Q: float
    route: str
    is_commit: bool
    loop_mode: str
    verifiable_ext: bool
    dry_rounds: int
    notes: str = ""
    risk_ext: Optional[float] = None
    bypassed_to_human: bool = False
    reason_code: str = ""

    def to_dict(self) -> dict:
        return {
            "commit_id": self.commit_id,
            "commit_name": self.commit_name,
            "R": round(self.R, 3),
            "C": round(self.C, 3),
            "O": round(self.O, 3),
            "Ro": round(self.Ro, 3),
            "Q": round(self.Q, 3),
            "route": self.route,
            "is_commit": self.is_commit,
            "loop_mode": self.loop_mode,
            "verifiable_ext": self.verifiable_ext,
            "dry_rounds": self.dry_rounds,
            "notes": redact_secrets(self.notes),
            "risk_ext": self.risk_ext,
            "bypassed_to_human": self.bypassed_to_human,
            "schema_version": SCHEMA_VERSION,
            "reason_code": self.reason_code,
        }

    def to_contract(self) -> dict:
        """机器可判定契约版本（REVISION_BRIEF.md 任务 1）——route 直接映射成
        gate_state，human_readable 用 notes，机器决策不应该解析这个字段。"""
        return build_gate_contract(
            gate_state=self.route, R=self.R, C=self.C, O=self.O, Ro=self.Ro,
            reason_code=self.reason_code,
            auto_repair_available=getattr(self, "repair_attempts", 0) > 0,
            human_readable=self.notes,
        )
