"""
Unit tests for api/main.py — uses FastAPI's TestClient so these run
against the real app (real routing, real Pydantic validation, real
verifier), forcing use_simulation=True to avoid needing an LLM API key.
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


class TestHealthAndProviders:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_providers_lists_supported(self):
        resp = client.get("/providers")
        assert resp.status_code == 200
        assert set(resp.json()["supported"]) == {"groq", "anthropic"}


class TestAnalyzeGaps:
    def test_forced_simulation_returns_heuristic_report(self):
        resp = client.post("/analyze-gaps", json={
            "name": "test_contract", "system": "a test tutor",
            "always": ["ask a question"], "never": ["give the answer"],
            "use_simulation": True,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "heuristic"
        assert 0.0 <= body["completeness_score"] <= 1.0
        assert isinstance(body["findings"], list)

    def test_without_key_falls_back_instead_of_erroring(self):
        # Unlike /verify, gap analysis never hard-fails — analyze_async
        # catches a failed LLM call and reports heuristic findings only.
        with patch.dict(os.environ, {}, clear=True):
            resp = client.post("/analyze-gaps", json={
                "name": "test_contract", "system": "a test tutor",
                "always": ["ask a question"], "never": ["give the answer"],
                "use_simulation": False,
            })
        assert resp.status_code == 200
        assert resp.json()["mode"] == "llm_augmentation_failed"

    def test_flags_empty_contract(self):
        resp = client.post("/analyze-gaps", json={
            "name": "empty", "system": "a bot", "use_simulation": True,
        })
        assert resp.status_code == 200
        categories = {f["category"] for f in resp.json()["findings"]}
        assert "empty_contract" in categories


class TestVerify:
    def test_verify_forced_simulation_returns_full_report(self):
        resp = client.post("/verify", json={
            "name": "test_contract", "system": "a test tutor",
            "always": ["ask a question"], "never": ["give the answer"],
            "threshold": 0.90, "topic": "7 times 8", "use_simulation": True,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "simulated"
        assert body["case_generation"] == "template"
        assert body["total_tests"] == 30
        assert 0.0 <= body["overall_compliance"] <= 1.0
        assert "compliance_by_intensity" in body
        assert "recommendations" in body

    def test_verify_without_key_and_without_simulation_returns_400(self):
        resp = client.post("/verify", json={
            "name": "test_contract", "system": "a test tutor",
            "always": ["ask a question"], "never": ["give the answer"],
            "use_simulation": False,
        })
        assert resp.status_code == 400
        assert "No LLM API key configured" in resp.json()["detail"]

    def test_verify_response_is_valid_json_even_with_degenerate_ci(self):
        # All-pass contract (empty never/always) still must not emit NaN in JSON
        resp = client.post("/verify", json={
            "name": "trivial", "system": "x", "always": [], "never": [],
            "threshold": 0.0, "use_simulation": True,
        })
        assert resp.status_code == 200
        # If this parsed at all without raising, the response was valid JSON —
        # Python's json module would happily emit a literal NaN token that
        # requests-under-test would still parse, so also assert the field
        # is either a float or None, never a NaN float (which fails equality).
        ci = resp.json()["confidence_interval"]
        for bound in ci:
            assert bound is None or bound == bound  # NaN != NaN
