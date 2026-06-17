#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build js/data.js from one or more provider spreadsheets.

Usage:
    python tools/build_data.py

Each provider has its own spreadsheet and column layout (see SOURCES below).
All providers are normalised into one shared schema, merged, sorted by
remoteness score (highest first), and written to js/data.js as
`window.PLACES = [...]` (UTF-8). Re-run whenever a spreadsheet changes.

To add a provider: drop its .xlsx in data/, add a SOURCES entry mapping its
columns to the logical fields, and re-run. Nothing else needs to change.

The site (js/site.js) derives connectivity badges and feature filters from the
`signals` array + `wifiListed` flag, so this script keeps data close to source.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bump_version import stamp as stamp_versions

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "js" / "data.js"
DATA = ROOT / "data"

MAX_EVIDENCE = 6
MAX_EVIDENCE_LEN = 320
MAX_IMAGES = 3
FEATURED_PER_PROVIDER = 2
WEIGHT_RE = re.compile(r"\s*\([+-]?\d+(?:\.\d+)?\)")  # strips "(+5)" / "(-3)" weight notes

# A `col` value of None means the provider's sheet has no such column.
SOURCES = [
    {
        "provider": "National Trust",
        "file": "NT_remoteness_ranking.xlsx",
        "sheet": "Ranked remotest first",
        "evidence_split": " | ",
        # Off-grid/Wi-Fi vary per property here, so read from the sheet.
        "wifi_free_by_design": False,
        "universal_signals": [],
        "col": {
            "name": "Property", "type": "Type", "region": "Region",
            "county": "County", "town": "Town/area", "postcode": "Postcode",
            "latlng": "Lat, Long", "wifi_listed": "Wi-Fi listed?",
            "signals": "Remoteness signals", "counter": "Counter-signals",
            "evidence": "Evidence (quotes from listing)", "blurb": "Listing summary",
            "link": "Listing link", "images": "Image URLs",
            "score": "Remoteness score",
        },
    },
    {
        "provider": "Unplugged",
        "file": "Unplugged_remoteness_ranking.xlsx",
        "sheet": "Ranked remotest first",
        "evidence_split": None,  # single quote per cabin
        # Every Unplugged cabin is off-grid (solar), Wi-Fi-free and ships a phone
        # lockbox by brand design; the sheet doesn't score these universal traits,
        # so inject them here for the connectivity badges to be correct.
        "wifi_free_by_design": True,
        "universal_signals": ["Off-grid / no mains electricity", "No Wi-Fi", "Phone lockbox provided"],
        "col": {
            "name": "Cabin", "type": "Type", "region": "Region (escape-from)",
            "county": "Area / county", "town": "Nearest city & travel time",
            "postcode": None, "latlng": None, "wifi_listed": None,
            "signals": "Remoteness signals", "counter": "Counter-signals",
            "evidence": "Evidence (quote from listing)", "blurb": "Listing summary",
            "link": "Listing link", "images": "Full-size image URLs (array)",
            "score": "Remoteness score",
        },
    },
    {
        "provider": "Unyoked",
        "file": "Unyoked_UK_remoteness_ranking.xlsx",
        "sheet": "Ranked remotest first",
        "evidence_split": None,
        # Every Unyoked cabin is off-grid by design (not scored). Phone reception
        # VARIES per cabin, so don't inject "No signal" — it comes from the signals.
        "wifi_free_by_design": True,
        "universal_signals": ["Off-grid / no mains electricity", "No Wi-Fi"],
        # Listing summary here is logistics (drive/train/hike), so it's the better
        # "From the listing" detail; the evocative blurb makes the card teaser.
        "col": {
            "name": "Cabin", "type": "Type", "region": "Region",
            "county": "Area / landscape", "town": "Nearest city & drive",
            "postcode": None, "latlng": None, "wifi_listed": None,
            "signals": "Remoteness signals", "counter": "Counter-signals",
            "evidence": "Listing summary", "blurb": "Evidence (listing blurb)",
            "link": "Listing link", "images": "Full-size image URLs (array)",
            "score": "Remoteness score",
        },
    },
    {
        # Aggregator/marketplace: a hand-picked editorial "most remote / off-grid"
        # shortlist of independent sites. Checked June 2026 — no overlap with the
        # operator providers above. No wifi field; treated as no-wifi (off-grid
        # collection). Type is free-text prose, so normalise it. No coords/postcode.
        "provider": "Canopy & Stars",
        "file": "CanopyAndStars_remote_offgrid_ranking.xlsx",
        "sheet": "Ranked remotest first",
        "evidence_split": None,
        "wifi_free_by_design": False,
        "universal_signals": [],
        "col": {
            "name": "Place", "type": "Type", "region": "Region",
            "county": None, "town": "Nearest public transport",
            "postcode": None, "latlng": None, "wifi_listed": None,
            "signals": "Remoteness signals", "counter": "Counter-signals",
            "evidence": "Evidence (guest quote)", "blurb": "Listing summary",
            "link": "Listing link", "images": "Full-size image URLs (array)",
            "score": "Remoteness score",
        },
    },
    {
        # Aggregator: Cool Places 'digital detox' editorial collection. Coarser data
        # (one-line taglines, keyword-scored — indicative). Cool Places is enquiry-only
        # (no booking on its pages), so it is NOT the real source: each row's true
        # bookable home was researched and recorded per-row in "Source provider" +
        # "Original source link" (the Cool Places URL is kept in "Listing link" for
        # provenance). `provider_col` makes the per-row brand override this entry's
        # "Cool Places" default; rows with no researched source keep "Cool Places".
        # `featured` is still grouped by this default (see `_group`), so reassigning
        # ~40 listings to ~20 micro-providers doesn't flood the homepage.
        "provider": "Cool Places",
        "file": "CoolPlaces_digitaldetox_remoteness_ranking.xlsx",
        "sheet": "Ranked remotest first",
        "evidence_split": None,
        "wifi_free_by_design": False,
        "universal_signals": [],
        "provider_col": "Source provider",
        "col": {
            "name": "Place", "type": "Type", "region": "Region",
            "county": None, "town": None,
            "postcode": None, "latlng": None, "wifi_listed": None,
            "signals": "Remoteness signals", "counter": "Counter-signals",
            "evidence": None, "blurb": "Listing summary",
            "link": "Original source link", "images": "Full-size image URLs (array)",
            "score": "Remoteness score",
        },
    },
]


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "place"


