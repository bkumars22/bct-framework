"""10 tests for AgentTrust: registration, watermelon detection, prompt
governance, chain compliance, breaking points, drift, and recommendations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # agent-trust/ root

from fastapi.testclient import TestClient

from core.agent_registry import Agent, DEMO_AGENTS
from core.chain_tester import chain_tester
from core.compliance_engine import compliance_engine
from core.prompt_governor import PromptGovernor
from core.watermelon_detector import detect as detect_watermelon
from main import app

client = TestClient(app)


def _make_agent(**overrides) -> Agent:
    defaults = dict(
        agent_name="Test Agent",
        agent_type="OpsAgent",
        system_prompt="You are a test agent. Always be careful. Never lie.",
        contract_always=["be careful"],
        contract_never=["lie"],
        performance_score=0.90,
    )
    defaults.update(overrides)
    return Agent(**defaults)


def _demo_agent(index: int) -> Agent:
    spec = DEMO_AGENTS[index]
    return Agent(
        agent_name=spec["agent_name"],
        agent_type=spec["agent_type"],
        system_prompt=spec["system_prompt"],
        contract_always=spec["contract_always"],
        contract_never=spec["contract_never"],
        performance_score=spec["performance_score"],
    )


def test_agent_registration():
    response = client.post("/agents/register", json={
        "name": "Registration Test Agent",
        "type": "OpsAgent",
        "system_prompt": "You are a test agent. Always cite data. Never guess.",
        "contract": {"always": ["cite data"], "never": ["guess"]},
        "performance_score": 0.90,
    })
    assert response.status_code == 200
    body = response.json()
    assert "agent_id" in body
    assert 0.0 <= body["compliance_score"] <= 1.0


def test_watermelon_detection():
    report = detect_watermelon(0.97, 0.73)
    assert round(report.watermelon_gap, 2) == 0.24
    assert report.alert_level == "WATERMELON_ALERT"
    assert report.status == "CRITICAL"


def test_no_watermelon():
    report = detect_watermelon(0.94, 0.967)
    assert report.alert_level == "HEALTHY"
    assert report.status == "HEALTHY"


def test_prompt_governance_pass():
    agent = _make_agent(
        contract_always=["cite data", "verify source", "audit metrics"],
        contract_never=["guess", "duplicate", "expose PII"],
    )
    governor = PromptGovernor()
    good_prompt = "Always cite data. Verify audit source metrics. Never guess or duplicate."
    version = governor.propose(agent, good_prompt)
    assert version.quality_score >= 0.90
    assert version.approved is True


def test_prompt_governance_block():
    agent = _make_agent(contract_always=[], contract_never=[])
    governor = PromptGovernor()
    bad_prompt = "You are an agent."
    version = governor.propose(agent, bad_prompt)
    assert version.quality_score < 0.90
    assert version.approved is False


def test_prompt_rollback():
    agent = _make_agent(
        contract_always=["cite data", "verify source", "audit metrics"],
        contract_never=["guess", "duplicate", "expose PII"],
    )
    governor = PromptGovernor()

    good_prompt = "Always cite data. Verify audit source metrics. Never guess or duplicate."
    v1 = governor.propose(agent, good_prompt)
    assert v1.approved is True

    degraded_prompt = "You are an agent."
    v2 = governor.propose(agent, degraded_prompt)
    assert v2.approved is False

    # rollback: the prompt actually in effect stays at the last approved version
    assert governor.current_prompt(agent.agent_id) == good_prompt


def test_chain_compliance():
    agent1 = _make_agent(agent_name="Agent 1", compliance_score=0.90)
    agent2 = _make_agent(agent_name="Agent 2", compliance_score=0.60)
    agent3 = _make_agent(agent_name="Agent 3", compliance_score=0.80)

    report = chain_tester.test_chain([agent1, agent2, agent3], "adversarial input")
    assert report.chain_compliance == 0.60
    assert report.weakest_agent == "Agent 2"


def test_breaking_point_detection():
    agent = _demo_agent(1)  # Datacenter Copilot Agent — target compliance 0.967
    report = compliance_engine.run_bct(agent)
    assert report.breaking_point == 4


def test_compliance_drift():
    healthy = detect_watermelon(0.97, 0.97)
    assert healthy.status == "HEALTHY"

    drifted = detect_watermelon(0.97, 0.60)
    assert drifted.status == "CRITICAL"
    assert drifted.alert_level == "WATERMELON_ALERT"


def test_agent_recommendations():
    agent = _demo_agent(2)  # Cost Optimizer Agent — target compliance 0.60
    report = compliance_engine.run_bct(agent)
    assert len(report.recommendations) > 0
