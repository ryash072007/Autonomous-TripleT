import { useEffect, useMemo, useRef } from 'react'
import { Copy, FileText } from 'lucide-react'
import { Btn, EmptyState, Eyebrow, Pane, Skeleton } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { ConsoleApi } from '@/hooks/useConsole'

const SOURCE = { fr_text: 'Federal Register full text', embedded: 'Spreadsheet-embedded text', summary: 'Summary only' } as const
type Seg = { s: number; e: number; id: string | null; active: boolean }

function Meta({ k, v, wide, mono }: { k: string; v: string; wide?: boolean; mono?: boolean }) {
  return <div className={cn(wide && 'col-span-2')}><div className="text-[10px] font-bold uppercase tracking-widest text-dim">{k}</div><div className={cn('text-[12.5px] [overflow-wrap:anywhere]', mono && 'font-mono text-xs')}>{v}</div></div>
}

export function SourceViewer({ c }: { c: ConsoleApi }) {
  const { doc, ev, activeCond } = c
  const box = useRef<HTMLDivElement>(null)
  const cond = ev?.conditions.find((k) => k.id === activeCond) ?? null
  const sec = doc?.applicability.section ?? null
  const span: [number, number] | null = cond?.span ?? (sec ? [sec.char_start, sec.char_end] : null)

  const parts = useMemo(() => {
    if (!doc) return null
    const src = doc.text
    const wrapEnd = src.indexOf('<body><pre>')
    const hideTo = wrapEnd >= 0 && (!span || wrapEnd + 11 <= span[0]) ? wrapEnd + 11 : 0
    const segs: Seg[] = []
    if (span) segs.push({ s: span[0], e: span[1], id: activeCond, active: true })
    ev?.conditions.forEach((k) => { if (k.span && (!span || k.span[0] >= span[1] || k.span[1] <= span[0])) segs.push({ s: k.span[0], e: k.span[1], id: k.id, active: false }) })
    segs.sort((a, b) => a.s - b.s)
    return { src, hideTo, segs }
  }, [doc, ev, span, activeCond])

  useEffect(() => {
    const m = box.current?.querySelector<HTMLElement>('mark[data-active="true"]')
    if (m && box.current) box.current.scrollTo({ top: Math.max(0, m.offsetTop - box.current.clientHeight / 3), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  }, [parts])

  const copy = () => {
    if (!doc || !span) return
    const s = `${doc.title}; docket ${doc.docket}; ${doc.citation ?? ''}; characters ${span[0]}-${span[1]}; proposed rule (NPRM), not legally binding.`
    void navigator.clipboard?.writeText(s)
  }

  const body = () => {
    if (!c.current) return <EmptyState icon={<FileText className="size-5" />} title="No source selected" text="The notice text, with the quoted passage highlighted, appears here." />
    if (c.docError) return <EmptyState icon={<FileText className="size-5" />} title="Source could not be loaded" text="Check the server, then select the directive again." />
    if (!doc || !parts) return <div className="flex flex-col gap-2"><Skeleton className="w-1/2" /><Skeleton className="h-52 w-full" /></div>
    const trail = ev?.revision_trail ?? []
    const out: React.ReactNode[] = []
    let pos = parts.hideTo
    if (parts.hideTo) out.push(<span key="w" className="markup" aria-hidden>{parts.src.slice(0, parts.hideTo)}</span>)
    parts.segs.forEach((g, i) => {
      if (g.s < pos) return
      out.push(parts.src.slice(pos, g.s))
      out.push(<mark key={i} className="cite" data-active={g.active} onClick={() => { if (g.id) { c.setActiveCond(g.id); c.setOpenConds((p) => new Set(p).add(g.id!)) } }}>{parts.src.slice(g.s, g.e)}</mark>)
      pos = g.e
    })
    out.push(parts.src.slice(pos))
    return (
      <>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border border-line bg-panel2 p-3">
          <Meta wide k="Notice" v={doc.title} />
          <Meta k="Type" v="NPRM (proposed rule)" /><Meta k="Docket" v={doc.docket} mono /><Meta k="Revision status" v={ev?.status ?? c.current.status} /><Meta k="Text source" v={SOURCE[doc.source] ?? doc.source} />
          <Meta wide k="Citation" v={`${doc.citation ?? '—'} ${doc.pages ?? ''}`} />
          {span && <><Meta k="Highlighted span" v={`${span[0]}–${span[1]}`} mono /><Meta wide k="Highlighted passage relates to" v={cond ? cond.label : 'Applicability paragraph'} /></>}
        </div>
        {trail.length > 1 && (
          <div>
            <Eyebrow className="mb-1.5">Revision history</Eyebrow>
            <ol className="ml-1">
              {[...trail].sort((a, b) => (a.date ?? '').localeCompare(b.date ?? '')).map((e) => (
                <li key={e.doc_id} className={cn('relative border-l-2 pb-2.5 pl-3.5 text-xs', e.doc_id === ev?.latest_doc_id ? 'border-cyan' : 'border-line2')}>
                  <span className={cn('absolute -left-[6px] top-1 size-2.5 rounded-full border-2', e.doc_id === ev?.latest_doc_id ? 'border-cyan bg-cyan' : 'border-line2 bg-panel')} />
                  <strong className="capitalize">{e.event.replace(/_/g, ' ')}</strong> <span className="text-dim">{e.date}</span> <span className="font-mono text-dim">{e.doc_id}{e.doc_id === ev?.latest_doc_id ? ' · latest' : ''}</span>
                </li>
              ))}
            </ol>
            <p className="text-xs text-dim">Text-level differences between revisions are not available in this dataset; only the dated history is shown.</p>
          </div>
        )}
        {doc.is_summary_only && <div className="rounded-md border border-amber/50 bg-amber/10 p-2.5 text-[12.5px] text-amber">Only the spreadsheet summary is available for this notice; there is no full text to quote.</div>}
        <div ref={box} className="relative min-h-72 flex-1 overflow-auto rounded-md border border-line bg-[#0b121a]">
          <div className="sticky top-0 z-10 flex justify-between gap-3 border-b border-line bg-[#0b121a] px-3.5 py-1.5 text-[11.5px] text-dim">
            <span><span className="rounded bg-[#ffd05a]/15 px-1.5 py-px text-[10px] font-bold uppercase tracking-widest text-[#f0cb63]">Original regulatory text</span> &nbsp;highlight = extracted quotation</span>
            <span className="hidden sm:inline">click a highlight to jump to its condition</span>
          </div>
          <pre tabIndex={0} aria-label="Notice text with the quoted passage highlighted" className="mx-auto max-w-[80ch] whitespace-pre-wrap px-5 py-4 font-read text-[15px] leading-[1.7] text-[#d6dfe9] [overflow-wrap:anywhere]">{out}</pre>
        </div>
      </>
    )
  }

  return (
    <Pane title="Regulatory evidence" icon={<FileText className="size-3.5" />} actions={doc && span ? <Btn size="sm" onClick={copy}><Copy className="size-3.5" />Copy citation</Btn> : null}>
      {body()}
    </Pane>
  )
}
