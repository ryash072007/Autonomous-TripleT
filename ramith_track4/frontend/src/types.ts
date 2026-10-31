export type Verdict = 'APPLIES' | 'DOES_NOT_APPLY' | 'CANNOT_DETERMINE'
export type CondState = 'PASS' | 'FAIL' | 'UNKNOWN' | 'NOT_EVALUATED'

export interface Directive {
  doc_id: string
  docket: string
  title: string
  make: string
  issue_date: string | null
  status: string
  latest: boolean
  withdrawn: boolean
  has_text: boolean
  scope: string | null
  snippet: string
  citation: string | null
  flags: { serial: boolean; external: boolean; pn: boolean; cutoff: boolean }
}

export interface Condition {
  id: string
  label: string
  required: string
  provided: string | null
  state: CondState
  span: [number, number] | null
  quote: string | null
}

export interface VerdictDetail {
  doc_id: string
  verdict: Verdict
  reason_codes: string[]
  main_reason: string
  rule_fired: string
  detail: string
}

export interface TrailEntry { doc_id: string; date: string | null; event: string }

export interface EvalResult {
  doc_id: string
  verdict: VerdictDetail
  conditions: Condition[]
  status: string
  latest_doc_id: string
  revision_trail: TrailEntry[]
  config_used: Record<string, unknown>
}

export interface DocData {
  doc_id: string
  doc_number: string | null
  docket: string
  title: string
  citation: string | null
  pages: string | null
  source: 'fr_text' | 'embedded' | 'summary'
  summary: string
  text: string
  is_summary_only: boolean
  applicability: { scope: string; section: { key: string; page: number | null; char_start: number; char_end: number } | null }
}

export interface Config {
  make: string
  model: string
  serial: string
  cofa_date: string
  part_numbers: string
  registration: string
  engine: string
}

export interface Refusal { code: string; message: string; what_would_resolve_it: string }

export interface QueryCard { doc_id: string; verdict: { verdict: Verdict } | null }
export interface QueryAnswer {
  type: 'answer' | 'refusal'
  cards: QueryCard[]
  refusal: Refusal | null
  config_used?: { make?: string; model?: string; serial?: string; cofa_date?: string; part_numbers?: string[] }
  warnings?: string[]
  latency_ms: { total: number | null }
}

export type Pair = [number, number]
export interface DashboardData {
  sets: { name: string; src_hash: string; engine: Pair; lookup: Pair; applicability: Pair; revision: Pair; refuse: Pair; refusal_right: Pair }[]
  pooled: { engine: Pair; lookup: Pair; applicability: Pair; revision: Pair; refuse: Pair; refusal_precision: Pair }
  final: {
    engine: { verdict_accuracy: number; reason_accuracy: number; confusion: Record<string, number>; per_gold: Record<string, number> }
    b2: { lookup: { pct: number }; applicability: { pct: number }; revision: { pct: number }; refusal: { recall: number; precision: number }; unsupported_quote_rate_pct?: number }
  }
  baselines: { set: string; system: string; lookup: number; applicability: number; revision: number; refuse_recall: number; refuse_precision: number | null; cited_not_in_corpus: number | null }[]
  v1: Record<string, { lookup: number; applicability: number; revision: number; refuse_recall: number }>
  rows_e: { id: string; category: string; ok: boolean; detail: string; query: string }[]
  rows_b1e: { id: string; gold: string; got: string; ok: boolean; gold_reason: string; got_reason: string | null }[]
}
export interface ResultsPayload { available?: boolean; markdown?: string; data?: DashboardData }
