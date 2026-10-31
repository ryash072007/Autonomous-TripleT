export type Dataset = "test" | "live";

export interface Latest {
  time_to_tca: number;
  miss_distance: number;
  risk: number | null;
  max_risk_estimate: number;
  relative_position_r: number | null;
  relative_position_t: number | null;
  relative_position_n: number | null;
  relative_speed: number | null;
  c_sigma_r: number | null;
  t_sigma_r: number | null;
  F10?: number | null;
  AP?: number | null;
}

export interface Cdm {
  time_to_tca: number;
  miss_distance: number;
  risk: number | null;
  max_risk_estimate: number;
  relative_position_r: number | null;
  relative_position_t: number | null;
  relative_position_n: number | null;
  relative_speed: number | null;
  c_sigma_r: number | null;
  t_sigma_r: number | null;
}

export interface Sens { feature: string; from: number; to: number; tier: number }

export interface OrbitD { sma_km: number; ecc: number; inc_deg: number; h_apo_km: number; h_per_km: number }

export interface EventLight {
  event_id: number;
  c_object_type: string;
  n_cdms: number;
  latest: Latest;
  tier: number;
  tier_name: string;
  p_tier: number[] | null;
  tier_set: number[];
  abstain: boolean;
  rule: string;
  forecast_tier_at_tca: number | null;
  p_forecast: number[] | null;
  recommendation: string | null;
  recommendation_reason?: string | null;
  orbit_display?: { t: OrbitD; c: OrbitD } | null;
  flags: string[];
  sensitivity?: { down: Sens | null; up: Sens | null } | null;
  names?: { t: string | null; c: string | null } | null;
  cdm_id?: string;
  created?: string;
  remaining_days?: number;
  dangerous?: boolean;
}

export interface EventFull extends EventLight {
  cdms: Cdm[];
}

export interface Summary {
  dataset: Dataset;
  total: number;
  counts: Record<string, number>;
  n_critical: number;
  n_abstain: number;
  model: { name: string; version: string; trained_utc: string | null } | null;
  generated_utc: string | null;
  has_model_probs: boolean;
  max_time_to_tca: number;
  min_time_to_tca: number;
  object_types: string[];
  message: string | null;
  sensitivity_note?: string | null;
  forecast_flag?: { t_critical: number; critical_recall_cv: number; source: string } | null;
  snapshot?: { source: string; latest_cdm_created: string | null; n_cdms: number } | null;
}

export interface WindowResp {
  elapsed_days: number;
  n: number;
  n_dangerous: number;
  events: EventLight[];
}

export interface ScoreResp {
  tier: number;
  tier_name: string;
  rule: string;
  p_tier: number[] | null;
  tier_set: number[];
  source: string;
}

export interface AuditRec {
  seq: number;
  ts: string;
  event_id: number;
  action: string;
  note: string;
  tier_name: string | null;
  model: string | null;
  prev_hash: string;
  hash: string;
}

export interface DemoResp {
  provisional: boolean;
  items: { key: string; event_id: number; reason: string }[];
}

export interface EvidenceResp {
  files: { file: string; name: string; content: unknown }[];
}

const RAW_BASE = ((import.meta.env.VITE_API_BASE as string | undefined) ?? "").trim();
const onLocalhost = typeof window !== "undefined" && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
/** Snapshot is forced with VITE_API_BASE=snapshot, or when no backend is configured and we are not on localhost. */
const FORCED = RAW_BASE === "snapshot" || (RAW_BASE === "" && !onLocalhost);
export const BASE = RAW_BASE === "snapshot" ? "" : RAW_BASE.replace(/\/$/, "");

// ---- data source: the live API, or the read-only snapshot under /snapshot ----
type Mode = "api" | "snapshot";
let mode: Mode = FORCED ? "snapshot" : "api";
let retryTimer: number | undefined;
const listeners = new Set<(m: Mode) => void>();
const setMode = (m: Mode) => { if (m !== mode) { mode = m; listeners.forEach((f) => f(m)); } };

export function onMode(cb: (m: Mode) => void): () => void {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}
export const isSnapshot = () => mode === "snapshot";
export const snapshotForced = () => FORCED;

async function timed(url: string, init: RequestInit | undefined, timeoutMs: number): Promise<Response> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: ctl.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** Re-try the API every 60 s while on the snapshot; switch back silently when it answers. */
function startRetry() {
  if (FORCED || retryTimer != null) return;
  retryTimer = window.setInterval(async () => {
    try {
      const r = await timed(BASE + "/api/health", undefined, 5000);
      if (r.ok) {
        setMode("api");
        window.clearInterval(retryTimer);
        retryTimer = undefined;
      }
    } catch { /* still offline */ }
  }, 60000);
}

// The first read waits for one reachability check (8 s at most); everything after follows the chosen mode.
const ready: Promise<void> = FORCED
  ? Promise.resolve()
  : (async () => {
      try {
        const r = await timed(BASE + "/api/health", undefined, 8000);
        if (!r.ok) throw new Error("health " + r.status);
      } catch {
        mode = "snapshot";
        listeners.forEach((f) => f("snapshot"));
        startRetry();
      }
    })();

async function req<T>(path: string, init?: RequestInit, timeoutMs = 30000): Promise<T> {
  const r = await timed(BASE + path, init, timeoutMs);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return (await r.json()) as T;
}

const sjson = async <T,>(rel: string): Promise<T> => {
  const r = await fetch(`/snapshot/${rel}`);
  if (!r.ok) throw new Error(`snapshot ${r.status} ${rel}`);
  return (await r.json()) as T;
};

