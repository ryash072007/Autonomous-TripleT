import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dataset, DemoResp, EventLight, Summary, api } from "./api";
import Landing from "./Landing";
import Queue from "./Queue";
import EventPage from "./EventPage";
import Backdrop from "./Backdrop";
import { DemoBar, demoHighlight } from "./Panels";
import Next24 from "./Next24";
import Results from "./Results";
import Insights from "./Insights";

type View = "landing" | "queue" | "next24" | "insights" | "evidence";
const TOUR_KEY = "orbitguard_tour_done";

function tourDone(): boolean {
  try { return window.localStorage.getItem(TOUR_KEY) === "1"; } catch { return false; }
}
function markTourDone() {
  try { window.localStorage.setItem(TOUR_KEY, "1"); } catch { /* storage blocked: tour then shows once per page load */ }
}

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
  const [typeFilter, setTypeFilter] = useState<string | null>(null);


  const [demo, setDemo] = useState<DemoResp | null>(null);
  const [demoStep, setDemoStep] = useState(0);
  const [anchor, setAnchor] = useState<string | null>(null);
  const [sky, setSky] = useState<EventLight[]>([]);
  const [fullFor, setFullFor] = useState<Dataset | null>(null);
  const tourTried = useRef(false);
  const [welcome, setWelcome] = useState(false);
  const [attn, setAttn] = useState(false);
  const pulse = () => { setAttn(true); window.setTimeout(() => setAttn(false), 10000); };

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


  const open = useCallback((id?: number) => {
    setTypeFilter(null);
    if (id != null) {
      setSelected(id);
      setMobileDetail(true);
    }
    setView("queue");
  }, []);

  const shown = useMemo(() => events.filter((e) => typeFilter == null || e.c_object_type === typeFilter), [events, typeFilter]);

  const startTour = useCallback(async () => {
    try {
      const d = await api.demo();
      if (!d.items.length) return;
      setDemo(d);
      setDemoStep(0);
      setView("queue");
      setMobileDetail(true);
    } catch {
      /* tour unavailable */
    }
  }, []);
  const endTour = () => { setDemo(null); markTourDone(); pulse(); };
  const explore = () => { setWelcome(false); markTourDone(); pulse(); };
  const begin = () => { setWelcome(false); startTour(); };

  // The tour starts by itself the first time the console opens, unless it was finished or skipped before.
  useEffect(() => {
    if (view === "landing" || tourTried.current) return;
    tourTried.current = true;
    if (window.location.hash.includes("notour") || window.location.hash.includes("demo=") || tourDone()) return;
    setWelcome(true);
  }, [view, startTour]);

  useEffect(() => {
    if (demo && demo.items[demoStep]) {
      setSelected(demo.items[demoStep].event_id);
      setMobileDetail(true);
      setView("queue");
    }
  }, [demoStep, demo]);

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

  if (view === "landing") return <Landing summary={summary} events={sky} clockDays={0} windowCount={0} onOpen={open} />;

  const key = demo?.items[demoStep]?.key;
  return (
    <div className="console">
      <div className="sky-fixed" />
      <Backdrop sky={sky} />
      <header className="topbar">
        <button className="wordmark" onClick={() => setView("landing")} aria-label="Back to landing">ORBITGUARD</button>
        <nav className="tabs">
          {([["queue", "Events"], ["next24", "Next 24 h"], ["insights", "Insights"], ["evidence", "Results"]] as [View, string][]).map(([v, l]) => (
            <button key={v} className={view === v ? "on" : ""} onClick={() => setView(v)}>{l}</button>
          ))}
        </nav>
        <span style={{ flex: 1 }} />
        <div className="seg" role="group" aria-label="Data source">
          <button className={dataset === "test" ? "on" : ""} onClick={() => setDataset("test")}>Test dataset</button>
          <button className={dataset === "live" ? "on" : ""} onClick={() => setDataset("live")}>Live</button>
        </div>
        <button className={"btn" + (attn ? " attn" : "")} onClick={startTour}>Guided tour</button>
      </header>

      {dataset === "live" && (
        <div className="banner">
          Space-Track public feed: emergency-reportable conjunctions only, so all are high-risk by design · tiered by rule
          {summary?.snapshot?.latest_cdm_created ? ` · snapshot ${summary.snapshot.latest_cdm_created.slice(0, 16)} UTC` : summary?.generated_utc ? ` · snapshot ${summary.generated_utc}` : ""}
          {events.length === 0 && message ? ` · ${message}` : ""}
        </div>
      )}

      <main className={"main" + (mobileDetail ? " show-detail" : "")}>
        {demo && view === "queue" && <div className="spot-dim" />}
        {view === "queue" && (
          <>
            <Queue events={shown} message={message} loading={loading} selected={selected}
              onSelect={(id) => { setSelected(id); setMobileDetail(true); }}
              typeFilter={typeFilter} setTypeFilter={setTypeFilter}
              types={summary?.object_types ?? []} forecastFlag={summary?.forecast_flag} />
            <EventPage id={dataset === "live" && events.length === 0 ? null : selected} dataset={dataset}
              modelName={summary?.model?.name ?? null} sensNote={summary?.sensitivity_note} forecastFlag={summary?.forecast_flag}
              highlight={demo ? demoHighlight(key) : null} autoSim={key === "worst_consequence"} fleet={events}
              onBack={() => setMobileDetail(false)} />
          </>
        )}
        {view === "next24" && <Next24 events={events} summary={summary} onOpen={(id) => open(id)} />}
        {view === "insights" && <Insights events={events} onOpen={(id) => open(id)} />}
        {view === "evidence" && (
          <Results anchor={anchor} testIds={new Set(events.map((e) => e.event_id))} onOpen={(id) => open(id)} />
        )}
      </main>

      {welcome && (
        <div className="welcome-back" role="dialog" aria-modal="true" aria-label="Welcome">
          <div className="card welcome">
            <div className="label">Collision triage</div>
            <h2 className="display welcome-h">New here? Take the 60-second tour</h2>
            <div className="welcome-actions">
              <button className="btn primary big" onClick={begin} autoFocus>Start tour</button>
              <button className="btn big" onClick={explore}>Explore on my own</button>
            </div>
            <p className="small dim welcome-steps">Clear Critical → Caught early → Where it fails → If they collide</p>
          </div>
        </div>
      )}
      {demo && view === "queue" && (
        <DemoBar step={demoStep} setStep={setDemoStep} demo={demo} onExit={endTour}
          onFailures={() => { endTour(); setView("evidence"); setAnchor("where-it-fails"); }} />
      )}
    </div>
  );
}
