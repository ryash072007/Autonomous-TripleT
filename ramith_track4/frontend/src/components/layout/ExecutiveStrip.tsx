import { AlertTriangle, CheckCircle2, CircleHelp, Download, Flag, Layers, ListChecks } from 'lucide-react'
import DecryptedText from '@/components/DecryptedText'
import SpotlightCard from '@/components/SpotlightCard'
import { Badge, Btn, Eyebrow } from '@/components/ui'
import { VERDICT_UI, hasModel, plainExplanation, shortTitle } from '@/lib/domain'
import { cn } from '@/lib/utils'
import type { ConsoleApi } from '@/hooks/useConsole'
import type { Verdict } from '@/types'

const ICON: Record<Verdict, typeof CheckCircle2> = { APPLIES: AlertTriangle, DOES_NOT_APPLY: CheckCircle2, CANNOT_DETERMINE: CircleHelp }
const SPOT: Record<Verdict | 'none', string> = { APPLIES: 'rgba(240,102,94,.16)', DOES_NOT_APPLY: 'rgba(63,186,144,.14)', CANNOT_DETERMINE: 'rgba(232,174,67,.15)', none: 'rgba(77,163,255,.1)' }

export function ExecutiveStrip({ c, onTask, onMemo, onFlag }: { c: ConsoleApi; onTask: () => void; onMemo: () => void; onFlag: () => void }) {
  const d = c.current
  const decided = !!c.ev && hasModel(c.cfg)
  const verdict: Verdict | 'none' = decided ? c.ev!.verdict.verdict : 'none'
  const ui = verdict === 'none' ? null : VERDICT_UI[verdict]
  const Icon = verdict === 'none' ? Layers : ICON[verdict]
  const chips = (['make', 'model', 'serial', 'cofa_date', 'part_numbers'] as const).filter((k) => c.cfg[k])
  const label: Record<string, string> = { make: 'make', model: 'model', serial: 'serial', cofa_date: 'CofA', part_numbers: 'P/N' }

  let eyebrow = 'Executive summary', title = 'No directive selected', text = 'Choose a notice from the Directives Stream, or ask a question below. Add an aircraft configuration to get an applicability verdict.'
  let extra = 'Every verdict is computed by deterministic rules over quoted text, shown with its evidence. Nothing here certifies compliance or airworthiness.'
  if (c.refusal && !d) {
    eyebrow = 'Search outcome'; title = VERDICT_UI.CANNOT_DETERMINE.title; text = c.refusal.message
    extra = `To resolve: ${c.refusal.what_would_resolve_it}  ·  code ${c.refusal.code}`
  } else if (d) {
    eyebrow = `${d.docket} · ${shortTitle(d.title)}`
    title = ui ? ui.title : 'AWAITING CONFIGURATION'
    text = decided ? plainExplanation(c.ev!) : 'Enter at least the aircraft model and press Evaluate. Until then the conditions are only listed, not judged.'
    extra = 'Generated items are drafts for an engineer to review. They are not approved maintenance instructions.'
  }
  const vv: Verdict | 'none' = c.refusal && !d ? 'CANNOT_DETERMINE' : verdict
  const RIcon = c.refusal && !d ? CircleHelp : Icon

  return (
    <SpotlightCard
      spotlightColor={SPOT[vv]} theme="dark" intensity={0.5} ambient={false} flare={false} grain={0}
      className={cn('rounded-lg! border! border-line! bg-panel! p-0! [&>*]:relative', vv !== 'none' && (vv === 'APPLIES' ? 'border-red/50!' : vv === 'DOES_NOT_APPLY' ? 'border-green/45!' : 'border-amber/50!'))}
    >
      <div className="grid gap-0 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-1.5 px-4 py-2.5">
          <Eyebrow className="truncate">{eyebrow}</Eyebrow>
          <div className={cn('flex items-center gap-3 text-2xl font-extrabold leading-none tracking-tight', vv === 'none' ? 'text-mute' : VERDICT_UI[vv].text)}>
            <RIcon className="size-6 shrink-0" aria-hidden />
            <DecryptedText key={title} text={title} animateOn="view" speed={40} maxIterations={9} sequential revealDirection="start" className="" parentClassName="" encryptedClassName="opacity-60" />
          </div>
          <p className="line-clamp-3 max-w-[78ch] text-[13px] text-ink">{text}</p>
          <div className="flex min-h-6 flex-wrap items-center gap-1.5">
            {d && chips.map((k) => (
              <span key={k} className="inline-flex items-center gap-1.5 rounded-full border border-line2 bg-panel3 px-2.5 py-0.5 text-xs"><b className="font-medium text-mute">{label[k]}</b>{c.cfg[k]}</span>
            ))}
            {d && c.flags[d.doc_id] && <Badge className="border-amber/40 bg-amber/15 text-amber">FLAGGED</Badge>}
          </div>
        </div>
        <div className="flex flex-col justify-center gap-2 border-t border-line bg-panel2/70 px-4 py-2.5 md:border-l md:border-t-0">
          <Eyebrow>Workflow (drafts only)</Eyebrow>
          <div className="flex flex-wrap gap-2">
            <Btn size="sm" disabled={!decided} onClick={onTask}><ListChecks className="size-3.5" />Generate compliance task</Btn>
            <Btn size="sm" disabled={!decided} onClick={onMemo}><Download className="size-3.5" />Export traceability memo</Btn>
            <Btn size="sm" disabled={!d} onClick={onFlag}><Flag className="size-3.5" />Flag for review</Btn>
          </div>
          {!d && <p className="text-xs text-mute">{extra}</p>}
        </div>
      </div>
    </SpotlightCard>
  )
}
