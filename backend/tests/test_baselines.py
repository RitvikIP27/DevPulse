"""Robust statistics used for historical comparison (PRD 2.8)."""

import pytest

from app.services.baselines import (
    MIN_BASELINE_SAMPLES,
    REGRESSION_THRESHOLD_PCT,
    compare,
    regression_signal,
    summarise,
)


class TestSummarise:
    def test_reports_median_and_p90(self):
        baseline = summarise([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert baseline.median_value == 5.5
        assert baseline.p90_value == 9
        assert baseline.sample_count == 10

    def test_median_resists_a_single_outlier_where_a_mean_would_not(self):
        """One pull request left open over a weekend must not redefine normal."""
        values = [7, 7, 8, 6, 7, 4000]
        baseline = summarise(values)

        mean = sum(values) / len(values)
        assert baseline.median_value == 7.0
        assert mean > 600  # the mean is destroyed; the median is not

    def test_empty_input_is_unavailable_not_zero(self):
        baseline = summarise([])
        assert baseline.is_available is False
        assert baseline.median_value is None


class TestCompare:
    def test_detects_the_prd_regression_example(self):
        """PRD 2.8: 7m baseline against a 24m current period is +243%."""
        comparison = compare([24, 25, 23], [7, 7, 8, 6, 7])

        assert comparison.change_pct == pytest.approx(242.9, abs=0.1)
        assert comparison.is_regression is True

    def test_normal_variation_is_not_a_regression(self):
        comparison = compare([7, 8, 7], [7, 7, 8, 6, 7])

        assert comparison.is_regression is False
        assert comparison.change_pct < REGRESSION_THRESHOLD_PCT

    def test_an_improvement_is_never_a_regression(self):
        comparison = compare([3, 3, 4], [7, 7, 8, 6, 7])

        assert comparison.change_pct < 0
        assert comparison.is_regression is False

    def test_a_thin_baseline_reports_why_rather_than_no_regression(self):
        """"Not enough history" and "no regression" are different claims."""
        comparison = compare([24, 25], [7, 7])

        assert comparison.change_pct is None
        assert comparison.is_regression is False
        assert str(MIN_BASELINE_SAMPLES) in comparison.reason

    def test_a_zero_baseline_does_not_divide_by_zero(self):
        comparison = compare([5, 5, 5], [0, 0, 0, 0, 0])

        assert comparison.change_pct is None
        assert "undefined" in comparison.reason


class TestRegressionSignal:
    @pytest.mark.parametrize(
        "change_pct,expected",
        [(None, 0.0), (-50.0, 0.0), (0.0, 0.0), (100.0, 50.0), (200.0, 100.0), (900.0, 100.0)],
    )
    def test_normalises_onto_a_bounded_scale(self, change_pct, expected):
        assert regression_signal(change_pct) == expected

    def test_getting_faster_never_contributes_to_a_bottleneck_score(self):
        assert regression_signal(-90.0) == 0.0
