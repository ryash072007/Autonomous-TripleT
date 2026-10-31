"""Collision consequence model: "if this pair collides, who else is threatened?"  DISPLAY AND PRIORITISATION ONLY.

Nothing here is an input to the tier model or the tier rule. The columns read below (rcs_estimate, cd_area_over_mass,
orbital heights) are outside ALLOWED_COLUMNS; `tests/test_features.py` checks they cannot reach a model feature list.

Assumptions (all of them approximations, none validated against flight data):
- Mass proxy: m = rcs_estimate [m^2] / cd_area_over_mass [m^2/kg] per object. cd_area_over_mass already contains the drag
  coefficient (~2.2) and rcs is not the true area, so mass is good to roughly a factor 2-3 at best. Used only when the
  result lies in [0.05, 20000] kg; otherwise a fixed per-type fallback: payload 500 kg, rocket body 1500 kg, debris 5 kg,
  unknown/TBA 10 kg (the target, the object being protected, falls back to payload).
- NASA Standard Breakup Model, simplified as in the reference repo: catastrophic if 0.5 m_small v_rel^2 / m_large > 40 J/g;
  ejected mass M = m1 + m2 if catastrophic, else m_small * v_rel[km/s]^2 (the SBM non-catastrophic form);
  N(Lc >= 10 cm) = 0.1 M^0.75 Lc^-1.71; fragment dv: log10(dv[m/s]) ~ N(0.9 chi + 2.9, 0.4), chi ~ N(-0.6, 0.5)
  independent of size. Ejection is isotropic about the collision point, relative velocity of the parents is ignored in
  the fragment frame, orbits are circular at the collision altitude, no drag, no J2, no re-entry bookkeeping.
- Exposure: fragments spread over the altitude range [perigee, apogee] of their post-kick orbits. Each fragment is assumed
  uniformly spread over the full spherical shell of every 25 km band it crosses (phase-mixed, ignores that inclination
  confines the cloud, which would raise density by a factor of a few). Encounters with active satellites follow
  kinetic-gas flux: expected = sum_bands S_b * (N f_b / V_b) * sigma * v * t with sigma = 10 m^2 per satellite,
  v = 10 km/s, t = 30 d. S_b counts ACTIVE satellites only (CelesTrak GP "active" group), not other debris.
  The loss of the two colliding objects themselves is not counted.
- Pc for harm ranking is the CDM's max_risk_estimate (an upper-bound style estimate), for display only.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import SEED
from .data import DATASET, ROOT

MU = 398600.4418  # km^3/s^2
RE = 6378.137  # km
CATASTROPHIC_J_PER_G = 40.0
POWER = 1.71
CHI_MEAN, CHI_SIGMA, DV_SIGMA_LOG10 = -0.6, 0.5, 0.4
BAND_KM = 25.0
MAX_ALT_KM = 2000.0
SIGMA_M2 = 10.0
V_ENCOUNTER_KMS = 10.0
WINDOW_DAYS = 30.0
MASS_MIN_KG, MASS_MAX_KG = 0.05, 20000.0
FALLBACK_KG = {"PAYLOAD": 500.0, "ROCKET BODY": 1500.0, "DEBRIS": 5.0, "UNKNOWN": 10.0, "TBA": 10.0}
POP_PATH = ROOT / "artifacts" / "population_by_altitude.json"
INPUT_COLUMNS = ["event_id", "time_to_tca", "t_rcs_estimate", "t_cd_area_over_mass", "c_rcs_estimate", "c_cd_area_over_mass"]


def load_consequence_inputs(split: str) -> pd.DataFrame:
    """Row-aligned mass-proxy columns. Display only: these are not allowed model inputs."""
    return pd.read_csv(DATASET / f"{split}_data.csv", usecols=INPUT_COLUMNS)


def mass_estimate(rcs, cd_aom, object_type: str | None, target: bool) -> tuple[float, str]:
    """(mass_kg, source) with source 'rcs/area' or 'fallback:<type>'."""
    try:
        m = float(rcs) / float(cd_aom)
    except (TypeError, ValueError, ZeroDivisionError):
        m = float("nan")
    if np.isfinite(m) and MASS_MIN_KG <= m <= MASS_MAX_KG:
        return m, "rcs/area"
    key = "PAYLOAD" if target else str(object_type or "UNKNOWN").upper()
    return FALLBACK_KG.get(key, FALLBACK_KG["UNKNOWN"]), f"fallback:{key.lower()}"


def is_catastrophic(m1: float, m2: float, v_rel_kms: float) -> bool:
    small, large = min(m1, m2), max(m1, m2)
    return 0.5 * small * (v_rel_kms * 1000.0) ** 2 / (large * 1000.0) > CATASTROPHIC_J_PER_G


def ejected_mass(m1: float, m2: float, v_rel_kms: float) -> float:
    return m1 + m2 if is_catastrophic(m1, m2, v_rel_kms) else min(m1, m2) * v_rel_kms**2


def n_fragments(mass_kg: float, lc_m: float = 0.10) -> float:
    return 0.1 * mass_kg**0.75 * lc_m**-POWER


def sample_dv(n: int, rng: np.random.Generator) -> np.ndarray:
    """Fragment kick magnitudes in km/s."""
    chi = rng.normal(CHI_MEAN, CHI_SIGMA, n)
    return 10.0 ** rng.normal(0.9 * chi + 2.9, DV_SIGMA_LOG10) / 1000.0


def isotropic(n: int, rng: np.random.Generator) -> np.ndarray:
    d = rng.normal(size=(n, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def post_kick_extent(alt_km: float, dv_kms: np.ndarray, dirs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Perigee/apogee altitudes and semi-major axis of fragments kicked from a circular orbit (x radial, y along-track)."""
    r0 = RE + alt_km
    vc = np.sqrt(MU / r0)
    v = np.stack([dv_kms * dirs[:, 0], vc + dv_kms * dirs[:, 1], dv_kms * dirs[:, 2]], axis=1)
    v2 = (v**2).sum(1)
    eps = 0.5 * v2 - MU / r0
    bound = eps < 0
    a = np.where(bound, -MU / (2 * np.where(bound, eps, -1.0)), np.inf)
    h2 = (r0 * v[:, 1]) ** 2 + (r0 * v[:, 2]) ** 2
    e = np.sqrt(np.clip(1 + 2 * eps * h2 / MU**2, 0, None))
    per, apo = a * (1 - e) - RE, a * (1 + e) - RE
    return np.where(bound, per, np.nan), np.where(bound, apo, np.nan), a


