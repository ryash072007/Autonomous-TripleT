export type Dataset = "test" | "live";

export interface Latest {
  time_to_tca: number;
  miss_distance: number;
  risk: number | null;
  max_risk_estimate: number;
  relative_position_r: number;
  relative_position_t: number;
  relative_position_n: number;
  relative_speed: number;
  c_sigma_r: number;
  t_sigma_r: number;
  F10: number;
  AP: number;
}

export interface Cdm {
  time_to_tca: number;
  miss_distance: number;
  risk: number | null;
  max_risk_estimate: number;
  relative_position_r: number;
  relative_position_t: number;
  relative_position_n: number;
  relative_speed: number;
  c_sigma_r: number;
  t_sigma_r: number;
}

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
  flags: string[];
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

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, init);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

const q = (o: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v != null && v !== "" && p.set(k, String(v)));
  const s = p.toString();
  return s ? "?" + s : "";
};

export const api = {
  summary: (dataset: Dataset) => req<Summary>("/api/summary" + q({ dataset })),
  events: (dataset: Dataset, tier?: number | null, object_type?: string | null) =>
    req<{ events: EventLight[]; message: string | null }>("/api/events" + q({ dataset, tier, object_type })),
  event: (id: number, dataset: Dataset) => req<EventFull>(`/api/events/${id}` + q({ dataset })),
  window: (elapsed_days: number, dataset: Dataset) =>
    req<WindowResp>("/api/window" + q({ elapsed_days: elapsed_days.toFixed(3), dataset })),
  score: (body: { miss_distance: number; max_risk_estimate: number }) =>
    req<ScoreResp>("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  evidence: () => req<EvidenceResp>("/api/evidence"),
  demo: () => req<DemoResp>("/api/demo"),
  audit: (event_id?: number) =>
    req<{ records: AuditRec[]; chain_ok: boolean }>("/api/audit" + q({ event_id })),
  postAudit: (event_id: number, action: string, note: string, dataset: Dataset) =>
    req<AuditRec>("/api/audit" + q({ dataset }), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id, action, note }),
    }),
};
