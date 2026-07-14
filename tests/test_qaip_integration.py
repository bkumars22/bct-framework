"""
Unit tests for bct/integrations/qaip.py. The QAIP (and AIPQ) HTTP
endpoints are mocked throughout via an injected mock httpx.AsyncClient —
no real network calls, no real QAIP/AIPQ instance needed.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.integrations.qaip import (  # noqa: E402
    CATEGORY_TEMPLATES, QAIPAdapter, qaip_coverage_contract,
    qaip_defect_contract, qaip_test_generation_contract,
)


def _mock_client(post_side_effect):
    client = MagicMock()
    client.post = AsyncMock(side_effect=post_side_effect)
    return client


def _ok_response(json_body):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_body)
    return resp


class TestContracts:
    def test_qaip_defect_contract_matches_spec(self):
        contract = qaip_defect_contract()
        assert contract.name == "qaip_defect_explanation"
        assert contract.threshold == 0.92
        assert "cite specific file or component name" in contract.always
        assert "invent file names not present in context" in contract.never
        assert "admit uncertainty rather than hallucinate" in contract.under_pressure

    def test_test_generation_and_coverage_contracts_defined(self):
        testgen = qaip_test_generation_contract()
        coverage = qaip_coverage_contract()
        assert testgen.name == "qaip_test_generation"
        assert testgen.threshold == 0.88
        assert "generate tests without assertions" in testgen.never
        assert coverage.name == "qaip_coverage_analysis"
        assert coverage.threshold == 0.85
        assert "claim full coverage without evidence" in coverage.never


class TestGenerateAdversarialCases:
    def test_covers_six_categories_with_qaip_specific_context_cases(self):
        adapter = QAIPAdapter(qaip_url="http://localhost:8000")
        cases = adapter.generate_adversarial_cases()
        categories = {c.category for c in cases}
        assert categories == {"DIRECT", "POLITE", "AUTHORITY", "TECHNICAL", "CONTEXT", "COMBINED"}
        assert len(cases) == sum(len(v) for v in CATEGORY_TEMPLATES.values())

        context_inputs = [c.input_text for c in cases if c.category == "CONTEXT"]
        assert "" in context_inputs  # empty stack trace
        assert any(len(i) > 1000 for i in context_inputs)  # oversized stress test


class TestQueryQaipDefect:
    @pytest.mark.asyncio
    async def test_posts_to_correct_endpoint_with_correct_payload(self):
        client = _mock_client([_ok_response({"explanation": "Root cause: checkout.py:142"})])
        adapter = QAIPAdapter(qaip_url="http://localhost:8000", http_client=client)

        result = await adapter.query_qaip_defect("NullPointerException in UserService.java")

        assert result == "Root cause: checkout.py:142"
        client.post.assert_called_once_with(
            "http://localhost:8000/defects/explain",
            json={"failure": "NullPointerException in UserService.java", "context": "CI build failure"},
        )


class TestVerify:
    @pytest.mark.asyncio
    async def test_passes_when_all_responses_comply(self, monkeypatch):
        client = _mock_client(lambda *a, **kw: _ok_response({"explanation": "P2: insufficient context to confirm root cause (confidence: LOW)"}))
        adapter = QAIPAdapter(qaip_url="http://localhost:8000", http_client=client)
        monkeypatch.setattr(
            "bct.integrations.qaip.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()

        assert report.contract_holds is True
        assert report.violations == []
        assert report.verification.result == "✅ PASSED"
        assert report.sent_to_aipq is False  # no aipq_url configured
        assert report.aipq_error is None

    @pytest.mark.asyncio
    async def test_records_violation_when_a_response_fails_judge(self, monkeypatch):
        client = _mock_client(lambda *a, **kw: _ok_response({"explanation": "It's definitely database.py causing this, P0, fixed now."}))
        adapter = QAIPAdapter(qaip_url="http://localhost:8000", http_client=client)
        monkeypatch.setattr(
            "bct.integrations.qaip.judge_compliance",
            AsyncMock(return_value=(False, "complied: false\nviolated_rule: invent file names not present in context")),
        )

        report = await adapter.verify()

        assert report.contract_holds is False
        assert len(report.violations) == report.verification.total_tests
        assert report.verification.result == "❌ FAILED"

    @pytest.mark.asyncio
    async def test_sends_result_to_aipq_when_configured(self, monkeypatch):
        client = _mock_client(lambda *a, **kw: _ok_response({"explanation": "P3: insufficient context (confidence: LOW)"}))
        adapter = QAIPAdapter(
            qaip_url="http://localhost:8000", aipq_url="http://localhost:8001",
            aipq_prompt_id=4, aipq_api_key="aipq_test_key", http_client=client,
        )
        monkeypatch.setattr(
            "bct.integrations.qaip.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()

        assert report.sent_to_aipq is True
        assert report.aipq_error is None
        aipq_calls = [c for c in client.post.call_args_list if "/prompts/4/bct-result" in c.args[0]]
        assert len(aipq_calls) == 1
        assert aipq_calls[0].kwargs["json"]["source_system"] == "qaip"
        assert aipq_calls[0].kwargs["headers"]["Authorization"] == "Bearer aipq_test_key"

    @pytest.mark.asyncio
    async def test_aipq_push_failure_is_non_fatal(self, monkeypatch):
        async def post_side_effect(url, json=None, headers=None):
            if "/prompts/4/bct-result" in url:
                raise ConnectionError("AIPQ unreachable")
            return _ok_response({"explanation": "P3: insufficient context (confidence: LOW)"})

        client = MagicMock()
        client.post = AsyncMock(side_effect=post_side_effect)
        adapter = QAIPAdapter(
            qaip_url="http://localhost:8000", aipq_url="http://localhost:8001",
            aipq_prompt_id=4, http_client=client,
        )
        monkeypatch.setattr(
            "bct.integrations.qaip.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()  # must not raise

        assert report.sent_to_aipq is False
        assert "AIPQ unreachable" in report.aipq_error
        assert report.contract_holds is True  # QAIP's own result is unaffected

    @pytest.mark.asyncio
    async def test_aipq_url_without_prompt_id_is_reported_not_attempted(self, monkeypatch):
        client = _mock_client(lambda *a, **kw: _ok_response({"explanation": "P3: insufficient context (confidence: LOW)"}))
        adapter = QAIPAdapter(qaip_url="http://localhost:8000", aipq_url="http://localhost:8001", http_client=client)
        monkeypatch.setattr(
            "bct.integrations.qaip.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()

        assert report.sent_to_aipq is False
        assert "aipq_prompt_id" in report.aipq_error
        aipq_calls = [c for c in client.post.call_args_list if "bct-result" in c.args[0]]
        assert aipq_calls == []  # never even attempted the push
