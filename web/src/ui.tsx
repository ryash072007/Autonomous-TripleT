import { ReactNode } from "react";

export const TIER_NAMES = ["Safe", "Elevated", "Critical"];
export const TIER_VAR = ["var(--safe)", "var(--elevated)", "var(--critical)"];

/** Tier shape: circle = Safe, triangle = Elevated, octagon = Critical. */
export function TierIcon({ tier, size = 14 }: { tier: number; size?: number }) {
  const c = TIER_VAR[tier];
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" style={{ flex: "none" }}>
      {tier === 0 && <circle cx="10" cy="10" r="7.5" fill={c} />}
      {tier === 1 && <path d="M10 2.5 L18 17 H2 Z" fill={c} />}
      {tier === 2 && <path d="M6.5 1.5h7l5 5v7l-5 5h-7l-5-5v-7z" fill={c} />}
    </svg>
  );
}

export function TierBadge({ tier, big }: { tier: number; big?: boolean }) {
  return (
    <span className={"tier-badge" + (big ? " big" : "")} style={{ color: TIER_VAR[tier] }}>
      <TierIcon tier={tier} size={big ? 22 : 14} />
      {TIER_NAMES[tier]}
    </span>
  );
}

export function AbstainBadge({ title }: { title?: string }) {
  return (
    <span className="abstain" title={title ?? "The tool is not sure which tier applies"}>
      <svg width="12" height="12" viewBox="0 0 20 20" aria-hidden="true">
        <path d="M10 1 L19 10 L10 19 L1 10 Z" fill="currentColor" />
      </svg>
      Analyst decides
    </span>
  );
}

const GLOSSARY: Record<string, string> = {
  Pc: "Probability of collision for this close approach. Shown as log10 (1e-4 means 1 in 10,000).",
  TCA: "Time of closest approach. 'T-2 d' means two days before it.",
  CDM: "Conjunction data message: one update on a predicted close approach, issued repeatedly as tracking improves.",
  RTN: "Radial, Transverse, Normal: a frame centred on our satellite (up, along-track, cross-track).",
  "miss distance": "Predicted distance between the two objects at TCA, in metres or km.",
};

export function Term({ k, children }: { k: keyof typeof GLOSSARY | string; children?: ReactNode }) {
  return (
    <span className="term" tabIndex={0} data-tip={GLOSSARY[k] ?? k}>
      {children ?? k}
    </span>
  );
}

export const fmtMiss = (m: number) => (m < 1000 ? `${m.toFixed(0)} m` : `${(m / 1000).toFixed(m < 10000 ? 2 : 1)} km`);
export const fmtPc = (log10: number | null | undefined) =>
  log10 == null ? "n/a" : log10 <= -29.9 ? "<1e-30" : `1e${log10.toFixed(1)}`;
export const fmtTtca = (d: number) => `T-${d.toFixed(2)} d`;
export const fmtClock = (days: number) => {
  const mins = Math.max(0, Math.round(days * 1440));
  const dd = Math.floor(mins / 1440);
  const hh = Math.floor((mins % 1440) / 60);
  const mm = mins % 60;
  return `T-${dd}d ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
};
