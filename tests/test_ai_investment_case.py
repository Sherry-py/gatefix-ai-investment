"""Tests for the ai_investment case — the first case in this repo whose judgment
target is an investment DECISION (not an agent action): whether the evidence
for investing in an AI project is sufficient to authorize committing capital.

This is also the first case backed by an AI-project sample (Qiongche / Noematrix)
whose evidence values come from public reporting + the company BP (both "to be
verified"), NOT a real internal due-diligence record — the honest-disclosure
stance is explicit about this. There is NO real investment decision behind
this case yet (n=0); the scoring field split and thresholds are a first pass,
to be tightened after real cases.

The intent of the committed evidence is to keep Qiongche's real state — most
governance evidence unconfirmed, landing evidence with unclear contract
口径 (contract/framework/intent not separated) — so the gate routes BOTH the
investment decision and the valuation to ESCALATE (human review), never PASS.
The governance gap is marked externally-verifiable, but Q lands below
tau_repair, so it escalates straight to the investment committee without an
automated repair attempt (AUTO_REPAIR only fires inside [tau_repair, tau_pass))."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine
from gate import GateConfig


EXPECTED_ROUTES = {
    "invest_decision": "ESCALATE",
    "valuation": "ESCALATE",
    "team_capability": "BYPASS_TO_HUMAN",
}


def test_ai_investment_case_reproduces_expected_routes():
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    assert len(records) == len(EXPECTED_ROUTES)
    routes = {r["commit_id"]: r["route"] for r in records}
    assert routes == EXPECTED_ROUTES


def test_ai_investment_governance_escalates_below_repair_band():
    """Qiongche's governance evidence is 0/6 confirmed — Q lands at 0.225,
    well below tau_repair — so it escalates straight to the investment
    committee without an automated repair attempt, even though the gap is
    marked externally-verifiable. This mirrors the "黄灯 → 人工终审" conclusion
    in the research notes, encoded deterministically."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "invest_decision")
    cfg = GateConfig()
    assert rec["Q"] < cfg.tau_repair
    assert rec["route"] == "ESCALATE"
    assert rec["dry_rounds"] == 0
    assert "AUTO_REPAIR" not in rec["notes"]
    assert "红线" in rec["notes"]


def test_ai_investment_landing_reports_verified_level():
    """Qiongche's landing evidence: deployment + industry embedding are present
    (2/5), but paid contracts / economic value / repeat orders are unverified —
    the verified landing level reports L1, with the L2 claim (2000 signed units)
    blocked on contract verification. The red line (deployment + verified paid
    contract) is not passed."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "valuation")
    assert rec["route"] == "ESCALATE"
    assert "L1" in rec["notes"]
    assert "红线" in rec["notes"]


def test_ai_investment_team_capability_bypasses_to_human():
    """Team capability (能不能把技术落地) is a relationship/execution judgment
    the machine cannot assemble — it must bypass straight to the investment
    committee, never entering 4D-CQ scoring."""
    engine.run_case("ai_investment")
    record_path = engine.BASE_DIR / "gate_record.jsonl"
    records = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines()]

    rec = next(r for r in records if r["commit_id"] == "team_capability")
    assert rec["route"] == "BYPASS_TO_HUMAN"
    assert rec["bypassed_to_human"] is True
    assert rec["R"] == 0 and rec["C"] == 0 and rec["Q"] == 0
