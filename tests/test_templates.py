"""Unit tests for bct/templates/ (the ready-made contract library)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.contract import BehavioralContract  # noqa: E402
from bct.templates import list_template_ids, load_all_templates, load_template  # noqa: E402

EXPECTED_TEMPLATE_IDS = {
    "socratic_tutor", "customer_support", "medical_assistant", "legal_analyzer", "code_reviewer",
}


class TestListTemplateIds:
    def test_lists_all_five_templates(self):
        assert set(list_template_ids()) == EXPECTED_TEMPLATE_IDS


class TestLoadTemplate:
    def test_returns_a_behavioral_contract(self):
        contract = load_template("socratic_tutor")
        assert isinstance(contract, BehavioralContract)
        assert contract.name == "socratic_tutor"
        assert contract.always
        assert contract.never
        assert contract.under_pressure
        assert 0.0 < contract.threshold <= 1.0

    def test_raises_clear_error_for_unknown_template(self):
        with pytest.raises(ValueError, match="No such template"):
            load_template("not_a_real_template")

    @pytest.mark.parametrize("template_id", sorted(EXPECTED_TEMPLATE_IDS))
    def test_every_template_loads_without_error(self, template_id):
        contract = load_template(template_id)
        assert contract.system
        assert contract.name


class TestLoadAllTemplates:
    def test_returns_all_five_as_contracts(self):
        templates = load_all_templates()
        assert set(templates.keys()) == EXPECTED_TEMPLATE_IDS
        assert all(isinstance(c, BehavioralContract) for c in templates.values())

    def test_medical_and_legal_have_stricter_thresholds_than_default(self):
        templates = load_all_templates()
        # Higher-stakes domains should require a higher compliance bar.
        assert templates["medical_assistant"].threshold >= 0.90
        assert templates["legal_analyzer"].threshold >= 0.90
