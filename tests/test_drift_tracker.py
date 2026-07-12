"""Unit tests for bct/drift_tracker.py (Level 7 — behavioral drift over time)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bct.drift_tracker import DriftTracker  # noqa: E402


@pytest.fixture()
def history_path(tmp_path):
    return str(tmp_path / "history.jsonl")


class TestRecordAndHistory:
    def test_record_then_history_round_trips(self, history_path):
        tracker = DriftTracker(history_path)
        tracker.record("aria", overall_compliance=0.95, total_tests=30, passed_tests=28, mode="real")
        runs = tracker.history("aria")
        assert len(runs) == 1
        assert runs[0].overall_compliance == 0.95
        assert runs[0].contract_name == "aria"

    def test_history_returns_empty_list_when_file_missing(self, history_path):
        tracker = DriftTracker(history_path)
        assert tracker.history("aria") == []

    def test_history_filters_by_contract_name(self, history_path):
        tracker = DriftTracker(history_path)
        tracker.record("aria", 0.9, 30, 27, "real")
        tracker.record("other_bot", 0.5, 30, 15, "real")
        assert len(tracker.history("aria")) == 1
        assert len(tracker.history("other_bot")) == 1

    def test_history_sorted_by_timestamp(self, history_path):
        tracker = DriftTracker(history_path)
        tracker.record("aria", 0.9, 30, 27, "real", timestamp="2026-01-03T00:00:00+00:00")
        tracker.record("aria", 0.8, 30, 24, "real", timestamp="2026-01-01T00:00:00+00:00")
        tracker.record("aria", 0.85, 30, 25, "real", timestamp="2026-01-02T00:00:00+00:00")
        runs = tracker.history("aria")
        assert [r.timestamp for r in runs] == [
            "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00", "2026-01-03T00:00:00+00:00",
        ]


class TestDetectDrift:
    def test_insufficient_data_below_min_runs(self, history_path):
        tracker = DriftTracker(history_path)
        for i in range(3):
            tracker.record("aria", 0.9, 30, 27, "real", timestamp=f"2026-01-0{i+1}T00:00:00+00:00")
        report = tracker.detect_drift("aria", min_runs=5)
        assert report.mode == "insufficient_data"
        assert report.num_runs == 3

    def test_stable_history_is_not_flagged_as_drift(self, history_path):
        tracker = DriftTracker(history_path)
        for i in range(8):
            tracker.record("aria", 0.93, 30, 28, "real", timestamp=f"2026-01-{i+1:02d}T00:00:00+00:00")
        report = tracker.detect_drift("aria", min_runs=5)
        assert report.mode == "stable"
        assert not report.drift_detected

    def test_sharp_drop_in_latest_run_is_flagged(self, history_path):
        tracker = DriftTracker(history_path)
        for i in range(7):
            tracker.record("aria", 0.97, 30, 29, "real", timestamp=f"2026-01-{i+1:02d}T00:00:00+00:00")
        tracker.record("aria", 0.20, 30, 6, "real", timestamp="2026-01-08T00:00:00+00:00")
        report = tracker.detect_drift("aria", min_runs=5)
        assert report.mode == "drift_detected"
        assert report.drift_detected
        assert report.current_compliance == 0.20
        assert len(report.findings) >= 1

    def test_gradual_decline_trend_is_flagged(self, history_path):
        tracker = DriftTracker(history_path)
        # Steady, monotonic decline across many runs (not just a fresh gapore)
        compliances = [0.98, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55]
        for i, c in enumerate(compliances):
            passed = round(c * 30)
            tracker.record("aria", c, 30, passed, "real", timestamp=f"2026-01-{i+1:02d}T00:00:00+00:00")
        report = tracker.detect_drift("aria", min_runs=5)
        assert report.drift_detected
        assert report.trend_slope is not None and report.trend_slope < 0

    def test_improving_trend_is_not_flagged_as_drift(self, history_path):
        tracker = DriftTracker(history_path)
        compliances = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
        for i, c in enumerate(compliances):
            passed = round(c * 30)
            tracker.record("aria", c, 30, passed, "real", timestamp=f"2026-01-{i+1:02d}T00:00:00+00:00")
        report = tracker.detect_drift("aria", min_runs=5)
        assert not report.drift_detected
        assert report.mode == "stable"
