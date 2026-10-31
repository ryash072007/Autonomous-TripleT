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
  const room = Math.max(0, 400 - crit.length);
  const step = Math.max(1, rest.length / Math.max(room, 1));
  const picked: EventLight[] = [];
  for (let i = 0; i < rest.length && picked.length < room; i += step) picked.push(rest[Math.floor(i)]);
  return [...crit, ...picked];
}

interface Props {
  summary: Summary | null;
  events: EventLight[];
  clockDays: number;
  windowCount: number;
  onOpen: (id?: number) => void;
}

export default function Landing({ summary, events, clockDays, windowCount, onOpen }: Props) {
  const [how, setHow] = useState(false);
  const [tip, setTip] = useState<{ e: EventLight; x: number; y: number } | null>(null);
  const sky = useMemo(() => sampleSky(events), [events]);
  const remaining = summary ? summary.max_time_to_tca - clockDays : 0;

  return (
    <div className="landing">
      <div className="sun" aria-hidden="true" />

      <div className="sky-lights">
        {sky.map((e) => {
          const h1 = hash(e.event_id), h2 = hash(e.event_id + 7919), h3 = hash(e.event_id + 104729);
          return (
            <button
              key={e.event_id}
              className={"light" + (e.tier === 2 ? " crit" : "")}
              style={{
                left: `${2 + h1 * 94}%`,
                top: `${4 + h2 * 52}%`,
                ["--dx" as string]: `${(h3 - 0.5) * 9}vw`,
                animationDuration: `${50 + h3 * 70}s`,
                animationDelay: `${-h1 * 60}s`,
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
              <TierIcon tier={e.tier} size={e.tier === 2 ? 13 : 10} />
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
        <svg width="34" height="34" viewBox="-24 -44 48 52">
          <Dish x={0} y={0} s={0.9} />
        </svg>
      </div>

      <div className="hero">
        <h1>ORBITGUARD</h1>
        <svg className="arc-rule" viewBox="0 0 600 24" aria-hidden="true">
          <path d="M0 18 H250 M350 18 H600" stroke="var(--ink-soft)" strokeWidth="1.2" fill="none" />
          <path d="M250 18 Q300 -4 350 18" stroke="var(--ink-soft)" strokeWidth="1.2" fill="none" />
          <circle cx="300" cy="7" r="2.6" fill="var(--ink-soft)" />
        </svg>
        <div className="subtitle">COLLISION&nbsp;&nbsp;TRIAGE</div>
        <p className="hook">
          {summary ? (
            <>
              <b>{summary.total.toLocaleString()}</b> close approaches. <b>{summary.n_critical.toLocaleString()}</b> need a
              decision. You have two days.
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
          replay clock {summary ? fmtClock(remaining) : "--"} · {windowCount} event{windowCount === 1 ? "" : "s"} in the 24 h
          window
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
            Why the 2-day mark matters: in exploratory analysis of the training data, 99 of 551 events that end Critical
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
