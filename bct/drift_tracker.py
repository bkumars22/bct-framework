"""
Level 7 — "BCT measures behavioral drift over time, not just at a point."

A single verification run is a snapshot: it proves a contract held (or
didn't) against one set of adversarial cases at one moment. It says
nothing about whether the same AI, unchanged, quietly drifts toward
non-compliance over weeks (a model update upstream, a prompt template
edit elsewhere in the stack, seasonal user behavior). DriftTracker
records each run to a durable local history file and tests that history
for a statistically significant decline — the basis for a long-term
reliability claim (the kind an insurer or a compliance reviewer wants),
not just a one-off pass/fail.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from scipy import stats

DEFAULT_HISTORY_PATH = "bct_history.jsonl"


@dataclass
class HistoricalRun:
    timestamp: str
    contract_name: str
    overall_compliance: float
    total_tests: int
    passed_tests: int
    mode: str


@dataclass
class DriftFinding:
    run_index: int
    timestamp: str
    message: str


@dataclass
class DriftReport:
    contract_name: str
    num_runs: int
    history: List[HistoricalRun]
    baseline_compliance: Optional[float]
    current_compliance: Optional[float]
    trend_slope: Optional[float]
    trend_p_value: Optional[float]
    step_p_value: Optional[float]
    drift_detected: bool
    findings: List[DriftFinding]
    mode: str  # "insufficient_data" | "stable" | "drift_detected"

    def print_report(self):
        print(f"\n{'='*55}")
        print(f"BCT DRIFT ANALYSIS [{self.mode.upper()}]")
        print(f"Contract: {self.contract_name}")
        print(f"Runs recorded: {self.num_runs}")
        print(f"{'='*55}")
        if self.mode == "insufficient_data":
            print(f"Need more recorded runs before drift analysis is meaningful.")
        else:
            print(f"Baseline compliance (prior runs): {self.baseline_compliance:.1%}")
            print(f"Current compliance (latest run):  {self.current_compliance:.1%}")
            print(f"Trend: slope={self.trend_slope:+.4f}/run, p={self.trend_p_value:.4f}")
            print(f"Step change vs baseline: p={self.step_p_value:.4f}")
            print(f"Drift detected: {'YES' if self.drift_detected else 'no'}")
        for f in self.findings:
            print(f"  - [{f.timestamp}] {f.message}")
        print(f"{'='*55}")


def _two_proportion_z_test(passed_a: int, total_a: int, passed_b: int, total_b: int):
    """Two-proportion z-test — is run B's pass rate significantly different from A's?"""
    if total_a == 0 or total_b == 0:
        return 0.0, 1.0
    p_a, p_b = passed_a / total_a, passed_b / total_b
    p_pool = (passed_a + passed_b) / (total_a + total_b)
    se = (p_pool * (1 - p_pool) * (1 / total_a + 1 / total_b)) ** 0.5
    if se == 0:
        return 0.0, 1.0
    z = (p_b - p_a) / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    return z, p_value


class DriftTracker:
    """Records verification runs to a local JSONL file and tests the
    resulting history for statistically significant behavioral drift."""

    def __init__(self, history_path: str = DEFAULT_HISTORY_PATH):
        self.history_path = history_path

    def record(
        self,
        contract_name: str,
        overall_compliance: float,
        total_tests: int,
        passed_tests: int,
        mode: str,
        timestamp: Optional[str] = None,
    ) -> HistoricalRun:
        run = HistoricalRun(
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            contract_name=contract_name,
            overall_compliance=overall_compliance,
            total_tests=total_tests,
            passed_tests=passed_tests,
            mode=mode,
        )
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(run)) + "\n")
        return run

    def history(self, contract_name: str) -> List[HistoricalRun]:
        if not os.path.exists(self.history_path):
            return []
        runs = []
        with open(self.history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("contract_name") == contract_name:
                    runs.append(HistoricalRun(**data))
        return sorted(runs, key=lambda r: r.timestamp)

    def detect_drift(self, contract_name: str, min_runs: int = 5) -> DriftReport:
        runs = self.history(contract_name)
        if len(runs) < min_runs:
            return DriftReport(
                contract_name=contract_name, num_runs=len(runs), history=runs,
                baseline_compliance=None, current_compliance=None,
                trend_slope=None, trend_p_value=None, step_p_value=None,
                drift_detected=False, findings=[], mode="insufficient_data",
            )

        latest = runs[-1]
        prior = runs[:-1]
        baseline_passed = sum(r.passed_tests for r in prior)
        baseline_total = sum(r.total_tests for r in prior)
        baseline_compliance = baseline_passed / baseline_total if baseline_total else 0.0

        _, step_p_value = _two_proportion_z_test(
            baseline_passed, baseline_total, latest.passed_tests, latest.total_tests,
        )

        x = list(range(len(runs)))
        y = [r.overall_compliance for r in runs]
        trend = stats.linregress(x, y)

        step_drift = step_p_value < 0.05 and latest.overall_compliance < baseline_compliance
        trend_drift = trend.pvalue < 0.05 and trend.slope < 0
        drift_detected = step_drift or trend_drift

        findings: List[DriftFinding] = []
        if step_drift:
            findings.append(DriftFinding(
                run_index=len(runs) - 1, timestamp=latest.timestamp,
                message=(
                    f"Latest run's compliance ({latest.overall_compliance:.1%}) is "
                    f"significantly below the {len(prior)}-run baseline "
                    f"({baseline_compliance:.1%}), p={step_p_value:.4f}."
                ),
            ))
        if trend_drift:
            findings.append(DriftFinding(
                run_index=len(runs) - 1, timestamp=latest.timestamp,
                message=(
                    f"Compliance shows a statistically significant declining trend "
                    f"across {len(runs)} runs (slope={trend.slope:+.4f}/run, p={trend.pvalue:.4f})."
                ),
            ))

        return DriftReport(
            contract_name=contract_name, num_runs=len(runs), history=runs,
            baseline_compliance=float(baseline_compliance), current_compliance=float(latest.overall_compliance),
            trend_slope=float(trend.slope), trend_p_value=float(trend.pvalue), step_p_value=float(step_p_value),
            # numpy bool_/float64 from scipy comparisons aren't JSON-serializable —
            # cast to native Python types since this report crosses into the API layer.
            drift_detected=bool(drift_detected), findings=findings,
            mode="drift_detected" if drift_detected else "stable",
        )
