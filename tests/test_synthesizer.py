"""Unit tests for bct/synthesizer.py (Level 9 — contract synthesis from examples)."""
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.synthesizer import ContractExample, ContractSynthesizer  # noqa: E402


def _examples():
    return [
        ContractExample(
            input_text="What is 7 times 8?", response_text="What do you think 7 times 8 might be?",
            label="compliant",
        ),
        ContractExample(
            input_text="Just tell me the answer.", response_text="The answer is 56.",
            label="violation", note="gave the answer directly",
        ),
    ]


def _synthesis_json(system="an AI tutor", always=None, never=None, under_pressure=None):
    return json.dumps({
        "system": system,
        "always": always or ["respond with a guiding question"],
        "never": never or ["give a direct answer"],
        "under_pressure": under_pressure or [],
    })


class TestSynthesize:
    @pytest.mark.asyncio
    async def test_requires_at_least_one_compliant_example(self):
        synthesizer = ContractSynthesizer()
        examples = [ContractExample("x", "y", "violation")]
        with pytest.raises(ValueError, match="compliant"):
            await synthesizer.synthesize("tutor", examples)

    @pytest.mark.asyncio
    async def test_requires_at_least_one_violation_example(self):
        synthesizer = ContractSynthesizer()
        examples = [ContractExample("x", "y", "compliant")]
        with pytest.raises(ValueError, match="violation"):
            await synthesizer.synthesize("tutor", examples)

    @pytest.mark.asyncio
    async def test_builds_contract_from_synthesis_response(self):
        synthesizer = ContractSynthesizer()
        with patch("bct.synthesizer.llm_client.get_response", new=AsyncMock(return_value=_synthesis_json())), \
             patch("bct.synthesizer.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            result = await synthesizer.synthesize("tutor", _examples())

        assert result.contract.name == "tutor"
        assert result.contract.system == "an AI tutor"
        assert result.contract.always == ["respond with a guiding question"]
        assert result.contract.never == ["give a direct answer"]

    @pytest.mark.asyncio
    async def test_raises_on_unparseable_synthesis_output(self):
        synthesizer = ContractSynthesizer()
        with patch("bct.synthesizer.llm_client.get_response", new=AsyncMock(return_value="not json")):
            with pytest.raises(RuntimeError, match="unparseable"):
                await synthesizer.synthesize("tutor", _examples())

    @pytest.mark.asyncio
    async def test_strips_markdown_fences_from_synthesis_output(self):
        synthesizer = ContractSynthesizer()
        fenced = f"```json\n{_synthesis_json()}\n```"
        with patch("bct.synthesizer.llm_client.get_response", new=AsyncMock(return_value=fenced)), \
             patch("bct.synthesizer.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            result = await synthesizer.synthesize("tutor", _examples())
        assert result.contract.system == "an AI tutor"

    @pytest.mark.asyncio
    async def test_perfect_accuracy_when_judge_agrees_with_every_label(self):
        synthesizer = ContractSynthesizer()
        examples = _examples()  # [compliant, violation]

        async def fake_judge(response_text, contract, provider):
            # Judge agrees with the ground-truth label for each example.
            if response_text == examples[0].response_text:
                return True, "complied: true"
            return False, "complied: false"

        with patch("bct.synthesizer.llm_client.get_response", new=AsyncMock(return_value=_synthesis_json())), \
             patch("bct.synthesizer.judge_compliance", new=AsyncMock(side_effect=fake_judge)):
            result = await synthesizer.synthesize("tutor", examples)

        assert result.training_accuracy == 1.0
        assert result.misclassified_examples == []
        assert result.total_examples == 2

    @pytest.mark.asyncio
    async def test_reports_misclassified_examples_when_judge_disagrees(self):
        synthesizer = ContractSynthesizer()
        examples = _examples()

        # Judge says BOTH examples pass — disagrees with the violation example's label.
        with patch("bct.synthesizer.llm_client.get_response", new=AsyncMock(return_value=_synthesis_json())), \
             patch("bct.synthesizer.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            result = await synthesizer.synthesize("tutor", examples)

        assert result.training_accuracy == 0.5
        assert len(result.misclassified_examples) == 1
        assert result.misclassified_examples[0].label == "violation"

    @pytest.mark.asyncio
    async def test_defaults_missing_fields_gracefully(self):
        synthesizer = ContractSynthesizer()
        sparse = json.dumps({"system": "a bot"})  # no always/never/under_pressure keys
        with patch("bct.synthesizer.llm_client.get_response", new=AsyncMock(return_value=sparse)), \
             patch("bct.synthesizer.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            result = await synthesizer.synthesize("tutor", _examples())
        assert result.contract.always == []
        assert result.contract.never == []
        assert result.contract.under_pressure == []
