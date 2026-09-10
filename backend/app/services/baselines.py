"""Historical baselines and regression detection (PRD 2.8).

Comparisons use the median and median absolute deviation rather than the mean
and standard deviation. Delivery data is heavily skewed — one pull request left
open over a weekend moves a mean far more than it moves reality — and rules.md 8
requires that a calculation be reproducible and defensible. Robust statistics
are what make a "CI got slower" claim survive a single outlier.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

#: Below this many samples a median is not meaningful enough to compare against,
#: so a baseline is reported as unavailable rather than computed from noise.
MIN_BASELINE_SAMPLES = 5

#: A change smaller than this is treated as normal variation, not a regression.
REGRESSION_THRESHOLD_PCT = 25.0

#: Percentage increase that counts as a fully saturated regression signal when
#: scoring. A stage that doubled (+100%) scores 50; +200% or worse scores 100.
REGRESSION_SATURATION_PCT = 200.0


@dataclass(frozen=True)
class Baseline:
    """A distribution summary for one measurement over one period."""

    sample_count: int
    median_value: float | None
    p90_value: float | None
    #: Median absolute deviation — the robust analogue of standard deviation.
    mad: float | None

    @property
    def is_available(self) -> bool:
        return self.median_value is not None


@dataclass(frozen=True)
class Comparison:
    """Current period measured against a historical baseline."""

    current: Baseline
    baseline: Baseline
    change_pct: float | None
    is_regression: bool
    #: Deviation from baseline expressed in MADs, when dispersion is known.
    deviation_mads: float | None
    reason: str | None


def _percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile. Deterministic and free of interpolation choices."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * len(ordered)) - 1))
    return ordered[index]


def summarise(values: list[float]) -> Baseline:
    usable = [value for value in values if value is not None]
    if not usable:
        return Baseline(sample_count=0, median_value=None, p90_value=None, mad=None)

    centre = median(usable)
    return Baseline(
        sample_count=len(usable),
        median_value=round(centre, 2),
        p90_value=round(_percentile(usable, 0.9) or centre, 2),
        mad=round(median([abs(value - centre) for value in usable]), 2),
    )


def compare(current_values: list[float], baseline_values: list[float]) -> Comparison:
    """Compare a current period against a baseline period.

    A regression requires both a sufficient baseline and a change beyond normal
    variation. Anything less is reported as "no comparison available" rather than
    as an absence of regression, because those are different claims.
    """
    current = summarise(current_values)
    baseline = summarise(baseline_values)

    if not current.is_available:
        return Comparison(current, baseline, None, False, None, "No data in the current period.")

    if baseline.sample_count < MIN_BASELINE_SAMPLES:
        return Comparison(
            current, baseline, None, False, None,
            f"Only {baseline.sample_count} historical sample(s); at least "
            f"{MIN_BASELINE_SAMPLES} are needed for a baseline.",
        )

    assert baseline.median_value is not None and current.median_value is not None
    if baseline.median_value == 0:
        return Comparison(
            current, baseline, None, False, None,
            "Baseline median is zero, so a percentage change is undefined.",
        )

    change_pct = round(
        (current.median_value - baseline.median_value) / baseline.median_value * 100, 1
    )
    deviation_mads = (
        round((current.median_value - baseline.median_value) / baseline.mad, 2)
        if baseline.mad
        else None
    )

    return Comparison(
        current=current,
        baseline=baseline,
        change_pct=change_pct,
        is_regression=change_pct >= REGRESSION_THRESHOLD_PCT,
        deviation_mads=deviation_mads,
        reason=None,
    )


def regression_signal(change_pct: float | None) -> float:
    """Normalise a percentage regression onto 0-100 for scoring.

    Linear up to the saturation point: a stage that doubled scores 50, one that
    tripled or worse scores 100. Improvements score 0 — getting faster is never
    evidence of a bottleneck.
    """
    if change_pct is None or change_pct <= 0:
        return 0.0
    return round(min(100.0, change_pct / REGRESSION_SATURATION_PCT * 100.0), 1)
