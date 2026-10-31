import { useMemo, useState } from "react";
import { EventLight, Summary } from "./api";
import { Ridges, Satellite, Dish } from "./Scene";
import { TIER_NAMES, TierIcon, fmtClock, fmtMiss } from "./ui";

function hash(n: number) {
  let x = (n + 1) * 2654435761;
  x ^= x >>> 15;
  x = Math.imul(x, 2246822519);
  x ^= x >>> 13;
  return ((x >>> 0) % 100000) / 100000;
}

function sampleSky(events: EventLight[]) {
  const crit = events.filter((e) => e.tier === 2);
  const rest = events.filter((e) => e.tier !== 2);
  const room = 60;
  const step = Math.max(1, rest.length / room);
  const picked: EventLight[] = [];
  for (let i = 0; i < rest.length && picked.length < room; i += step) picked.push(rest[Math.floor(i)]);
  return [...crit, ...picked];
}

/** Position in % of the sky, rejecting the no-fly ellipse behind the title, subtitle, hook and CTA. */
function skyPos(id: number) {
  const narrow = window.innerWidth < 700;
  const rx = narrow ? 80 : 36, cy = narrow ? 30 : 38, ry = narrow ? 26 : 30;
  for (let k = 0; k < 12; k++) {
    const x = 2 + hash(id + k * 131) * 96;
    const y = 3 + hash(id + 7919 + k * 977) * 55;
    const dx = (x - 50) / rx, dy = (y - cy) / ry;
    if (dx * dx + dy * dy > 1) return { x, y };
  }
  return { x: 2 + hash(id) * 96, y: narrow ? 52 + hash(id + 1) * 8 : 3 + hash(id + 1) * 6 };
}

interface Props {
  summary: Summary | null;
  events: EventLight[];
  clockDays: number;
  windowCount: number;
  onOpen: (id?: number) => void;
  offline?: boolean;
}

