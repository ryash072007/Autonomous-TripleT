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

Top bar: OrbitGuard wordmark, replay clock, counts per tier, "Guided demo" button. A thin ridge silhouette strip at
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
