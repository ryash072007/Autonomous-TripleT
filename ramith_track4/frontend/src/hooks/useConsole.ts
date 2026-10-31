import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { evaluate as apiEvaluate, getDirectives, getDoc, search as apiSearch } from '@/lib/api'
import { EMPTY_CONFIG, hasModel, validCofa } from '@/lib/domain'
import type { Config, Directive, DocData, EvalResult, Refusal, Verdict } from '@/types'

export type PresetKey = 'all' | 'serial' | 'cutoff' | 'external' | 'revision' | 'withdrawn' | 'ambiguous' | 'flagged'
export type Flag = { reason: string; comment: string; status: string; at: string }
export type Notice = { text: string; kind: 'info' | 'error' | 'busy'; retry?: boolean }

/** All application state lives here so the sidebar, logic tree, source viewer and confidence panel stay in sync. */
export function useConsole() {
  const [dirs, setDirs] = useState<Directive[]>([])
  const [dirsError, setDirsError] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [ev, setEv] = useState<EvalResult | null>(null)
  const [cfg, setCfg] = useState<Config>(EMPTY_CONFIG)
  const [question, setQuestion] = useState('')
  const [activeCond, setActiveCond] = useState<string | null>(null)
  const [openConds, setOpenConds] = useState<Set<string>>(new Set())
  const [searchIds, setSearchIds] = useState<string[] | null>(null)
  const [searchVerdicts, setSearchVerdicts] = useState<Record<string, Verdict>>({})
  const [refusal, setRefusal] = useState<Refusal | null>(null)
  const [preset, setPreset] = useState<PresetKey>('all')
  const [notice, setNotice] = useState<Notice>({ text: 'Ready. Select a directive or ask a question.', kind: 'info' })
  const [busy, setBusy] = useState(false)
  const [flags, setFlags] = useState<Record<string, Flag>>(() => JSON.parse(localStorage.getItem('adFlags') ?? '{}'))
  const docs = useRef<Record<string, DocData>>({})
  const [doc, setDoc] = useState<DocData | null>(null)
  const [docError, setDocError] = useState(false)
  const seq = useRef(0)

  useEffect(() => {
    getDirectives().then(setDirs).catch(() => setDirsError(true))
  }, [])

  const current = useMemo(() => dirs.find((d) => d.doc_id === selected) ?? null, [dirs, selected])

  const loadDoc = useCallback(async (id: string) => {
    setDocError(false)
    if (docs.current[id]) { setDoc(docs.current[id]); return }
    setDoc(null)
    try {
      const d = await getDoc(id)
      docs.current[id] = d
      setDoc(d)
    } catch { setDocError(true) }
  }, [])

  const runEvaluate = useCallback(async (id: string, c: Config, preview: boolean) => {
    if (!validCofa(c.cofa_date)) { setNotice({ text: 'The certificate date must be YYYY-MM-DD.', kind: 'error' }); return }
    const mine = ++seq.current
    setBusy(true)
    setNotice({ text: preview ? 'Reading the notice…' : 'Evaluating applicability conditions…', kind: 'busy' })
    try {
      const r = await apiEvaluate(id, c)
      if (mine !== seq.current) return
      setEv(r)
      setActiveCond(r.conditions.find((k) => k.span)?.id ?? null)
      setNotice({ text: preview && !hasModel(c) ? 'Notice loaded. Enter an aircraft configuration and press Evaluate.' : `Evaluation complete: ${r.conditions.length} condition(s) checked against the quoted text.`, kind: 'info' })
    } catch (e) {
      if (mine !== seq.current) return
      setEv(null)
      setNotice({ text: `Evaluation failed: ${(e as Error).message}`, kind: 'error' })
    } finally { if (mine === seq.current) setBusy(false) }
  }, [])

  const select = useCallback(async (id: string | null, c?: Config) => {
    setSelected(id)
    setEv(null)
    setActiveCond(null)
    setOpenConds(new Set())
    if (!id) { setDoc(null); return }
    void loadDoc(id)
    await runEvaluate(id, c ?? cfg, true)
  }, [cfg, loadDoc, runEvaluate])

  const evaluateSelected = useCallback(() => { if (selected) void runEvaluate(selected, cfg, false) }, [selected, cfg, runEvaluate])

  const runSearch = useCallback(async () => {
    const q = question.trim()
    if (!q) { setNotice({ text: 'Enter a question first.', kind: 'error' }); return }
    if (!validCofa(cfg.cofa_date)) { setNotice({ text: 'The certificate date must be YYYY-MM-DD.', kind: 'error' }); return }
    setBusy(true)
    setNotice({ text: 'Retrieving regulatory sources…', kind: 'busy' })
    try {
      const a = await apiSearch(q, cfg)
      if (a.type === 'refusal' && a.refusal) {
        setSearchIds(null); setSearchVerdicts({}); setRefusal(a.refusal); setSelected(null); setEv(null); setDoc(null)
        setNotice({ text: `The tool declined to answer: ${a.refusal.code}`, kind: 'info' })
        return
      }
      setRefusal(null)
      const verdicts: Record<string, Verdict> = {}
      a.cards.forEach((k) => { if (k.verdict) verdicts[k.doc_id] = k.verdict.verdict })
      setSearchVerdicts(verdicts)
      setSearchIds(a.cards.map((k) => k.doc_id))
      // Adopt everything the backend parsed out of the question text (make, model, serial, certificate date, part numbers) so the
      // follow-up evaluation uses the same configuration the search used; anything the user typed explicitly wins.
      const u = a.config_used ?? {}
      const next: Config = {
        ...cfg,
        make: cfg.make || u.make || '', model: cfg.model || u.model || '', serial: cfg.serial || u.serial || '',
        cofa_date: cfg.cofa_date || u.cofa_date || '', part_numbers: cfg.part_numbers || (u.part_numbers ?? []).join(', '),
      }
      setCfg(next)
      setNotice({ text: `${a.cards.length} source${a.cards.length === 1 ? '' : 's'} retrieved in ${a.latency_ms.total} ms. ${a.warnings?.[0] ?? ''}`, kind: 'info' })
      if (a.cards[0]) await select(a.cards[0].doc_id, next)
      else setNotice({ text: 'No sources found. Try adding a make, model or docket number.', kind: 'error' })
    } catch (e) {
      setNotice({ text: `Search failed: ${(e as Error).message}. Check that the server is running, then retry.`, kind: 'error', retry: true })
    } finally { setBusy(false) }
  }, [question, cfg, select])

  const saveFlag = useCallback((id: string, f: Flag | null) => {
    setFlags((prev) => {
      const next = { ...prev }
      if (f) next[id] = f; else delete next[id]
      localStorage.setItem('adFlags', JSON.stringify(next))
      return next
    })
  }, [])

  const clearConfig = useCallback(() => setCfg(EMPTY_CONFIG), [])

  return {
    dirs, dirsError, selected, current, ev, cfg, setCfg, question, setQuestion, activeCond, setActiveCond, openConds, setOpenConds,
    searchIds, searchVerdicts, refusal, preset, setPreset, notice, busy, flags, doc, docError,
    select, evaluateSelected, runSearch, saveFlag, clearConfig,
  }
}
export type ConsoleApi = ReturnType<typeof useConsole>
