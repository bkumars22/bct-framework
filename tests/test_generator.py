"""Unit tests for bct/generator.py's generate() (template) and generate_async() (LLM synthesis passthrough)."""
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.contract import BehavioralContract  # noqa: E402
from bct.generator import AdversarialTestGenerator  # noqa: E402


def _contract():
    return BehavioralContract(
        name="test_contract", system="a test tutor",
        always=["ask a question"], never=["give the answer"],
    )


class TestGenerate:
    def test_returns_30_cases_across_6_categories(self):
        cases = AdversarialTestGenerator().generate(_contract(), "7 times 8")
        assert len(cases) == 30
        assert {c.category for c in cases} == {
            "DIRECT", "POLITE", "AUTHORITY", "TECHNICAL", "MULTILINGUAL", "COMBINED",
        }


class TestGenerateAsync:
    @pytest.mark.asyncio
    async def test_delegates_to_case_synthesizer(self):
        sentinel = ["case-from-llm"]
        with patch("bct.case_synthesizer.synthesize_cases", new=AsyncMock(return_value=sentinel)):
            result = await AdversarialTestGenerator().generate_async(_contract(), "topic", provider="groq")
        assert result == sentinel

    @pytest.mark.asyncio
    async def test_propagates_synthesis_failure_without_catching(self):
        with patch("bct.case_synthesizer.synthesize_cases", new=AsyncMock(side_effect=RuntimeError("boom"))):
            with pytest.raises(RuntimeError, match="boom"):
                await AdversarialTestGenerator().generate_async(_contract(), "topic", provider="groq")
