import { useEffect, useMemo, useRef, useState } from 'react'
import { Badge, inputCls } from '@/components/ui'
import { Modal } from '@/components/workflow/Modals'
import { shortTitle } from '@/lib/domain'
import { cn } from '@/lib/utils'
import type { ConsoleApi } from '@/hooks/useConsole'
import type { View } from '@/components/layout/Header'

type Item = { label: string; kind: string; run: () => void }

export function CommandPalette({ c, onClose, setView }: { c: ConsoleApi; onClose: () => void; setView: (v: View) => void }) {
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => { input.current?.focus() }, [])

  const items = useMemo<Item[]>(() => {
    const needle = q.toLowerCase()
    const cmds: Item[] = [
      { label: 'Focus question box', kind: 'Command', run: () => { setView('console'); setTimeout(() => document.getElementById('q')?.focus(), 50) } },
      { label: 'Open evaluation dashboard', kind: 'Command', run: () => setView('evaluation') },
      { label: 'Open console', kind: 'Command', run: () => setView('console') },
      { label: 'Clear aircraft configuration', kind: 'Command', run: c.clearConfig },
      { label: 'Clear selected directive', kind: 'Command', run: () => void c.select(null) },
    ].filter((i) => i.label.toLowerCase().includes(needle))
    const dirs: Item[] = c.dirs
      .filter((d) => !needle || `${d.docket} ${d.title} ${d.make}`.toLowerCase().includes(needle))
      .slice(0, 12)
      .map((d) => ({ label: `${d.docket} · ${shortTitle(d.title)}`.slice(0, 110), kind: (d.make || 'Directive').slice(0, 28), run: () => { setView('console'); void c.select(d.doc_id) } }))
    return [...cmds, ...dirs]
  }, [q, c, setView])

  const go = (i: Item) => { onClose(); i.run() }
  return (
    <Modal title="Command palette" onClose={onClose}>
      <input ref={input} className={inputCls} placeholder="Search directives or type a command…" aria-label="Command palette search" autoComplete="off" value={q}
        onChange={(e) => { setQ(e.target.value); setSel(0) }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(0, s - 1)) }
          else if (e.key === 'Enter' && items[sel]) go(items[sel])
        }} />
      <div role="listbox" className="-mx-4 -mb-4 max-h-[44vh] overflow-auto border-t border-line">
        {items.map((it, i) => (
          <button key={it.label + i} type="button" role="option" aria-selected={i === sel} onClick={() => go(it)} onMouseEnter={() => setSel(i)}
            className={cn('flex w-full cursor-pointer items-center gap-2.5 border-b border-line px-4 py-2 text-left', i === sel && 'bg-panel3')}>
            <span className="min-w-0 flex-1 truncate">{it.label}</span><Badge className="border-line2 bg-dim/15 text-mute">{it.kind}</Badge>
          </button>
        ))}
        {!items.length && <div className="p-6 text-center text-mute">No matches</div>}
      </div>
    </Modal>
  )
}
