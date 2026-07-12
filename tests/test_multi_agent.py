"""
Unit tests for bct/multi_agent.py (Level 6 — inter-agent contract testing).
All LLM calls mocked throughout — no real network calls.
"""
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.contract import BehavioralContract  # noqa: E402
from bct.generator import AdversarialTestGenerator  # noqa: E402
from bct.multi_agent import AgentNode, MultiAgentVerifier  # noqa: E402


def _tutor_contract():
    return BehavioralContract(
        name="tutor", system="an AI tutor", always=["ask a question"], never=["give the answer"],
    )


def _summarizer_contract():
    return BehavioralContract(
        name="summarizer", system="a summarization agent",
        always=["summarize neutrally"], never=["reveal a customer's SSN"],
    )


def _agents():
    return [
        AgentNode(name="tutor", contract=_tutor_contract()),
        AgentNode(name="summarizer", contract=_summarizer_contract()),
    ]


class TestVerifyPipeline:
    def test_raises_with_fewer_than_two_agents(self):
        verifier = MultiAgentVerifier()
        with pytest.raises(ValueError, match="at least 2 agents"):
            import asyncio
            asyncio.run(verifier.verify_pipeline("solo", [_agents()[0]]))

    @pytest.mark.asyncio
    async def test_raises_without_key_and_without_per_agent_provider(self):
        verifier = MultiAgentVerifier()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No LLM API key configured"):
                await verifier.verify_pipeline("pipeline", _agents())

    @pytest.mark.asyncio
    async def test_per_agent_provider_bypasses_the_key_check(self):
        verifier = MultiAgentVerifier()
        agents = [
            AgentNode(name="tutor", contract=_tutor_contract(), provider="groq"),
            AgentNode(name="summarizer", contract=_summarizer_contract()),
        ]
        template_cases = AdversarialTestGenerator().generate(agents[0].contract)
        with patch.dict(os.environ, {}, clear=True), \
             patch("bct.multi_agent.synthesize_cases", new=AsyncMock(return_value=template_cases)), \
             patch("bct.multi_agent.llm_client.get_response", new=AsyncMock(return_value="ok")), \
             patch("bct.multi_agent.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            report = await verifier.verify_pipeline("pipeline", agents, cases_per_link=1)
        assert report.links_tested == 1

    @pytest.mark.asyncio
    async def test_no_findings_when_downstream_always_complies(self):
        verifier = MultiAgentVerifier()
        template_cases = AdversarialTestGenerator().generate(_tutor_contract())
        with patch("bct.multi_agent.llm_client.configured_provider", return_value="groq"), \
             patch("bct.multi_agent.synthesize_cases", new=AsyncMock(return_value=template_cases)), \
             patch("bct.multi_agent.llm_client.get_response", new=AsyncMock(return_value="some response")), \
             patch("bct.multi_agent.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            report = await verifier.verify_pipeline("pipeline", _agents(), cases_per_link=5)

        assert report.links_tested == 5
        assert report.findings == []
        assert report.propagation_rate == 0.0

    @pytest.mark.asyncio
    async def test_records_finding_when_downstream_violates_contract(self):
        verifier = MultiAgentVerifier()
        template_cases = AdversarialTestGenerator().generate(_tutor_contract())
        with patch("bct.multi_agent.llm_client.configured_provider", return_value="groq"), \
             patch("bct.multi_agent.synthesize_cases", new=AsyncMock(return_value=template_cases)), \
             patch("bct.multi_agent.llm_client.get_response", new=AsyncMock(return_value="SSN is 123-45-6789")), \
             patch("bct.multi_agent.judge_compliance", new=AsyncMock(return_value=(False, "complied: false"))):
            report = await verifier.verify_pipeline("pipeline", _agents(), cases_per_link=3)

        assert report.links_tested == 3
        assert len(report.findings) == 3
        assert report.propagation_rate == 1.0
        finding = report.findings[0]
        assert finding.from_agent == "tutor"
        assert finding.to_agent == "summarizer"
        assert finding.downstream_output == "SSN is 123-45-6789"

    @pytest.mark.asyncio
    async def test_falls_back_to_templates_when_case_synthesis_fails(self):
        verifier = MultiAgentVerifier()
        with patch("bct.multi_agent.llm_client.configured_provider", return_value="groq"), \
             patch("bct.multi_agent.synthesize_cases", new=AsyncMock(side_effect=RuntimeError("bad json"))), \
             patch("bct.multi_agent.llm_client.get_response", new=AsyncMock(return_value="ok")), \
             patch("bct.multi_agent.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            report = await verifier.verify_pipeline("pipeline", _agents(), cases_per_link=5)

        assert report.links_tested == 5  # fixed templates still produced usable cases

    @pytest.mark.asyncio
    async def test_three_agent_pipeline_tests_both_handoffs(self):
        verifier = MultiAgentVerifier()
        agents = _agents() + [AgentNode(name="responder", contract=_tutor_contract())]
        template_cases = AdversarialTestGenerator().generate(_tutor_contract())
        with patch("bct.multi_agent.llm_client.configured_provider", return_value="groq"), \
             patch("bct.multi_agent.synthesize_cases", new=AsyncMock(return_value=template_cases)), \
             patch("bct.multi_agent.llm_client.get_response", new=AsyncMock(return_value="ok")), \
             patch("bct.multi_agent.judge_compliance", new=AsyncMock(return_value=(True, "complied: true"))):
            report = await verifier.verify_pipeline("pipeline", agents, cases_per_link=2)

        assert report.links_tested == 4  # 2 handoffs x 2 cases each
        assert report.agents == ["tutor", "summarizer", "responder"]