GLAMPING_WORDS = (
    "safari", "yurt", "pod", "shepherd", "bell tent", "tent", "treehouse",
    "dome", "roulotte", "wagon", "caravan", "carriage", "gypsy", "tipi", "glamping", "hut",
)


SCORE_CAPS = {"access": 25, "signal": 20, "offgrid": 13, "wifi": 12, "framing": 12, "distance": 10, "wild": 8}
# Listing wording that means signal WAS assessed (so don't infer it).
_SIGNAL_STATED = ("reception", "mobile signal", "phone signal")
# Wording implying genuinely no signal vs merely-remote (poor signal).
_DEEP_WILD = ("wilderness", "most remote", "cut off", "miles from a road", "no road",
              "peninsula", "great wilderness", "only people", "full hermit", "turn your back on civilisation")
_REMOTE_FRAMING = ("remote", "secluded", "isolated", "hidden", "away from it all", "away-from-it-all",
                   "on an island", "national park", "moor", "mountain", "hard to reach", "wilds", "off the beaten")


def adjust_for_fairness(place):
    """Correct two systematic biases in the listing-copy scores (see CLAUDE.md):
    (A) terse listings (esp. National Trust) leave mobile signal unstated even when an
        off-grid, remote place plainly has none — infer it; (B) a sub-300m hike-in was
        over-credited as a 'notable walk-in'. Returns a tag for logging, mutates breakdown."""
    bd = place.get("scoreBreakdown")
    if not bd:
        return None
    sigs = place.get("signals", [])
    sig_text = " ".join(sigs).lower()
    text = sig_text + " " + (place.get("blurb") or "").lower()
    off_grid = any("off-grid" in s.lower() for s in sigs)
    tag = None

    # (A) Infer signal when unstated + off-grid + remote-framed.
    if bd.get("signal", 0) == 0 and off_grid and not any(t in sig_text for t in _SIGNAL_STATED):
        if any(w in text for w in _DEEP_WILD):
            bd["signal"] = 20; tag = "signal->20"
        elif any(w in text for w in _REMOTE_FRAMING):
            bd["signal"] = 13; tag = "signal->13"

    # (B) Ease access for short hike-ins over-credited above the remote-drive tier.
    hikes = [int(x) for x in re.findall(r"hike-in\s*(\d+)\s*m", sig_text)]
    if hikes and min(hikes) < 300 and bd.get("access", 0) > 13:
        bd["access"] = 13; tag = (tag + " +access<=13") if tag else "access<=13"
    return tag


