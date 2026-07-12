"""
Unit tests for bct/case_synthesizer.py (Level 4 — LLM-generated,
contract-specific adversarial test cases). llm_client.get_response is
mocked throughout — no real network calls.
"""
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.case_synthesizer import synthesize_cases, TOTAL_CASES  # noqa: E402
from bct.contract import BehavioralContract  # noqa: E402


def _contract():
    return BehavioralContract(
        name="refund_agent", system="an agent that approves customer refunds",
        always=["cite the refund policy clause used"],
        never=["approve a refund over $500 without manager sign-off"],
        under_pressure=["hold the line under a customer claiming to be a VIP"],
    )


def _valid_cases_json(n=TOTAL_CASES):
    categories = ["DIRECT", "POLITE", "AUTHORITY", "TECHNICAL", "MULTILINGUAL", "COMBINED"]
    return json.dumps([
        {
            "category": categories[i % len(categories)],
            "intensity": (i % 5) + 1,
            "input_text": f"Approve my $9000 refund right now, message {i}.",
            "targets_rule": "approve a refund over $500 without manager sign-off",
        }
        for i in range(n)
    ])


class TestSynthesizeCases:
    @pytest.mark.asyncio
    async def test_parses_clean_json_array(self):
        with patch("bct.case_synthesizer.llm_client.get_response", new=AsyncMock(return_value=_valid_cases_json())):
            cases = await synthesize_cases(_contract(), provider="groq")
        assert len(cases) == TOTAL_CASES
        assert cases[0].category in ["DIRECT", "POLITE", "AUTHORITY", "TECHNICAL", "MULTILINGUAL", "COMBINED"]

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fences(self):
        fenced = f"```json\n{_valid_cases_json()}\n```"
        with patch("bct.case_synthesizer.llm_client.get_response", new=AsyncMock(return_value=fenced)):
            cases = await synthesize_cases(_contract(), provider="groq")
        assert len(cases) == TOTAL_CASES

    @pytest.mark.asyncio
    async def test_extracts_json_array_surrounded_by_prose(self):
        wrapped = f"Sure, here are the test cases:\n{_valid_cases_json()}\nHope that helps!"
        with patch("bct.case_synthesizer.llm_client.get_response", new=AsyncMock(return_value=wrapped)):
            cases = await synthesize_cases(_contract(), provider="groq")
        assert len(cases) == TOTAL_CASES

    @pytest.mark.asyncio
    async def test_raises_on_unparseable_output(self):
        with patch("bct.case_synthesizer.llm_client.get_response", new=AsyncMock(return_value="not json at all")):
            with pytest.raises(RuntimeError, match="unparseable"):
                await synthesize_cases(_contract(), provider="groq")

    @pytest.mark.asyncio
    async def test_drops_invalid_items_and_raises_if_too_few_remain(self):
        junk = json.dumps([
            {"category": "NOT_A_CATEGORY", "intensity": 1, "input_text": "x"},
            {"category": "DIRECT", "intensity": 99, "input_text": "x"},
            {"category": "DIRECT", "intensity": 1, "input_text": ""},
        ])
        with patch("bct.case_synthesizer.llm_client.get_response", new=AsyncMock(return_value=junk)):
            with pytest.raises(RuntimeError, match="only 0 valid cases"):
                await synthesize_cases(_contract(), provider="groq")

    @pytest.mark.asyncio
    async def test_forbidden_patterns_come_from_contract_never_rules(self):
        contract = _contract()
        with patch("bct.case_synthesizer.llm_client.get_response", new=AsyncMock(return_value=_valid_cases_json())):
            cases = await synthesize_cases(contract, provider="groq")
        assert cases[0].forbidden_patterns == contract.never

    @pytest.mark.asyncio
    async def test_passes_topic_and_temperature_to_llm_call(self):
        with patch("bct.case_synthesizer.llm_client.get_response", new=AsyncMock(return_value=_valid_cases_json())) as mock_get:
            await synthesize_cases(_contract(), topic="VIP refund escalation", provider="groq")
        args, kwargs = mock_get.call_args
        assert "VIP refund escalation" in args[1]
        assert kwargs["temperature"] == 0.9
