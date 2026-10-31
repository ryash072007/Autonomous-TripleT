import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, ArrowDown, ArrowUp } from 'lucide-react'
import CountUp from '@/components/CountUp'
import SpotlightCard from '@/components/SpotlightCard'
import { EmptyState, Eyebrow, Pane, Skeleton, inputCls } from '@/components/ui'
import { getResults } from '@/lib/api'
import { wilson } from '@/lib/domain'
import { cn } from '@/lib/utils'
import type { Pair, ResultsPayload } from '@/types'

const pct = (p: Pair) => (p[1] ? (100 * p[0]) / p[1] : 0)
const ci = (p: Pair) => wilson(p[0], p[1]).map((x) => x.toFixed(1)).join('–')
const GRID = '#1c2b3b', TICK = { fill: '#93a6ba', fontSize: 12 }

function Metric({ label, value, unit, note }: { label: string; value: number; unit: string; note: string }) {
  return (
    <SpotlightCard theme="dark" spotlightColor="rgba(77,163,255,.16)" intensity={0.5} ambient={false} flare={false} grain={0} className="rounded-lg! border! border-line! bg-panel! p-4!">
      <Eyebrow>{label}</Eyebrow>
      <div className="mt-1 flex items-baseline gap-1 text-[30px] font-extrabold leading-none tabular-nums"><CountUp to={value} decimals={1} duration={1} /><span className="text-sm font-medium text-mute">{unit}</span></div>
      <p className="mt-1.5 text-xs text-mute">{note}</p>
    </SpotlightCard>
  )
}

function tip({ active, payload }: { active?: boolean; payload?: { payload: { name: string; k: number; n: number; v: number; lo: number; hi: number } }[] }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return <div className="rounded-md border border-line2 bg-panel3 px-3 py-2 text-xs shadow-xl"><div className="font-semibold">{p.name}</div><div className="font-mono">{p.k}/{p.n} · {p.v.toFixed(1)}%</div><div className="text-mute">95% CI {p.lo.toFixed(1)}–{p.hi.toFixed(1)}</div></div>
}

