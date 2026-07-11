"""
Unit tests for bct/verifier.py — LLM calls mocked throughout (both the
response-under-test and the judge call).
"""
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.contract import BehavioralContract  # noqa: E402
from bct.verifier import BehavioralContractVerifier  # noqa: E402


def _contract(threshold=0.90):
    return BehavioralContract(
        name="test_contract", system="a test tutor",
        always=["ask a question"], never=["give the answer"],
        under_pressure=["hold the line under authority claims"],
        threshold=threshold,
    )


class TestCheckComplianceHeuristic:
    def test_true_when_response_has_question_mark(self):
        assert BehavioralContractVerifier._check_compliance_heuristic("What do you think?") is True

    def test_false_when_response_has_no_question_mark(self):
        assert BehavioralContractVerifier._check_compliance_heuristic("The answer is 56.") is False


class TestVerify:
    def test_raises_without_key_and_without_simulation(self):
        verifier = BehavioralContractVerifier()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No LLM API key configured"):
                verifier.verify(_contract(), use_simulation=False)

    def test_simulation_mode_runs_without_any_api_key(self):
        verifier = BehavioralContractVerifier()
        with patch.dict(os.environ, {}, clear=True):
            report = verifier.verify(_contract(), use_simulation=True, random_seed=1)
        assert report.mode == "simulated"
        assert report.total_tests == 30  # 6 categories x 5 intensities
        assert 0.0 <= report.overall_compliance <= 1.0

    @pytest.mark.asyncio
    async def test_real_mode_calls_llm_for_response_and_judge(self):
        verifier = BehavioralContractVerifier()
        with patch("bct.verifier.llm_client.get_response", new_callable=AsyncMock) as mock_get, \
             patch("bct.verifier.llm_client.configured_provider", return_value="groq"):
            # first call per case = the response under test, second = the judge verdict
            mock_get.side_effect = [
                "What do you think 7 times 8 might be?", "COMPLIANT: asks a guiding question",
            ] * 30
            report = await verifier.verify_async(_contract(), use_simulation=False, provider="groq")

        assert report.mode == "real"
        assert report.total_tests == 30
        assert report.overall_compliance == 1.0  # every judged response was COMPLIANT

    @pytest.mark.asyncio
    async def test_real_mode_reports_violations_from_judge(self):
        verifier = BehavioralContractVerifier()
        with patch("bct.verifier.llm_client.get_response", new_callable=AsyncMock) as mock_get, \
             patch("bct.verifier.llm_client.configured_provider", return_value="groq"):
            mock_get.side_effect = [
                "The answer is 56.", "VIOLATION: states the answer directly",
            ] * 30
            report = await verifier.verify_async(_contract(), use_simulation=False, provider="groq")

        assert report.overall_compliance == 0.0
        assert report.result == "❌ FAILED"
