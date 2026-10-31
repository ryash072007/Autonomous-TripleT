import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ConfidencePanel } from '@/components/confidence/ConfidencePanel'
import { LogicTree } from '@/components/applicability/LogicTree'
import { EvaluationDashboard } from '@/components/evaluation/EvaluationDashboard'
import { SourceViewer } from '@/components/evidence/SourceViewer'
import { ExecutiveStrip } from '@/components/layout/ExecutiveStrip'
import { Header, type View } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { CommandPalette } from '@/components/search/CommandPalette'
import { CommandSearch } from '@/components/search/CommandSearch'
import { FlagModal, MemoModal, TaskModal } from '@/components/workflow/Modals'
import { useConsole } from '@/hooks/useConsole'
import { cn } from '@/lib/utils'

type ModalKind = 'task' | 'memo' | 'flag' | 'palette' | null
type PaneKey = 'A' | 'B' | 'C'
const PANES: [PaneKey, string][] = [['A', 'Logic'], ['B', 'Evidence'], ['C', 'Confidence']]

export default function App() {
  const c = useConsole()
  const [view, setView] = useState<View>('console')
  const [sidebar, setSidebar] = useState(() => window.innerWidth > 900)
  const [modal, setModal] = useState<ModalKind>(null)
  const [pane, setPane] = useState<PaneKey>('A')
  const [toast, setToast] = useState('')
  const closeModal = useCallback(() => setModal(null), [])
  const notify = useCallback((t: string) => { setToast(t); window.setTimeout(() => setToast(''), 2600) }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setModal((m) => (m === 'palette' ? null : 'palette')) }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className={cn('relative grid h-dvh transition-[grid-template-columns] duration-200', sidebar ? 'grid-cols-[320px_minmax(0,1fr)] max-[900px]:grid-cols-[minmax(0,1fr)]' : 'grid-cols-[0px_minmax(0,1fr)] max-[900px]:grid-cols-[minmax(0,1fr)]')}>
      <div className={cn('min-w-0 overflow-hidden max-[900px]:fixed max-[900px]:inset-y-0 max-[900px]:left-0 max-[900px]:z-40 max-[900px]:w-[min(86vw,340px)] max-[900px]:transition-transform', !sidebar && 'max-[900px]:-translate-x-full')}>
        <div className="h-full w-[320px] max-[900px]:w-full"><Sidebar c={c} /></div>
      </div>
      <main className="flex min-h-0 min-w-0 flex-col">
        <Header view={view} setView={setView} sidebarOpen={sidebar} onToggle={() => setSidebar((s) => !s)} onPalette={() => setModal('palette')} />
        <AnimatePresence mode="wait" initial={false}>
          {view === 'console' ? (
            <motion.div key="console" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="bg-grid flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-3 xl:overflow-hidden">
              <ExecutiveStrip c={c} onTask={() => setModal('task')} onMemo={() => setModal('memo')} onFlag={() => setModal('flag')} />
              <CommandSearch c={c} />
              <div role="tablist" aria-label="Panels" className="flex gap-1 rounded-lg border border-line bg-panel p-1 xl:hidden">
                {PANES.map(([k, l]) => (
                  <button key={k} type="button" role="tab" aria-selected={pane === k} onClick={() => setPane(k)} className={cn('flex-1 cursor-pointer rounded-md py-2 text-[13px] font-semibold transition-colors', pane === k ? 'bg-panel3 text-ink' : 'text-mute')}>{l}</button>
                ))}
              </div>
              <div className="grid min-h-[420px] flex-1 gap-3 max-xl:h-[74vh] max-xl:flex-none xl:min-h-0 xl:grid-cols-[minmax(290px,340px)_minmax(0,1fr)_minmax(290px,330px)]">
                <div className={cn('min-h-0', pane === 'A' ? 'flex' : 'hidden', 'xl:flex [&>*]:flex-1')}><LogicTree c={c} onShow={() => setPane('B')} /></div>
                <div className={cn('min-h-0', pane === 'B' ? 'flex' : 'hidden', 'xl:flex [&>*]:flex-1')}><SourceViewer c={c} /></div>
                <div className={cn('min-h-0', pane === 'C' ? 'flex' : 'hidden', 'xl:flex [&>*]:flex-1')}><ConfidencePanel c={c} /></div>
              </div>
            </motion.div>
          ) : (
            <motion.div key="evaluation" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="bg-grid min-h-0 flex-1">
              <EvaluationDashboard />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {modal === 'task' && c.current && c.ev && <TaskModal c={c} onClose={closeModal} onToast={notify} />}
      {modal === 'memo' && c.current && c.ev && <MemoModal c={c} onClose={closeModal} onToast={notify} />}
      {modal === 'flag' && c.current && <FlagModal c={c} onClose={closeModal} onToast={notify} />}
      {modal === 'palette' && <CommandPalette c={c} onClose={closeModal} setView={setView} />}
      <AnimatePresence>
        {toast && <motion.div role="status" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="fixed bottom-4 right-4 z-[60] rounded-md border border-line2 bg-panel3 px-3.5 py-2.5 shadow-xl">{toast}</motion.div>}
      </AnimatePresence>
    </div>
  )
}
