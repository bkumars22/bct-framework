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

from bct import BehavioralContract, BehavioralContractVerifier
from bct.llm_client import SUPPORTED_PROVIDERS, configured_provider

app = FastAPI(title="BCT API")

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
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))

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
    }
