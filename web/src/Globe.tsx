import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { feature } from "topojson-client";
import landTopo from "world-atlas/land-110m.json";
import type { EventLight } from "./api";

const RE = 6371;
const EXAG = 3; // altitude exaggeration so shells are visible
const radius = (altKm: number) => 1 + (EXAG * altKm) / RE;
const TIER_HEX = ["#2F7A68", "#C77A12", "#B0302A"];

export interface Orb { sma_km: number; ecc: number; inc_deg: number; h_apo_km?: number; h_per_km?: number }

type Ring = number[][];
let landCache: Float32Array | null = null;

function inRing(x: number, y: number, ring: Ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Sample a lat/lon grid and keep points on land (world-atlas 110m). Returns unit-sphere xyz. */
function landPoints(): Float32Array {
  if (landCache) return landCache;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const topo = landTopo as any;
  const fc = feature(topo, topo.objects.land) as unknown as { features?: any[]; geometry?: any };
  const geoms = fc.features ? fc.features.map((f) => f.geometry) : [fc.geometry];
  const polys: { rings: Ring[]; box: number[] }[] = [];
  for (const g of geoms) {
    const ps: Ring[][] = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    for (const rings of ps) {
      let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
      for (const [x, y] of rings[0]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
      polys.push({ rings, box: [x0, y0, x1, y1] });
    }
  }
  const out: number[] = [];
  const step = 2.4;
  for (let lat = -88; lat <= 88; lat += step) {
    const dl = step / Math.max(0.15, Math.cos((lat * Math.PI) / 180));
    for (let lon = -180; lon < 180; lon += dl) {
      let land = false;
      for (const p of polys) {
        const [x0, y0, x1, y1] = p.box;
        if (lon < x0 || lon > x1 || lat < y0 || lat > y1) continue;
        if (inRing(lon, lat, p.rings[0]) && !p.rings.slice(1).some((h) => inRing(lon, lat, h))) { land = true; break; }
      }
      if (land) {
        const a = (lat * Math.PI) / 180, b = (lon * Math.PI) / 180;
        out.push(Math.cos(a) * Math.sin(b), Math.sin(a), Math.cos(a) * Math.cos(b));
      }
    }
  }
  landCache = new Float32Array(out);
  return landCache;
}

function dotTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 32;
  const g = c.getContext("2d")!;
  g.beginPath(); g.arc(16, 16, 14, 0, 7); g.fillStyle = "#fff"; g.fill();
  return new THREE.CanvasTexture(c);
}

function markerTexture(fill: string, outline: string) {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  g.beginPath(); g.arc(32, 32, 26, 0, 7); g.fillStyle = outline; g.fill();
  g.beginPath(); g.arc(32, 32, 19, 0, 7); g.fillStyle = fill; g.fill();
  return new THREE.CanvasTexture(c);
}

function haloTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  g.beginPath(); g.arc(32, 32, 27, 0, 7); g.lineWidth = 6; g.strokeStyle = "#B0302A"; g.stroke();
  return new THREE.CanvasTexture(c);
}

function hash(n: number) {
  let x = (n + 1) * 2654435761;
  x ^= x >>> 15; x = Math.imul(x, 2246822519); x ^= x >>> 13;
  return ((x >>> 0) % 100000) / 100000;
}

/** Unit vectors p (conjunction point) and the in-plane orbit ring through p for inclination inc, branch sign. */
function ringBasis(p: THREE.Vector3, incDeg: number, sign: 1 | -1) {
  const lat = Math.asin(p.y);
  const inc = Math.min(incDeg, 180 - incDeg);
  const cosI = Math.cos((incDeg * Math.PI) / 180);
  const north = new THREE.Vector3(0, 1, 0);
  const u = north.clone().sub(p.clone().multiplyScalar(p.y)).normalize(); // north tangent at p
  const w = new THREE.Vector3().crossVectors(p, u); // east tangent
  const cl = Math.max(Math.cos(lat), 1e-3);
  const a = Math.max(-1, Math.min(1, cosI / cl));
  const b = sign * Math.sqrt(1 - a * a);
  void inc;
  const n = u.clone().multiplyScalar(a).add(w.clone().multiplyScalar(b)).normalize();
  const q = new THREE.Vector3().crossVectors(n, p).normalize();
  return { n, q };
}

