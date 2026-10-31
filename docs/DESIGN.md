# Design brief: OrbitGuard console

Stack: **React + Vite + TypeScript** front end in `web/`, **FastAPI** in `ca_triage/api.py`. No Streamlit.

## Mood

Golden-hour Earth. Modelled on the NASA "Perseverance" landing page the team picked as reference: one calm full-bleed
scene, a warm peach haze sky, layered rocky ridges silhouetted at the bottom, a huge condensed white title, lots of
empty sky. Ours is Earth: the ridges are terrestrial (with a ground-station dish on the nearest ridge), and the sky
holds satellites, not a helicopter.

The dashboard keeps the same palette but becomes an ops console: dense, quiet, readable. The scene is the
atmosphere; the data is the content. Never let decoration compete with a tier colour.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--sky-top` | `#EFC3A8` | Sky gradient top |
| `--sky-mid` | `#F4D3BC` | Sky gradient middle |
| `--haze` | `#F8E4CF` | Horizon haze, panel background |
| `--ridge-far` | `#DDB096` | Farthest ridge |
| `--ridge-mid` | `#C08D78` | |
| `--ridge-near` | `#93614F` | |
| `--rock` | `#5A3A33` | Foreground rock, primary text on light |
| `--ink-soft` | `#7A5A50` | Secondary text (subtitle "COLLISION TRIAGE" colour) |
| `--paper` | `#FFF8F1` | Cards |
| `--safe` | `#2F7A68` | Safe tier (muted teal, readable on haze) |
| `--elevated` | `#C77A12` | Elevated tier (amber) |
| `--critical` | `#B0302A` | Critical tier (deep red) |
| `--abstain` | `#5B5F8F` | "Analyst decides" (dusk violet, the only cool accent) |

Every tier is also shown with a text label and an icon shape (circle / triangle / octagon), never by colour alone.

Fonts (Google Fonts): **Barlow Condensed 600/700** for the display title and big numbers, **Manrope** for UI text,
**JetBrains Mono** for telemetry values. Numbers use tabular figures.

## Landing (the first 10 seconds a judge sees)

One screen, no scrolling required, one obvious action.

```
 [dish mark]                                                           [satellite, slow drift]
                                O R B I T G U A R D            (huge, condensed, white)
                         ──────────── ◠ ────────────
                                COLLISION   TRIAGE             (letter-spaced, --ink-soft)

          2,167 close approaches.  186 need a decision.  You have two days.   (numbers from the API)

                          [ Open the queue → ]     How it works (40 s)

   · · lights drifting across the sky = real test events, coloured by tier; Critical ones pulse faintly · ·

 ▁▂▃▅▆▇ far ridge ▆▅▃▂▁▂▃▅▇▆ mid ridge ▅▃▂ near ridge with ground-station dish ▃▅▆▇▆▅
 replay clock T−2d 04:12 · 3 events entered the 24 h window                 Data: ESA CAC (CC BY 4.0)
```

- The sky lights are the real event list from the API. Hovering one shows its ID and tier; clicking jumps to that
  event in the queue. That is the "live" hook and a shortcut into the tool.
- "How it works" is a 3-step overlay (Read CDMs → Estimate Pc + tier with uncertainty → Analyst decides), skippable,
  with the "99 of 551 Critical events looked fine at T−2 days" fact. Not a long scroll story.
- Motion: slow parallax on the ridges, satellites drifting on arcs. `prefers-reduced-motion` turns it off.

## Console

Top bar: OrbitGuard wordmark, **data toggle `Test dataset | Live`** (Test is default; Live shows a banner: "Space-Track public CDMs, tiered by rule only, model inputs not published" and the snapshot time), replay clock, counts per tier, "Guided demo" button. A thin ridge silhouette strip at
the bottom of the page keeps the scene.

1. **Queue** (left, ~360 px): events sorted by tier then time to TCA. Each row: tier icon + label, event ID, time to
   TCA, miss distance, Pc, abstain badge. Filter chips by tier and object type. Keyboard j/k.
2. **Event** (right):
   - Header: tier with **the rule that fired** in plain words, tier probabilities, "Analyst decides" if the tier set
     has more than one tier, Act / Wait / Dismiss recommendation with expected cost.
   - CDM timeline: risk and miss distance against time to TCA, with the T−2 d line and the tier bands shaded.
   - Encounter geometry: relative position in RTN with a straight-line fly-by, labelled as a short-encounter
     approximation.
   - "Why": top feature contributions, covariance-fragility badge, what-if sliders (miss distance, sigmas) that
     re-score live through the API.
   - Brief: LLM text with a "checked against computed facts" or "template fallback" tag.
   - Actions: Accept / Escalate / Dismiss with a note, written to the audit log, shown as a timeline with hashes.
3. **Next 24 h**: events whose TCA falls inside the replay window and are Critical or inside 1 km. The
   problem statement's "warnings in 24 hour frame" view.
4. **Evidence**: baselines vs model, confusion matrices, coverage of the tier sets, drift audit, failure gallery.
   Every number reads from `artifacts/evidence/*.json` and shows its source file.

## Ease of use for judges

- Two clicks from landing to any feature. "Guided demo" walks through three pre-picked events: one clear Critical,
  one the model catches early, one it gets wrong (the failure case).
- Glossary tooltips on Pc, TCA, CDM, RTN, miss distance.
- The app works with no API key (template brief) and no network beyond localhost.
- One command starts everything (`python scripts/serve.py` builds the web app if needed and serves it from FastAPI).

