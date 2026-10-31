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

function valueNoise(seed: number) {
  const r = rng(seed);
  const tab = Array.from({ length: 256 }, () => r());
  return (x: number) => {
    const i = Math.floor(x), f = x - i;
    const u = f * f * (3 - 2 * f);
    return tab[((i % 256) + 256) % 256] * (1 - u) + tab[(((i + 1) % 256) + 256) % 256] * u;
  };
}

/** Jagged ridgeline: ridged fractal noise (sharp peaks) plus a few seeded cliffs. Deterministic per seed. */
function ridgePath(seed: number, w: number, h: number, base: number, amp: number, rough = 0.6, cliffs = 3) {
  const n = valueNoise(seed);
  const r = rng(seed * 7 + 1);
  const steps = Array.from({ length: cliffs }, () => ({ x: 100 + r() * (w - 200), dy: (r() - 0.5) * amp * 0.7 }));
  const y = (x: number) => {
    let ridged = 0, smooth = 0, a = 0.5, f = x / 260;
    for (let o = 0; o < 6; o++) {
      const v = n(f + o * 31.7);
      ridged += a * (1 - Math.abs(2 * v - 1));
      smooth += a * v;
      a *= 0.52 + rough * 0.1;
      f *= 2.05;
    }
    let v = base - amp * (rough * ridged + (1 - rough) * smooth) * 1.15;
    for (const s of steps) v -= s.dy * Math.max(0, Math.min(1, (x - s.x) / 10 + 0.5));
    return v;
  };
  const pts: string[] = [];
  for (let x = 0; x <= w; x += 5) pts.push(`${x},${y(x).toFixed(1)}`);
  return { d: `M0,${h} L${pts.join(" L")} L${w},${h} Z`, y };
}

/** Dark rocky foreground mound with a flat spot at dishX for the ground-station dish. */
function moundPath(seed: number, w: number, h: number, cx: number, dishX: number) {
  const n = valueNoise(seed);
  const raw = (x: number) => {
    const bump = Math.exp(-(((x - cx) / (w * 0.3)) ** 2));
    const edge = Math.max(0, Math.abs(x - w / 2) / (w / 2) - 0.6) / 0.4;
    return h - 30 - (h - 90) * bump + (n(x / 14) - 0.5) * 26 * (0.4 + bump) + (n(x / 5) - 0.5) * 8 + 90 * edge * edge;
  };
  const flatY = raw(dishX);
  const y = (x: number) => {
    const d = Math.abs(x - dishX);
    if (d < 38) return flatY;
    if (d < 80) { const t = (d - 38) / 42; return flatY * (1 - t) + raw(x) * t; }
    return raw(x);
  };
  const pts: string[] = [];
  for (let x = 0; x <= w; x += 4) pts.push(`${x},${y(x).toFixed(1)}`);
  return { d: `M0,${h} L${pts.join(" L")} L${w},${h} Z`, dishY: flatY };
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
      { id: "r0", top: "#E9CDB6", ...ridgePath(3, W, 300, 150, 80, 0.5, 2), op: 0.8 },
      { id: "r1", top: "var(--ridge-far)", ...ridgePath(11, W, 300, 185, 100, 0.6, 3), op: 0.92 },
      { id: "r2", top: "var(--ridge-mid)", ...ridgePath(23, W, 300, 225, 110, 0.7, 4), op: 1 },
      { id: "r3", top: "var(--ridge-near)", ...ridgePath(37, W, 300, 262, 95, 0.75, 4), op: 1 },
    ];
  }, []);
  const mound = useMemo(() => moundPath(5, 640, 260, 250, 270), []);
  return (
    <div className="ridges" aria-hidden="true">
      {layers.map((l, i) => (
        <svg key={l.id} className={"ridge L" + i} viewBox="0 0 1600 300" preserveAspectRatio="xMidYMax slice">
          <defs>
            <linearGradient id={l.id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={l.top} />
              <stop offset="1" stopColor="#F8E4CF" stopOpacity={i < 3 ? 0.9 : 0.3} />
            </linearGradient>
          </defs>
          <path d={l.d} fill={`url(#${l.id})`} opacity={l.op} />
        </svg>
      ))}
      <svg className="ridge mound" viewBox="0 0 640 260" preserveAspectRatio="xMidYMax meet">
        <path d={mound.d} fill="var(--rock)" />
        <Dish x={270} y={mound.dishY + 3} s={1.5} />
      </svg>
    </div>
  );
}

/** Thin ridge strip kept at the bottom of the console. */
export function RidgeStrip() {
  const d = useMemo(() => ridgePath(5, 1600, 60, 56, 40, 0.7, 2).d, []);
  return (
    <svg className="ridge-strip" viewBox="0 0 1600 60" preserveAspectRatio="none" aria-hidden="true">
      <path d={d} fill="var(--ridge-mid)" opacity="0.55" />
    </svg>
  );
}
