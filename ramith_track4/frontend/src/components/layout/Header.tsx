import { Command, Menu, ShieldAlert } from 'lucide-react'
import { Btn } from '@/components/ui'
import { cn } from '@/lib/utils'

export type View = 'console' | 'evaluation'
const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

export function Header({ view, setView, onToggle, onPalette, sidebarOpen }: { view: View; setView: (v: View) => void; onToggle: () => void; onPalette: () => void; sidebarOpen: boolean }) {
  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-line bg-panel/90 px-4 py-2 backdrop-blur">
      <Btn variant="ghost" size="sm" aria-label="Toggle directives sidebar" aria-expanded={sidebarOpen} onClick={onToggle} className="size-8 px-0"><Menu className="size-4" /></Btn>
      <nav aria-label="Views" className="flex gap-0.5">
        {(['console', 'evaluation'] as const).map((v) => (
          <button key={v} type="button" aria-current={view === v ? 'page' : undefined} onClick={() => setView(v)}
            className={cn('cursor-pointer border-b-2 px-3.5 py-2 text-[13px] font-medium capitalize transition-colors', view === v ? 'border-cyan text-ink' : 'border-transparent text-mute hover:text-ink')}>
            {v}
          </button>
        ))}
      </nav>
      <div role="note" className="ml-auto hidden items-center gap-1.5 rounded-full border border-amber/45 bg-amber/10 px-3 py-0.5 text-xs text-amber lg:flex">
        <ShieldAlert className="size-3.5" aria-hidden />Proposed rules only · decision support, not a compliance or airworthiness finding
      </div>
      <Btn size="sm" onClick={onPalette} aria-label="Open command palette" className="ml-auto lg:ml-0">
        <Command className="size-3.5" aria-hidden /><span className="rounded border border-line2 bg-bg px-1.5 font-mono text-[11px] text-mute">{isMac ? '⌘ K' : 'Ctrl K'}</span>
      </Btn>
    </header>
  )
}
