import { useMemo } from "react";
import { EventLight } from "./api";
import { Ridges } from "./Scene";

function hash(n: number) {
  let x = (n + 1) * 2654435761;
  x ^= x >>> 15;
  x = Math.imul(x, 2246822519);
  x ^= x >>> 13;
  return ((x >>> 0) % 100000) / 100000;
}

/** Fixed golden-hour scene behind the console: sky gradient, drifting tier lights, small ridges and the dish mound. */
export default function Backdrop({ sky }: { sky: EventLight[] }) {
  const dots = useMemo(() => sky.slice(0, 120), [sky]);
  return (
    <div className="backdrop" aria-hidden="true">
      <div className="sun" />
      {dots.map((e) => {
        const h3 = hash(e.event_id + 104729), h4 = hash(e.event_id + 55);
        return (
          <span
            key={e.event_id}
            className={"light t" + e.tier}
            style={{
              left: `${2 + hash(e.event_id) * 96}%`,
              top: `${3 + hash(e.event_id + 7919) * 70}%`,
              pointerEvents: "none",
              ["--dx" as string]: `${(h3 - 0.5) * 7}vw`,
              ["--dy" as string]: `${(h4 - 0.5) * 5}vh`,
              animationDuration: `${70 + h3 * 80}s, ${40 + h4 * 50}s`,
              animationDelay: `${-h4 * 60}s, ${-h3 * 40}s`,
            }}
          >
            <span className="dot" />
          </span>
        );
      })}
      <div className="ridges-small">
        <Ridges />
      </div>
    </div>
  );
}
