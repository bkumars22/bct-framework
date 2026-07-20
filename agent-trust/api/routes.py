"""All AgentTrust API routes."""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from core.agent_registry import Agent, registry
from core.chain_tester import chain_tester
from core.compliance_engine import compliance_engine
from core.prompt_governor import prompt_governor
from core.watermelon_detector import detect as detect_watermelon

from .models import (
    AgentDetailResponse,
    AgentSummaryResponse,
    ChainTestRequest,
    ChainTestResponse,
    DashboardMetricsResponse,
    PromptUpdateRequest,
    PromptUpdateResponse,
    RegisterAgentRequest,
    RegisterAgentResponse,
    TestAgentResponse,
    WatermelonResponse,
)

router = APIRouter()

# In-memory tally of chain tests run, for the dashboard summary — resets
# with the process, same as everything else in this demo.
_chain_tests_run: List = []


def run_bct_and_update(agent: Agent) -> None:
    report = compliance_engine.run_bct(agent)
    watermelon = detect_watermelon(agent.performance_score, report.overall_compliance, report.weakest_category)

    agent.compliance_score = report.overall_compliance
    agent.breaking_point = report.breaking_point
    agent.weakest_category = report.weakest_category
    agent.compliance_by_intensity = report.compliance_by_intensity
    agent.compliance_by_category = report.compliance_by_category
    agent.recommendations = report.recommendations
    agent.watermelon_gap = watermelon.watermelon_gap
    agent.status = watermelon.status
    agent.last_tested_at = datetime.now(timezone.utc)
    agent.compliance_history.append({
        "tested_at": agent.last_tested_at.isoformat(),
        "compliance_score": agent.compliance_score,
        "performance_score": agent.performance_score,
        "watermelon_gap": agent.watermelon_gap,
    })
    registry.update(agent)


def _get_agent_or_404(agent_id: str) -> Agent:
    agent = registry.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent


def _summary_dict(agent: Agent) -> dict:
    return {
        "agent_id": agent.agent_id,
        "agent_name": agent.agent_name,
        "agent_type": agent.agent_type,
        "performance_score": agent.performance_score,
        "compliance_score": agent.compliance_score,
        "breaking_point": agent.breaking_point,
        "weakest_category": agent.weakest_category,
        "watermelon_gap": agent.watermelon_gap,
        "status": agent.status,
        "registered_at": agent.registered_at,
        "last_tested_at": agent.last_tested_at,
    }


@router.post("/agents/register", response_model=RegisterAgentResponse)
def register_agent(body: RegisterAgentRequest) -> RegisterAgentResponse:
    agent = Agent(
        agent_name=body.name,
        agent_type=body.type,
        system_prompt=body.system_prompt,
        contract_always=body.contract.always,
        contract_never=body.contract.never,
        performance_score=body.performance_score,
    )
    registry.register(agent)
    run_bct_and_update(agent)

    return RegisterAgentResponse(
        agent_id=agent.agent_id,
        compliance_score=agent.compliance_score,
        breaking_point=agent.breaking_point,
        watermelon_gap=agent.watermelon_gap,
        status=agent.status,
        recommendations=agent.recommendations,
    )


@router.get("/agents", response_model=List[AgentSummaryResponse])
def list_agents() -> List[AgentSummaryResponse]:
    return [AgentSummaryResponse(**_summary_dict(a)) for a in registry.list_all()]


@router.get("/agents/{agent_id}", response_model=AgentDetailResponse)
def get_agent(agent_id: str) -> AgentDetailResponse:
    agent = _get_agent_or_404(agent_id)
    watermelon = detect_watermelon(agent.performance_score, agent.compliance_score, agent.weakest_category)
    return AgentDetailResponse(
        **_summary_dict(agent),
        system_prompt=agent.system_prompt,
        contract_always=agent.contract_always,
        contract_never=agent.contract_never,
        compliance_by_intensity=agent.compliance_by_intensity,
        compliance_by_category=agent.compliance_by_category,
        recommendations=agent.recommendations,
        compliance_history=agent.compliance_history,
        prompt_versions=[vars(v) for v in prompt_governor.history(agent.agent_id)],
        watermelon_alert_level=watermelon.alert_level,
    )


@router.post("/agents/{agent_id}/test", response_model=TestAgentResponse)
def retest_agent(agent_id: str) -> TestAgentResponse:
    agent = _get_agent_or_404(agent_id)
    run_bct_and_update(agent)
    return TestAgentResponse(
        agent_id=agent.agent_id,
        compliance_score=agent.compliance_score,
        breaking_point=agent.breaking_point,
        weakest_category=agent.weakest_category,
        compliance_by_intensity=agent.compliance_by_intensity,
        compliance_by_category=agent.compliance_by_category,
        watermelon_gap=agent.watermelon_gap,
        status=agent.status,
        recommendations=agent.recommendations,
    )


@router.post("/agents/{agent_id}/prompt", response_model=PromptUpdateResponse)
def update_prompt(agent_id: str, body: PromptUpdateRequest) -> PromptUpdateResponse:
    agent = _get_agent_or_404(agent_id)
    version = prompt_governor.propose(agent, body.new_prompt)

    if version.approved:
        agent.system_prompt = body.new_prompt
        registry.update(agent)
        run_bct_and_update(agent)

    return PromptUpdateResponse(
        approved=version.approved,
        quality_score=version.quality_score,
        version=version.version,
        reason_if_blocked=None if version.approved else version.reason,
    )


@router.get("/agents/{agent_id}/watermelon", response_model=WatermelonResponse)
def get_watermelon(agent_id: str) -> WatermelonResponse:
    agent = _get_agent_or_404(agent_id)
    watermelon = detect_watermelon(agent.performance_score, agent.compliance_score, agent.weakest_category)
    return WatermelonResponse(
        performance_score=watermelon.performance_score,
        compliance_score=watermelon.compliance_score,
        watermelon_gap=watermelon.watermelon_gap,
        alert_level=watermelon.alert_level,
        recommendation=watermelon.recommendation,
    )


@router.post("/chains/test", response_model=ChainTestResponse)
def test_chain(body: ChainTestRequest) -> ChainTestResponse:
    agents = [_get_agent_or_404(agent_id) for agent_id in body.agent_ids]

    report = chain_tester.test_chain(agents, body.test_input)
    _chain_tests_run.append(report)

    return ChainTestResponse(
        chain_compliance=report.chain_compliance,
        weakest_agent=report.weakest_agent,
        chain_breaking_point=report.chain_breaking_point,
    )


@router.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
def dashboard_metrics() -> DashboardMetricsResponse:
    agents = registry.list_all()
    total = len(agents)
    healthy = sum(1 for a in agents if a.status == "HEALTHY")
    warning = sum(1 for a in agents if a.status == "WARNING")
    critical = sum(1 for a in agents if a.status == "CRITICAL")
    avg_compliance = round(sum(a.compliance_score for a in agents) / total, 3) if total else 0.0
    avg_performance = round(sum(a.performance_score for a in agents) / total, 3) if total else 0.0
    watermelon_alerts = sum(1 for a in agents if a.watermelon_gap > 0.20)

    return DashboardMetricsResponse(
        total_agents=total,
        healthy=healthy,
        warning=warning,
        critical=critical,
        avg_compliance=avg_compliance,
        avg_performance=avg_performance,
        watermelon_alerts=watermelon_alerts,
        chain_tests=len(_chain_tests_run),
    )
