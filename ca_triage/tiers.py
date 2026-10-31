"""Operational risk tiers from the problem statement (NASA/SP-20205011318, ESA SDO practice).

The single source of truth for thresholds. `risk` is log10(Pc); `miss_distance` is in metres.
"""

from __future__ import annotations

from enum import IntEnum

import numpy as np

CRITICAL_LOG10_PC = -4.0
ELEVATED_LOG10_PC = -6.0
CRITICAL_MISS_M = 1_000.0
ELEVATED_MISS_M = 5_000.0


class Tier(IntEnum):
    SAFE = 0
    ELEVATED = 1
    CRITICAL = 2


TIER_NAMES = {Tier.SAFE: "Safe", Tier.ELEVATED: "Elevated", Tier.CRITICAL: "Critical"}


def tier(log10_pc, miss_distance_m) -> np.ndarray:
    """Vectorised tier for arrays (or scalars) of log10(Pc) and miss distance in metres."""
    pc = np.asarray(log10_pc, dtype=float)
    miss = np.asarray(miss_distance_m, dtype=float)
    critical = (pc >= CRITICAL_LOG10_PC) | (miss < CRITICAL_MISS_M)
    elevated = (pc >= ELEVATED_LOG10_PC) | (miss <= ELEVATED_MISS_M)
    return np.where(critical, Tier.CRITICAL, np.where(elevated, Tier.ELEVATED, Tier.SAFE)).astype(int)


def rule_fired(log10_pc: float, miss_distance_m: float) -> str:
    """Human-readable reason for one CDM's tier, for the dashboard and the audit log."""
    t = Tier(int(tier(log10_pc, miss_distance_m)))
    if t is Tier.CRITICAL:
        if log10_pc >= CRITICAL_LOG10_PC:
            return f"Critical: Pc = 1e{log10_pc:.2f} >= 1e-4"
        return f"Critical: miss distance {miss_distance_m / 1000:.2f} km < 1.0 km"
    if t is Tier.ELEVATED:
        if log10_pc >= ELEVATED_LOG10_PC:
            return f"Elevated: 1e-6 <= Pc = 1e{log10_pc:.2f} < 1e-4"
        return f"Elevated: miss distance {miss_distance_m / 1000:.2f} km within 1.0-5.0 km"
    return f"Safe: Pc = 1e{log10_pc:.2f} < 1e-6 and miss distance {miss_distance_m / 1000:.2f} km > 5.0 km"
