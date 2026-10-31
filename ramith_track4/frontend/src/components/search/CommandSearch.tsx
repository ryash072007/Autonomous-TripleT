import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronRight, Search, X } from 'lucide-react'
import { Btn, inputCls } from '@/components/ui'
import { validCofa } from '@/lib/domain'
import { cn } from '@/lib/utils'
import type { ConsoleApi } from '@/hooks/useConsole'
import type { Config } from '@/types'

const FIELDS: { k: keyof Config; label: string; ph: string; note?: string; chip: string }[] = [
  { k: 'make', label: 'Manufacturer', ph: 'Airbus', chip: 'Make' },
  { k: 'model', label: 'Model', ph: 'A330-243', chip: 'Model' },
  { k: 'serial', label: 'Serial number', ph: '1456', chip: 'Serial' },
  { k: 'cofa_date', label: 'Original CofA', ph: 'YYYY-MM-DD', chip: 'CofA' },
  { k: 'part_numbers', label: 'Part numbers', ph: 'comma separated', chip: 'P/N' },
  { k: 'registration', label: 'Registration', ph: '9V-XXX', note: 'recorded only', chip: 'Reg' },
  { k: 'engine', label: 'Engine', ph: 'Trent 700', note: 'recorded only', chip: 'Engine' },
]

export function CommandSearch({ c }: { c: ConsoleApi }) {
  const [open, setOpen] = useState(false)
  const set = (k: keyof Config, v: string) => c.setCfg((p) => ({ ...p, [k]: v }))
  const filled = FIELDS.filter((f) => c.cfg[f.k])
  const dateOk = validCofa(c.cfg.cofa_date)
  const submit = () => (c.selected && !c.question.trim() ? c.evaluateSelected() : void c.runSearch())

  return (
    <section aria-label="Command search" className="flex flex-col gap-2.5 rounded-lg border border-line bg-panel px-3.5 py-3">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2.5">
        <div className="relative">
          <label htmlFor="q" className="sr-only">Regulatory question</label>
          <textarea
            id="q" rows={2} value={c.question} onChange={(e) => c.setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); submit() } }}
            placeholder="Ask a regulatory applicability question…  e.g. Does the latest proposed AD in docket FAA-2026-1338 apply to my A330-243?"
            className={cn(inputCls, 'min-h-14 resize-y border-[1.5px] px-3 py-2.5 pr-20 text-[15px]')}
          />
          <span className="pointer-events-none absolute right-2.5 top-2.5 rounded border border-line2 bg-bg px-1.5 font-mono text-[11px] text-mute">Ctrl ↵</span>
        </div>
        <Btn variant="primary" disabled={c.busy} onClick={() => void c.runSearch()} className="h-full min-w-36"><Search className="size-4" />Search</Btn>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="inline-flex cursor-pointer items-center gap-1.5 rounded px-1 text-xs font-semibold text-mute transition-colors hover:text-ink">
          <ChevronRight className={cn('size-3.5 transition-transform', open && 'rotate-90')} />Aircraft configuration
        </button>
        {filled.map((f) => (
          <span key={f.k} className="inline-flex items-center gap-1.5 rounded-full border border-line2 bg-panel3 py-0.5 pl-2.5 pr-1 text-xs">
            <b className="font-medium text-mute">{f.chip}</b>{c.cfg[f.k]}
            <button type="button" aria-label={`Remove ${f.chip}`} onClick={() => set(f.k, '')} className="grid size-4 cursor-pointer place-items-center rounded-full text-dim hover:bg-line2 hover:text-ink"><X className="size-3" /></button>
          </span>
        ))}
        {!filled.length && <span className="text-xs text-dim">none set — add a model to get a verdict</span>}
        <Btn size="sm" disabled={c.busy || !c.selected} onClick={c.evaluateSelected} className="ml-1">Evaluate selected</Btn>
        <div aria-live="polite" className="ml-auto flex min-h-5 items-center gap-2 text-xs text-mute">
          {c.notice.kind === 'busy' && <div className="relative h-0.5 w-24 overflow-hidden rounded bg-line"><div className="absolute inset-y-0 w-1/3 animate-sweep rounded bg-cyan" /></div>}
          <span className={cn(c.notice.kind === 'error' && 'text-red')}>{c.notice.text}</span>
          {c.notice.retry && <Btn size="sm" onClick={() => void c.runSearch()}>Retry</Btn>}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.18 }} className="overflow-hidden">
            <div className="grid grid-cols-2 gap-2 pb-1 sm:grid-cols-4 xl:grid-cols-7">
              {FIELDS.map((f) => (
                <div key={f.k}>
                  <label htmlFor={`c_${f.k}`} className="mb-0.5 block text-[10.5px] font-bold uppercase tracking-wider text-dim">
                    {f.label}{f.note && <span className="ml-1 font-normal normal-case tracking-normal"> ({f.note})</span>}
                  </label>
                  <input
                    id={`c_${f.k}`} className={cn(inputCls, f.k === 'cofa_date' && !dateOk && 'border-red')} placeholder={f.ph} autoComplete="off"
                    value={c.cfg[f.k]} aria-invalid={f.k === 'cofa_date' ? !dateOk : undefined} onChange={(e) => set(f.k, e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); c.selected ? c.evaluateSelected() : void c.runSearch() } }}
                  />
                  {f.k === 'cofa_date' && !dateOk && <div role="alert" className="mt-0.5 text-[11.5px] text-red">Use YYYY-MM-DD, for example 2025-06-01.</div>}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </section>
  )
}
