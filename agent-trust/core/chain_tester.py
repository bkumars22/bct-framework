"""Multi-agent chain compliance testing.

Chains model a pipeline of registered agents (e.g. diagnostic -> copilot ->
ticketing) where one agent's output becomes the next agent's input. A
chain is only as trustworthy as its weakest link, so chain_compliance is
the MIN of the participating agents' individual compliance scores, not an
average — one non-compliant agent in the chain is enough to fail it.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ChainReport:
    agent_ids: List[str]
    agent_names: List[str]
    agent_scores: List[float]
    chain_compliance: float
    weakest_agent: str
    chain_breaking_point: Optional[int]
    test_input: str


class ChainTester:
    def test_chain(self, agents: List, test_input: str) -> ChainReport:
        if not agents:
            raise ValueError("A chain needs at least one agent.")

        scores = [a.compliance_score for a in agents]
        chain_compliance = min(scores)
        weakest_agent = agents[scores.index(chain_compliance)].agent_name

        breaking_points = [a.breaking_point for a in agents if a.breaking_point is not None]
        chain_breaking_point = min(breaking_points) if breaking_points else None

        return ChainReport(
            agent_ids=[a.agent_id for a in agents],
            agent_names=[a.agent_name for a in agents],
            agent_scores=scores,
            chain_compliance=chain_compliance,
            weakest_agent=weakest_agent,
            chain_breaking_point=chain_breaking_point,
            test_input=test_input,
        )


chain_tester = ChainTester()
