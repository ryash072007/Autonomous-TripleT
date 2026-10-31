import numpy as np
import pytest

from ca_triage.tiers import Tier, rule_fired, tier


@pytest.mark.parametrize(
    "log10_pc, miss_m, expected",
    [
        (-30.0, 20_000, Tier.SAFE),
        (-6.01, 5_000.1, Tier.SAFE),
        (-6.0, 20_000, Tier.ELEVATED),  # Pc = 1e-6 is Elevated
        (-4.01, 20_000, Tier.ELEVATED),
        (-30.0, 5_000, Tier.ELEVATED),  # 5.0 km inclusive
        (-30.0, 1_000, Tier.ELEVATED),  # 1.0 km is Elevated, < 1.0 km is Critical
        (-4.0, 20_000, Tier.CRITICAL),  # risk >= -4.0
        (-30.0, 999.9, Tier.CRITICAL),
        (-2.0, 500, Tier.CRITICAL),
    ],
)
def test_tier_boundaries(log10_pc, miss_m, expected):
    assert tier(log10_pc, miss_m) == expected


def test_vectorised():
    out = tier(np.array([-30, -5, -3]), np.array([10_000, 10_000, 10_000]))
    assert out.tolist() == [Tier.SAFE, Tier.ELEVATED, Tier.CRITICAL]


def test_rule_names_the_branch():
    assert "miss distance" in rule_fired(-30.0, 500)
    assert "Pc" in rule_fired(-3.0, 50_000)