function ChartBars({ rows, color, height }: { rows: { name: string; pair: Pair; color?: string }[]; color: string; height: number }) {
  const data = rows.map((r) => { const [lo, hi] = wilson(r.pair[0], r.pair[1]); const v = pct(r.pair); return { name: r.name, k: r.pair[0], n: r.pair[1], v, lo, hi, err: [v - lo, hi - v] as [number, number], color: r.color ?? color, lab: `${v.toFixed(1)}% · ${r.pair[0]}/${r.pair[1]}` } })
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 4, top: 4, bottom: 4 }}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tick={TICK} tickFormatter={(v) => `${v}%`} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" tick={TICK} width={118} axisLine={false} tickLine={false} />
        <YAxis yAxisId="r" orientation="right" type="category" dataKey="lab" tick={{ fill: '#e7eef6', fontSize: 11.5, fontFamily: 'JetBrains Mono Variable, monospace' }} width={104} axisLine={false} tickLine={false} />
        <Tooltip content={tip as never} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
        <Bar dataKey="v" radius={[0, 3, 3, 0]} barSize={16} isAnimationActive>
          {data.map((d) => <Cell key={d.name} fill={d.color} />)}
          <ErrorBar dataKey="err" width={5} stroke="#e7eef6" strokeWidth={1.4} direction="x" />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function Markdown({ md }: { md: string }) {
  const inl = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  const lines = md.split('\n'), out: string[] = []
  for (let i = 0; i < lines.length;) {
    const l = lines[i]
    if (/^#{1,3} /.test(l)) { out.push(`<h4>${inl(l.replace(/^#+ /, ''))}</h4>`); i++ }
    else if (l.startsWith('|')) { const r: string[] = []; while (i < lines.length && lines[i].startsWith('|')) r.push(lines[i++]); const cells = (x: string) => x.replace(/^\||\|$/g, '').split('|').map((s) => s.trim()); out.push(`<table><thead><tr>${cells(r[0]).map((h) => `<th>${inl(h)}</th>`).join('')}</tr></thead><tbody>${r.slice(2).map((x) => `<tr>${cells(x).map((s) => `<td>${inl(s)}</td>`).join('')}</tr>`).join('')}</tbody></table>`) }
    else if (l.startsWith('- ')) { out.push('<ul>'); while (i < lines.length && lines[i].startsWith('- ')) out.push(`<li>${inl(lines[i++].slice(2))}</li>`); out.push('</ul>') }
    else { if (l.trim()) out.push(`<p>${inl(l)}</p>`); i++ }
  }
  return <div className="max-w-[90ch] text-[13px] text-mute [&_code]:rounded [&_code]:bg-panel3 [&_code]:px-1 [&_h4]:mt-3 [&_h4]:font-semibold [&_h4]:text-ink [&_table]:my-2 [&_table]:border-collapse [&_td]:border [&_td]:border-line [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-line [&_th]:px-2 [&_th]:py-1 [&_ul]:ml-4 [&_ul]:list-disc" dangerouslySetInnerHTML={{ __html: out.join('') }} />
}

export function EvaluationDashboard() {
  const [res, setRes] = useState<ResultsPayload | null>(null)
  const [err, setErr] = useState(false)
  const [filter, setFilter] = useState('')
  const [sort, setSort] = useState<{ k: 'id' | 'category' | 'ok' | 'detail' | 'query'; asc: boolean }>({ k: 'id', asc: true })
  useEffect(() => { getResults().then(setRes).catch(() => setErr(true)) }, [])

  const D = res?.data
  const rows = useMemo(() => {
    if (!D) return []
    const f = filter.toLowerCase()
    const v = D.rows_e.filter((r) => !f || JSON.stringify(r).toLowerCase().includes(f))
    return [...v].sort((a, b) => String(a[sort.k]).localeCompare(String(b[sort.k]), undefined, { numeric: true }) * (sort.asc ? 1 : -1))
  }, [D, filter, sort])

  if (err) return <div className="p-6"><EmptyState icon={<AlertTriangle className="size-5" />} title="Report could not be loaded" text="Check the server and reopen this tab." /></div>
  if (!res) return <div className="flex flex-col gap-3 p-4"><Skeleton className="h-24" /><Skeleton className="h-60" /></div>
  if (!D) return <div className="p-6"><EmptyState icon={<AlertTriangle className="size-5" />} title="No evaluation saved" text="Run eval/make_report.py to generate the benchmark data." /></div>

  const P = D.pooled, e = D.final.engine, b2 = D.final.b2, v1 = D.v1.full
  const cm = e.confusion
  const labs = ['APPLIES', 'DOES_NOT_APPLY', 'CANNOT_DETERMINE'] as const
  const short: Record<string, string> = { APPLIES: 'Applies', DOES_NOT_APPLY: 'Not apply', CANNOT_DETERMINE: 'Cannot det.' }
  const bl = D.baselines.filter((x) => x.set === 'b2e')
  const th = (k: typeof sort.k, label: string) => (
    <th scope="col" aria-sort={sort.k === k ? (sort.asc ? 'ascending' : 'descending') : 'none'} className="sticky top-0 cursor-pointer select-none bg-panel px-2.5 py-2 text-left text-[11px] font-bold uppercase tracking-wider text-mute" onClick={() => setSort((s) => ({ k, asc: s.k === k ? !s.asc : true }))}>
      <span className="inline-flex items-center gap-1">{label}{sort.k === k && (sort.asc ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}</span>
    </th>
  )

  return (
    <div className="flex h-full min-h-0 flex-col gap-3.5 overflow-auto p-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Fresh-document engine accuracy" value={pct(P.engine)} unit="%" note={`${P.engine[0]}/${P.engine[1]} verdicts · 95% CI ${ci(P.engine)} · pooled, 5 first-pass sets`} />
        <Metric label="Free-text applicability (pooled)" value={pct(P.applicability)} unit="%" note={`${P.applicability[0]}/${P.applicability[1]} · 95% CI ${ci(P.applicability)}`} />
        <Metric label="Refusal precision (pooled)" value={pct(P.refusal_precision)} unit="%" note={`${P.refusal_precision[0]}/${P.refusal_precision[1]} refusals were right to refuse`} />
        <Metric label="Unsupported quotes (set B2e)" value={b2.unsupported_quote_rate_pct ?? 0} unit="%" note="Share of quotes that failed the check against the stored source. Failing quotes are dropped before display." />
      </div>

      <div role="note" className="flex gap-2.5 rounded-lg border border-amber/50 bg-amber/10 p-3 text-[13px]">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber" aria-hidden />
        <p><strong>Read this before quoting numbers.</strong> The builder-written held-out test scored {v1.lookup}% lookup / {v1.applicability}% applicability / {v1.revision}% revision / {v1.refuse_recall}% refusal recall, which is optimistic. The blind numbers come from an independent annotator on documents the rules had never seen. Each bar below is a different system version (fixes were made between sets), so the sequence is not an improvement curve.</p>
      </div>

      <div className="grid gap-3.5 xl:grid-cols-2">
        <Pane title="First-pass engine accuracy by set (fresh documents)" bodyClass="min-h-[250px]">
          <ChartBars color="#38c6d8" height={240} rows={D.sets.map((s) => ({ name: `${s.name.split('/')[0]} · ${s.src_hash.slice(0, 6)}`, pair: s.engine }))} />
          <p className="text-xs text-dim">Whiskers are 95% Wilson intervals computed from the counts.</p>
        </Pane>
        <Pane title="Pooled blind results by task" bodyClass="min-h-[250px]">
          <ChartBars color="#4da3ff" height={240} rows={[{ name: 'Lookup', pair: P.lookup }, { name: 'Applicability', pair: P.applicability, color: '#e8ae43' }, { name: 'Revision', pair: P.revision }, { name: 'Refusal recall', pair: P.refuse }]} />
        </Pane>
        <Pane title="Confusion matrix · set B1e (annotator gold vs engine)">
          <div className="grid grid-cols-[96px_repeat(3,minmax(0,1fr))] gap-1 text-xs">
            <div />{labs.map((l) => <div key={l} className="py-1 text-center text-[11px] text-mute">engine: {short[l]}</div>)}
            {labs.map((g) => (
              <div key={g} className="contents">
                <div className="flex items-center text-[11px] text-mute">gold: {short[g]}</div>
                {labs.map((p) => { const n = cm[`${g}->${p}`] ?? 0; return <div key={p} className={cn('rounded py-3 text-center text-sm font-bold tabular-nums', g === p ? (n ? 'bg-green/15 text-green' : 'bg-panel2 text-dim') : n ? 'bg-red/15 text-red' : 'bg-panel2 text-dim')}>{n}</div> })}
              </div>
            ))}
          </div>
          <p className="text-xs text-dim">{e.verdict_accuracy}% verdict accuracy and {e.reason_accuracy}% reason-code accuracy on this set (n = {Object.values(cm).reduce((a, b) => a + b, 0)}).</p>
        </Pane>
        <Pane title="Baselines on B2e (same questions)">
          <div className="overflow-auto rounded-md border border-line">
            <table className="w-full border-collapse text-[12.5px] tabular-nums">
              <thead><tr className="bg-panel2 text-left text-[11px] uppercase tracking-wider text-mute">{['System', 'Lookup', 'Applic.', 'Revision', 'Refuse recall'].map((h) => <th key={h} className="px-2.5 py-2">{h}</th>)}</tr></thead>
              <tbody>
                <tr className="border-t border-line font-semibold"><td className="px-2.5 py-1.5">Full system</td><td>{b2.lookup.pct}%</td><td>{b2.applicability.pct}%</td><td>{b2.revision.pct}%</td><td>{b2.refusal.recall}%</td></tr>
                {bl.map((x) => <tr key={x.system} className="border-t border-line"><td className="px-2.5 py-1.5">{x.system}</td><td>{x.lookup}%</td><td>{x.applicability}%</td><td>{x.revision}%</td><td>{x.refuse_recall}%</td></tr>)}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-dim">Lookup and revision questions reuse each notice’s own wording, so keyword search also solves them. LLM-baseline revision is scored on what the model itself said; forced LLM answers cite documents that do not exist about {bl.find((x) => x.system === 'llm_forced')?.cited_not_in_corpus ?? 'n/a'}% of the time.</p>
        </Pane>
      </div>

      <Pane title={`Raw evaluation records · set B2e (${rows.length})`} bodyClass="p-0 gap-0" actions={<input aria-label="Filter evaluation records" placeholder="Filter records…" className={inputCls + ' max-w-60'} value={filter} onChange={(e) => setFilter(e.target.value)} />}>
        <div className="max-h-96 overflow-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead><tr>{th('id', 'id')}{th('category', 'category')}{th('ok', 'result')}{th('detail', 'detail')}{th('query', 'query')}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-line align-top">
                  <td className="px-2.5 py-1.5 font-mono text-xs">{r.id}</td><td className="px-2.5 py-1.5">{r.category}</td>
                  <td className="px-2.5 py-1.5"><span className={cn('rounded border px-1.5 py-px text-[10.5px] font-bold tracking-wider', r.ok ? 'border-green/40 bg-green/15 text-green' : 'border-red/40 bg-red/15 text-red')}>{r.ok ? 'CORRECT' : 'MISS'}</span></td>
                  <td className="px-2.5 py-1.5">{r.detail}</td><td className="px-2.5 py-1.5 text-mute">{r.query}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Pane>

      <details className="rounded-lg border border-line bg-panel px-4 py-3">
        <summary className="cursor-pointer font-semibold">Full generated report (REPORT.md)</summary>
        <div className="mt-3"><Markdown md={res.markdown ?? ''} /></div>
      </details>
    </div>
  )
}
