"""
Unit tests for bct/statistical_proof.py (Level 10 — honest statistical
coverage claims, explicitly NOT a claim of exhaustive formal proof).
"""
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.statistical_proof import (  # noqa: E402
    EXHAUSTIVE_GRAMMAR_SIZE, StatisticalCoverageProver, clopper_pearson_upper_bound,
)


@dataclass
class _FakeReport:
    contract_name: str
    total_tests: int
    passed_tests: int


class TestClopperPearsonUpperBound:
    def test_zero_trials_returns_full_uncertainty(self):
        assert clopper_pearson_upper_bound(0, 0) == 1.0

    def test_all_trials_violated_returns_full_uncertainty(self):
        assert clopper_pearson_upper_bound(10, 10) == 1.0

    def test_zero_violations_in_30_trials_matches_known_formula(self):
        # Exact formula for k=0: upper = 1 - alpha^(1/n)
        bound = clopper_pearson_upper_bound(0, 30, confidence=0.95)
        expected = 1 - 0.05 ** (1 / 30)
        assert abs(bound - expected) < 1e-9

    def test_more_trials_with_zero_violations_tightens_the_bound(self):
        bound_30 = clopper_pearson_upper_bound(0, 30, confidence=0.95)
        bound_300 = clopper_pearson_upper_bound(0, 300, confidence=0.95)
        assert bound_300 < bound_30

    def test_higher_confidence_widens_the_bound(self):
        bound_95 = clopper_pearson_upper_bound(0, 30, confidence=0.95)
        bound_99 = clopper_pearson_upper_bound(0, 30, confidence=0.99)
        assert bound_99 > bound_95

    def test_some_violations_gives_a_looser_bound_than_zero_violations(self):
        bound_zero = clopper_pearson_upper_bound(0, 30, confidence=0.95)
        bound_some = clopper_pearson_upper_bound(3, 30, confidence=0.95)
        assert bound_some > bound_zero

    def test_bound_always_at_least_the_observed_rate(self):
        bound = clopper_pearson_upper_bound(5, 30, confidence=0.95)
        assert bound >= 5 / 30


class TestStatisticalCoverageProver:
    def test_perfect_run_of_30_is_exhaustive_over_grammar(self):
        report = _FakeReport(contract_name="tutor", total_tests=30, passed_tests=30)
        proof = StatisticalCoverageProver().prove_from_report(report)
        assert proof.is_exhaustive_over_grammar is True
        assert proof.violations == 0
        assert proof.observed_violation_rate == 0.0
        assert 0.0 < proof.violation_rate_upper_bound < 1.0

    def test_fewer_than_grammar_size_trials_is_not_exhaustive(self):
        report = _FakeReport(contract_name="tutor", total_tests=10, passed_tests=10)
        proof = StatisticalCoverageProver().prove_from_report(report)
        assert proof.is_exhaustive_over_grammar is False
        assert proof.exhaustive_grammar_size == EXHAUSTIVE_GRAMMAR_SIZE

    def test_reports_observed_violations_accurately(self):
        report = _FakeReport(contract_name="tutor", total_tests=30, passed_tests=27)
        proof = StatisticalCoverageProver().prove_from_report(report)
        assert proof.violations == 3
        assert abs(proof.observed_violation_rate - 0.1) < 1e-9

    def test_honesty_notice_disclaims_formal_proof_over_all_inputs(self):
        report = _FakeReport(contract_name="tutor", total_tests=30, passed_tests=30)
        proof = StatisticalCoverageProver().prove_from_report(report)
        assert "NOT" in proof.honesty_notice
        assert "all possible natural-language" in proof.honesty_notice

    def test_zero_total_tests_does_not_crash(self):
        report = _FakeReport(contract_name="empty", total_tests=0, passed_tests=0)
        proof = StatisticalCoverageProver().prove_from_report(report)
        assert proof.observed_violation_rate == 0.0
        assert proof.violation_rate_upper_bound == 1.0
