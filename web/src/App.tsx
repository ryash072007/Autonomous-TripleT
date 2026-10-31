import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dataset, DemoResp, EventLight, Summary, api } from "./api";
import Landing from "./Landing";
import Queue from "./Queue";
import EventPage from "./EventPage";
import Backdrop from "./Backdrop";
import { DemoBar, demoHighlight } from "./Panels";
import { useSnapshotMode } from "./ui";
import { snapshotForced } from "./api";
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
  const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [mobileDetail, setMobileDetail] = useState(() => /[#&]e=\d+/.test(window.location.hash)); // deep link to an event
  const [typeFilter, setTypeFilter] = useState<string | null>(null);


  const [demo, setDemo] = useState<DemoResp | null>(null);
  const [demoStep, setDemoStep] = useState(0);
  const [anchor, setAnchor] = useState<string | null>(null);
  const [sky, setSky] = useState<EventLight[]>([]);
  const [fullFor, setFullFor] = useState<Dataset | null>(null);
  const tourTried = useRef(false);
  const snap = useSnapshotMode();
  const [menuOpen, setMenuOpen] = useState(false);
  const [tourHidden, setTourHidden] = useState(false);
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
  }, [dataset, reload]);

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
  }, [view, dataset, fullFor, reload]);


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
      d.items.forEach((it) => { api.event(it.event_id, dataset).catch(() => {}); api.brief(it.event_id, dataset).catch(() => {}); }); // warm the cache so steps switch instantly
      setDemo(d);
      setDemoStep(0);
      setTourHidden(false);
      setMenuOpen(false);
      setView("queue");
      setMobileDetail(true);
    } catch {
      /* tour unavailable */
    }
  }, [dataset]);
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
    if (!demo || tourHidden) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA") return;
      if (e.key === "Escape") endTour();
      else if (e.key === "ArrowRight") setDemoStep((x) => Math.min(demo.items.length - 1, x + 1));
      else if (e.key === "ArrowLeft") setDemoStep((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [demo, tourHidden]);

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

  const snapBadge = snap ? <div className="snap-badge" role="status">{snapshotForced() ? "Showing a saved snapshot" : "Showing a saved snapshot (backend offline)"} · read-only</div> : null;

  if (view === "landing") return <>{snapBadge}<Landing summary={summary} events={sky} clockDays={0} windowCount={0} onOpen={open} offline={apiErr} /></>;

  const key = demo?.items[demoStep]?.key;
  return (
    <div className={"console" + (demo && !tourHidden ? " touring" : "")}>
      {snapBadge}
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
        <button className={"btn tour-btn" + (attn ? " attn" : "")} onClick={startTour}>Guided tour</button>
        <button className={"menu-btn" + (attn ? " attn" : "")} aria-label="Menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((o) => !o)}>{menuOpen ? "✕" : "☰"}</button>
      </header>
      {menuOpen && (
        <div className="menu-sheet card" role="menu">
          {([["queue", "Events"], ["next24", "Next 24 h"], ["insights", "Insights"], ["evidence", "Results"]] as [View, string][]).map(([v, l]) => (
            <button key={v} className={"menu-item" + (view === v ? " on" : "")} onClick={() => { setView(v); setMenuOpen(false); if (v === "queue") setMobileDetail(false); }}>{l}</button>
          ))}
          <div className="seg menu-seg" role="group" aria-label="Data source">
            <button className={dataset === "test" ? "on" : ""} onClick={() => { setDataset("test"); setMenuOpen(false); }}>Test dataset</button>
            <button className={dataset === "live" ? "on" : ""} onClick={() => { setDataset("live"); setMenuOpen(false); }}>Live</button>
          </div>
          <button className="menu-item primary" onClick={startTour}>Guided tour</button>
        </div>
      )}

      {dataset === "live" && (
        <div className="banner">
          Space-Track public feed: emergency-reportable conjunctions only, so all are high-risk by design · tiered by rule
          {summary?.snapshot?.latest_cdm_created ? ` · snapshot ${summary.snapshot.latest_cdm_created.slice(0, 16)} UTC` : summary?.generated_utc ? ` · snapshot ${summary.generated_utc}` : ""}
          {events.length === 0 && message ? ` · ${message}` : ""}
        </div>
      )}

      {apiErr && (
        <main className="main offline-main">
          <div className="card offline">
            <div className="label">Backend offline</div>
            <h2 className="display offline-h">CANNOT REACH THE DATA SERVER</h2>
            <p>The console needs the OrbitGuard API, and it is not answering right now. It may be restarting, or the host machine may be off.</p>
            <p className="small dim">The full walkthrough, with screenshots, is in the <a href="https://github.com/ryash072007/Autonomous-TripleT#readme" target="_blank" rel="noreferrer">README</a>.</p>
            <button className="btn primary" onClick={() => { setApiErr(false); setReload((n) => n + 1); }}>Retry</button>
          </div>
        </main>
      )}
      <main className={"main" + (mobileDetail ? " show-detail" : "")} style={apiErr ? { display: "none" } : undefined}>
                {view === "queue" && (
          <>
            <Queue events={shown} message={message} loading={loading} selected={selected}
              onSelect={(id) => { setSelected(id); setMobileDetail(true); }}
              typeFilter={typeFilter} setTypeFilter={setTypeFilter}
              types={summary?.object_types ?? []} forecastFlag={summary?.forecast_flag} />
            <EventPage id={dataset === "live" && events.length === 0 ? null : selected} dataset={dataset}
              modelName={summary?.model?.name ?? null} sensNote={summary?.sensitivity_note} forecastFlag={summary?.forecast_flag}
              highlight={demo && !tourHidden ? demoHighlight(key) : null} autoSim={key === "worst_consequence"} fleet={events}
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
        <div className="welcome-mini card" role="dialog" aria-label="Tour offer">
          <div className="label">Collision triage</div>
          <div className="display welcome-q">Take the 60-second tour?</div>
          <p className="small dim">Clear Critical → Caught early → Where it fails → If they collide</p>
          <div className="welcome-actions">
            <button className="btn primary" onClick={begin} autoFocus>Start</button>
            <button className="btn" onClick={explore}>No thanks</button>
          </div>
        </div>
      )}
      {demo && view === "queue" && (
        <DemoBar step={demoStep} setStep={setDemoStep} demo={demo} onExit={endTour} hidden={tourHidden} setHidden={setTourHidden}
          onFailures={() => { endTour(); setView("evidence"); setAnchor("where-it-fails"); }} />
      )}
    </div>
  );
}