def load_population() -> dict:
    return json.loads(POP_PATH.read_text())


def band_edges() -> np.ndarray:
    return np.arange(0.0, MAX_ALT_KM + BAND_KM, BAND_KM)


def exposure_for(alt_km: float, n_ge10: float, counts: np.ndarray, per: np.ndarray, apo: np.ndarray) -> dict:
    """Expected encounters (30 d) of the cloud with active satellites, and the affected altitude band."""
    edges = band_edges()
    lo, hi = edges[:-1], edges[1:]
    ok = np.isfinite(per)
    p, q = per[ok], apo[ok]
    # fraction of bound fragments whose [perigee, apogee] overlaps each band (unbound ones cross everything: ignored)
    f = ((p[:, None] <= hi[None, :]) & (q[:, None] >= lo[None, :])).mean(0) * ok.mean()
    r_mid = RE + 0.5 * (lo + hi)
    vol = 4 * np.pi * r_mid**2 * BAND_KM
    dens = n_ge10 * f / vol  # fragments per km^3
    sigma_km2 = SIGMA_M2 * 1e-6
    per_sat = dens * sigma_km2 * V_ENCOUNTER_KMS * WINDOW_DAYS * 86400.0
    expected = float((counts * per_sat).sum())
    crossed = f >= 0.5  # bands crossed by at least half the fragments
    if crossed.any():
        band = [float(lo[crossed].min()), float(hi[crossed].max())]
    else:
        band = [float(max(alt_km - BAND_KM, 0)), float(alt_km + BAND_KM)]
    in_band = int(counts[(lo >= band[0]) & (hi <= band[1])].sum())
    return {"exposure_30d": expected, "band_km": band, "active_sats_in_band": in_band}


CLOUD_DV_MAX_KMS = 0.5  # linear relative motion is only valid for kicks well below the orbital speed
CLOUD_NOTE = ("illustrative spread of >= 10 cm fragments with Delta-v <= 500 m/s (about 70% of them) by Clohessy-Wiltshire linear relative motion "
              "on a circular orbit, no drag/J2; offsets are [along-track phase rad (wrapped to +-pi), radial km, cross-track km]; null = none")


def cloud_offsets(alt_km: float, dv_kms: np.ndarray, dirs: np.ndarray, hours=(0, 1, 6, 24, 168)) -> dict:
    """Fragment positions relative to the collision point in the rotating (radial, along-track, cross-track) frame.

    Clohessy-Wiltshire closed form with zero initial offset and kick (u, v, w) = dv * (radial, along-track, cross-track):
        x(t) = u sin(nt)/n + 2v (1 - cos nt)/n                      radial, bounded and oscillating
        y(t) = -2u (1 - cos nt)/n + v (4 sin nt - 3 nt)/n           along-track, secular drift -3 v t
        z(t) = w sin(nt)/n                                          cross-track
    Phase = y / r0 wrapped to (-pi, pi]. Display only: valid for small kicks, so callers pass dv <= CLOUD_DV_MAX_KMS.
    The exposure numbers do NOT use this; they use the full Keplerian altitude extent (`post_kick_extent`).
    """
    r0 = RE + alt_km
    n = np.sqrt(MU / r0**3)
    u, v, w = (dv_kms * dirs[:, k] for k in range(3))
    out = []
    for hr in hours:
        t = hr * 3600.0
        nt = n * t
        x = (u * np.sin(nt) + 2 * v * (1 - np.cos(nt))) / n
        y = (-2 * u * (1 - np.cos(nt)) + v * (4 * np.sin(nt) - 3 * nt)) / n
        z = w * np.sin(nt) / n
        phase = (y / r0 + np.pi) % (2 * np.pi) - np.pi
        out.append([[round(float(p), 3) + 0.0, round(float(a), 0) + 0.0, round(float(c), 0) + 0.0] for p, a, c in zip(phase, x, z)])
    return {"t_hours": list(hours), "offsets": out}


def cloud_samples(n: int = 150) -> tuple[np.ndarray, np.ndarray]:
    """n fragment kicks (km/s) and directions from the breakup distribution, restricted to the linear regime."""
    dv, dirs = standard_samples(4 * n * 2)
    keep = dv <= CLOUD_DV_MAX_KMS
    return dv[keep][:n], dirs[keep][:n]


def consequence_score(exposure_30d: float) -> float:
    """0-100 log index of expected 30-day encounters (1e-3 -> 12, 1e-2 -> 43, 1e-1 -> 80, saturates near 0.3)."""
    return float(100 * np.clip(np.log10(1 + exposure_30d / 1e-3) / 2.5, 0, 1))


def standard_samples(n: int = 1500) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(SEED)
    return sample_dv(n, rng), isotropic(n, rng)
