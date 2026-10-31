import { useEffect, useRef, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { Badge, Btn, inputCls } from '@/components/ui'
import { VERDICT_UI, memoMarkdown, taskText } from '@/lib/domain'
import type { ConsoleApi, Flag } from '@/hooks/useConsole'

export function Modal({ title, onClose, children, footer }: { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  const close = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    close.current?.focus()
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('keydown', esc); prev?.focus?.() }
  }, [onClose])
  return (
    <div role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }} className="fixed inset-0 z-50 grid place-items-start justify-items-center bg-black/65 p-4 pt-[9vh]">
      <motion.div initial={{ opacity: 0, y: 8, scale: 0.985 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.16 }} className="max-h-[82vh] w-full max-w-2xl overflow-auto rounded-xl border border-line2 bg-panel shadow-2xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3"><h2 className="text-[15px] font-semibold">{title}</h2><Btn ref={close as never} variant="ghost" size="sm" aria-label="Close" onClick={onClose} className="size-8 px-0"><X className="size-4" /></Btn></div>
        <div className="flex flex-col gap-3 p-4">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-4 py-3">{footer}</div>}
      </motion.div>
    </div>
  )
}

const pre = 'm-0 max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-bg p-2.5 font-mono text-xs'

export function TaskModal({ c, onClose, onToast }: { c: ConsoleApi; onClose: () => void; onToast: (t: string) => void }) {
  const d = c.current!, ev = c.ev!, V = VERDICT_UI[ev.verdict.verdict]
  const text = taskText(d, ev, c.cfg)
  return (
    <Modal title="Generate compliance task (draft)" onClose={onClose} footer={<><Btn onClick={() => { void navigator.clipboard?.writeText(text); onToast('Task text copied') }}>Copy text</Btn><Btn variant="primary" onClick={onClose}>Close</Btn></>}>
      <div className="rounded-md border border-amber/50 bg-amber/10 p-2.5 text-[12.5px] text-amber"><strong>Draft only.</strong> This is a review task for an engineer, not an approved maintenance instruction, and it has not been saved to any maintenance system.</div>
      <dl className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-[13px]">
        <dt className="text-dim">Directive</dt><dd>{d.docket}</dd>
        <dt className="text-dim">Aircraft</dt><dd>{[c.cfg.make, c.cfg.model, c.cfg.serial].filter(Boolean).join(' ')}</dd>
        <dt className="text-dim">Outcome</dt><dd><Badge className={V.chip}>{V.label}</Badge></dd>
        <dt className="text-dim">Task status</dt><dd>DRAFT — requires engineering review</dd>
      </dl>
      <pre className={pre}>{text}</pre>
    </Modal>
  )
}

export function MemoModal({ c, onClose, onToast }: { c: ConsoleApi; onClose: () => void; onToast: (t: string) => void }) {
  const d = c.current!, ev = c.ev!
  const md = memoMarkdown(d, ev, c.cfg, c.question)
  const download = () => {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([md], { type: 'text/markdown' }))
    a.download = `traceability-memo-${d.docket.replace(/[^A-Za-z0-9-]/g, '_')}.md`
    a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 2000)
    onToast('Memo downloaded')
  }
  return (
    <Modal title="Export traceability memo" onClose={onClose} footer={<><Btn variant="primary" onClick={download}>Download .md</Btn><Btn onClick={onClose}>Close</Btn></>}>
      <div className="rounded-md border border-line bg-panel2 p-2.5 text-[12.5px]">The memo contains the question, configuration, exact quotations, evaluation logic, outcome and limitations. Nothing is added that the tool did not produce.</div>
      <pre className={pre + ' max-h-80'}>{md}</pre>
    </Modal>
  )
}

const REASONS = ['Applicability unclear', 'Source text looks wrong or incomplete', 'Result disagrees with my reading', 'Needs senior engineer sign-off', 'Other']
export function FlagModal({ c, onClose, onToast }: { c: ConsoleApi; onClose: () => void; onToast: (t: string) => void }) {
  const d = c.current!, ex = c.flags[d.doc_id]
  const [reason, setReason] = useState(ex?.reason ?? REASONS[0])
  const [comment, setComment] = useState(ex?.comment ?? '')
  const [status, setStatus] = useState(ex?.status ?? 'Open')
  const save = () => { const f: Flag = { reason, comment, status, at: new Date().toISOString() }; c.saveFlag(d.doc_id, f); onClose(); onToast('Flagged for review (stored in this browser only)') }
  return (
    <Modal title="Flag for review" onClose={onClose} footer={<>{ex && <Btn onClick={() => { c.saveFlag(d.doc_id, null); onClose(); onToast('Flag cleared') }}>Clear flag</Btn>}<Btn variant="primary" onClick={save}>Save flag</Btn></>}>
      <div className="rounded-md border border-amber/50 bg-amber/10 p-2.5 text-[12.5px] text-amber"><strong>Stored in this browser only</strong> (local demonstration). No review system or server stores this.</div>
      <label className="block text-xs font-bold uppercase tracking-wider text-dim">Reason<select className={inputCls + ' mt-1 font-normal normal-case tracking-normal'} value={reason} onChange={(e) => setReason(e.target.value)}>{REASONS.map((r) => <option key={r}>{r}</option>)}</select></label>
      <label className="block text-xs font-bold uppercase tracking-wider text-dim">Comment<textarea rows={3} className={inputCls + ' mt-1 font-normal normal-case tracking-normal'} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Short comment" /></label>
      <label className="block text-xs font-bold uppercase tracking-wider text-dim">Review status<select className={inputCls + ' mt-1 font-normal normal-case tracking-normal'} value={status} onChange={(e) => setStatus(e.target.value)}>{['Open', 'In review', 'Resolved'].map((r) => <option key={r}>{r}</option>)}</select></label>
    </Modal>
  )
}
