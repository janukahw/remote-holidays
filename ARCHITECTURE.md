# Architecture — Out of Range

Big-picture map of how the site is built, scored, rendered and deployed. Day-to-day rules live in [CLAUDE.md](CLAUDE.md); user journeys in [FLOWS.md](FLOWS.md).

## At a glance

A plain static site (HTML / CSS / vanilla JS) — **no build step or framework for the site itself**. The only "build" is a Python script that turns five provider spreadsheets into one generated `js/data.js`. Hosted on GitHub Pages.

## Pipeline (source → live)

```
data/*.xlsx                      5 provider spreadsheets — the source of truth
   │
   │  python tools/build_data.py
   │    • map each provider's columns → one shared schema   (SOURCES)
   │    • normalise types (clean_type), strip signal weights, inject universal signals
   │    • merge all providers + dedupe (slug collisions are warned)
   │    • apply unified 0–100 score from data/unified_scores.json
   │        then adjust_for_fairness()  (signal inference, short-hike access ease)
   │    • feature top-N per provider, sort by score (desc)
   │    • stamp content-hash ?v= cache-busting   (tools/bump_version.py)
   ▼
js/data.js   (window.PLACES = [ …577 ])           ← GENERATED, never hand-edit
   │
   │  loaded via <script> on every page
   ▼
index.html · browse.html · place.html   +   css/styles.css   +   js/site.js
   │
   │  git push  →  GitHub Pages builds (main / root, .nojekyll)
   ▼
https://janukahw.github.io/remote-holidays/
```

## Three layers

1. **Data** — `data/*.xlsx` (one per provider) + `data/unified_scores.json` (the 0–100 scores). Only `build_data.py` reads them; its output is `js/data.js`.
2. **Scoring** — a unified 0–100 remoteness rubric of 7 capped dimensions (access 25, mobile signal 20, off-grid 13, WiFi 12, isolation 12, distance 10, wild 8). Raw per-place scores are LLM-derived and persisted in `unified_scores.json`; `build_data.py` layers **deterministic fairness corrections** (`adjust_for_fairness`) on top and recomputes the total as the capped sum. See [CLAUDE.md](CLAUDE.md).
3. **Presentation** — three HTML pages share one stylesheet and one script. `js/site.js` is a single IIFE; each page runs only the block whose container element exists. Connectivity badges and feature filters are **derived client-side** from each place's `signals` + `wifiListed` (never stored).

## Key files

| File | Role |
|---|---|
| `data/*.xlsx` | Source listings, one spreadsheet per provider |
| `data/unified_scores.json` | Raw 0–100 score + breakdown per place id |
| `tools/build_data.py` | Generates `js/data.js`: merge → score → fairness → cache-bust |
| `tools/bump_version.py` | Content-hash `?v=` cache-busting on asset links |
| `js/data.js` | Generated dataset (`window.PLACES`) |
| `js/site.js` | Rendering + filtering + score display (one IIFE) |
| `css/styles.css` | All styling (design tokens, layout, components) |
| `index/browse/place.html` | Home · browse+filter · detail (`?id=<slug>`) |

## Data model (per place)

`id, provider, name, type, region, county, town, postcode, lat, lng, wifiListed, signals[], blurb, evidence[], counter, link, images[], score, scoreBreakdown, scoreWhy, featured`.
Connectivity (no WiFi / patchy / no signal / off-grid) and features (island, bothy, dark skies, lighthouse, hard-to-reach) are **derived in `site.js`** from `signals` + `wifiListed`, not stored.

## Deployment

GitHub Pages serves `main` / root; `.nojekyll` makes it serve files as-is (no Jekyll). Every push to `main` triggers a rebuild (~1–2 min). Asset links carry a content-hash `?v=` so browsers refetch only changed files. Provider photos hotlink from each CDN with `referrerpolicy="no-referrer"`, with a gradient fallback (`imgFallback`) if one fails.
