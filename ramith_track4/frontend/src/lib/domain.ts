import type { Condition, CondState, Config, Directive, EvalResult, Verdict } from '@/types'

export const VERDICT_UI: Record<Verdict, { label: string; badge: string; title: string; text: string; ring: string; chip: string }> = {
  APPLIES: { label: 'APPLIES · PROPOSED RULE', badge: 'RED', title: 'APPLIES', text: 'text-red', ring: 'border-red/50', chip: 'bg-red/15 text-red border-red/40' },
  DOES_NOT_APPLY: { label: 'OUT OF SCOPE', badge: 'GREEN', title: 'DOES NOT APPLY', text: 'text-green', ring: 'border-green/45', chip: 'bg-green/15 text-green border-green/40' },
  CANNOT_DETERMINE: { label: 'UNCERTAIN · REFUSED', badge: 'AMBER', title: 'UNCERTAIN — REFUSAL', text: 'text-amber', ring: 'border-amber/50', chip: 'bg-amber/15 text-amber border-amber/40' },
}

export const COND_UI: Record<CondState, { label: string; text: string; bg: string }> = {
  PASS: { label: 'PASS', text: 'text-green', bg: 'bg-green/15' },
  FAIL: { label: 'FAIL', text: 'text-red', bg: 'bg-red/15' },
  UNKNOWN: { label: 'UNKNOWN', text: 'text-amber', bg: 'bg-amber/15' },
  NOT_EVALUATED: { label: 'NOT EVALUATED', text: 'text-dim', bg: 'bg-dim/15' },
}

/** What the user must supply to resolve an UNKNOWN condition, keyed by condition id. */
export const NEEDS: Record<string, string> = {
  model: 'the aircraft model',
  part_number: 'the installed part numbers',
  cert_date: 'the original certificate of airworthiness date',
  serial: 'the serial number',
  exclusion: 'whether your aircraft meets the excluded condition',
  other: 'whether your aircraft meets the configuration clause',
  external: 'the outside document that defines applicability',
  text: 'the full notice text',
}

export const EMPTY_CONFIG: Config = { make: '', model: '', serial: '', cofa_date: '', part_numbers: '', registration: '', engine: '' }
export const hasModel = (c: Config) => c.model.trim().length > 0
export const validCofa = (v: string) => !v.trim() || (/^\d{4}-\d{2}-\d{2}$/.test(v.trim()) && !Number.isNaN(Date.parse(v.trim())))
export const shortTitle = (t: string) => t.replace('Airworthiness Directives; ', '')

export function streamBadge(d: Directive, verdict?: Verdict): { text: string; cls: string } {
  if (verdict) return { text: VERDICT_UI[verdict].label, cls: VERDICT_UI[verdict].chip }
  if (d.withdrawn || d.status === 'WITHDRAWN') return { text: 'WITHDRAWN', cls: 'bg-dim/15 text-mute border-line2' }
  if (d.status.startsWith('REVISED') || !d.latest) return { text: 'UNDER REVISION', cls: 'bg-cyan/12 text-cyan border-cyan/40' }
  return { text: 'PROPOSED', cls: 'bg-accent/12 text-accent border-accent/40' }
}

export function plainExplanation(ev: EvalResult): string {
  const v = ev.verdict
  const unknown = ev.conditions.filter((c) => c.state === 'UNKNOWN')
  if (v.verdict === 'CANNOT_DETERMINE') {
    const needs = unknown.map((c) => NEEDS[c.id] ?? c.label).filter(Boolean)
    return v.detail + (needs.length ? ` Needed: ${needs.join('; ')}.` : '')
  }
  if (v.verdict === 'DOES_NOT_APPLY') return `${v.detail} The evaluated conditions are not met for the configuration you gave. This is not a clearance.`
  return `${v.detail} If this proposal is adopted, review it with a qualified engineer.`
}

export function taskText(d: Directive, ev: EvalResult, c: Config): string {
  const lines = ev.conditions.map((k) => `- ${k.label}: ${k.state}${k.provided ? ` (aircraft: ${k.provided})` : ''}`).join('\n')
  const cites = ev.conditions.filter((k) => k.span).map((k) => `${k.label} [chars ${k.span![0]}-${k.span![1]}]`).join('; ')
  return [
    'DRAFT COMPLIANCE REVIEW TASK (not an approved maintenance instruction)',
    'Status: DRAFT — requires engineering review',
    `Directive: ${d.docket} — ${d.title}`,
    `Citation: ${d.citation ?? 'n/a'}`,
    `Aircraft: ${[c.make, c.model, c.serial && 'S/N ' + c.serial, c.registration && 'Reg ' + c.registration].filter(Boolean).join(' ')}`,
    `Tool outcome: ${VERDICT_UI[ev.verdict.verdict].title}`,
    'Conditions:', lines,
    'Required engineering review: confirm the outcome against the final AD text.',
    `Evidence: ${cites || 'none'}`,
    `Generated: ${new Date().toISOString()}`,
  ].join('\n')
}

export function memoMarkdown(d: Directive, ev: EvalResult, c: Config, question: string): string {
  const trail = ev.revision_trail.map((e) => `- ${e.date ?? ''} ${e.event} (${e.doc_id})`).join('\n') || '- none recorded'
  const conds = ev.conditions
    .map((k: Condition) => `### ${k.label}: ${k.state}\n- Required: ${k.required}\n- Aircraft: ${k.provided ?? 'not provided'}\n${k.quote && k.span ? `- Exact quotation (chars ${k.span[0]}-${k.span[1]}):\n> ${k.quote.replace(/\n/g, '\n> ')}` : '- No source span available'}`)
    .join('\n\n')
  const cfg = (['make', 'model', 'serial', 'cofa_date', 'part_numbers', 'registration', 'engine'] as const).map((k) => `- ${k}: ${c[k] || 'not provided'}`).join('\n')
  return `# Traceability memo (draft)

**Generated:** ${new Date().toISOString()}
**Data:** FAA NPRM spreadsheet (supplied by the organisers); full text from the Federal Register API.

> Proposed rules only. Decision support, not a compliance or airworthiness finding. A qualified person must verify against the final AD.

## Question
${question || '(directive selected directly; no free-text question)'}

## Aircraft configuration
${cfg}
(registration and engine are recorded only; the rules do not evaluate them)

## Source
- Notice: ${d.title}
- Docket: ${d.docket}
- Citation: ${d.citation ?? 'n/a'}
- Revision status: ${ev.status}

## Conditions and evidence
${conds}

## Outcome
**${VERDICT_UI[ev.verdict.verdict].title}** (${ev.verdict.reason_codes.join(', ')}), rule fired: ${ev.verdict.rule_fired}.

${ev.verdict.detail}

## Uncertainty and limitations
- Only the applicability paragraph is read; conditions stated elsewhere are not evaluated.
- Unknown or unreadable conditions are reported as UNKNOWN, never as pass or fail.
- Revision text differences are not available; only the dated history.

## Revision history
${trail}
`
}

export function wilson(k: number, n: number): [number, number] {
  if (!n) return [0, 0]
  const z = 1.96, p = k / n, d = 1 + (z * z) / n, c = p + (z * z) / (2 * n), h = z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))
  return [(100 * (c - h)) / d, (100 * (c + h)) / d]
}
