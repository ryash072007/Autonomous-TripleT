import { useEffect, useRef } from "react";
import { EventLight } from "./api";
import { AbstainBadge, RecChip, sigmaUnusable, TIER_NAMES, TIER_VAR, TierBadge, Term, fmtMiss, fmtPc, fmtTtca } from "./ui";

interface Props {
  events: EventLight[];
  message: string | null;
  loading: boolean;
  selected: number | null;
  onSelect: (id: number) => void;
  tierFilter: number | null;
  setTierFilter: (t: number | null) => void;
  typeFilter: string | null;
  setTypeFilter: (t: string | null) => void;
  types: string[];
  counts: Record<string, number>;
}

export default function Queue(p: Props) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || e.metaKey || e.ctrlKey) return;
      if (e.key !== "j" && e.key !== "k") return;
      if (!p.events.length) return;
      const i = p.events.findIndex((x) => x.event_id === p.selected);
      const n = e.key === "j" ? Math.min(p.events.length - 1, i + 1) : Math.max(0, i - 1);
      p.onSelect(p.events[n].event_id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [p.events, p.selected, p.onSelect]);

  useEffect(() => {
    listRef.current?.querySelector(".row.sel")?.scrollIntoView({ block: "nearest" });
  }, [p.selected]);

  return (
    <aside className="queue" aria-label="Event queue">
      <div className="chips" role="group" aria-label="Filter by tier">
        <button className={"chip" + (p.tierFilter == null ? " on" : "")} onClick={() => p.setTierFilter(null)}>
          All
        </button>
        {[2, 1, 0].map((t) => (
          <button
            key={t}
            className={"chip" + (p.tierFilter === t ? " on" : "")}
            style={{ ["--c" as string]: TIER_VAR[t] }}
            onClick={() => p.setTierFilter(p.tierFilter === t ? null : t)}
          >
            {TIER_NAMES[t]} {p.counts[TIER_NAMES[t]] ?? 0}
          </button>
        ))}
      </div>
      <div className="chips" role="group" aria-label="Filter by object type">
        {p.types.map((t) => (
          <button
            key={t}
            className={"chip small" + (p.typeFilter === t ? " on" : "")}
            onClick={() => p.setTypeFilter(p.typeFilter === t ? null : t)}
          >
            {t.toLowerCase()}
          </button>
        ))}
      </div>
      <div className="q-head mono">
        <span>
          Tier / event
        </span>
        <span>
          <Term k="TCA" /> / <Term k="miss distance">miss</Term> / <Term k="Pc" />
        </span>
      </div>
      <div className="q-list" ref={listRef}>
        {p.events.length === 0 && (
          <div className="empty">{p.loading ? "Loading..." : p.message ?? "No events match these filters."}</div>
        )}
        {p.events.map((e) => (
          <button
            key={e.event_id}
            className={"row" + (e.event_id === p.selected ? " sel" : "")}
            onClick={() => p.onSelect(e.event_id)}
          >
            <span className="r1">
              <TierBadge tier={e.tier} />
              <span className="mono id">#{e.event_id}</span>
              {e.names && <span className="names">{e.names.t} × {e.names.c}</span>}
              {(e.abstain || e.tier_set.length > 1) && e.recommendation !== "Analyst decides" && <AbstainBadge />}
              <RecChip rec={e.recommendation} reason={e.recommendation_reason} />
              {sigmaUnusable(e.latest.c_sigma_r) && (
                <span className="chip-warn" title="Radial sigma is a placeholder: no usable covariance">no covariance</span>
              )}
              {e.flags.map((f) => (
                <span key={f} className="flag">
                  {f.replace(/_/g, " ")}
                </span>
              ))}
            </span>
            <span className="r2 mono">
              <span>{fmtTtca(e.latest.time_to_tca)}</span>
              <span>{fmtMiss(e.latest.miss_distance)}</span>
              <span>{fmtPc(e.latest.max_risk_estimate)}</span>
            </span>
          </button>
        ))}
      </div>
      <div className="q-foot mono">{p.events.length.toLocaleString()} shown · j / k to move</div>
    </aside>
  );
}
