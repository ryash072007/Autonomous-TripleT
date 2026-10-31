import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dataset, DemoResp, EventLight, Summary, WindowResp, api } from "./api";
import Landing from "./Landing";
import Queue from "./Queue";
import EventDetail from "./EventDetail";
import { DemoBar, Next24, demoHighlight } from "./Panels";
import Results from "./Results";
import Insights from "./Insights";
import { RidgeStrip } from "./Scene";
import { TIER_NAMES, TierIcon, fmtClock } from "./ui";

type View = "landing" | "queue" | "next24" | "insights" | "evidence";
const SPEEDS = [0.1, 0.25, 0.5, 1];

export default function App() {
  const [view, setView] = useState<View>(() => {
    const h = window.location.hash.slice(1).split("&")[0];
    return h === "queue" || h === "next24" || h === "insights" || h === "evidence" || h === "results" ? (h === "results" ? "evidence" : h) : "landing";
  });
  const [dataset, setDataset] = useState<Dataset>(() => (window.location.hash.includes("ds=live") ? "live" : "test"));
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<EventLight[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiErr, setApiErr] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [mobileDetail, setMobileDetail] = useState(false);
  const [tierFilter, setTierFilter] = useState<number | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  // Replay clock: elapsed days; an event's remaining time is latest.time_to_tca - elapsed.
  const [elapsed, setElapsed] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(0.25);
  const [win, setWin] = useState<WindowResp | null>(null);

  const [demo, setDemo] = useState<DemoResp | null>(null);
  const [demoStep, setDemoStep] = useState(0);
  const [anchor, setAnchor] = useState<string | null>(null);

  const [sky, setSky] = useState<EventLight[]>([]);
  const [fullFor, setFullFor] = useState<Dataset | null>(null);

  // First paint needs only the summary and a small sky sample, not the full event list.
  useEffect(() => {
    setApiErr(false);
    setFullFor(null);
    setEvents([]);
    Promise.all([api.summary(dataset), api.events(dataset, null, null, "sky")])
      .then(([s, e]) => {
        setSummary(s);
        setSky(e.events);
        setMessage(e.message ?? s.message);
        setElapsed(Math.max(0, s.min_time_to_tca - 0.9));
      })
      .catch(() => setApiErr(true));
  }, [dataset]);

  useEffect(() => {
    if (view === "landing" || fullFor === dataset) return;
    setLoading(true);
    api.events(dataset)
      .then((e) => {
        setEvents(e.events);
        setFullFor(dataset);
        setMessage((m) => e.message ?? m);
        const m = /e=(\d+)/.exec(window.location.hash);
        setSelected((cur) => (cur != null && e.events.some((x) => x.event_id === cur) ? cur : m ? +m[1] : e.events[0]?.event_id ?? null));
      })
      .catch(() => setApiErr(true))
      .finally(() => setLoading(false));
  }, [view, dataset, fullFor]);

  const clockMin = summary ? Math.max(0, summary.min_time_to_tca - 1) : 0;
  const clockMax = summary?.max_time_to_tca ?? 0;

  useEffect(() => {
    if (!playing || !summary) return;
    const id = setInterval(() => {
      setElapsed((x) => {
        const n = x + speed * 0.1;
        return n > clockMax ? clockMin : n;
      });
    }, 100);
    return () => clearInterval(id);
  }, [playing, speed, summary, clockMin, clockMax]);

  const lastFetch = useRef(0);
  useEffect(() => {
    if (!summary || view === "landing") return;
    const wait = Math.max(0, 250 - (Date.now() - lastFetch.current));
    const t = setTimeout(() => {
      lastFetch.current = Date.now();
      api.window(elapsed, dataset).then(setWin).catch(() => {});
    }, wait);
    return () => clearTimeout(t);
  }, [elapsed, dataset, summary, view]);

  const clockLabel = fmtClock(clockMax - elapsed);

  const open = useCallback((id?: number) => {
    setTierFilter(null);
    setTypeFilter(null);
    if (id != null) {
      setSelected(id);
      setMobileDetail(true);
    }
    setView("queue");
  }, []);

  const shown = useMemo(
    () => events.filter((e) => (tierFilter == null || e.tier === tierFilter) && (typeFilter == null || e.c_object_type === typeFilter)),
    [events, tierFilter, typeFilter],
  );

  const startDemo = async () => {
    try {
      const d = await api.demo();
      if (!d.items.length) return;
      setDemo(d);
      setDemoStep(0);
      open(d.items[0].event_id);
    } catch {
      /* demo unavailable */
    }
  };
  useEffect(() => {
    if (demo && demo.items[demoStep]) open(demo.items[demoStep].event_id);
  }, [demoStep]);

  useEffect(() => {
    const m = /demo=(\d)/.exec(window.location.hash);
    if (!m) return;
    api.demo().then((d) => { setDemo(d); setDemoStep(Math.min(d.items.length, +m[1]) - 1); }).catch(() => {});
  }, []);

  if (apiErr)
    return (
      <div className="page" style={{ padding: 32 }}>
        <h2>OrbitGuard</h2>
        <p>Cannot reach the API. Start it with <code>python scripts/serve.py</code>, or set VITE_API_BASE.</p>
      </div>
    );

  if (view === "landing")
    return (
      <Landing summary={summary} events={sky} clockDays={elapsed} windowCount={win?.n ?? 0} onOpen={open} />
    );

  return (
    <div className="console">
      <header className="topbar">
        <button className="wordmark" onClick={() => setView("landing")} aria-label="Back to landing">
          ORBITGUARD
        </button>
        <div className="seg" role="group" aria-label="Data source">
          <button className={dataset === "test" ? "on" : ""} onClick={() => setDataset("test")}>Test dataset</button>
          <button className={dataset === "live" ? "on" : ""} onClick={() => setDataset("live")}>Live</button>
        </div>
        <nav className="tabs">
          {([["queue", "Queue"], ["next24", "Next 24 h"], ["insights", "Insights"], ["evidence", "Results"]] as [View, string][]).map(([v, l]) => (
            <button key={v} className={view === v ? "on" : ""} onClick={() => setView(v)}>{l}</button>
          ))}
        </nav>
        <div className="clock mono" title="Replay clock: events enter the 24 h window as it advances">
          <button className="icon-btn" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause replay" : "Play replay"}>
            {playing ? "❚❚" : "▶"}
          </button>
          <input type="range" min={clockMin} max={clockMax} step={0.01} value={Math.min(Math.max(elapsed, clockMin), clockMax)}
            onChange={(e) => setElapsed(+e.target.value)} aria-label="Replay clock" />
          <span>{clockLabel}</span>
          <select value={speed} onChange={(e) => setSpeed(+e.target.value)} aria-label="Replay speed">
            {SPEEDS.map((s) => <option key={s} value={s}>{s} d/s</option>)}
          </select>
          <span className="win-count" title="Events inside the 24 h window">{win?.n ?? 0} in 24 h</span>
        </div>
        <div className="counts mono">
          {[2, 1, 0].map((t) => (
            <span key={t}><TierIcon tier={t} size={12} /> {summary?.counts[TIER_NAMES[t]] ?? 0}</span>
          ))}
        </div>
        <button className="btn primary" onClick={startDemo}>Guided demo</button>
      </header>

      {dataset === "live" && (
        <div className="banner">
          Space-Track public CDMs · tiered by rule only (model inputs not published)
          {summary?.snapshot?.latest_cdm_created ? ` · snapshot ${summary.snapshot.latest_cdm_created} UTC` : summary?.generated_utc ? ` · snapshot ${summary.generated_utc}` : ""}
          {events.length === 0 && message ? ` · ${message}` : ""}
        </div>
      )}
      {dataset === "test" && summary && summary.model && (
        <div className="banner soft mono">
          Model: {summary.model.name} ({summary.model.version}) · scored {summary.generated_utc ?? "n/a"}
          {!summary.has_model_probs && " · rule only: no tier probabilities or forecast yet"}
        </div>
      )}

      <main className={"main" + (mobileDetail ? " show-detail" : "")}>
        {view === "queue" && (
          <>
            <Queue events={shown} message={message} loading={loading} selected={selected}
              onSelect={(id) => { setSelected(id); setMobileDetail(true); }}
              tierFilter={tierFilter} setTierFilter={setTierFilter} typeFilter={typeFilter} setTypeFilter={setTypeFilter}
              types={summary?.object_types ?? []} counts={summary?.counts ?? {}} />
            <EventDetail id={dataset === "live" && events.length === 0 ? null : selected} dataset={dataset}
              modelName={summary?.model?.name ?? null} sensNote={summary?.sensitivity_note} highlight={demo ? demoHighlight(demo.items[demoStep]?.key) : null} onBack={() => setMobileDetail(false)} />
          </>
        )}
        {view === "next24" && (
          <Next24 win={win} clockLabel={clockLabel} onOpen={(id) => open(id)} />
        )}
        {view === "insights" && <Insights events={events} onOpen={(id) => open(id)} />}
        {view === "evidence" && (
          <Results anchor={anchor} testIds={new Set(events.map((e) => e.event_id))} onOpen={(id) => open(id)} />
        )}
      </main>

      {demo && view === "queue" && (
        <DemoBar step={demoStep} setStep={setDemoStep} demo={demo} onExit={() => setDemo(null)}
          onFailures={() => { setDemo(null); setView("evidence"); setAnchor("where-it-fails"); }} />
      )}
      <RidgeStrip />
    </div>
  );
}
