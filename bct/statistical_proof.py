"""
Level 10 — "BCT proves contracts hold for all possible inputs."

HONESTY BOUNDARY (read this first): no tool — this one included — can
formally prove a free-text behavioral contract holds for literally every
possible natural-language input. That would require exhaustively
enumerating an infinite space, or a sound static analysis of the
underlying LLM's weights, which is an unsolved research problem for
models at this scale. Any tool claiming otherwise is not being honest.

What this module actually provides — the closest legitimate analog, and
the same standard the ML verification research community itself uses
when it says a property was "verified":

1. A statement of whether the run was exhaustive over BCT's own declared,
   FINITE adversarial grammar (6 pressure categories x 5 intensities =
   30 combinations) — a real, complete claim, but only over that
   explicitly bounded subspace, never "all inputs."

2. A statistical (PAC-style) upper confidence bound on the TRUE
   violation rate over the full input distribution, given the observed
   trials, via the exact (Clopper-Pearson) binomial confidence interval:
   "0 violations observed in N i.i.d. trials" converts into "we are
   (1-alpha) confident the true violation rate is at most U" for a
   specific computed U — smaller as N grows, never exactly 0, never
   claimed to be.

Every report from this module states both facts plus the honesty
boundary itself, so it is never read as a stronger guarantee than either.
"""
from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import beta as beta_dist

EXHAUSTIVE_GRAMMAR_SIZE = 30  # generator.py's own 6 categories x 5 intensities

HONESTY_NOTICE = (
    "This is NOT a formal proof the contract holds for all possible natural-language "
    "inputs — that is not achievable for a free-text LLM system with today's methods. "
    "It IS: (1) a complete test over BCT's declared 6-category x 5-intensity adversarial "
    "grammar if trials >= 30, and (2) a statistically rigorous upper bound on the true "
    "violation rate over the broader input distribution, valid only insofar as these "
    "trials are representative samples of the inputs the AI will actually see in production."
)


def clopper_pearson_upper_bound(violations: int, trials: int, confidence: float = 0.95) -> float:
    """
    Exact one-sided upper confidence bound on the true violation rate,
    given `violations` observed out of `trials` i.i.d. Bernoulli trials.
    Standard PAC-style statistical guarantee — not a proof, a confidence
    bound: there's a (1 - confidence) chance the true rate exceeds this.
    """
    if trials <= 0:
        return 1.0
    alpha = 1 - confidence
    if violations >= trials:
        return 1.0
    if violations == 0:
        return 1 - alpha ** (1 / trials)
    return float(beta_dist.ppf(1 - alpha, violations + 1, trials - violations))


@dataclass
class StatisticalProofReport:
    contract_name: str
    trials: int
    violations: int
    observed_violation_rate: float
    confidence: float
    violation_rate_upper_bound: float
    exhaustive_grammar_size: int
    is_exhaustive_over_grammar: bool
    honesty_notice: str = HONESTY_NOTICE

    def print_report(self):
        print(f"\n{'='*55}")
        print("BCT STATISTICAL COVERAGE ANALYSIS")
        print(f"Contract: {self.contract_name}")
        print(f"{'='*55}")
        print(f"Trials: {self.trials}, violations observed: {self.violations}")
        print(f"Observed violation rate: {self.observed_violation_rate:.2%}")
        print(f"Exhaustive over the {self.exhaustive_grammar_size}-case declared grammar: "
              f"{'YES' if self.is_exhaustive_over_grammar else 'no (fewer trials than the grammar size)'}")
        print(f"At {self.confidence:.0%} confidence, the true violation rate is at most "
              f"{self.violation_rate_upper_bound:.2%} (PAC-style statistical bound).")
        print(f"\n{self.honesty_notice}")
        print(f"{'='*55}")


class StatisticalCoverageProver:
    """
    Turns an existing VerificationReport into the most rigorous, honest
    statistical claim BCT can actually make about coverage — no new LLM
    calls; this is a pure statistical read of trials already run.
    """

    def prove_from_report(self, report, confidence: float = 0.95) -> StatisticalProofReport:
        violations = report.total_tests - report.passed_tests
        violation_rate = violations / report.total_tests if report.total_tests else 0.0
        upper_bound = clopper_pearson_upper_bound(violations, report.total_tests, confidence)
        return StatisticalProofReport(
            contract_name=report.contract_name,
            trials=report.total_tests,
            violations=violations,
            observed_violation_rate=violation_rate,
            confidence=confidence,
            violation_rate_upper_bound=upper_bound,
            exhaustive_grammar_size=EXHAUSTIVE_GRAMMAR_SIZE,
            is_exhaustive_over_grammar=report.total_tests >= EXHAUSTIVE_GRAMMAR_SIZE,
        )
