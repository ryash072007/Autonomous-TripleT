import { AnimatePresence, motion } from 'framer-motion'
import { Check, ChevronDown, CircleHelp, Layers, Minus, X } from 'lucide-react'
import { EmptyState, Pane, Skeleton } from '@/components/ui'
import { COND_UI, NEEDS } from '@/lib/domain'
import { cn } from '@/lib/utils'
import type { ConsoleApi } from '@/hooks/useConsole'
import type { CondState } from '@/types'

const ICON: Record<CondState, typeof Check> = { PASS: Check, FAIL: X, UNKNOWN: CircleHelp, NOT_EVALUATED: Minus }

function Tag({ kind, children }: { kind: 'src' | 'tool' | 'human'; children: string }) {
  const cls = { src: 'bg-[#ffd05a]/15 text-[#f0cb63]', tool: 'bg-accent/15 text-accent', human: 'bg-mute/15 text-mute' }[kind]
  return <span className={cn('inline-block rounded px-1.5 py-px text-[10px] font-bold uppercase tracking-widest', cls)}>{children}</span>
}

function StateDot({ s, small }: { s: CondState; small?: boolean }) {
  const I = ICON[s]
  return <span className={cn('grid shrink-0 place-items-center rounded-full', COND_UI[s].bg, COND_UI[s].text, small ? 'size-4' : 'size-6')}><I className={small ? 'size-2.5' : 'size-3.5'} strokeWidth={2.6} aria-hidden /></span>
}

export function LogicTree({ c, onShow }: { c: ConsoleApi; onShow: () => void }) {
  const ev = c.ev
  return (
    <Pane title="Applicability logic" icon={<Layers className="size-3.5" />}>
      {!ev && c.busy && <div className="flex flex-col gap-2.5"><Skeleton className="w-3/5" /><Skeleton /><Skeleton className="w-4/5" /></div>}
      {!ev && !c.busy && <EmptyState icon={<Layers className="size-5" />} title="No conditions yet" text="Select a directive. Its applicability conditions are listed here and checked against your aircraft configuration." />}
      {ev && (
        <>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-mute">
            {(Object.keys(COND_UI) as CondState[]).map((s) => <span key={s} className="inline-flex items-center gap-1.5"><StateDot s={s} small />{COND_UI[s].label}</span>)}
          </div>
          {ev.conditions.map((k) => {
            const open = c.openConds.has(k.id)
            const toggle = () => {
              c.setOpenConds((p) => { const n = new Set(p); if (n.has(k.id)) n.delete(k.id); else n.add(k.id); return n })
              if (k.span) c.setActiveCond(k.id)
            }
            return (
              <div key={k.id} className={cn('rounded-md border bg-panel2 transition-colors', c.activeCond === k.id ? 'border-cyan bg-panel3' : 'border-line')}>
                <button type="button" aria-expanded={open} onClick={toggle} className="flex w-full cursor-pointer items-center gap-2.5 px-2.5 py-2 text-left">
                  <StateDot s={k.state} />
                  <span className="min-w-0 flex-1 font-semibold">{k.label}</span>
                  <span className={cn('text-[10.5px] font-bold tracking-wider', COND_UI[k.state].text)}>{COND_UI[k.state].label}</span>
                  <ChevronDown className={cn('size-3.5 text-dim transition-transform', open && 'rotate-180')} aria-hidden />
                </button>
                <AnimatePresence initial={false}>
                  {open && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.16 }} className="overflow-hidden">
                      <div className="flex flex-col gap-2 px-3 pb-3 pl-11 text-[12.5px]">
                        <dl className="grid grid-cols-[84px_minmax(0,1fr)] gap-x-2 gap-y-1">
                          <dt className="text-dim">Required</dt><dd className="[overflow-wrap:anywhere]">{k.required}</dd>
                          <dt className="text-dim">Your aircraft</dt><dd>{k.provided ?? <em className="text-dim">not provided</em>}</dd>
                        </dl>
                        <p>{k.state === 'PASS' ? 'This condition is met by the value you gave.' : k.state === 'FAIL' ? 'This condition is not met by the value you gave.' : k.state === 'UNKNOWN' ? `This cannot be decided: ${NEEDS[k.id] ?? 'more information'} is needed or cannot be read reliably.` : 'The engine stopped at an earlier decisive condition, so this was not reached.'}</p>
                        {k.quote ? (
                          <div>
                            <Tag kind="src">Quoted source text</Tag>
                            <div className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap font-read text-[13px] leading-snug text-[#c9d4e0]">{k.quote}</div>
                            <button type="button" onClick={() => { c.setActiveCond(k.id); onShow() }} className="mt-1.5 cursor-pointer text-xs font-semibold text-accent underline underline-offset-2">Show in source</button>
                          </div>
                        ) : <Tag kind="human">No source span for this condition</Tag>}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
          <div className="rounded-md border border-accent/40 bg-accent/10 p-3 text-[12.5px]">
            <Tag kind="tool">Tool explanation</Tag>
            <p className="mt-1.5">{ev.verdict.detail}</p>
            <p className="mt-1.5 font-mono text-[11.5px] text-dim">rule: {ev.verdict.rule_fired} · codes: {ev.verdict.reason_codes.join(', ')}</p>
          </div>
          <div className="rounded-md border border-line bg-panel2 p-3 text-[12.5px]">
            <Tag kind="human">Engineering interpretation</Tag>
            <p className="mt-1.5 text-mute">Reserved for the qualified engineer. The tool states what it checked and what it could not.</p>
          </div>
        </>
      )}
    </Pane>
  )
}
