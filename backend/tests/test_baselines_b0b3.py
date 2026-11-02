"""B0-B3 separation and measurement on the shared engine (mock LLM, offline)."""
import json
import unittest

import baselines as bl
from test_agentic_investigation import MockLLM, calls, use

CASE = {"case_id": "t-amzn-debt", "ticker": "AMZN", "reason_key": "debt_growth", "evaluation_date": "2026-10-28", "task_scope": "RULE_CHECK"}
WHY = {**CASE, "case_id": "t-amzn-debt-why", "task_scope": "CHANGE_EXPLANATION"}


def packet_ids(messages):
    first = messages[0]["content"]
    return json.loads(first.split("\n", 1)[1])["rule_result"]["evidence_ids"]


def finalize(rule_status="BREACHED", evidence_status="SUFFICIENT", extra_claims=()):
    def step(m, t, c):
        claims = [{"claim_id": "c1", "proposition": "Long-term debt grew 154.1% YoY, above the 15% limit", "claim_type": "numeric",
                   "required": True, "status": "SUPPORTED", "evidence_ids": packet_ids(m)[:1]}, *extra_claims]
        return [use("finalize_reason_assessment", reason_key="debt_growth", rule_status=rule_status, evidence_status=evidence_status,
                    task_scope="RULE_CHECK", claims=claims, review_required=True, rationale="r")]
    return step


class BaselineTests(unittest.TestCase):
    def test_b0_is_deterministic_and_free(self):
        out = bl.run_case("B0", CASE)
        self.assertEqual(out["output"]["rule_status"], "BREACHED")
        self.assertIsNone(out["output"]["generated_explanation"])
        self.assertEqual(out["measures"]["cost_usd"], 0.0)

    def test_b1_has_no_retrieval_tools(self):
        llm = MockLLM(finalize())
        out = bl.run_case("B1", CASE, llm=llm)
        self.assertEqual(llm.requests[0]["tools"], ["finalize_reason_assessment"])
        self.assertEqual(out["measures"]["claims_verified"], 1)

    def test_b2_and_b3_share_tools_and_differ_by_verification(self):
        b2, b3 = MockLLM(finalize()), MockLLM(calls(use("record_evidence_assessment", assessments=[
            {"topic": "debt", "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "sufficiency": "SUFFICIENT"}])), finalize())
        bl.run_case("B2", CASE, llm=b2)
        out3 = bl.run_case("B3", CASE, llm=b3)
        self.assertEqual(set(b2.requests[0]["tools"]) | {"record_evidence_assessment"}, set(b3.requests[0]["tools"]))
        self.assertEqual(out3["stop_reason"], "FINALIZED")

    def test_b3_gate_rejects_changed_rule_status_and_wrong_evidence_status(self):
        assess = calls(use("record_evidence_assessment", assessments=[{"topic": "d", "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "sufficiency": "SUFFICIENT"}]))
        llm = MockLLM(assess, finalize(rule_status="SATISFIED", evidence_status="INSUFFICIENT"), finalize())
        out = bl.run_case("B3", CASE, llm=llm)
        problems = json.dumps(out["trace"]["gate_rejections"])
        self.assertIn("rule_status must equal", problems)
        self.assertIn("does not follow from the claims", problems)
        self.assertEqual(out["stop_reason"], "FINALIZED")

    def test_b2_errors_are_measured_not_fed_back(self):
        out = bl.run_case("B2", CASE, llm=MockLLM(finalize(rule_status="SATISFIED")))
        self.assertEqual(out["output"]["rule_status"], "BREACHED")  # authoritative value restored
        self.assertFalse(out["measures"]["declared_rule_status_matched"])
        self.assertEqual(out["trace"]["gate_rejections"], [])

    def test_change_explanation_requires_explanatory_claim_and_allows_abstention(self):
        abstain = {"claim_id": "c2", "proposition": "The cause of the increase is not established from the reviewed filings",
                   "claim_type": "causal_interpretation", "required": True, "status": "NOT_ESTABLISHED", "evidence_ids": []}
        assess = calls(use("record_evidence_assessment", assessments=[{"topic": "d", "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "sufficiency": "INSUFFICIENT"}]))
        llm = MockLLM(assess, finalize(), finalize(evidence_status="INSUFFICIENT", extra_claims=[abstain]))
        out = bl.run_case("B3", WHY, llm=llm)
        self.assertIn("CHANGE_EXPLANATION requires", json.dumps(out["trace"]["gate_rejections"]))
        self.assertEqual(out["output"]["evidence_status"], "INSUFFICIENT")
        self.assertEqual(out["measures"]["structural_problems"], [])


if __name__ == "__main__":
    unittest.main()