def clean_type(text):
    """Bucket free-text type descriptions into a small set of filterable categories.
    Applied to every provider so the Stay-type filter stays clean."""
    tl = str(text).lower()
    if "champing" in tl or "church" in tl:
        return "Church"
    if "hostel" in tl:
        return "Hostel"
    if "campsite" in tl or "camping" in tl:
        return "Campsite"
    if "cruising" in tl or "ship" in tl:  # actual vessels, not "cottage (boat access)"
        return "Boat"
    if any(w in tl for w in GLAMPING_WORDS):
        return "Glamping"
    if "cottage" in tl:
        return "Cottage"
    return "Cabin"


# Travel-destination region taxonomy, grouped by country. Each listing is mapped
# to exactly one canonical region by substring-matching its county / region / town
# text (county first — it's the richest, cleanest signal) against the keyword lists
# below, in order; first hit wins. Order is most-specific -> least, so the
# country-level fallbacks (bare "wales"/"scotland") sit LAST. Keep NI keys as full
# "county X" phrases so "down"/"londonderry" don't clash with "South Downs"/"London".
REGION_RULES = [
    ("Wales", "North Wales", ["gwynedd", "conwy", "anglesey", "snowdonia", "eryri", "betws", "wrexham", "flintshire", "denbighshire", "llangollen", "berwyn", "clwydian", "north wales"]),
    ("Wales", "Mid Wales", ["ceredigion", "powys", "tylwch", "machynlleth", "mid wales"]),
    ("Wales", "South & West Wales", ["pembroke", "carmarthen", "monmouth", "brecon", "bannau", "swansea", "gower", "glamorgan", "south wales"]),
    ("Scotland", "Scottish Highlands", ["inverness", "ardnish", "lochaber", "fort william", "skye", "wester ross", "sutherland", "caithness", "highland"]),
    ("Scotland", "Argyll", ["argyll", "bute", "oban", "bonawe", "lochgilphead"]),
    ("Scotland", "Cairngorms & Aberdeenshire", ["cairngorm", "aberdeenshire", "grampian", "speyside", "aviemore"]),
    ("Scotland", "Scottish Borders & Perthshire", ["scottish borders", "perthshire", "stirling", "dumfries", "galloway", "lothian", "fife"]),
    ("Northern Ireland", "Northern Ireland", ["county fermanagh", "county down", "county antrim", "county londonderry", "county tyrone", "county armagh", "northern ireland"]),
    ("England", "Cornwall", ["cornwall", "bodmin"]),
    ("England", "Devon", ["devon", "exeter", "dartmoor"]),
    ("England", "Dorset", ["dorset", "cranborne"]),
    ("England", "Somerset & Wiltshire", ["somerset", "wiltshire", "bristol", "frome", "porlock", "exmoor", "wessex downs"]),
    ("England", "Cotswolds & Gloucestershire", ["cotswold", "gloucester"]),
    ("England", "Peak District & Derbyshire", ["peak district", "derbyshire"]),
    ("England", "Lake District & Cumbria", ["cumbria", "lake district", "lakeland", "ullswater", "ennerdale"]),
    ("England", "Yorkshire", ["yorkshire", "dalby"]),
    ("England", "Northumberland & North East", ["northumberland", "county durham", "tyne & wear", "tyne and wear"]),
    ("England", "Shropshire & the Marches", ["shropshire", "herefordshire", "worcestershire", "staffordshire", "welsh border"]),
    ("England", "Cheshire & the North West", ["cheshire", "peckforton", "beeston", "tarporley", "manchester", "lancashire"]),
    ("England", "Norfolk", ["norfolk"]),
    ("England", "Suffolk", ["suffolk", "dedham"]),
    ("England", "Isle of Wight", ["isle of wight"]),
    ("England", "New Forest & Hampshire", ["new forest", "hampshire", "candover"]),
    ("England", "Kent, Surrey & Sussex", ["kent", "surrey", "sussex", "south downs", "high weald", "tunbridge", "south of london"]),
    ("England", "East Midlands", ["nottingham", "leicestershire", "northamptonshire", "lincolnshire", "notts", "rutland"]),
    ("England", "Cambridgeshire & the East", ["cambridgeshire", "essex", "east anglia", "saffron walden", "finchingfield"]),
    ("England", "Chilterns & Home Counties", ["hertfordshire", "berkshire", "buckingham", "oxford", "oxon", "chiltern", "thatcham", "thames", "west of london", "north of london", "gaddesden", "westmill"]),
    ("Wales", "Wales", ["wales", "cymru"]),
    ("Scotland", "Scotland", ["scotland", "scottish"]),
]


