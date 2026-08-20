"""Tests for the MCP server surface —— the interface external partners call.

The MCP server exposes the same deterministic judgment as the CLI, but on
LIVE evidence (caller-provided) rather than the static evidence YAML. These
tests call the tool functions directly (like the rest of the suite does) — no
MCP transport needed, matching the module's own design note that the
@mcp.tool() decorator does not change the function itself."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("mcp")

from mcp_server import server  # noqa: E402


ALL_GREEN_GOVERNANCE = {
    "filing_license_verified": True,
    "data_compliance_verified": True,
    "safety_certified": True,
    "controllability_data_present": True,
    "privacy_compliance_verified": True,
    "cross_border_compliance_verified": True,
    "compliance_before_operations": True,
    "evidence_source_verified": True,
}


def test_list_precondition_functions_exposes_two_gates():
    funcs = server.list_precondition_functions(case="ai_investment")
    names = {f["precondition_fn"] for f in funcs}
    assert names == {"score_invest_governance", "score_landing_level"}
    for f in funcs:
        assert f["commit_name"] in ("AI 项目投资决策（治理证据闸门）", "估值锁定（落地证据闸门）")
        assert f["doc"]  # docstring is how partners learn what evidence to send


def test_authorize_pass_with_all_green_evidence():
    r = server.authorize(
        case="ai_investment",
        precondition_fn="score_invest_governance",
        evidence=ALL_GREEN_GOVERNANCE,
    )
    assert r["route"] == "PASS"
    assert r["authorized"] is True
    assert r["gate_state"] == "PASS"
    assert r["Q"] == 1.0


def test_authorize_escalate_with_missing_evidence():
    weak = {"filing_license_verified": True, "evidence_source_verified": False}
    r = server.authorize(
        case="ai_investment",
        precondition_fn="score_invest_governance",
        evidence=weak,
    )
    assert r["route"] == "ESCALATE"
    assert r["authorized"] is False
    assert r["Q"] < 0.5  # below tau_repair → straight to ESCALATE, no repair


def test_authorize_returns_machine_readable_contract():
    r = server.authorize(
        case="ai_investment",
        precondition_fn="score_invest_governance",
        evidence=ALL_GREEN_GOVERNANCE,
    )
    # task-1 contract: downstream should read these structured fields, not parse text
    for key in ("gate_state", "schema_version", "cq_scores", "reason_code", "auto_repair_available"):
        assert key in r
    assert r["reason_code"] == "PASS_ABOVE_THRESHOLD"


def test_authorize_unknown_precondition_raises():
    with pytest.raises(ValueError, match="unknown precondition_fn"):
        server.authorize(
            case="ai_investment",
            precondition_fn="does_not_exist",
            evidence={},
        )


def test_bypass_commit_is_not_exposed_to_external_clients():
    """team_capability is bypass_to_human (人情类，机器不拍板) — the full case
    has 3 commit points, but list_precondition_functions only exposes the 2
    evidence-judged gates; the bypass commit must not appear, so an external
    client cannot use evidence alone to 'authorize' a decision that belongs to
    the investment committee."""
    funcs = server.list_precondition_functions(case="ai_investment")
    commit_ids = {f["commit_id"] for f in funcs}
    assert commit_ids == {"invest_decision", "valuation"}
    assert "team_capability" not in commit_ids
