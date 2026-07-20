"""Pydantic request/response schemas for the AgentTrust API."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ContractSpec(BaseModel):
    always: List[str] = Field(default_factory=list)
    never: List[str] = Field(default_factory=list)


class RegisterAgentRequest(BaseModel):
    name: str
    type: str
    system_prompt: str
    contract: ContractSpec = Field(default_factory=ContractSpec)
    performance_score: float = 0.90


class RegisterAgentResponse(BaseModel):
    agent_id: str
    compliance_score: float
    breaking_point: Optional[int]
    watermelon_gap: float
    status: str
    recommendations: List[str]


class AgentSummaryResponse(BaseModel):
    agent_id: str
    agent_name: str
    agent_type: str
    performance_score: float
    compliance_score: float
    breaking_point: Optional[int]
    weakest_category: str
    watermelon_gap: float
    status: str
    registered_at: datetime
    last_tested_at: Optional[datetime]


class AgentDetailResponse(AgentSummaryResponse):
    system_prompt: str
    contract_always: List[str]
    contract_never: List[str]
    compliance_by_intensity: Dict[int, float]
    compliance_by_category: Dict[str, float]
    recommendations: List[str]
    compliance_history: List[dict]
    prompt_versions: List[dict]
    watermelon_alert_level: str


class TestAgentResponse(BaseModel):
    agent_id: str
    compliance_score: float
    breaking_point: Optional[int]
    weakest_category: str
    compliance_by_intensity: Dict[int, float]
    compliance_by_category: Dict[str, float]
    watermelon_gap: float
    status: str
    recommendations: List[str]


class PromptUpdateRequest(BaseModel):
    new_prompt: str


class PromptUpdateResponse(BaseModel):
    approved: bool
    quality_score: float
    version: int
    reason_if_blocked: Optional[str]


class WatermelonResponse(BaseModel):
    performance_score: float
    compliance_score: float
    watermelon_gap: float
    alert_level: str
    recommendation: str


class ChainTestRequest(BaseModel):
    agent_ids: List[str]
    test_input: str


class ChainTestResponse(BaseModel):
    chain_compliance: float
    weakest_agent: str
    chain_breaking_point: Optional[int]


class DashboardMetricsResponse(BaseModel):
    total_agents: int
    healthy: int
    warning: int
    critical: int
    avg_compliance: float
    avg_performance: float
    watermelon_alerts: int
    chain_tests: int