## Assets

All scenery is procedural SVG (layered ridge paths, haze gradients, dish and satellite line art) drawn in code.
No stock or NASA imagery, so no licensing questions and it stays sharp at any size.

## Globe and visual insights (added 2026-10-31)

**Display-only orbit data.** The globe uses `t_j2k_sma, t_j2k_ecc, t_j2k_inc, c_j2k_sma, c_j2k_ecc, c_j2k_inc,
t_h_apo, t_h_per, c_h_apo, c_h_per` from the CDMs. These are **never model inputs** (the allowed-column rule is for
the model); they only draw orbits. They live in a separate `orbit_display` block in the scored JSON, and the UI
labels them "display only".

**Globe** (three.js, warm palette, not a photo texture): a dotted-continent Earth (world-atlas TopoJSON points) in
`--ridge-mid` on a `--haze` ocean with a soft atmosphere rim. Two views:
1. **Event globe** (event detail): the two objects' orbit rings at their real altitude and inclination. The
   right ascension of the ascending node isn't in the data, so both rings are drawn to pass through one
   conjunction point. The caption says exactly that. The conjunction point pulses in the event's tier colour,
   and a small inset shows the RTN miss geometry. Drag to rotate; slow auto-rotate otherwise.
2. **Fleet globe** (Insights page and optional landing backdrop): every test event as a point on a shell at its
   altitude, at a deterministic longitude, latitude bounded by inclination. Coloured by tier, sized by
   1/time to TCA. It shows the LEO crowding by altitude band (most events cluster in the 500–900 km bands).

**Insights page** (every chart reads JSON from the API, with source shown):
- Workload funnel: CDMs → events → model alerts → "Analyst decides" → Act. Shows the reduction the tool gives.
- Tier flow 2 days out → at TCA (Sankey or stacked bars), from train events: where persistence fails.
- Altitude band × tier heat strip, and object type × tier bars.
- Risk vs time to TCA spaghetti for a sample of events, plus the median band per final tier: "most events fade,
  a few rise late".
- Reliability curve (calibration) for P(Critical), and the conformal α vs abstain vs miss curve.
- Space weather: Critical rate by F10 bucket (only if the evidence shows an effect; otherwise say "no effect seen").


## Console v2 (2026-10-31)

The landing look now runs through the whole console, and the console is organised around the analyst's question
("what should I do, and what happens if I am wrong?").

- **Scenery everywhere.** The golden-hour gradient and the drifting tier lights sit fixed behind every page; the layered
  ridges and the dish mound sit fixed at the bottom at about 14vh (`web/src/Backdrop.tsx`, reusing `Ridges`). Content is
  translucent paper cards (about 88% alpha, backdrop blur, soft shadow, 18 px radius, hairline border only).
- **Type.** Barlow Condensed for page and event headlines ("EVENT 1387" beside the tier word); letter-spaced Manrope
  small caps for section labels ("COLLISION TRIAGE", "WHERE", "HOW SURE"). Monospace only for raw telemetry in the
  specialist drawer. The top bar is transparent with a small landing-style wordmark; the replay clock moved to the
  Next 24 h page.
- **Queue by action.** Three collapsible sections with big counts: ACT NOW (Act), YOUR CALL (Analyst decides, Wait),
  CLEARED (Dismiss). Without recommendations (live) it groups by tier. Cards: tier icon and word, id, time to TCA, miss
  distance, a "debris risk: high" badge for the top 5% by harm rank. Sorted by expected harm when `consequence` exists,
  else by time to TCA. Search by event id; `j`/`k` still move.
- **Event page as a story.** (a) hero: huge id, tier, recommendation chip, the brief's first sentence; (b) three tiles:
  WHERE (globe), TREND (miss distance and Pc on one chart, T-2 d line, tier bands), HOW SURE (segmented probability bars,
  tier-set line, plain-language flag chips, the forecast-threshold sentence); (c) IF THEY COLLIDE; (d) a sticky decision
  bar (Accept / Escalate / Dismiss + note, audit trail as an expander); (e) a collapsed SPECIALIST DETAIL drawer
  (full brief, raw numbers, RTN geometry, cost slider, what-if and sensitivity).
- **If they collide.** Stat cards read from `consequence` (fragments >= 10 cm, catastrophic, active satellites in the band,
  30-day exposure, harm rank vs Pc rank). "Simulate collision" plays `consequence.debris_cloud` on the globe: 150 sample
  fragments (phase, radial, cross-track offsets) interpolated between 0, 1, 6, 24 and 168 h with a log-time scrubber;
  other test events inside the affected altitude band are faint points that light up after about a day. Labelled as a
  model with stated assumptions (simplified NASA breakup model, masses from radar size, two-body spread, no drag). The
  cloud exists only for the top events by harm and the demo events; others show the stats and say so. All field-name
  mapping lives in `web/src/Consequence.tsx`.
- **Insights.** Adds a Pc-rank vs harm-rank scatter (log axes) with off-diagonal events in red.
- **Tour.** Starts by itself the first time the console opens (localStorage key `orbitguard_tour_done`; if storage is
  blocked it runs once per page load). "Skip tour" ends it for good; "Guided tour" replays it. Steps come from
  `artifacts/demo.json`; `worst_consequence` adds step 4 ("Low Pc, but if they collide") and auto-plays the simulation.
  The card sits bottom-left, over the list and clear of the panel it points at. Hash options for screenshots:
  `#queue&notour`, `&demo=N`, `&e=ID`, `&ds=live`.