function ringThrough(p: THREE.Vector3, incDeg: number, sign: 1 | -1, r: number) {
  const { q } = ringBasis(p, incDeg, sign);
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= 180; i++) {
    const t = (i / 180) * Math.PI * 2;
    pts.push(p.clone().multiplyScalar(Math.cos(t)).add(q.clone().multiplyScalar(Math.sin(t))).multiplyScalar(r));
  }
  return pts;
}

type Props =
  | { kind: "event"; id: number; t: Orb; c: Orb; tier: number; height?: number }
  | { kind: "collide"; onAffected?: (n: number, total: number) => void; id: number; t: Orb; c: Orb; tier: number; cloud: { t_hours: number[]; offsets: (number[] | null)[][]; band: [number, number] | null }; hours: number; fleet: EventLight[]; height?: number }
  | { kind: "fleet"; events: EventLight[]; onPick: (id: number) => void; height?: number };

export function orbAlt(o: { h_apo_km?: number; h_per_km?: number; sma_km: number }) {
  return o.h_apo_km != null && o.h_per_km != null ? (o.h_apo_km + o.h_per_km) / 2 : o.sma_km - RE;
}

export default function Globe(props: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<{ id: number; tier: number; alt: number; x: number; y: number } | null>(null);
  const [fail, setFail] = useState(false);
  const [lab, setLab] = useState<{ text: string; x: number; y: number } | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;
  const key = props.kind === "event" ? `e${props.id}` : props.kind === "collide" ? `c${props.id}` : `f${props.events.length}`;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setFail(true);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    el.appendChild(renderer.domElement);
    renderer.domElement.style.display = "block";
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
    camera.position.set(0, 0, props.kind === "event" || props.kind === "collide" ? 4.4 : 5.8);
    scene.add(new THREE.AmbientLight(0xffffff, 1.25));
    const sun = new THREE.DirectionalLight(0xffffff, 0.35);
    sun.position.set(-3, 2, 4);
    scene.add(sun);

    const root = new THREE.Group();
    scene.add(root);
    const earth = new THREE.Group();
    root.add(earth);
    earth.add(new THREE.Mesh(new THREE.SphereGeometry(0.995, 64, 48), new THREE.MeshBasicMaterial({ color: 0xf8e4cf })));
    const tex = dotTexture();
    const lp = new THREE.BufferGeometry();
    lp.setAttribute("position", new THREE.BufferAttribute(landPoints(), 3));
    earth.add(new THREE.Points(lp, new THREE.PointsMaterial({ color: 0xc08d78, size: 3.6, sizeAttenuation: false, map: tex, alphaTest: 0.4, transparent: true })));
    const atmo = new THREE.Mesh(
      new THREE.SphereGeometry(1.16, 48, 32),
      new THREE.ShaderMaterial({
        transparent: true, side: THREE.BackSide, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: "varying vec3 n; void main(){ n = normalize(normalMatrix*normal); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }",
        fragmentShader: "varying vec3 n; void main(){ float i = pow(0.72 - dot(n, vec3(0.0,0.0,1.0)), 3.0); gl_FragColor = vec4(1.0,0.74,0.55,1.0)*i*0.45; }",
      }),
    );
    scene.add(atmo);

    const disposables: { dispose(): void }[] = [tex, lp];
    let pulse: THREE.Mesh | null = null;
    let pulseRing: THREE.Mesh | null = null;
    let fleetPts: THREE.Points[] = [];
    let fleetIds: number[][] = [];
    const lines: THREE.Object3D[] = [];

    let frag: { geo: THREE.BufferGeometry; pos: Float32Array; p: THREE.Vector3; b: { n: THREE.Vector3; q: THREE.Vector3 }; r: number; n: number; times: number[]; off: (number[] | null)[][] } | null = null;
    let satPts: { sp: Float32Array; n: number; calm: { g: THREE.BufferGeometry; m: THREE.PointsMaterial }; hot: { g: THREE.BufferGeometry; m: THREE.PointsMaterial }; core: { g: THREE.BufferGeometry; m: THREE.PointsMaterial } } | null = null;
    let markers: { v: THREE.Vector3; text: string }[] = [];
    let lastCount = -1;

    if (props.kind === "event" || props.kind === "collide") {
      earth.rotation.y = hash(props.id) * Math.PI * 2;
      const incT = props.t.inc_deg, incC = props.c.inc_deg;
      const lat = (0.35 * Math.min(Math.min(incT, 180 - incT), Math.min(incC, 180 - incC)) * Math.PI) / 180;
      const p = new THREE.Vector3(0, Math.sin(lat), Math.cos(lat));
      const mk = (o: Orb, sign: 1 | -1, color: number) => {
        const g = new THREE.BufferGeometry().setFromPoints(ringThrough(p, o.inc_deg, sign, radius(orbAlt(o))));
        const m = new THREE.LineBasicMaterial({ color });
        const l = new THREE.Line(g, m);
        root.add(l);
        disposables.push(g, m);
        lines.push(l);
      };
      mk(props.t, 1, 0x5a3a33);
      mk(props.c, -1, 0xc77a12);
      const col = new THREE.Color(TIER_HEX[props.tier]);
      const rp = radius((orbAlt(props.t) + orbAlt(props.c)) / 2);
      const sg = new THREE.SphereGeometry(0.03, 16, 12);
      const sm = new THREE.MeshBasicMaterial({ color: col });
      pulse = new THREE.Mesh(sg, sm);
      pulse.position.copy(p).multiplyScalar(rp);
      root.add(pulse);
      const rg = new THREE.RingGeometry(0.04, 0.05, 32);
      const rm = new THREE.MeshBasicMaterial({ color: col, transparent: true, side: THREE.DoubleSide });
      pulseRing = new THREE.Mesh(rg, rm);
      pulseRing.position.copy(pulse.position);
      root.add(pulseRing);
      disposables.push(sg, sm, rg, rm);
      root.rotation.x = 0.25;

      if (props.kind === "collide") {
        const cl = props.cloud;
        const N = cl.offsets[0]?.length ?? 0;
        const bT = ringBasis(p, props.t.inc_deg, 1);
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(N * 3);
        geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        const fm = new THREE.PointsMaterial({ color: 0xb0302a, size: 6.5, sizeAttenuation: false, map: tex, alphaTest: 0.4, transparent: true, opacity: 0.9 });
        const fp = new THREE.Points(geo, fm);
        fp.frustumCulled = false;
        root.add(fp);
        disposables.push(geo, fm);
        geo.userData.mat = fm;
        frag = { geo, pos, p, b: bT, r: radius((orbAlt(props.t) + orbAlt(props.c)) / 2), n: N, times: cl.t_hours, off: cl.offsets };

        // markers for our satellite and the other object, placed on their own rings shortly before the conjunction
        const bC = ringBasis(p, props.c.inc_deg, -1);
        const mkMarker = (b: { q: THREE.Vector3 }, o: Orb, phase: number, tx: THREE.Texture, size: number) => {
          const r = radius(orbAlt(o));
          const v = p.clone().multiplyScalar(Math.cos(phase)).add(b.q.clone().multiplyScalar(Math.sin(phase))).multiplyScalar(r);
          const g = new THREE.BufferGeometry().setFromPoints([v]);
          const m = new THREE.PointsMaterial({ size, sizeAttenuation: false, map: tx, alphaTest: 0.3, transparent: true, depthTest: false });
          const pt = new THREE.Points(g, m);
          pt.renderOrder = 5;
          root.add(pt);
          disposables.push(g, m, tx);
          return v;
        };
        markers = [
          { v: mkMarker(bT, props.t, -0.22, markerTexture("#5A3A33", "#FFFFFF"), 21), text: "Our satellite" },
          { v: mkMarker(bC, props.c, 0.22, markerTexture("#C77A12", "#5A3A33"), 21), text: "The other object" },
        ];

        // satellites in the affected altitude band (other test events)
        const alt0 = (orbAlt(props.t) + orbAlt(props.c)) / 2;
        const lo = cl.band ? cl.band[0] : alt0 - 150, hi = cl.band ? cl.band[1] : alt0 + 150;
        const sats = props.fleet.filter((e) => e.orbit_display && orbAlt(e.orbit_display.t) >= lo && orbAlt(e.orbit_display.t) <= hi && e.event_id !== props.id).slice(0, 300);
        const sp = new Float32Array(sats.length * 3);
        sats.forEach((e, i) => {
          const od = e.orbit_display!;
          const inc = Math.min(od.t.inc_deg, 180 - od.t.inc_deg);
          const lat2 = Math.sin(hash(e.event_id + 11) * Math.PI * 2) * inc * (Math.PI / 180), lon2 = hash(e.event_id) * Math.PI * 2;
          const rr = radius(orbAlt(od.t));
          sp.set([rr * Math.cos(lat2) * Math.sin(lon2), rr * Math.sin(lat2), rr * Math.cos(lat2) * Math.cos(lon2)], i * 3);
        });
        const mkSet = (color: number, size: number, opacity: number, map: THREE.Texture) => {
          const g = new THREE.BufferGeometry();
          g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(sats.length * 3), 3));
          const m = new THREE.PointsMaterial({ color, size, sizeAttenuation: false, map, alphaTest: 0.2, transparent: true, opacity });
          const pt = new THREE.Points(g, m);
          pt.frustumCulled = false;
          root.add(pt);
          disposables.push(g, m);
          return { g, m, pt };
        };
        const halo = haloTexture();
        disposables.push(halo);
        const calm = mkSet(0x5b5f8f, 3.6, 0.35, tex);
        const hot = mkSet(0xb0302a, 13, 0.95, halo);
        const core = mkSet(0xffffff, 5.2, 1, tex);
        satPts = { sp, n: sats.length, calm, hot, core };
      }
    } else {
      root.rotation.x = 0.3;
      const groups: { pos: number[]; ids: number[]; color: THREE.Color; size: number }[] = [
        { pos: [], ids: [], color: new THREE.Color(TIER_HEX[0]), size: 3.2 },
        { pos: [], ids: [], color: new THREE.Color(TIER_HEX[1]), size: 3.8 },
        { pos: [], ids: [], color: new THREE.Color(TIER_HEX[2]), size: 6 },
      ];
      for (const e of props.events) {
        const od = (e as unknown as { orbit_display?: { t: Orb } }).orbit_display;
        if (!od) continue;
        const inc = Math.min(od.t.inc_deg, 180 - od.t.inc_deg);
        const lat = Math.sin(hash(e.event_id + 11) * Math.PI * 2) * inc * (Math.PI / 180);
        const lon = hash(e.event_id) * Math.PI * 2;
        const r = radius(orbAlt(od.t));
        const g = groups[e.tier];
        g.pos.push(r * Math.cos(lat) * Math.sin(lon), r * Math.sin(lat), r * Math.cos(lat) * Math.cos(lon));
        g.ids.push(e.event_id);
      }
      for (const g of groups) {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(g.pos), 3));
        const m = new THREE.PointsMaterial({ color: g.color, size: g.size, sizeAttenuation: false, map: tex, alphaTest: 0.4, transparent: true });
        const pts = new THREE.Points(geo, m);
        root.add(pts);
        fleetPts.push(pts);
        fleetIds.push(g.ids);
        disposables.push(geo, m);
      }
    }

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    let dragging = false, moved = 0, lx = 0, ly = 0, hover: number | null = null;
    const ray = new THREE.Raycaster();
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    ray.params.Points = { threshold: coarse ? 0.07 : 0.025 };
    let lastTap: number | null = null;
    const canvas = renderer.domElement;
    canvas.style.touchAction = "pan-y"; // vertical swipes scroll the page; horizontal drags rotate the globe
    canvas.style.cursor = "grab";
    const down = (e: PointerEvent) => { dragging = true; moved = 0; lx = e.clientX; ly = e.clientY; canvas.setPointerCapture(e.pointerId); canvas.style.cursor = "grabbing"; };
    const hoverAt = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      if (markers.length) {
        let found: { text: string; x: number; y: number } | null = null;
        for (const mk of markers) {
          const v = mk.v.clone();
          root.localToWorld(v);
          v.project(camera);
          const sx = ((v.x + 1) / 2) * rect.width, sy = ((1 - v.y) / 2) * rect.height;
          if (Math.hypot(sx - (e.clientX - rect.left), sy - (e.clientY - rect.top)) < (coarse ? 30 : 16)) found = { text: mk.text, x: sx, y: sy };
        }
        setLab(found);
        return;
      }
      if (!fleetPts.length) return;
      ray.setFromCamera(new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1), camera);
      let best: { id: number; tier: number; dist: number; alt: number } | null = null;
      fleetPts.forEach((pts, ti) => {
        for (const h of ray.intersectObject(pts)) {
          // ignore points on the far side of the Earth
          if (h.point.z < 0.15) continue;
          if (!best || h.distance < best.dist) best = { id: fleetIds[ti][h.index ?? 0], tier: ti, dist: h.distance, alt: (h.point.length() - 1) * RE / EXAG };
        }
      });
      hover = best ? (best as { id: number }).id : null;
      canvas.style.cursor = hover != null ? "pointer" : "grab";
      setTip(best ? { id: (best as { id: number }).id, tier: (best as { tier: number }).tier, alt: (best as { alt: number }).alt, x: e.clientX - rect.left, y: e.clientY - rect.top } : null);
    };
    const move = (e: PointerEvent) => {
      if (dragging) {
        const dx = e.clientX - lx, dy = e.clientY - ly;
        moved += Math.abs(dx) + Math.abs(dy);
        root.rotation.y += dx * 0.006;
        root.rotation.x = Math.max(-1.2, Math.min(1.2, root.rotation.x + dy * 0.006));
        lx = e.clientX; ly = e.clientY;
        setTip(null);
        return;
      }
      hoverAt(e);
    };
    const up = (e: PointerEvent) => {
      dragging = false;
      canvas.style.cursor = "grab";
      const pr = propsRef.current;
      if (moved >= 5) return;
      if (e.pointerType === "touch") {
        // tap equivalent of hover: first tap shows the label, a second tap on the same point opens it
        hoverAt(e);
        if (pr.kind === "fleet" && hover != null) {
          if (lastTap === hover) pr.onPick(hover);
          lastTap = hover;
        }
        return;
      }
      if (hover != null && pr.kind === "fleet") pr.onPick(hover);
    };
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointerleave", () => setTip(null));
    canvas.addEventListener("pointercancel", () => { dragging = false; });

    let raf = 0;
    const t0 = performance.now();
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const t = (performance.now() - t0) / 1000;
      if (!reduce && !dragging) root.rotation.y += 0.0016;
      if (frag && props.kind === "collide") {
        const hrs = (propsRef.current as { hours: number }).hours;
        const f = frag;
        const T = f.times;
        let k = 0;
        while (k < T.length - 2 && hrs > T[k + 1]) k++;
        const w = Math.max(0, Math.min(1, (hrs - T[k]) / (T[k + 1] - T[k])));
        for (let i = 0; i < f.n; i++) {
          const o0 = f.off[k][i], o1 = f.off[k + 1][i];
          const o = o1 && o0 ? [o0[0] + (o1[0] - o0[0]) * w, o0[1] + (o1[1] - o0[1]) * w, o0[2] + (o1[2] - o0[2]) * w] : o1 ?? o0;
          if (!o) { f.pos[i * 3] = f.pos[i * 3 + 1] = f.pos[i * 3 + 2] = 1e4; continue; }
          const ca = Math.cos(o[0]), sa = Math.sin(o[0]);
          const sq = (v: number, k: number) => k * Math.tanh(v / k); // compress far outliers so the cloud stays on screen
          const rr = f.r + (sq(o[1], 450) * EXAG) / RE, cross = (sq(o[2], 700) * EXAG) / RE;
          f.pos[i * 3] = f.p.x * ca * rr + f.b.q.x * sa * rr + f.b.n.x * cross;
          f.pos[i * 3 + 1] = f.p.y * ca * rr + f.b.q.y * sa * rr + f.b.n.y * cross;
          f.pos[i * 3 + 2] = f.p.z * ca * rr + f.b.q.z * sa * rr + f.b.n.z * cross;
        }
        (f.geo.attributes.position as THREE.BufferAttribute).needsUpdate = true;
        // fade the ember fragments as time passes
        const fm = frag.geo.userData.mat as THREE.PointsMaterial | undefined;
        if (fm) fm.opacity = 0.95 - 0.4 * Math.min(1, Math.log(hrs) / Math.log(168));
        if (satPts) {
          // a satellite is potentially affected when a sampled fragment passes within reach of it at this time
          const R2 = 0.11 * 0.11;
          let na = 0, nu = 0;
          const A = (satPts.hot.g.attributes.position as THREE.BufferAttribute).array as Float32Array;
          const U = (satPts.calm.g.attributes.position as THREE.BufferAttribute).array as Float32Array;
          for (let i = 0; i < satPts.n; i++) {
            const x = satPts.sp[i * 3], y = satPts.sp[i * 3 + 1], z = satPts.sp[i * 3 + 2];
            let hit = false;
            for (let j = 0; j < frag.n && !hit; j++) {
              const dx = frag.pos[j * 3] - x, dy = frag.pos[j * 3 + 1] - y, dz = frag.pos[j * 3 + 2] - z;
              if (dx * dx + dy * dy + dz * dz < R2) hit = true;
            }
            const T = hit ? A : U;
            const k = hit ? na++ : nu++;
            T[k * 3] = x; T[k * 3 + 1] = y; T[k * 3 + 2] = z;
          }
          satPts.hot.g.setDrawRange(0, na); satPts.core.g.setDrawRange(0, na); satPts.calm.g.setDrawRange(0, nu);
          (satPts.core.g.attributes.position as THREE.BufferAttribute).array.set(A.subarray(0, na * 3));
          (satPts.hot.g.attributes.position as THREE.BufferAttribute).needsUpdate = true;
          (satPts.core.g.attributes.position as THREE.BufferAttribute).needsUpdate = true;
          (satPts.calm.g.attributes.position as THREE.BufferAttribute).needsUpdate = true;
          satPts.hot.m.size = reduce ? 13 : 13 + 3 * Math.sin(t * 3.2);
          satPts.hot.m.opacity = reduce ? 0.95 : 0.7 + 0.3 * (0.5 + 0.5 * Math.sin(t * 3.2));
          if (na !== lastCount) { lastCount = na; (propsRef.current as { onAffected?: (n: number, t: number) => void }).onAffected?.(na, satPts.n); }
        }
      }
      if (pulse && pulseRing) {
        const k = reduce ? 1 : 1 + 0.35 * Math.sin(t * 3);
        pulse.scale.setScalar(k);
        const ph = reduce ? 0.5 : (t % 1.6) / 1.6;
        pulseRing.scale.setScalar(1 + ph * 3);
        (pulseRing.material as THREE.MeshBasicMaterial).opacity = 0.8 * (1 - ph);
        pulseRing.lookAt(camera.position.clone().applyMatrix4(root.matrixWorld.clone().invert()));
      }
      renderer.render(scene, camera);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [key]);

  if (fail) return <div className="empty">WebGL is not available in this browser.</div>;
  return (
    <div className="globe-wrap" style={{ height: props.height ?? 340 }}>
      <div ref={host} className="globe" />
      {lab && (
        <div className="sky-tip" style={{ position: "absolute", left: Math.min(lab.x + 12, 200), top: lab.y + 12 }}><b>{lab.text}</b></div>
      )}
      {tip && (
        <div className="sky-tip" style={{ position: "absolute", left: Math.min(tip.x + 10, 220), top: tip.y + 10 }}>
          <b>{["Safe", "Elevated", "Critical"][tip.tier]}</b> · event {tip.id}
          <div className="mono dim">altitude {tip.alt.toFixed(0)} km</div>
        </div>
      )}
    </div>
  );
}