def map_region(region, county, town):
    """Map a listing to (country, canonical_region) from its location text.
    County is matched first as it's the cleanest signal; region/town are
    fallbacks. Returns ('England', 'Elsewhere in England') only if nothing hits
    (currently never — all known listings resolve to a specific region)."""
    text = " || ".join([county or "", region or "", town or ""]).lower()
    for country, canon, keywords in REGION_RULES:
        if any(kw in text for kw in keywords):
            return country, canon
    return "England", "Elsewhere in England"


def strip_weights(text):
    return WEIGHT_RE.sub("", text)


def clean_quote(q):
    q = strip_weights(q).strip()
    q = re.sub(r"^[\*\-\s]+", "", q)
    return q.replace("**", "").strip()


def split_latlng(value):
    if not value:
        return None, None
    parts = str(value).split(",")
    if len(parts) != 2:
        return None, None
    try:
        return round(float(parts[0]), 6), round(float(parts[1]), 6)
    except ValueError:
        return None, None


def load_source(src, seen_ids):
    wb = openpyxl.load_workbook(DATA / src["file"], read_only=True, data_only=True)
    ws = wb[src["sheet"]]
    rows = list(ws.iter_rows(values_only=True))
    idx = {h: i for i, h in enumerate(rows[0])}
    cmap = src["col"]

    def cell(row, key):
        name = cmap.get(key)
        if not name or name not in idx:
            return ""
        v = row[idx[name]]
        return v if v is not None else ""

    out = []
    for row in rows[1:]:
        name = str(cell(row, "name")).strip()
        if not name:
            continue

        base = slugify(name)
        if base in seen_ids:
            seen_ids[base]["n"] += 1
            print(f"  ! possible duplicate: {name!r} ({src['provider']}) "
                  f"shares a name with {seen_ids[base]['first']} — kept both, check it's not the same place")
            slug = f"{base}-{seen_ids[base]['n']}"
        else:
            seen_ids[base] = {"n": 1, "first": f"{name!r} ({src['provider']})"}
            slug = base

        # Signals: strip weight notes, drop blanks and 0-point tokens (e.g.
        # Unyoked's "Full reception (0)" is the opposite of a remoteness signal),
        # then prepend the provider's universal traits.
        sheet_signals = []
        for raw in str(cell(row, "signals")).split(";"):
            m = WEIGHT_RE.search(raw)
            if m and float(m.group(0).strip().strip("()")) == 0:
                continue
            label = strip_weights(raw).strip()
            if label:
                sheet_signals.append(label)
        signals = src["universal_signals"] + [s for s in sheet_signals if s not in src["universal_signals"]]

        # Evidence: one column, either a single quote or " | "-joined.
        raw_ev = str(cell(row, "evidence"))
        ev_parts = raw_ev.split(src["evidence_split"]) if src["evidence_split"] else [raw_ev]
        evidence = []
        for q in ev_parts:
            cq = clean_quote(q)
            if cq:
                evidence.append(cq[:MAX_EVIDENCE_LEN])
            if len(evidence) >= MAX_EVIDENCE:
                break

        images = [u.strip() for u in str(cell(row, "images")).splitlines() if u.strip()][:MAX_IMAGES]

        counter = strip_weights(str(cell(row, "counter"))).strip().strip("()").strip()
        if counter == "-":
            counter = ""

        lat, lng = split_latlng(cell(row, "latlng"))
        wifi_listed = False if src["wifi_free_by_design"] else (
            str(cell(row, "wifi_listed")).strip().lower() == "yes"
        )

        type_val = clean_type(str(cell(row, "type")).strip())

        # Normalise the messy per-provider location strings to one canonical
        # travel region (+ its country) for the grouped Region filter; keep the
        # raw county/town for search and the detail page's specificity.
        raw_region = str(cell(row, "region")).strip()
        county = str(cell(row, "county")).strip()
        town = str(cell(row, "town")).strip()
        country, region = map_region(raw_region, county, town)

        # Provider is the source default, unless the source declares a per-row
        # provider column (e.g. Cool Places, whose true source varies per listing).
        provider = src["provider"]
        pcol = src.get("provider_col")
        if pcol and pcol in idx and row[idx[pcol]] not in (None, ""):
            provider = str(row[idx[pcol]]).strip()

        score = cell(row, "score")
        out.append({
            "id": slug,
            "score": score if score != "" else 0,
            "name": name,
            "provider": provider,
            "_group": src["provider"],
            "type": type_val,
            "country": country,
            "region": region,
            "county": county,
            "town": town,
            "postcode": str(cell(row, "postcode")).strip(),
            "lat": lat,
            "lng": lng,
            "wifiListed": wifi_listed,
            "signals": signals,
            "blurb": str(cell(row, "blurb")).strip(),
            "evidence": evidence,
            "counter": counter,
            "link": str(cell(row, "link")).strip(),
            "images": images,
            "featured": False,
        })
    return out


