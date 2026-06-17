# User Flows — Out of Range

Three representative journeys through the site, each with the UI touchpoints and the code / URL path behind it. Architecture in [ARCHITECTURE.md](ARCHITECTURE.md); dev rules in [CLAUDE.md](CLAUDE.md).

## 1. "Get me as far off-grid as possible" — the total-detox seeker

Wants the single most cut-off place for a no-phone week.

1. Lands on **home** (`index.html`) → hero "Switch off. Properly." → skims *How the ranking works*.
2. Clicks **"No WiFi or signal"** → `browse.html?connectivity=nowifi,nosignal` (the deep-link pre-checks those Connectivity boxes via `applyQuery()`).
3. Optionally ticks **Connectivity → Off-grid power** to narrow further; leaves **Sort = Remotest first** (score desc).
4. Scans the top cards (highest 0–100 scores — the off-grid cabins and boat-access bothies in the high-70s/low-80s) and opens one.
5. **Detail** (`place.html?id=…`): reads the **How it scores** breakdown (why it ranks so high), the *What makes it remote* chips, and *From the listing*.
6. Clicks **View on [provider]** to book on the operator's own site.

Path: `applyQuery → compute() (passGroup over connectivity predicates, AND across groups) → draw() → card → place.html → conn()/feat() + score breakdown render`.

## 2. "Remote, but I still need to work" — the connected-but-quiet planner

Wants a quiet rural stay with reliable-ish internet (remote work / family).

1. Goes straight to **Browse**.
2. Connectivity → **WiFi available** (~92 places, all National Trust — every cabin brand is deliberately Wi-Fi-free) and **Sort = Most connected first** (score asc).
3. Adds a **Region** filter (e.g. *Lake District*) to stay in one area; or types a keyword in **search**.
4. Opens a result → checks the factbox **Connectivity** note ("doesn't flag connectivity problems — assume broadly connected") and notes the deliberately **low** remoteness score.
5. Books via **View on National Trust**.

Key point: the site is honest that genuinely-connected stays score *low*, so this user effectively **inverts** the ranking to find them.

## 3. "I fancy a bothy — or a glamping trip in Wales" — the type-and-place browser

Knows the vibe and rough region, not a specific place.

1. **Browse** → **Stay type** = `Glamping` (or `Cabin`), or **Features** = `Bothy / bunkhouse`.
2. Adds **Region** (e.g. *Wales*) and/or **Provider** (e.g. *Canopy & Stars*); facets AND together to narrow.
3. Wants comforts, not a rough shelter? Ticks **Hide → Bothies & bunkhouses** to exclude them.
4. Uses **Show more** to page through results (`PAGE_SIZE` = 24 at a time); compares a few by their score badges.
5. Opens 2–3 details, compares **score breakdowns**, taps **View on map** (opens Apple Maps on iOS / Google Maps elsewhere via `mapUrl()`), then books.

Path: include facets (`feature`/`type`/`region`/`provider`) AND-combined, the `exclude` ("Hide") group removes matches, pagination caps the DOM, `mapUrl()` picks the right maps app per device.
