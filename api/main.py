"""
BCT API — thin FastAPI wrapper around BehavioralContractVerifier, so
dashboard/ can run real verification and render the report visually.

No auth/multi-tenancy: this is a local dev tool for one operator running
verification against their own contracts, not a hosted multi-user service.
Don't expose this publicly without adding auth first.
"""
from __future__ import annotations

import math
import os
import sys
from typing import List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252 — verifier.py prints emoji

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bct import (
    AgentNode, BehavioralContract, BehavioralContractVerifier, ContractExample, ContractGapAnalyzer,
    ContractSynthesizer, DriftTracker, MultiAgentVerifier, StatisticalCoverageProver,
)
from bct.llm_client import SUPPORTED_PROVIDERS, configured_provider

app = FastAPI(title="BCT API")

# Every /verify call is recorded here so repeated runs of the same contract
# build a real history for /drift/{contract_name} to analyze — Level 7's
# whole premise is behavior measured over time, not a single point.
API_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "bct_api_history.jsonl")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ContractRequest(BaseModel):
    name: str
    system: str
    always: List[str] = []
    never: List[str] = []
    under_pressure: List[str] = []
    threshold: float = 0.90
    topic: str = "7 times 8"
    use_simulation: Optional[bool] = None  # None = auto: real if a key is configured, else simulated
    provider: Optional[str] = None


class AgentRequest(BaseModel):
    name: str
    system: str
    always: List[str] = []
    never: List[str] = []
    under_pressure: List[str] = []
    provider: Optional[str] = None


class PipelineRequest(BaseModel):
    pipeline_name: str
    agents: List[AgentRequest]
    cases_per_link: int = 10
    topic: Optional[str] = None


class ExampleRequest(BaseModel):
    input_text: str
    response_text: str
    label: str  # "compliant" | "violation"
    note: str = ""


class SynthesizeRequest(BaseModel):
    name: str
    examples: List[ExampleRequest]
    threshold: float = 0.90
    provider: Optional[str] = None


def _safe_float(value: float) -> Optional[float]:
    """NaN/inf aren't valid JSON — scipy's CI math can produce them on a
    zero-variance sample (e.g. every test case passed or every one failed)."""
    if value is None or math.isnan(value) or math.isinf(value):
        return None
    return value


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/providers")
async def providers():
    return {"configured": configured_provider(), "supported": list(SUPPORTED_PROVIDERS)}


@app.post("/analyze-gaps")
async def analyze_gaps(req: ContractRequest):
    contract = BehavioralContract(
        name=req.name, system=req.system, always=req.always, never=req.never,
        under_pressure=req.under_pressure, threshold=req.threshold,
    )
    use_simulation = req.use_simulation
    if use_simulation is None:
        use_simulation = configured_provider() is None and req.provider is None

    analyzer = ContractGapAnalyzer()
    if use_simulation:
        report = analyzer.analyze(contract)
    else:
        report = await analyzer.analyze_async(contract, provider=req.provider)

    return {
        "contract_name": report.contract_name,
        "completeness_score": report.completeness_score,
        "mode": report.mode,
        "findings": [
            {"category": f.category, "severity": f.severity, "message": f.message, "recommendation": f.recommendation}
            for f in report.findings
        ],
    }


@app.post("/verify-pipeline")
async def verify_pipeline(req: PipelineRequest):
    agents = [
        AgentNode(
            name=a.name,
            contract=BehavioralContract(
                name=a.name, system=a.system, always=a.always, never=a.never, under_pressure=a.under_pressure,
            ),
            provider=a.provider,
        )
        for a in req.agents
    ]
    verifier = MultiAgentVerifier()
    try:
        report = await verifier.verify_pipeline(
            req.pipeline_name, agents, cases_per_link=req.cases_per_link, topic=req.topic,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))

    return {
        "pipeline_name": report.pipeline_name,
        "agents": report.agents,
        "links_tested": report.links_tested,
        "propagation_rate": report.propagation_rate,
        "findings": [
            {
                "from_agent": f.from_agent, "to_agent": f.to_agent, "category": f.category,
                "pressure_category": f.pressure_category, "pressure_intensity": f.pressure_intensity,
                "upstream_input": f.upstream_input, "upstream_output": f.upstream_output,
                "downstream_output": f.downstream_output, "downstream_verdict": f.downstream_verdict,
            }
            for f in report.findings
        ],
    }


