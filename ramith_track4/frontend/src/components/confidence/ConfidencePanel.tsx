import { CircleHelp, ShieldCheck } from 'lucide-react'
import CountUp from '@/components/CountUp'
import { EmptyState, Pane } from '@/components/ui'
import { NEEDS, hasModel } from '@/lib/domain'
import { cn } from '@/lib/utils'
import type { ConsoleApi } from '@/hooks/useConsole'

function Ring({ pct, label }: { pct: number; label: string }) {
  const r = 30, circ = 2 * Math.PI * r
  return (
    <div className="flex flex-col items-center gap-1 rounded-md border border-line bg-panel2 p-2.5 text-center">
      <div className="relative size-[74px]">
        <svg viewBox="0 0 80 80" className="size-full -rotate-90" role="img" aria-label={`${label} ${Math.round(pct)} percent`}>
          <circle cx="40" cy="40" r={r} fill="none" strokeWidth="7" className="stroke-line2" />
          <circle cx="40" cy="40" r={r} fill="none" strokeWidth="7" strokeLinecap="round" className="stroke-cyan transition-[stroke-dashoffset] duration-700" strokeDasharray={circ} strokeDashoffset={circ * (1 - pct / 100)} />
        </svg>
        <div className="absolute inset-0 grid place-items-center text-lg font-bold tabular-nums"><CountUp to={Math.round(pct)} duration={0.9} suffix="%" /></div>
      </div>
      <div className="text-[11px] leading-tight text-mute">{label}</div>
    </div>
  )
}

export function ConfidencePanel({ c }: { c: ConsoleApi }) {
  const ev = c.ev
  const decided = !!ev && hasModel(c.cfg)
  const conds = ev?.conditions ?? []
  const n = conds.length || 1
  const needed = conds.filter((k) => k.state !== 'NOT_EVALUATED')
  const pctDecided = (100 * conds.filter((k) => k.state === 'PASS' || k.state === 'FAIL').length) / n
  const pctCited = (100 * conds.filter((k) => k.span).length) / n
  const pctCfg = needed.length ? (100 * needed.filter((k) => k.provided).length) / needed.length : 0
  const verdict = decided ? ev!.verdict.verdict : null
  const level = !decided ? 1 : verdict === 'CANNOT_DETERMINE' ? 2 : 4
  const levelText = !decided ? 'Awaiting configuration' : verdict === 'CANNOT_DETERMINE' ? 'Refused — incomplete' : 'Decisive — engineering review still required'
  const unknown = conds.filter((k) => k.state === 'UNKNOWN')

  return (
    <Pane title="Confidence & traceability" icon={<ShieldCheck className="size-3.5" />}>
      {!ev ? (
        <EmptyState icon={<ShieldCheck className="size-5" />} title="Evidence quality" text="Coverage and traceability indicators appear once a directive is evaluated." />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2.5">
            <Ring pct={pctDecided} label="Conditions decided" />
            <Ring pct={pctCited} label="Conditions with a source quote" />
            <Ring pct={pctCfg} label="Configuration complete" />
            <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-line bg-panel2 p-2.5 text-center">
              <div className="flex w-full gap-1">{[1, 2, 3, 4].map((i) => <i key={i} className={cn('h-2 flex-1 rounded-sm', i <= level ? 'bg-cyan' : 'bg-line2')} />)}</div>
              <div className="text-[11.5px] font-semibold leading-tight">{levelText}</div>
            </div>
          </div>
          <div className="rounded-md border border-line bg-panel2 p-3 text-[12.5px]"><strong>Coverage is not confidence.</strong> These bars measure how much of the notice’s conditions were decided and quoted. The tool calculates no probability and none is shown.</div>
          {decided && verdict === 'CANNOT_DETERMINE' && (
            <div className="flex flex-col gap-2 rounded-md border border-amber/50 bg-amber/10 p-3 text-[12.5px]">
              <h3 className="flex items-center gap-2 text-[13.5px] font-semibold text-amber"><CircleHelp className="size-4" />Refusal — applicability not determined</h3>
              <p>{ev.verdict.detail}</p>
              <div><strong>What cannot be evaluated</strong>
                <ul className="ml-4 list-disc">{unknown.length ? unknown.map((k) => <li key={k.id}>{k.label}: needs {NEEDS[k.id] ?? 'more information'}</li>) : <li>See the explanation above.</li>}</ul>
              </div>
              <p><strong>What would resolve it:</strong> provide the items above, or read the quoted clause yourself.</p>
            </div>
          )}
          {decided && verdict !== 'CANNOT_DETERMINE' && (
            <div className="rounded-md border border-accent/40 bg-accent/10 p-3 text-[12.5px]"><span className="rounded bg-accent/15 px-1.5 py-px text-[10px] font-bold uppercase tracking-widest text-accent">Tool explanation</span><p className="mt-1.5">{ev.verdict.detail}</p></div>
          )}
          <div className="rounded-md border border-amber/50 bg-amber/10 p-3 text-[12.5px] text-amber"><strong>Human judgement remains authoritative.</strong> This is decision support over proposed rules. It does not certify compliance or airworthiness.</div>
        </>
      )}
    </Pane>
  )
}
