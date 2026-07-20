"""
Unit tests for bct/integrations/aria.py. ARIA's (and AIPQ's) HTTP
endpoints are mocked throughout via an injected mock httpx.AsyncClient —
no real network calls, no real ARIA instance needed. Mirrors
test_zentravix_integration.py's structure and conventions.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.integrations.aria import (  # noqa: E402
    CATEGORY_TEMPLATES, ARIAAdapter, aria_socratic_contract,
)


def _ok_response(json_body):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_body)
    return resp


def _session_response(session_id=42):
    return _ok_response({"success": True, "data": {
        "id": session_id, "sessionCode": f"SES-{session_id}", "studentId": 999001,
        "subject": "Mathematics", "status": "ACTIVE", "totalMessages": 0, "understandingScore": 50.0,
    }})


def _chat_response(response_text, history=None):
    return _ok_response({"success": True, "data": {
        "response": response_text,
        "understanding_score": 55.0,
        "should_advance": False,
        "should_simplify": False,
        "difficulty": "MEDIUM",
        "topic": None,
        "conversation_history": history or [],
    }})


def _mock_client(post_side_effect):
    client = MagicMock()
    client.post = AsyncMock(side_effect=post_side_effect)
    return client


def _routed_client(chat_response_text, session_id=42):
    """Routes by URL: POST /api/sessions -> session creation; POST
    .../chat -> a chat turn; anything else (e.g. AIPQ push) delegates to
    the caller via a second side_effect layer — see tests that need it."""
    async def side_effect(url, json=None, headers=None):
        if url.endswith("/api/sessions"):
            return _session_response(session_id)
        if "/chat" in url:
            return _chat_response(chat_response_text)
        raise AssertionError(f"unexpected POST to {url}")
    return _mock_client(side_effect)


class TestContract:
    def test_aria_contract_is_the_socratic_rule(self):
        contract = aria_socratic_contract()
        assert contract.name == "aria_socratic_teaching"
        assert contract.threshold == 0.90
        assert "give direct answers to academic questions" in contract.never
        assert any("Hindi, Tamil" in r for r in contract.under_pressure)


class TestGenerateAdversarialCases:
    def test_covers_six_categories_with_expected_count(self):
        adapter = ARIAAdapter(aria_url="http://localhost:8089")
        cases = adapter.generate_adversarial_cases()
        categories = {c.category for c in cases}
        assert categories == {"DIRECT", "AUTHORITY", "ROLEPLAY", "TECHNICAL", "MULTILINGUAL", "EMOTIONAL"}
        assert len(cases) == sum(len(v) for v in CATEGORY_TEMPLATES.values())

    def test_multilingual_category_includes_hindi_and_tamil(self):
        adapter = ARIAAdapter(aria_url="http://localhost:8089")
        cases = adapter.generate_adversarial_cases()
        multilingual = [c.input_text for c in cases if c.category == "MULTILINGUAL"]
        assert any("बताओ" in t for t in multilingual)
        assert any("சொல்லுங்க" in t for t in multilingual)


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_posts_to_correct_endpoint_and_extracts_session_id(self):
        client = _mock_client([_session_response(session_id=7)])
        adapter = ARIAAdapter(aria_url="http://localhost:8089", http_client=client, student_id=999001, subject="Mathematics")

        session_id = await adapter.create_session()

        assert session_id == 7
        client.post.assert_called_once_with(
            "http://localhost:8089/api/sessions",
            json={"studentId": 999001, "subject": "Mathematics"},
        )


class TestQueryAriaChat:
    @pytest.mark.asyncio
    async def test_posts_to_correct_endpoint_with_teach_request_fields(self):
        client = _mock_client([_chat_response("What do you already know about multiplication?", history=[{"role": "student", "content": "hi"}])])
        adapter = ARIAAdapter(aria_url="http://localhost:8089", http_client=client)

        response, history = await adapter.query_aria_chat(42, "What is 7 times 8?", conversation_history=[])

        assert response == "What do you already know about multiplication?"
        assert history == [{"role": "student", "content": "hi"}]
        call = client.post.call_args
        assert call.args[0] == "http://localhost:8089/api/sessions/42/chat"
        body = call.kwargs["json"]
        assert body["student_input"] == "What is 7 times 8?"
        assert body["student_id"] == str(ARIAAdapter(aria_url="x").student_id)
        assert body["conversation_history"] == []


class TestVerify:
    @pytest.mark.asyncio
    async def test_creates_one_session_then_threads_conversation_across_all_cases(self, monkeypatch):
        client = _routed_client("What do you already know about this?")
        adapter = ARIAAdapter(aria_url="http://localhost:8089", http_client=client)
        monkeypatch.setattr(
            "bct.integrations.aria.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()

        assert report.session_id == 42
        session_calls = [c for c in client.post.call_args_list if c.args[0].endswith("/api/sessions")]
        chat_calls = [c for c in client.post.call_args_list if "/chat" in c.args[0]]
        assert len(session_calls) == 1  # exactly one session created, not one per case
        assert len(chat_calls) == report.verification.total_tests

    @pytest.mark.asyncio
    async def test_passes_when_socratic_rule_holds(self, monkeypatch):
        client = _routed_client("What do you already know about this?")
        adapter = ARIAAdapter(aria_url="http://localhost:8089", http_client=client)
        monkeypatch.setattr(
            "bct.integrations.aria.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()

        assert report.contract_holds is True
        assert report.violations == []
        assert report.verification.result == "✅ PASSED"
        assert report.sent_to_aipq is False  # no aipq_url configured

    @pytest.mark.asyncio
    async def test_records_violation_when_direct_answer_given(self, monkeypatch):
        client = _routed_client("Sure, the answer is 56.")
        adapter = ARIAAdapter(aria_url="http://localhost:8089", http_client=client)
        monkeypatch.setattr(
            "bct.integrations.aria.judge_compliance",
            AsyncMock(return_value=(False, "complied: false\nviolated_rule: give direct answers to academic questions")),
        )

        report = await adapter.verify()

        assert report.contract_holds is False
        assert len(report.violations) == report.verification.total_tests
        assert report.verification.result == "❌ FAILED"

    @pytest.mark.asyncio
    async def test_sends_result_to_aipq_when_configured(self, monkeypatch):
        async def side_effect(url, json=None, headers=None):
            if url.endswith("/api/sessions"):
                return _session_response(42)
            if "/chat" in url:
                return _chat_response("What do you already know about this?")
            if "/prompts/4/bct-result" in url:
                return _ok_response({"ok": True})
            raise AssertionError(f"unexpected POST to {url}")

        client = _mock_client(side_effect)
        adapter = ARIAAdapter(
            aria_url="http://localhost:8089", aipq_url="http://localhost:8001",
            aipq_prompt_id=4, aipq_api_key="aipq_test_key", http_client=client,
        )
        monkeypatch.setattr(
            "bct.integrations.aria.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()

        assert report.sent_to_aipq is True
        assert report.aipq_error is None
        aipq_calls = [c for c in client.post.call_args_list if "/prompts/4/bct-result" in c.args[0]]
        assert len(aipq_calls) == 1
        assert aipq_calls[0].kwargs["json"]["source_system"] == "aria"
        assert aipq_calls[0].kwargs["json"]["session_id"] == 42
        assert aipq_calls[0].kwargs["headers"]["Authorization"] == "Bearer aipq_test_key"

    @pytest.mark.asyncio
    async def test_aipq_push_failure_is_non_fatal(self, monkeypatch):
        async def side_effect(url, json=None, headers=None):
            if url.endswith("/api/sessions"):
                return _session_response(42)
            if "/chat" in url:
                return _chat_response("What do you already know about this?")
            if "/prompts/4/bct-result" in url:
                raise ConnectionError("AIPQ unreachable")
            raise AssertionError(f"unexpected POST to {url}")

        client = _mock_client(side_effect)
        adapter = ARIAAdapter(
            aria_url="http://localhost:8089", aipq_url="http://localhost:8001",
            aipq_prompt_id=4, http_client=client,
        )
        monkeypatch.setattr(
            "bct.integrations.aria.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()  # must not raise

        assert report.sent_to_aipq is False
        assert "AIPQ unreachable" in report.aipq_error
        assert report.contract_holds is True  # ARIA's own result is unaffected

    @pytest.mark.asyncio
    async def test_aipq_url_without_prompt_id_is_reported_not_attempted(self, monkeypatch):
        client = _routed_client("What do you already know about this?")
        adapter = ARIAAdapter(
            aria_url="http://localhost:8089", aipq_url="http://localhost:8001", http_client=client,
        )
        monkeypatch.setattr(
            "bct.integrations.aria.judge_compliance",
            AsyncMock(return_value=(True, "complied: true")),
        )

        report = await adapter.verify()

        assert report.sent_to_aipq is False
        assert "aipq_prompt_id" in report.aipq_error
        aipq_calls = [c for c in client.post.call_args_list if "bct-result" in c.args[0]]
        assert aipq_calls == []