def main():
    seen_ids = {}
    places = []
    for src in SOURCES:
        loaded = load_source(src, seen_ids)
        places.extend(loaded)
        print(f"  {src['provider']}: {len(loaded)} places")

    # Apply the unified 0-100 remoteness score (generated by tools/score workflow),
    # so all providers are on one comparable scale. Falls back to the per-provider
    # source score for any id not present.
    scores_file = DATA / "unified_scores.json"
    if scores_file.exists():
        unified = json.loads(scores_file.read_text(encoding="utf-8"))
        applied = 0
        adjusted = 0
        for p in places:
            u = unified.get(p["id"])
            if u:
                p["scoreBreakdown"] = dict(u.get("breakdown") or {})
                p["scoreWhy"] = u.get("why", "")
                if adjust_for_fairness(p):
                    adjusted += 1
                bd = p["scoreBreakdown"]
                p["score"] = sum(min(SCORE_CAPS.get(k, 0), int(v)) for k, v in bd.items())
                applied += 1
        print(f"  unified scores applied: {applied}/{len(places)} (fairness-adjusted: {adjusted})")
        missing = [p["id"] for p in places if p["id"] not in unified]
        if missing:
            print(f"  ! {len(missing)} places missing a unified score: {missing[:10]}")

    # Feature the top few of each source (by the score now in effect). Grouped by
    # `_group` (the originating source/sheet), NOT the display provider, so a
    # per-row-reassigned source like Cool Places still contributes only its top few.
    by_group = {}
    for p in places:
        by_group.setdefault(p["_group"], []).append(p)
    for group in by_group.values():
        for p in sorted(group, key=lambda x: -x["score"])[:FEATURED_PER_PROVIDER]:
            p["featured"] = True

    # Highest remoteness score first.
    places.sort(key=lambda p: -p["score"])

    providers = sorted({p["provider"] for p in places})
    header = (
        "/*\n"
        " * Out of Range — places data (GENERATED).\n"
        " *\n"
        " * Remote UK stays ranked by a keyword-based remoteness score derived from\n"
        " * each listing's own copy. Sorted highest-score first.\n"
        f" * {len(places)} places from: {', '.join(providers)}.\n"
        " *\n"
        " * Do NOT edit by hand — edit the spreadsheets in data/ and re-run:\n"
        " *   python tools/build_data.py\n"
        " *\n"
        " * `score` is a UNIFIED 0-100 remoteness rating (data/unified_scores.json),\n"
        " * applied across all providers so they are directly comparable. Connectivity\n"
        " * badges / feature filters are derived in js/site.js from `signals` + `wifiListed`.\n"
        " */\n"
    )
    for p in places:
        p.pop("_group", None)  # internal featuring-group key, not part of the schema
    payload = json.dumps(places, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(header + "window.PLACES = " + payload + ";\n", encoding="utf-8")
    print(f"Wrote {len(places)} places to {OUT} ({OUT.stat().st_size // 1024} KB)")

    # Refresh content-hash cache-busting on the HTML asset links.
    stamp_versions()


if __name__ == "__main__":
    main()
