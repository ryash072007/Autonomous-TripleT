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

/** Wide low rocky mound with a flat plateau at 26.7% of its width for the dish. Returns ridgeline path pieces. */
function moundPath(seed: number, w: number, h: number) {
  const n = valueNoise(seed);
  const dishX = w * 0.267;
  const raw = (x: number) => {
    const t = x / w;
    const hill = Math.exp(-(((t - 0.3) / 0.26) ** 2)) * 0.75 + Math.exp(-(((t - 0.68) / 0.2) ** 2)) * 0.45;
    const edge = Math.pow(Math.max(0, Math.abs(t - 0.5) * 2 - 0.82) / 0.18, 2);
    const jag = (1 - Math.abs(2 * n(x / 22) - 1)) * 14 + (n(x / 7) - 0.5) * 7;
    return h - 14 - (h - 50) * hill - jag * (0.4 + hill) + 70 * edge;
  };
  const flat = raw(dishX);
  const y = (x: number) => {
    const d = Math.abs(x - dishX);
    if (d < 26) return flat;
    if (d < 60) { const t = (d - 26) / 34; return flat * (1 - t) + raw(x) * t; }
    return raw(x);
  };
  const pts: [number, number][] = [];
  for (let x = 0; x <= w; x += 4) pts.push([x, y(x)]);
  const line = pts.map(([x, yy]) => `${x},${yy.toFixed(1)}`).join(" L");
  const shade = pts.map(([x, yy]) => `${x},${(yy + 26 + (n(x / 30) * 14)).toFixed(1)}`).join(" L");
  const facets = pts.filter((_, i) => i % 9 === 4).map(([x, yy]) => `M${x},${yy.toFixed(1)} l${(18 + n(x) * 30).toFixed(0)},${(40 + n(x + 3) * 30).toFixed(0)}`).join(" ");
  return {
    d: `M0,${h} L${line} L${w},${h} Z`,
    shade: `M0,${h} L${shade} L${w},${h} Z`,
    facets,
    dishY: flat,
  };
}

export function Dish({ x, y, s = 1 }: { x: number; y: number; s?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} strokeLinecap="round" strokeLinejoin="round">
      <path d="M-13 0 L-5 -36 H5 L13 0 Z" fill="#3E2722" />
      <rect x="-16" y="-3" width="32" height="4" fill="#3E2722" />
      <g transform="translate(0 -38) rotate(-38)">
        <path d="M-28 -8 Q0 22 28 -8 Z" fill="#3E2722" />
        <path d="M-28 -8 Q0 22 28 -8" fill="none" stroke="#7a5246" strokeWidth="1.6" />
        <ellipse cx="0" cy="-8" rx="28" ry="5.5" fill="#8a5c4e" stroke="#3E2722" strokeWidth="1.5" />
        <path d="M-26 -8 L0 -40 M26 -8 L0 -40" fill="none" stroke="#3E2722" strokeWidth="1.5" />
        <rect x="-3.5" y="-45" width="7" height="7" rx="1.5" fill="#3E2722" />
      </g>
      <circle cx="0" cy="-38" r="4" fill="#3E2722" />
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
  const mound = useMemo(() => moundPath(5, 1000, 200), []);
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
      <svg className="mound" viewBox="0 0 1000 200" preserveAspectRatio="none">
        <defs>
          <linearGradient id="mg" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#6A443A" />
            <stop offset="1" stopColor="#5A3A33" />
          </linearGradient>
        </defs>
        <path d={mound.d} fill="url(#mg)" />
        <path d={mound.facets} stroke="rgba(255,225,200,0.10)" strokeWidth="2" fill="none" />
        <path d={mound.shade} fill="#44292A" opacity="0.8" />
      </svg>
      <svg className="mound-dish" viewBox="-60 -110 120 120" aria-hidden="true">
        <Dish x={0} y={0} s={1} />
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
