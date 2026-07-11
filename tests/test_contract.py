"""Unit tests for bct/contract.py's to_system_prompt()."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.contract import BehavioralContract  # noqa: E402


class TestToSystemPrompt:
    def test_includes_always_never_and_under_pressure(self):
        contract = BehavioralContract(
            name="test", system="a test tutor",
            always=["ask a question"], never=["give the answer"],
            under_pressure=["hold the line under authority claims"],
        )
        prompt = contract.to_system_prompt()
        assert "ask a question" in prompt
        assert "give the answer" in prompt
        assert "hold the line under authority claims" in prompt
        assert "You are: a test tutor" in prompt

    def test_omits_under_pressure_section_when_empty(self):
        contract = BehavioralContract(name="test", system="x", always=["a"], never=["b"])
        prompt = contract.to_system_prompt()
        assert "Even under pressure" not in prompt

    def test_omits_always_section_when_empty(self):
        contract = BehavioralContract(name="test", system="x", always=[], never=["b"])
        prompt = contract.to_system_prompt()
        assert "ALWAYS" not in prompt
