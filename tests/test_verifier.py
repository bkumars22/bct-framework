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
from bct.drift_tracker import DriftTracker  # noqa: E402
from bct.formal import KeywordPredicate, Not  # noqa: E402
from bct.generator import AdversarialTestGenerator  # noqa: E402
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


class TestJudgeFormal:
    @pytest.mark.asyncio
    async def test_passes_when_all_formal_rules_pass(self):
        from bct.formal import FormalRule

        verifier = BehavioralContractVerifier()
        contract = _contract()
        contract.formal_rules = [
            FormalRule("no_direct_answer", Not(KeywordPredicate("answer", ["the answer is"]))),
        ]
        passed, detail = await verifier._judge_formal("x", "What do you think?", contract, None)
        assert passed is True
        assert "all formal rules passed" in detail

    @pytest.mark.asyncio
    async def test_fails_and_names_the_violated_rule(self):
        from bct.formal import FormalRule

        verifier = BehavioralContractVerifier()
        contract = _contract()
        contract.formal_rules = [
            FormalRule("no_direct_answer", Not(KeywordPredicate("answer", ["the answer is"]))),
        ]
        passed, detail = await verifier._judge_formal("x", "The answer is 56.", contract, None)
        assert passed is False
        assert "no_direct_answer" in detail

    @pytest.mark.asyncio
    async def test_verify_async_uses_formal_rules_instead_of_llm_judge_when_present(self):
        from bct.formal import FormalRule

        verifier = BehavioralContractVerifier()
        contract = _contract()
        contract.formal_rules = [FormalRule("no_answer", Not(KeywordPredicate("a", ["the answer is"])))]
        template_cases = AdversarialTestGenerator().generate(contract)

        with patch.object(verifier.generator, "generate_async", new=AsyncMock(return_value=template_cases)), \
             patch("bct.verifier.llm_client.get_response", new=AsyncMock(return_value="What do you think?")), \
             patch("bct.verifier.llm_client.configured_provider", return_value="groq"), \
             patch("bct.verifier.judge_compliance", new=AsyncMock()) as mock_llm_judge:
            report = await verifier.verify_async(contract, use_simulation=False, provider="groq")

        mock_llm_judge.assert_not_called()  # formal rules replace the free-text judge entirely
        assert report.overall_compliance == 1.0  # "What do you think?" never violates the formal rule


class TestJudgeCompliance:
    @pytest.mark.asyncio
    async def test_uses_prompt_library_config_and_parses_complied_true(self):
        from bct.prompt_library import BCT_COMPLIANCE_JUDGE

        verifier = BehavioralContractVerifier()
        with patch("bct.verifier.llm_client.get_response", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "complied: true\nviolated_rule: none\nevidence: asked a question"
            passed, verdict = await verifier._judge_compliance("What do you think?", _contract(), provider="groq")

        assert passed is True
        args, kwargs = mock_get.call_args
        assert args[0] == BCT_COMPLIANCE_JUDGE.system
        assert kwargs["temperature"] == BCT_COMPLIANCE_JUDGE.temperature
        assert kwargs["max_tokens"] == BCT_COMPLIANCE_JUDGE.max_tokens

    @pytest.mark.asyncio
    async def test_parses_complied_false(self):
        verifier = BehavioralContractVerifier()
        with patch("bct.verifier.llm_client.get_response", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "complied: false\nviolated_rule: give the answer\nevidence: 56"
            passed, _verdict = await verifier._judge_compliance("It's 56.", _contract(), provider="groq")

        assert passed is False


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
        contract = _contract()
        template_cases = AdversarialTestGenerator().generate(contract)
        with patch.object(verifier.generator, "generate_async", new=AsyncMock(return_value=template_cases)), \
             patch("bct.verifier.llm_client.get_response", new_callable=AsyncMock) as mock_get, \
             patch("bct.verifier.llm_client.configured_provider", return_value="groq"):
            # first call per case = the response under test, second = the judge verdict
            mock_get.side_effect = [
                "What do you think 7 times 8 might be?", "complied: true\nviolated_rule: none\nevidence: asks a guiding question",
            ] * 30
            report = await verifier.verify_async(contract, use_simulation=False, provider="groq")

        assert report.mode == "real"
        assert report.total_tests == 30
        assert report.overall_compliance == 1.0  # every judged response was compliant
        assert report.case_generation == "llm_synthesis"

    @pytest.mark.asyncio
    async def test_real_mode_reports_violations_from_judge(self):
        verifier = BehavioralContractVerifier()
        contract = _contract()
        template_cases = AdversarialTestGenerator().generate(contract)
        with patch.object(verifier.generator, "generate_async", new=AsyncMock(return_value=template_cases)), \
             patch("bct.verifier.llm_client.get_response", new_callable=AsyncMock) as mock_get, \
             patch("bct.verifier.llm_client.configured_provider", return_value="groq"):
            mock_get.side_effect = [
                "The answer is 56.", "complied: false\nviolated_rule: give the answer\nevidence: states the answer directly",
            ] * 30
            report = await verifier.verify_async(contract, use_simulation=False, provider="groq")

        assert report.overall_compliance == 0.0
        assert report.result == "❌ FAILED"

    @pytest.mark.asyncio
    async def test_real_mode_falls_back_to_templates_when_case_synthesis_fails(self):
        verifier = BehavioralContractVerifier()
        contract = _contract()
        with patch.object(verifier.generator, "generate_async", new=AsyncMock(side_effect=RuntimeError("bad json"))), \
             patch("bct.verifier.llm_client.get_response", new_callable=AsyncMock) as mock_get, \
             patch("bct.verifier.llm_client.configured_provider", return_value="groq"):
            mock_get.side_effect = [
                "What do you think 7 times 8 might be?", "complied: true\nviolated_rule: none\nevidence: asks a guiding question",
            ] * 30
            report = await verifier.verify_async(contract, use_simulation=False, provider="groq")

        assert report.case_generation == "template_fallback"
        assert report.total_tests == 30

    def test_simulation_mode_uses_templates_directly(self):
        verifier = BehavioralContractVerifier()
        with patch.dict(os.environ, {}, clear=True):
            report = verifier.verify(_contract(), use_simulation=True, random_seed=1)
        assert report.case_generation == "template"

    def test_history_path_records_a_run_when_provided(self, tmp_path):
        history_path = str(tmp_path / "history.jsonl")
        verifier = BehavioralContractVerifier()
        with patch.dict(os.environ, {}, clear=True):
            report = verifier.verify(
                _contract(), use_simulation=True, random_seed=1, history_path=history_path,
            )
        runs = DriftTracker(history_path).history(_contract().name)
        assert len(runs) == 1
        assert runs[0].overall_compliance == report.overall_compliance

    def test_no_history_file_written_when_history_path_omitted(self, tmp_path):
        history_path = str(tmp_path / "history.jsonl")
        verifier = BehavioralContractVerifier()
        with patch.dict(os.environ, {}, clear=True):
            verifier.verify(_contract(), use_simulation=True, random_seed=1)
        assert not os.path.exists(history_path)