export default function Landing({ summary, events, clockDays, windowCount, onOpen, offline }: Props) {
  const [how, setHow] = useState(false);
  const [tip, setTip] = useState<{ e: EventLight; x: number; y: number } | null>(null);
  const sky = useMemo(() => sampleSky(events), [events]);
  const remaining = summary ? summary.max_time_to_tca - clockDays : 0;

  return (
    <div className="landing">
      <div className="sun" aria-hidden="true" />

      <div className="sky-lights">
        {sky.map((e) => {
          const { x, y } = skyPos(e.event_id);
          const h3 = hash(e.event_id + 104729), h4 = hash(e.event_id + 55);
          return (
            <button
              key={e.event_id}
              className={"light t" + e.tier}
              style={{
                left: `${x}%`,
                top: `${y}%`,
                ["--dx" as string]: `${(h3 - 0.5) * 7}vw`,
                ["--dy" as string]: `${(h4 - 0.5) * 5}vh`,
                animationDuration: `${70 + h3 * 80}s, ${40 + h4 * 50}s`,
                animationDelay: `${-h4 * 60}s, ${-h3 * 40}s`,
              }}
              aria-label={`Event ${e.event_id}, ${TIER_NAMES[e.tier]}`}
              onMouseEnter={(ev) => setTip({ e, x: ev.clientX, y: ev.clientY })}
              onFocus={(ev) => {
                const r = ev.currentTarget.getBoundingClientRect();
                setTip({ e, x: r.left, y: r.top });
              }}
              onMouseLeave={() => setTip(null)}
              onBlur={() => setTip(null)}
              onClick={() => onOpen(e.event_id)}
            >
              <span className="dot" />
            </button>
          );
        })}
      </div>
      {tip && (
        <div className="sky-tip" style={{ left: Math.min(tip.x + 12, window.innerWidth - 190), top: tip.y + 14 }}>
          <TierIcon tier={tip.e.tier} size={12} /> <b>{TIER_NAMES[tip.e.tier]}</b> · event {tip.e.event_id}
          <div className="mono dim">
            miss {fmtMiss(tip.e.latest.miss_distance)} · {tip.e.c_object_type.toLowerCase()}
          </div>
        </div>
      )}

      <div className="sat-drift" aria-hidden="true">
        <Satellite />
      </div>

      <div className="dish-mark" aria-hidden="true">
        <svg width="38" height="42" viewBox="-34 -82 68 86">
          <Dish x={0} y={0} s={1} />
        </svg>
      </div>

      <div className="hero">
        <h1>ORBITGUARD</h1>
        <svg className="arc-rule" viewBox="0 0 600 34" aria-hidden="true">
          <g fill="none" stroke="#fff" strokeLinecap="round">
            <path d="M20 28 H215 M385 28 H580" strokeWidth="1.4" opacity="0.75" />
            <path d="M215 28 Q300 -8 385 28" strokeWidth="2.6" />
          </g>
          <path d="M300 4 L302.2 10.4 L309 11 L303.6 14.8 L305.4 21.5 L300 17.6 L294.6 21.5 L296.4 14.8 L291 11 L297.8 10.4 Z" fill="#fff" />
        </svg>
        <div className="subtitle">COLLISION&nbsp;&nbsp;TRIAGE</div>
        <p className="hook">
          {summary ? (
            <>
              <b>{summary.total.toLocaleString()}</b> close approaches. <b>{summary.n_critical.toLocaleString()}</b> need a decision. You have two days.
            </>
          ) : offline ? (
            <>
              Live data is offline right now. The full walkthrough is in the{" "}
              <a className="hook-link" href="https://github.com/ryash072007/Autonomous-TripleT#readme" target="_blank" rel="noreferrer">README</a>.
            </>
          ) : (
            <span className="dim">Loading events...</span>
          )}
        </p>
        <div className="cta-row">
          <button className="cta" onClick={() => onOpen()}>
            Open the queue <span aria-hidden="true">→</span>
          </button>
          <button className="link-btn" onClick={() => setHow(true)}>
            How it works (40 s)
          </button>
        </div>
      </div>

      <Ridges />

      <div className="land-foot mono">
        <span>
          {summary?.model
            ? `Model: ${summary.model.name.replace(/\s*\(.*\)/, "")} · scored ${(summary.generated_utc ?? "").slice(0, 10)} · ${summary.dataset} dataset`
            : offline ? "Backend offline" : "Loading model info..."}
        </span>
        <span>Data: ESA CAC (CC BY 4.0)</span>
      </div>

      {how && <HowItWorks onClose={() => setHow(false)} onOpen={() => onOpen()} />}
    </div>
  );
}

function HowItWorks({ onClose, onOpen }: { onClose: () => void; onOpen: () => void }) {
  const [i, setI] = useState(0);
  const steps = [
    { h: "Read CDMs", p: "Every few hours a conjunction data message updates the predicted miss distance and collision probability for each close approach. Analysts read them one by one." },
    { h: "Estimate Pc and tier, with uncertainty", p: "Each event gets a Safe, Elevated or Critical tier from fixed operational thresholds, plus the rule that fired. Where the call is uncertain, the tool says so." },
    { h: "Analyst decides", p: "OrbitGuard never decides for you. You Accept, Escalate or Dismiss, with a note, and every action goes into a hash-chained audit trail." },
  ];
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label="How it works">
      <div className="card how">
        <div className="how-step mono">
          Step {i + 1} of 3
        </div>
        <h2>{steps[i].h}</h2>
        <p>{steps[i].p}</p>
        {i === 0 && (
          <p className="fact">
            <TierIcon tier={2} size={14} /> Why the 2-day mark matters: in exploratory analysis of the training data, 99 of 551 events that end Critical
            looked fine at T-2 days (exploratory figure from docs/PLAN.md; not yet from an evidence file).
          </p>
        )}
        <div className="how-actions">
          <button className="link-btn" onClick={onClose}>
            Skip
          </button>
          <span style={{ flex: 1 }} />
          {i > 0 && (
            <button className="btn" onClick={() => setI(i - 1)}>
              Back
            </button>
          )}
          {i < 2 ? (
            <button className="btn primary" onClick={() => setI(i + 1)}>
              Next
            </button>
          ) : (
            <button
              className="btn primary"
              onClick={() => {
                onClose();
                onOpen();
              }}
            >
              Open the queue →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
