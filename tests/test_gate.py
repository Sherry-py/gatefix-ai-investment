"""Unit tests for gate.py —— the domain-agnostic judgment core (4D-CQ scoring,
four-state routing, commit/reversibility classification, fail-closed semantics,
secret redaction, machine-readable contract).

These exercise the core directly, independent of any case (ai_investment's
integration tests live in test_ai_investment_case.py). The point is to pin the
boundary behavior — especially Q exactly at tau_pass/tau_repair, and the
fail-closed guarantee that a throwing evaluator can never become a PASS."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gate
from gate import GateConfig, ReasonCode, classify_regular_reason_code


def _cfg():
    return GateConfig()


# ---- 4D-CQ quality score ----

def test_quality_score_is_weighted_sum():
    cfg = _cfg()
    # equal weights 0.25 each
    assert cfg.quality_score(1.0, 1.0, 1.0, 1.0) == 1.0
    assert cfg.quality_score(0.2, 0.4, 0.3, 1.0) == 0.25 * (0.2 + 0.4 + 0.3 + 1.0)
    assert cfg.quality_score(0.0, 0.0, 0.0, 0.0) == 0.0


# ---- four-state routing boundaries ----

def test_route_pass_at_exactly_tau_pass():
    cfg = _cfg()
    assert cfg.route(cfg.tau_pass, verifiable_ext=True) == "PASS"
    assert cfg.route(cfg.tau_pass + 0.0001, verifiable_ext=True) == "PASS"


def test_route_auto_repair_inside_band():
    cfg = _cfg()
    # tau_repair <= Q < tau_pass, verifiable → AUTO_REPAIR (before k_dry)
    assert cfg.route(cfg.tau_repair, verifiable_ext=True) == "AUTO_REPAIR"
    assert cfg.route(0.70, verifiable_ext=True, dry_rounds=0) == "AUTO_REPAIR"


def test_route_escalate_below_tau_repair():
    cfg = _cfg()
    assert cfg.route(cfg.tau_repair - 0.0001, verifiable_ext=True) == "ESCALATE"
    assert cfg.route(0.0, verifiable_ext=True) == "ESCALATE"


def test_route_escalate_when_gap_not_externally_verifiable():
    cfg = _cfg()
    # inside the repair band, but the gap cannot be verified externally → no auto-repair
    assert cfg.route(0.70, verifiable_ext=False) == "ESCALATE"


def test_route_escalate_after_k_dry_rounds():
    cfg = _cfg()
    assert cfg.route(0.70, verifiable_ext=True, dry_rounds=cfg.k_dry - 1) == "AUTO_REPAIR"
    assert cfg.route(0.70, verifiable_ext=True, dry_rounds=cfg.k_dry) == "ESCALATE"


# ---- commit (reversibility) classification ----

def test_is_commit_inf_reverse_is_always_commit():
    cfg = _cfg()
    assert cfg.is_commit(float("inf"), 100.0) is True


def test_is_commit_reversible_cheap_action_is_not_commit():
    cfg = _cfg()
    # cost_reverse (10) <= lambda * value (1.0 * 100) → not a commit
    assert cfg.is_commit(10.0, 100.0) is False


def test_is_commit_expensive_reverse_is_commit():
    cfg = _cfg()
    assert cfg.is_commit(101.0, 100.0) is True


# ---- fail-closed semantics ----

def test_safe_score_returns_result_and_no_fault():
    def good(e):
        return {"R": 1.0, "C": 1.0, "O": 1.0, "Ro": 1.0, "verifiable_ext": True, "notes": "ok"}

    result, fault = gate.safe_score(good, {})
    assert fault is False
    assert result["R"] == 1.0


def test_safe_score_fail_closed_on_exception():
    def bad(e):
        raise RuntimeError("boom")

    result, fault = gate.safe_score(bad, {})
    assert fault is True
    # fail-closed placeholder: all-zero scores, can never route to PASS
    assert result["R"] == 0.0 and result["C"] == 0.0 and result["O"] == 0.0 and result["Ro"] == 0.0
    assert result["verifiable_ext"] is False
    assert "FAIL-CLOSED" in result["notes"]


def test_safe_repair_fail_closed_on_exception():
    def bad(e):
        raise RuntimeError("boom")

    new_evidence, fault = gate.safe_repair(bad, {})
    assert fault is True
    assert new_evidence is None


# ---- secret redaction ----

def test_redact_secrets():
    assert gate.redact_secrets("api_key=abc123") == "[REDACTED]"
    assert "Bearer" not in gate.redact_secrets("Authorization: Bearer abcdefghijk")
    assert "sk-" not in gate.redact_secrets("key sk-abcdefghijklmn")
    # non-secret text passes through unchanged
    assert gate.redact_secrets("refund_account_name=第三方") == "refund_account_name=第三方"


def test_build_gate_contract_redacts_human_readable():
    contract = gate.build_gate_contract(
        gate_state="PASS", R=1.0, C=1.0, O=1.0, Ro=1.0,
        reason_code=ReasonCode.PASS_ABOVE_THRESHOLD,
        auto_repair_available=False,
        human_readable="evidence has api_key=secret",
    )
    assert "api_key" not in contract["human_readable"]
    assert "REDACTED" in contract["human_readable"]
    assert contract["gate_state"] == "PASS"
    assert contract["schema_version"] == gate.SCHEMA_VERSION


# ---- expectation gate (soft commit) ----

def test_expectation_gate_truth_table():
    # Send(msg) allowed ⟺ ¬ContainsPromise ∨ HasFeasibilityEvidence
    assert GateConfig.expectation_gate(contains_promise=False, has_feasibility_evidence=False) is True
    assert GateConfig.expectation_gate(contains_promise=False, has_feasibility_evidence=True) is True
    assert GateConfig.expectation_gate(contains_promise=True, has_feasibility_evidence=True) is True
    assert GateConfig.expectation_gate(contains_promise=True, has_feasibility_evidence=False) is False


# ---- reason code classification ----

def test_classify_regular_reason_code_pass():
    code = classify_regular_reason_code(
        route="PASS", Q=0.9, tau_repair=0.5, verifiable_ext=True,
        dry_rounds=0, k_dry=3, repair_attempts=0, repair_fn_registered=True,
    )
    assert code == ReasonCode.PASS_ABOVE_THRESHOLD


def test_classify_regular_reason_code_gap_not_verifiable():
    code = classify_regular_reason_code(
        route="ESCALATE", Q=0.7, tau_repair=0.5, verifiable_ext=False,
        dry_rounds=0, k_dry=3, repair_attempts=0, repair_fn_registered=True,
    )
    assert code == ReasonCode.GAP_NOT_EXTERNALLY_VERIFIABLE
