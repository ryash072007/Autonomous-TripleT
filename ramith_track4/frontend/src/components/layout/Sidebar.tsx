import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Plane, Search } from 'lucide-react'
import ShinyText from '@/components/ShinyText'
import { Badge, EmptyState, inputCls } from '@/components/ui'
import { shortTitle, streamBadge } from '@/lib/domain'
import { cn } from '@/lib/utils'
import type { ConsoleApi, PresetKey } from '@/hooks/useConsole'

const PRESETS: [PresetKey, string][] = [
  ['all', 'All directives'], ['serial', 'Serial-number conditions'], ['cutoff', 'Certificate-date conditions'], ['external', 'Outside-document references'],
  ['revision', 'Under revision'], ['withdrawn', 'Withdrawn'], ['ambiguous', 'Ambiguous (last search)'], ['flagged', 'Flagged by you'],
]
const selectCls = cn(inputCls, 'py-1.5 pr-1')

export function Sidebar({ c }: { c: ConsoleApi }) {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [make, setMake] = useState('')
  const [sort, setSort] = useState<'date' | 'status'>('date')

  const makes = useMemo(() => [...new Set(c.dirs.map((d) => d.make).filter(Boolean))].sort(), [c.dirs])
  const view = useMemo(() => {
    const byId = new Map(c.dirs.map((d) => [d.doc_id, d]))
    const base = c.searchIds ? c.searchIds.map((id) => byId.get(id)).filter((d): d is NonNullable<typeof d> => !!d) : c.dirs
    const needle = q.trim().toLowerCase()
    let v = base.filter((d) => {
      const revised = d.status.startsWith('REVISED') || !d.latest
      if (make && d.make !== make) return false
      if (status === 'WITHDRAWN' && !d.withdrawn) return false
      if (status === 'REVISED' && !revised) return false
      if (status === 'NPRM' && (d.withdrawn || revised)) return false
      return !needle || `${d.docket} ${d.title} ${d.make} ${d.snippet}`.toLowerCase().includes(needle)
    })
    const p = c.preset
    if (p === 'serial') v = v.filter((d) => d.flags.serial)
    else if (p === 'cutoff') v = v.filter((d) => d.flags.cutoff)
    else if (p === 'external') v = v.filter((d) => d.flags.external)
    else if (p === 'revision') v = v.filter((d) => d.status.startsWith('REVISED') || !d.latest)
    else if (p === 'withdrawn') v = v.filter((d) => d.withdrawn)
    else if (p === 'ambiguous') v = v.filter((d) => c.searchVerdicts[d.doc_id] === 'CANNOT_DETERMINE')
    else if (p === 'flagged') v = v.filter((d) => c.flags[d.doc_id])
    return sort === 'status' ? [...v].sort((a, b) => a.status.localeCompare(b.status)) : v
  }, [c.dirs, c.searchIds, c.preset, c.searchVerdicts, c.flags, q, status, make, sort])

  return (
    <aside aria-label="Directives stream" className="flex h-full min-h-0 flex-col border-r border-line bg-panel">
      <div className="flex items-center gap-2.5 px-3.5 pb-2 pt-3.5">
        <div className="grid size-9 place-items-center rounded-lg border border-[#3b6db3] bg-gradient-to-br from-[#2a5a9e] to-[#1e3a5f]"><Plane className="size-5 text-white" aria-hidden /></div>
        <div className="min-w-0">
          <ShinyText text="AD Applicability Desk" color="#e7eef6" shineColor="#7cc8ff" speed={4} className="text-[14.5px] font-semibold leading-tight" />
          <div className="text-[11px] text-mute">Regulatory evidence console</div>
        </div>
      </div>
      <div className="flex items-center gap-1.5 px-3.5 pb-2.5 text-[11px] text-mute">
        <span className={cn('size-1.5 rounded-full', c.dirsError ? 'bg-red' : 'bg-green')} aria-hidden />
        {c.dirsError ? 'Server unreachable' : c.dirs.length ? `${c.dirs.length} directives indexed` : 'Connecting…'}
      </div>
      <div className="flex items-center justify-between px-3.5 py-1.5 text-[11px] font-bold tracking-[0.12em] text-dim">
        <span>DIRECTIVES STREAM</span><span>{view.length}{c.searchIds ? ' results' : ''}</span>
      </div>
      <div className="flex flex-col gap-2 border-b border-line px-3.5 pb-2.5">
        <label className="relative block">
          <span className="sr-only">Search directives</span>
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-dim" aria-hidden />
          <input className={cn(inputCls, 'pl-8')} placeholder="Search directives…" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <div className="grid grid-cols-3 gap-1.5">
          <select aria-label="Filter by status" className={selectCls} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All status</option><option value="REVISED">Revised</option><option value="WITHDRAWN">Withdrawn</option><option value="NPRM">Proposed</option>
          </select>
          <select aria-label="Filter by manufacturer" className={selectCls} value={make} onChange={(e) => setMake(e.target.value)}>
            <option value="">All makes</option>{makes.map((m) => <option key={m}>{m}</option>)}
          </select>
          <select aria-label="Sort" className={selectCls} value={sort} onChange={(e) => setSort(e.target.value as 'date' | 'status')}>
            <option value="date">Newest</option><option value="status">Status</option>
          </select>
        </div>
        <div role="group" aria-label="Quick filters" className="-mx-3.5 flex gap-1.5 overflow-x-auto px-3.5 pb-1">
          {PRESETS.map(([k, l]) => (
            <button key={k} type="button" aria-pressed={c.preset === k} onClick={() => c.setPreset(k)}
              className={cn('shrink-0 cursor-pointer rounded-full border px-2.5 py-0.5 text-[11.5px] transition-colors', c.preset === k ? 'border-cyan/55 bg-cyan/15 text-cyan' : 'border-line2 bg-panel2 text-mute hover:border-[#46617d] hover:text-ink')}>
              {l}
            </button>
          ))}
        </div>
      </div>
      <div role="listbox" aria-label="Directives" className="min-h-0 flex-1 overflow-auto">
        {c.dirsError && <EmptyState icon={<Search className="size-5" />} title="Directives could not be loaded" text="Check that the server is running and reload." />}
        {!c.dirsError && !view.length && c.dirs.length > 0 && <EmptyState icon={<Search className="size-5" />} title="No directives match" text="Clear a filter or search for something else." />}
        {view.slice(0, 300).map((d) => {
          const sel = c.selected === d.doc_id
          const verdict = sel && c.ev && c.cfg.model ? c.ev.verdict.verdict : c.searchVerdicts[d.doc_id]
          const b = streamBadge(d, verdict)
          return (
            <motion.button
              key={d.doc_id} type="button" role="option" aria-selected={sel} onClick={() => void c.select(d.doc_id)}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}
              className={cn('relative block w-full cursor-pointer border-b border-line px-3.5 py-2.5 text-left transition-colors hover:bg-panel2', sel && 'bg-panel3')}
            >
              {sel && <motion.span layoutId="sel-bar" className="absolute inset-y-0 left-0 w-[3px] bg-cyan" />}
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11.5px] text-accent">{d.docket}</span>
                <Badge className={b.cls}>{b.text}</Badge>
              </div>
              <div className="mt-1 line-clamp-2 text-[13px] font-semibold leading-snug [overflow-wrap:anywhere]">{shortTitle(d.title)}</div>
              <div className="mt-0.5 text-[11.5px] text-mute">{d.make} · {d.issue_date}{c.flags[d.doc_id] ? ' · flagged' : ''}</div>
              <div className="mt-1 line-clamp-2 text-xs text-dim">{d.snippet}</div>
            </motion.button>
          )
        })}
      </div>
      <div className="border-t border-line px-3.5 py-2 text-[11px] text-dim">Real records from the supplied FAA NPRM spreadsheet. No synthetic data.</div>
    </aside>
  )
}
