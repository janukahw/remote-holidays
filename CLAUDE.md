# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Out of Range** — a static site that ranks 577 remote UK places to stay (cottages, cabins, glamping, campsites) by how cut off they are: no WiFi / no signal / off-grid / hard to reach. Listings come from five providers — National Trust, Unplugged, Unyoked, Canopy & Stars and Cool Places (the last two are aggregators). Personal project — **not** a Cloud of Goods repo, so a normal CLAUDE.md (this file) is fine.

## Commands

Plain HTML/CSS/JS — **no build system, no package manager, no tests, no linter.** The only tooling is two Python scripts (need `pip install openpyxl`). Don't invent test/lint commands; there are none.

- **View the site:** open `index.html` in a browser — it works over `file://` (data loads via a `<script>` tag; nothing is `fetch`ed). Or serve it: `python -m http.server 8000`.
- **Regenerate data** (after editing a spreadsheet in `data/` or a `SOURCES` entry): `python tools/build_data.py` — rewrites `js/data.js` and restamps cache-bust versions.
- **Cache-bust after hand-editing css/js:** `python tools/bump_version.py`.
- **Local-dev gotcha:** browsers cache `js/site.js` hard during rapid edits. Hard-refresh (Ctrl+F5) or serve from a fresh port if a change doesn't show. (Playwright/automation can't use `file://` — serve over http.)

## Architecture

Three pages — `index.html`, `browse.html`, `place.html` — share `css/styles.css`, `js/data.js` (generated) and `js/site.js`.

### Data pipeline — `tools/build_data.py`
- **Sources of truth are the spreadsheets in `data/`** (one per provider). The script is multi-source: a `SOURCES` list maps each provider's columns to one shared schema, merges all, applies the unified score, features the top few per provider, sorts, and writes `js/data.js`. **Never hand-edit `js/data.js`** — edit a spreadsheet (or add a `SOURCES` entry) and re-run.
- Per-provider quirks live in `SOURCES`, not in the site code:
  - Column names differ per provider — map them in the entry's `col`.
  - `universal_signals` injects traits universal to a provider but unscored in its sheet (e.g. every Unplugged cabin is off-grid / no-WiFi / phone-lockbox by design) so connectivity badges are correct.
  - Signal text may carry `(+N)` weight notes — stripped on import; **0-point tokens are dropped** (e.g. Unyoked "Full reception (0)" is the opposite of remote).
  - `clean_type()` always buckets free-text type prose into a small set: **Cottage / Cabin / Campsite / Hostel / Glamping / Church / Boat**.
  - Aggregators often lack lat/lng & postcode → those fields stay empty and the detail page hides the map button.
- **Duplicate guard:** the build prints `! possible duplicate` when a name slug collides across providers (keeps both with a `-N` suffix). Aggregators can re-list operator places — when adding a source, check that log and the listings. As of June 2026 there are no collisions.

### Unified remoteness score (0–100)
- The shared ranking metric is `score`, a **unified 0–100 rating, comparable across all providers** (it replaced the old per-provider, non-comparable scores). It's the sum of 7 capped dimensions: access 25, mobile signal 20, off-grid 13, WiFi 12, isolation framing 12, distance 10, wild setting 8.
- Scores live in **`data/unified_scores.json`** (`{id: {score, breakdown, why}}`), merged by `build_data.py` (falls back to the source score for any id not present). Each place also gets `scoreBreakdown` + `scoreWhy`, shown on the detail page.
- **Fairness adjustment (`adjust_for_fairness` in `build_data.py`)** corrects two systematic biases in listing-copy scoring, applied on top of the raw LLM breakdown at build time (so it's deterministic/reproducible — the raw scores stay in `unified_scores.json`): (A) if mobile signal is *unstated*, the place is off-grid, and it's remote/wilderness-framed → infer poor signal (13) or none (20 for deep-wilderness wording); (B) a sub-300m hike-in is capped at the remote-drive access tier (13), not the walk-in tier. The final `score` is recomputed as the capped sum of the (possibly adjusted) breakdown. Without this, terse NT off-grid cottages (e.g. Hafod Y Fedw) were unfairly out-ranked by brands that advertise their disconnection.
- Scores are **LLM-derived** (a fan-out pass judged each listing against the rubric; totals are recomputed as the sum of the breakdown because agents' hand-sums drift) and then **persisted** for reproducibility — re-running the scoring gives slightly different numbers. They reflect how a place is *described*, not measured GPS isolation (Cool Places is coarsest — taglines only). To re-score: chunk the listings, score each batch against the rubric, recompute sums, write `unified_scores.json`, rebuild.

### Rendering — `js/site.js`
- One IIFE; each page runs only the block whose container element exists (`#featured-grid`, `#results`, `#place-detail`).
- Each place stores raw `signals` (array) + `wifiListed` (bool). **Connectivity badges, feature filters and the connectivity sentence are derived here** via `conn()` / `feat()` (substring matches on `signals`) — add facets here, not in the data. `conn().noSignal` matches "mobile signal", "phone signal" and "No reception" (but NOT "Some/Full reception").
- Browse: `provider`/`region`/`type` facets are derived from the data; connectivity/feature are predicate lists; there's an exclude ("Hide") group; results paginate (`PAGE_SIZE = 24`). Filters are deep-linkable via query params (e.g. `browse.html?provider=Unyoked&connectivity=nowifi`).
- `place.html` renders from `?id=<slug>` (slug from the name, deduped across providers with a numeric suffix).
- Photos hotlink from each provider's CDN with `referrerpolicy="no-referrer"`; `imgFallback()` swaps in a gradient if one fails.

## Conventions & guardrails
- All data values pass through `esc()` (and `attr()` for attributes) before `innerHTML`. URL query params only ever match existing checkboxes — **never written to the DOM**. That's the only XSS surface; keep it closed.
- Cache-bust `?v=` values are content hashes stamped by `tools/bump_version.py` — don't hand-edit them.
- **Attribution / IP:** names, photos, links and locations are © their providers (National Trust, Unplugged, Unyoked, Canopy & Stars, Cool Places), shown for reference; the site is independent and non-commercial. Flag each provider's terms of use before any public deployment. Keep the footer's "scores judged from listing copy, can be wrong" + "no signal cuts both ways" safety note.

## Definition of done
All three pages render correctly when served over http, the browse filters narrow/widen with correct counts across providers, and `python tools/build_data.py` regenerates `js/data.js` (and restamps cache-bust versions) without error.
