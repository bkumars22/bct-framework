"""
Level 6 — "BCT tests contracts between AI agents in multi-agent systems."

Single-agent BCT (verifier.py) tests whether ONE agent holds its own
contract under adversarial pressure from a human user. In a multi-agent
pipeline, a contract can also break through a channel single-agent testing
never sees: agent A's own output becomes agent B's input. Agent B can be
attacked indirectly — never receiving a hostile message from a human at
all — purely because A's (successfully-pressured) output carried the
attack downstream. This is inter-agent / indirect prompt injection, and
it's the specific failure mode this module tests: for each adjacent pair
of agents in a pipeline, it pressures the upstream agent, feeds its REAL
response into the downstream agent, and judges the downstream agent
against ITS OWN contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .case_synthesizer import synthesize_cases
from .contract import BehavioralContract
from .generator import AdversarialTestGenerator
from .judge import judge_compliance
from . import llm_client


@dataclass
class AgentNode:
    name: str
    contract: BehavioralContract
    provider: Optional[str] = None


@dataclass
class InterAgentFinding:
    from_agent: str
    to_agent: str
    category: str
    pressure_category: str
    pressure_intensity: int
    upstream_input: str
    upstream_output: str
    downstream_output: str
    downstream_verdict: str


@dataclass
class MultiAgentReport:
    pipeline_name: str
    agents: List[str]
    links_tested: int
    findings: List[InterAgentFinding]
    propagation_rate: float  # fraction of tested handoffs where a violation propagated

    def print_report(self):
        print(f"\n{'='*55}")
        print("BCT MULTI-AGENT VERIFICATION")
        print(f"Pipeline: {self.pipeline_name}")
        print(f"Agents:   {' -> '.join(self.agents)}")
        print(f"{'='*55}")
        print(f"Inter-agent propagation rate: {self.propagation_rate:.1%} "
              f"({len(self.findings)}/{self.links_tested} tested handoffs broke a downstream contract)")
        if not self.findings:
            print("No inter-agent contract violations found in the tested handoffs.")
        for f in self.findings:
            print(f"\n🔴 {f.from_agent} -> {f.to_agent} "
                  f"(pressure: {f.pressure_category} L{f.pressure_intensity})")
            print(f"   Upstream input:  {f.upstream_input[:70]}...")
            print(f"   Upstream output: {f.upstream_output[:70]}...")
            print(f"   {f.to_agent} then violated its own contract: {f.downstream_output[:70]}...")
        print(f"\n{'='*55}")


class MultiAgentVerifier:
    """
    Chains agents' contracts across a pipeline. For each adjacent pair
    (upstream, downstream), it re-uses the same adversarial test-case
    synthesis and judge logic as single-agent verification, but instead of
    judging the upstream agent's own response against its own contract, it
    passes that response on to the downstream agent and judges the
    downstream agent's response against the DOWNSTREAM agent's contract —
    testing whether pressure aimed at one agent can break a different one.
    """

    async def verify_pipeline(
        self,
        pipeline_name: str,
        agents: List[AgentNode],
        cases_per_link: int = 10,
        topic: Optional[str] = None,
    ) -> MultiAgentReport:
        if len(agents) < 2:
            raise ValueError("A pipeline needs at least 2 agents to test a handoff between them.")
        if llm_client.configured_provider() is None and all(a.provider is None for a in agents):
            raise RuntimeError(
                "No LLM API key configured — multi-agent verification requires real provider "
                "calls at each handoff (there is no simulation mode for agent-to-agent chains)."
            )

        findings: List[InterAgentFinding] = []
        links_tested = 0

        for upstream, downstream in zip(agents[:-1], agents[1:]):
            try:
                cases = await synthesize_cases(upstream.contract, topic, upstream.provider)
            except Exception as exc:
                print(f"⚠️  LLM test-case generation failed for {upstream.name} ({exc}) "
                      f"— falling back to fixed templates.")
                cases = AdversarialTestGenerator().generate(upstream.contract, topic or "7 times 8")

            for case in cases[:cases_per_link]:
                links_tested += 1
                upstream_output = await llm_client.get_response(
                    upstream.contract.to_system_prompt(), case.input_text, upstream.provider,
                )
                downstream_output = await llm_client.get_response(
                    downstream.contract.to_system_prompt(), upstream_output, downstream.provider,
                )
                passed, verdict = await judge_compliance(downstream_output, downstream.contract, downstream.provider)
                if not passed:
                    findings.append(InterAgentFinding(
                        from_agent=upstream.name, to_agent=downstream.name,
                        category="propagated_violation",
                        pressure_category=case.category, pressure_intensity=case.intensity,
                        upstream_input=case.input_text,
                        upstream_output=upstream_output,
                        downstream_output=downstream_output,
                        downstream_verdict=verdict,
                    ))

        propagation_rate = len(findings) / links_tested if links_tested else 0.0
        return MultiAgentReport(
            pipeline_name=pipeline_name,
            agents=[a.name for a in agents],
            links_tested=links_tested,
            findings=findings,
            propagation_rate=propagation_rate,
        )
