import { Suspense, lazy, useEffect, useState } from "react";
import { EventLight, api } from "./api";
import { HarmScatter } from "./Consequence";
import { F10, Funnel, Obj, Reliability, Spaghetti, Strip, TC, TierFlow, sum } from "./InsightCharts";

const Globe = lazy(() => import("./Globe"));
export default function Insights({ events, onOpen }: { events: EventLight[]; onOpen: (id: number) => void }) {
  const [ins, setIns] = useState<{ available: boolean; content?: Obj; message?: string } | null>(null);
  useEffect(() => { api.insights().then(setIns).catch(() => setIns({ available: false })); }, []);
  const withOrbit = events.filter((e) => e.orbit_display);
  const d: Obj = ins?.content ?? {};
  const ab: Obj | undefined = d.altitude_band, ot: Obj | undefined = d.object_type_tier_test;
  const altRows = ab?.bins_km_target_perigee_height
    ? (ab.bins_km_target_perigee_height as string[]).map((b, i) => ({ band: b, counts: ab.test_current_tier_counts[i] as number[] })).filter((r) => sum(r.counts) > 0)
    : [];
  const typeRows = ot?.types ? (ot.types as string[]).map((t, i) => ({ object_type: t, counts: ot.counts[i] as number[] })) : [];
  return (
    <div className="page insights">
      <div className="label">Collision triage</div>
      <h2 className="display page-h">INSIGHTS</h2>
      <p className="dim">Every chart reads JSON written by a script; the source path is under each one.</p>
      <section className="card ins">
        <h3>The fleet, by altitude</h3>
        {withOrbit.length === 0 ? (
          <div className="empty">pending data: scored events have no orbit_display yet.</div>
        ) : (
          <>
            <p className="take">
              {(() => {
                const alts = withOrbit.map((e) => (e.orbit_display!.t.h_apo_km + e.orbit_display!.t.h_per_km) / 2);
                const bin = (lo: number, hi: number) => alts.filter((a) => a >= lo && a < hi).length;
                const best = [300, 400, 500, 600, 700, 800, 900, 1000].map((lo) => ({ lo, n: bin(lo, lo + 100) })).sort((a, b) => b.n - a.n)[0];
                return `${best.n} of ${withOrbit.length} events sit in the ${best.lo} to ${best.lo + 100} km band, the most crowded.`;
              })()}
            </p>
            <Suspense fallback={<div className="empty">Loading globe...</div>}>
              <Globe kind="fleet" events={withOrbit} onPick={onOpen} height={460} />
            </Suspense>
            <div className="legend small">
              Point = one test event at its altitude (exaggerated 3x), at a deterministic longitude and a latitude bounded by its inclination.
              <span style={{ color: TC[2] }}> ● Critical</span> <span style={{ color: TC[1] }}> ● Elevated</span> <span style={{ color: TC[0] }}> ● Safe</span>. Hover for id and altitude, click to open. Orbit data is display only.
            </div>
          </>
        )}
      </section>
      {!ins?.available && ins && <div className="banner soft">{ins.message ?? "pending data: insights.json not written yet"}</div>}
      <div className="ins-grid">
        <Funnel d={d} />
        <TierFlow d={d} />
        <Strip title="Altitude band and tier (test events)" path="altitude_band.test_current_tier_counts" label="band" rows={altRows}
          note="Bands by the target perigee height, display column only." />
        <Strip title="Object type and tier (test events)" path="object_type_tier_test.counts" label="object_type" rows={typeRows} />
        <Spaghetti d={d} />
        <Reliability d={d} />
        <F10 d={d} />
        <HarmScatter events={events} onOpen={onOpen} />
      </div>
    </div>
  );
}