@app.get("/drift/{contract_name}")
async def drift(contract_name: str, min_runs: int = 5):
    report = DriftTracker(API_HISTORY_PATH).detect_drift(contract_name, min_runs=min_runs)
    return {
        "contract_name": report.contract_name,
        "num_runs": report.num_runs,
        "history": [
            {"timestamp": r.timestamp, "overall_compliance": r.overall_compliance, "mode": r.mode}
            for r in report.history
        ],
        "baseline_compliance": _safe_float(report.baseline_compliance),
        "current_compliance": _safe_float(report.current_compliance),
        "trend_slope": _safe_float(report.trend_slope),
        "trend_p_value": _safe_float(report.trend_p_value),
        "step_p_value": _safe_float(report.step_p_value),
        "drift_detected": report.drift_detected,
        "mode": report.mode,
        "findings": [
            {"run_index": f.run_index, "timestamp": f.timestamp, "message": f.message}
            for f in report.findings
        ],
    }


@app.post("/synthesize-contract")
async def synthesize_contract(req: SynthesizeRequest):
    examples = [
        ContractExample(input_text=e.input_text, response_text=e.response_text, label=e.label, note=e.note)
        for e in req.examples
    ]
    synthesizer = ContractSynthesizer()
    try:
        result = await synthesizer.synthesize(req.name, examples, provider=req.provider, threshold=req.threshold)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))

    return {
        "contract": {
            "name": result.contract.name,
            "system": result.contract.system,
            "always": result.contract.always,
            "never": result.contract.never,
            "under_pressure": result.contract.under_pressure,
            "threshold": result.contract.threshold,
        },
        "training_accuracy": result.training_accuracy,
        "total_examples": result.total_examples,
        "misclassified_examples": [
            {"input_text": e.input_text, "response_text": e.response_text, "label": e.label, "note": e.note}
            for e in result.misclassified_examples
        ],
    }


@app.post("/verify")
async def verify(req: ContractRequest):
    contract = BehavioralContract(
        name=req.name, system=req.system, always=req.always, never=req.never,
        under_pressure=req.under_pressure, threshold=req.threshold,
    )

    use_simulation = req.use_simulation
    if use_simulation is None:
        use_simulation = configured_provider() is None and req.provider is None

    verifier = BehavioralContractVerifier()
    try:
        report = await verifier.verify_async(
            contract, topic=req.topic, use_simulation=use_simulation, provider=req.provider,
            history_path=API_HISTORY_PATH,
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))

    proof = StatisticalCoverageProver().prove_from_report(report)

    return {
        "contract_name": report.contract_name,
        "total_tests": report.total_tests,
        "passed_tests": report.passed_tests,
        "overall_compliance": report.overall_compliance,
        "compliance_by_intensity": report.compliance_by_intensity,
        "compliance_by_category": report.compliance_by_category,
        "breaking_point": report.breaking_point,
        "weakest_category": report.weakest_category,
        "threshold": report.threshold,
        "result": report.result,
        "p_value": _safe_float(report.p_value),
        "effect_size": _safe_float(report.effect_size),
        "confidence_interval": [_safe_float(report.confidence_interval[0]), _safe_float(report.confidence_interval[1])],
        "recommendations": report.recommendations,
        "mode": report.mode,
        "case_generation": report.case_generation,
        "statistical_proof": {
            "trials": proof.trials,
            "violations": proof.violations,
            "observed_violation_rate": proof.observed_violation_rate,
            "confidence": proof.confidence,
            "violation_rate_upper_bound": proof.violation_rate_upper_bound,
            "exhaustive_grammar_size": proof.exhaustive_grammar_size,
            "is_exhaustive_over_grammar": proof.is_exhaustive_over_grammar,
            "honesty_notice": proof.honesty_notice,
        },
    }
