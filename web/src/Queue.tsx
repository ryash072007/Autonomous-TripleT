import { useEffect, useMemo, useRef, useState } from "react";
import { EventLight } from "./api";
import { conseq, harmLevel } from "./Consequence";
import { ForecastFlag, RecChip, TIER_NAMES, TIER_VAR, TierBadge, flagSentence, fmtMiss, isThresholdFlag, sigmaUnusable } from "./ui";

interface Props {
  events: EventLight[];
  message: string | null;
  loading: boolean;
  selected: number | null;
  onSelect: (id: number) => void;
  typeFilter: string | null;
  setTypeFilter: (t: string | null) => void;
  types: string[];
  forecastFlag?: ForecastFlag | null;
}

interface Group { key: string; title: string; hint: string; color: string; items: EventLight[] }

const harmOf = (e: EventLight) => conseq(e)?.harm ?? (conseq(e)?.harmRank != null ? -(conseq(e)!.harmRank as number) : null);

function group(events: EventLight[]): Group[] {
  const hasRec = events.some((e) => e.recommendation);
  const sorter = (a: EventLight, b: EventLight) => {
    const ha = harmOf(a), hb = harmOf(b);
    if (ha != null && hb != null && ha !== hb) return hb - ha;
    return a.latest.time_to_tca - b.latest.time_to_tca;
  };
  let gs: Group[];
  if (hasRec) {
    gs = [
      { key: "act", title: "ACT NOW", hint: "The tool recommends a manoeuvre", color: "var(--critical)", items: events.filter((e) => e.recommendation === "Act") },
      { key: "call", title: "YOUR CALL", hint: "The tool is not sure, or says wait", color: "var(--abstain)", items: events.filter((e) => e.recommendation === "Analyst decides" || e.recommendation === "Wait" || !e.recommendation) },
      { key: "clear", title: "CLEARED", hint: "Recommended to dismiss", color: "var(--safe)", items: events.filter((e) => e.recommendation === "Dismiss") },
    ];
  } else {
    gs = [2, 1, 0].map((t) => ({ key: "t" + t, title: TIER_NAMES[t].toUpperCase(), hint: "Tiered by rule only", color: TIER_VAR[t], items: events.filter((e) => e.tier === t) }));
  }
  gs.forEach((g) => g.items.sort(sorter));
  return gs;
}

export default function Queue(p: Props) {
  const listRef = useRef<HTMLDivElement>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({ act: true, call: true, clear: false, t2: true, t1: true, t0: false });
  const [more, setMore] = useState<Record<string, number>>({});

  const filtered = useMemo(() => (q.trim() ? p.events.filter((e) => String(e.event_id).includes(q.trim()) || (e.names && `${e.names.t} ${e.names.c}`.toLowerCase().includes(q.trim().toLowerCase()))) : p.events), [p.events, q]);
  const groups = useMemo(() => group(filtered), [filtered]);
  const visible = useMemo(() => groups.filter((g) => open[g.key] || q.trim()).flatMap((g) => g.items.slice(0, more[g.key] ?? 60)), [groups, open, more, q]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || e.metaKey || e.ctrlKey) return;
      if (e.key !== "j" && e.key !== "k") return;
      if (!visible.length) return;
      const i = visible.findIndex((x) => x.event_id === p.selected);
      const n = e.key === "j" ? Math.min(visible.length - 1, i + 1) : Math.max(0, i - 1);
      p.onSelect(visible[n].event_id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible, p.selected, p.onSelect]);

  useEffect(() => {
    listRef.current?.querySelector(".qcard.sel")?.scrollIntoView({ block: "nearest" });
  }, [p.selected]);

  const n = p.events.length;
  return (
    <aside className="queue card" aria-label="Event list">
      <div className="q-search">
        <input type="search" placeholder="Find an event id" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && filtered.length) p.onSelect(filtered[0].event_id); }} aria-label="Search event id" />
        <select value={p.typeFilter ?? ""} onChange={(e) => p.setTypeFilter(e.target.value || null)} aria-label="Object type">
          <option value="">All objects</option>
          {p.types.map((t) => <option key={t} value={t}>{t.toLowerCase()}</option>)}
        </select>
      </div>
      <div className="q-list" ref={listRef}>
        {filtered.length === 0 && <div className="empty">{p.loading ? "Loading..." : p.message ?? "No events match."}</div>}
        {groups.map((g) => {
          const isOpen = open[g.key] || !!q.trim();
          const shown = g.items.slice(0, more[g.key] ?? 60);
          return (
            <div key={g.key} className="qgroup">
              <button className="qhead" onClick={() => setOpen({ ...open, [g.key]: !open[g.key] })} aria-expanded={isOpen}>
                <span className="display qcount" style={{ color: g.color }}>{g.items.length.toLocaleString()}</span>
                <span>
                  <span className="label" style={{ color: g.color }}>{g.title}</span>
                  <span className="small dim qhint">{g.hint}</span>
                </span>
                <span className="chev">{isOpen ? "▾" : "▸"}</span>
              </button>
              {isOpen && shown.map((e) => {
                const hl = harmLevel(e, n);
                return (
                  <button key={e.event_id} className={"qcard" + (e.event_id === p.selected ? " sel" : "")} onClick={() => p.onSelect(e.event_id)}
                    title={e.p_forecast && e.forecast_tier_at_tca === 2 ? (isThresholdFlag(2, e.p_forecast) ? flagSentence(e.p_forecast, p.forecastFlag) : `Forecast: Critical. P(Critical at TCA) = ${(e.p_forecast[2] * 100).toFixed(1)}%.`) : undefined}>
                    <span className="r1">
                      <TierBadge tier={e.tier} />
                      <span className="id">#{e.event_id}</span>
                      {e.names && <span className="names">{e.names.t} × {e.names.c}</span>}
                      {hl && <span className="harm-badge" title="Large debris cloud if they collide">debris risk: high</span>}
                      {g.key !== "act" && g.key !== "clear" && <RecChip rec={e.recommendation} reason={e.recommendation_reason} />}
                      {sigmaUnusable(e.latest.c_sigma_r) && <span className="chip-warn" title="Uncertainty data is a placeholder">no covariance</span>}
                    </span>
                    <span className="r2">
                      <span>in {e.latest.time_to_tca.toFixed(1)} d</span>
                      <span>miss {fmtMiss(e.latest.miss_distance)}</span>
                    </span>
                  </button>
                );
              })}
              {isOpen && g.items.length > shown.length && (
                <button className="link-btn qmore" onClick={() => setMore({ ...more, [g.key]: (more[g.key] ?? 60) + 120 })}>
                  Show {Math.min(120, g.items.length - shown.length)} more of {g.items.length - shown.length}
                </button>
              )}
            </div>
          );
        })}
      </div>
      <div className="q-foot small dim">{n.toLocaleString()} events · j / k to move · sorted by {p.events.some((e) => conseq(e)) ? "harm, then time" : "time to closest approach"}</div>
    </aside>
  );
}
