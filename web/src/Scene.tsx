import { useMemo } from "react";

function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Ridge silhouette as a closed path: sum of sines with seeded phases. flat = [x0,x1] forces a plateau. */
function ridgePath(seed: number, w: number, h: number, base: number, amp: number, flat?: [number, number]) {
  const r = rng(seed);
  const waves = Array.from({ length: 5 }, (_, i) => ({
    f: (i + 1) * 0.0035 * (0.7 + r() * 0.6),
    p: r() * 6.28,
    a: amp / (1 + i * 0.9),
  }));
  const y = (x: number) => {
    let v = base;
    for (const k of waves) v -= k.a * (0.5 + 0.5 * Math.sin(x * k.f + k.p));
    return v;
  };
  const pts: string[] = [];
  const plateau = flat ? y(flat[0]) : 0;
  for (let x = 0; x <= w; x += 20) {
    let yy = y(x);
    if (flat && x >= flat[0] - 60 && x <= flat[1] + 60) {
      const edge = Math.max(0, Math.min(1, (60 - Math.max(flat[0] - x, x - flat[1], 0)) / 60));
      yy = flat[0] <= x && x <= flat[1] ? plateau : yy * (1 - edge) + plateau * edge;
    }
    pts.push(`${x},${yy.toFixed(1)}`);
  }
  return { d: `M0,${h} L${pts.join(" L")} L${w},${h} Z`, plateauY: plateau };
}

export function Dish({ x, y, s = 1 }: { x: number; y: number; s?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} fill="none" stroke="var(--rock)" strokeWidth="3" strokeLinecap="round">
      <path d="M-14 0 L0 -34 L14 0" />
      <path d="M-18 0 H18" strokeWidth="4" />
      <g transform="translate(0 -34) rotate(-38)">
        <path d="M-34 -6 Q0 22 34 -6" fill="var(--rock)" stroke="none" opacity="0.92" />
        <path d="M-34 -6 Q0 22 34 -6" />
        <path d="M0 8 V-26 M-5 -26 H5" />
      </g>
    </g>
  );
}

export function Satellite({ size = 96, stroke = "var(--rock)" }: { size?: number; stroke?: string }) {
  return (
    <svg width={size} height={size * 0.45} viewBox="0 0 120 54" fill="none" stroke={stroke} strokeWidth="1.8" aria-hidden="true">
      <rect x="46" y="16" width="28" height="22" rx="2" />
      <path d="M46 27 H34 M74 27 H86" />
      <rect x="4" y="12" width="30" height="30" />
      <path d="M14 12 V42 M24 12 V42 M4 27 H34" />
      <rect x="86" y="12" width="30" height="30" />
      <path d="M96 12 V42 M106 12 V42 M86 27 H116" />
      <path d="M60 16 V8 M54 8 H66" />
      <circle cx="60" cy="27" r="4" />
    </svg>
  );
}

export function Ridges() {
  const layers = useMemo(() => {
    const W = 1600;
    return [
      { cls: "far", fill: "var(--ridge-far)", ...ridgePath(3, W, 300, 150, 70) },
      { cls: "mid", fill: "var(--ridge-mid)", ...ridgePath(11, W, 300, 190, 90) },
      { cls: "near", fill: "var(--ridge-near)", ...ridgePath(23, W, 300, 250, 85, [180, 330]) },
    ];
  }, []);
  return (
    <div className="ridges" aria-hidden="true">
      {layers.map((l) => (
        <svg
          key={l.cls}
          className={"ridge " + l.cls}
          viewBox="0 0 1600 300"
          preserveAspectRatio={l.cls === "near" ? "xMinYMax slice" : "xMidYMax slice"}
        >
          <path d={l.d} fill={l.fill} />
          {l.cls === "near" && <Dish x={255} y={l.plateauY + 2} s={1.15} />}
        </svg>
      ))}
    </div>
  );
}

/** Thin ridge strip kept at the bottom of the console. */
export function RidgeStrip() {
  const d = useMemo(() => ridgePath(5, 1600, 60, 48, 34).d, []);
  return (
    <svg className="ridge-strip" viewBox="0 0 1600 60" preserveAspectRatio="none" aria-hidden="true">
      <path d={d} fill="var(--ridge-mid)" opacity="0.55" />
    </svg>
  );
}
