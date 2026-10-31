import type { Config, DocData, Directive, EvalResult, QueryAnswer, ResultsPayload } from '@/types'

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`The server answered ${r.status}`)
  return r.json() as Promise<T>
}

const post = (url: string, body: unknown) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

/** Config values the backend understands (registration and engine are recorded only, never evaluated). */
export const apiConfig = (c: Config) => ({ make: c.make, model: c.model, serial: c.serial, cofa_date: c.cofa_date, part_numbers: c.part_numbers })

/** The backend addresses notices by document id; 8 multi-docket notices share one, so keep the first of each (also keeps React keys unique). */
export const getDirectives = () =>
  fetch('/directives').then((r) => json<Directive[]>(r)).then((rows) => {
    const seen = new Set<string>()
    return rows.filter((d) => (seen.has(d.doc_id) ? false : (seen.add(d.doc_id), true)))
  })
export const getDoc = (id: string) => fetch('/doc/' + encodeURIComponent(id).replace(/%40/g, '@')).then((r) => json<DocData>(r))
export const getResults = () => fetch('/results').then((r) => json<ResultsPayload>(r))
export const evaluate = (doc_id: string, c: Config) => post('/evaluate', { doc_id, config: apiConfig(c) }).then((r) => json<EvalResult>(r))
export const search = (query: string, c: Config) => post('/query', { query, config: apiConfig(c) }).then((r) => json<QueryAnswer>(r))