/** Read from the API, or from the snapshot when offline. A network failure mid-session also flips to the snapshot. */
async function read<T>(apiPath: string, snap: () => Promise<T>, timeoutMs = 30000): Promise<T> {
  await ready;
  if (mode === "snapshot") return snap();
  try {
    return await req<T>(apiPath, undefined, timeoutMs);
  } catch (e) {
    if (e instanceof Error && /^\d{3} /.test(e.message) && !/^5\d\d /.test(e.message)) throw e; // a real 4xx from a live API
    setMode("snapshot");
    startRetry();
    return snap();
  }
}

const q = (o: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v != null && v !== "" && p.set(k, String(v)));
  const s = p.toString();
  return s ? "?" + s : "";
};

const LIVE_MSG = "Live needs the backend";
const chunkCache = new Map<string, Promise<Record<string, unknown>>>();
async function fromChunk<T>(kind: "events" | "briefs", id: number): Promise<T> {
  const index = await (chunkCache.get("index") ?? chunkCache.set("index", sjson<Record<string, unknown>>("index.json")).get("index")!);
  const k = index[String(id)];
  if (k == null) throw new Error("404 event not found");
  const key = `${kind}/${k}`;
  const chunk = await (chunkCache.get(key) ?? chunkCache.set(key, sjson<Record<string, unknown>>(`${kind}/${k}.json`)).get(key)!);
  return chunk[String(id)] as T;
}

const emptyLive: Summary = {
  dataset: "live", total: 0, counts: { Safe: 0, Elevated: 0, Critical: 0 }, n_critical: 0, model: null, generated_utc: null,
  has_model_probs: false, max_time_to_tca: 0, min_time_to_tca: 0, object_types: [], message: LIVE_MSG, n_abstain: 0,
};

/** Same thresholds and wording as ca_triage/tiers.py (tier, rule_fired). Used for what-if scoring when offline. */
function ruleScore(miss: number, risk: number): ScoreResp {
  const km = (miss / 1000).toFixed(2);
  let tier = 0, rule: string;
  if (risk >= -4 || miss < 1000) {
    tier = 2;
    rule = risk >= -4 ? `Critical: Pc = 1e${risk.toFixed(2)} >= 1e-4` : `Critical: miss distance ${km} km < 1.0 km`;
  } else if (risk >= -6 || miss <= 5000) {
    tier = 1;
    rule = risk >= -6 ? `Elevated: 1e-6 <= Pc = 1e${risk.toFixed(2)} < 1e-4` : `Elevated: miss distance ${km} km within 1.0-5.0 km`;
  } else {
    rule = `Safe: Pc = 1e${risk.toFixed(2)} < 1e-6 and miss distance ${km} km > 5.0 km`;
  }
  return { tier, tier_name: ["Safe", "Elevated", "Critical"][tier], rule, p_tier: null, tier_set: [tier], source: "rule (offline snapshot)" };
}

export const api = {
  summary: (dataset: Dataset) =>
    read<Summary>("/api/summary" + q({ dataset }), () => (dataset === "live" ? Promise.resolve(emptyLive) : sjson<Summary>("summary.json")), 8000),
  brief: (id: number, dataset: Dataset) =>
    read<{ text: string; source: string; fallback_reason: string | null }>(`/api/events/${id}/brief` + q({ dataset }), () =>
      dataset === "live" ? Promise.reject(new Error("404")) : fromChunk("briefs", id)),
  events: (dataset: Dataset, tier?: number | null, object_type?: string | null, fields?: string) =>
    read<{ events: EventLight[]; message: string | null }>("/api/events" + q({ dataset, tier, object_type, fields }), () =>
      dataset === "live" ? Promise.resolve({ events: [], message: LIVE_MSG }) : sjson(fields === "sky" ? "sky.json" : "events.json")),
  event: (id: number, dataset: Dataset) =>
    read<EventFull>(`/api/events/${id}` + q({ dataset }), () => (dataset === "live" ? Promise.reject(new Error("404")) : fromChunk("events", id))),
  window: (elapsed_days: number, dataset: Dataset) =>
    read<WindowResp>("/api/window" + q({ elapsed_days: elapsed_days.toFixed(3), dataset }), () => Promise.reject(new Error("window needs the backend"))),
  score: async (body: { miss_distance: number; max_risk_estimate: number }): Promise<ScoreResp> => {
    await ready;
    if (mode === "snapshot") return ruleScore(body.miss_distance, body.max_risk_estimate);
    return req<ScoreResp>("/api/score", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  },
  insights: () =>
    read<{ available: boolean; message?: string; file?: string; content?: Record<string, unknown> }>("/api/insights", () => sjson("insights.json")),
  evidence: () => read<EvidenceResp>("/api/evidence", () => sjson("evidence.json")),
  demo: () => read<DemoResp>("/api/demo", () => sjson("demo.json")),
  audit: async (event_id?: number): Promise<{ records: AuditRec[]; chain_ok: boolean }> => {
    await ready;
    if (mode === "snapshot") return { records: [], chain_ok: true };
    return req("/api/audit" + q({ event_id }));
  },
  postAudit: async (event_id: number, action: string, note: string, dataset: Dataset): Promise<AuditRec> => {
    await ready;
    if (mode === "snapshot") throw new Error("Decisions are logged by the backend; offline snapshot is read-only");
    return req<AuditRec>("/api/audit" + q({ dataset }), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event_id, action, note }),
    });
  },
};
