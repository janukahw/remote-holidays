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
        # (one-line taglines, keyword-scored — indicative). Checked June 2026: no
        # overlap with the providers above (its own cross-reference column only flags
        # an external "Guardian" file not used here). No coords/postcode/quote column.
        "provider": "Cool Places",
        "file": "CoolPlaces_digitaldetox_remoteness_ranking.xlsx",
        "sheet": "Ranked remotest first",
        "evidence_split": None,
        "wifi_free_by_design": False,
        "universal_signals": [],
        "col": {
            "name": "Place", "type": "Type", "region": "Region",
            "county": None, "town": None,
            "postcode": None, "latlng": None, "wifi_listed": None,
            "signals": "Remoteness signals", "counter": "Counter-signals",
            "evidence": None, "blurb": "Listing summary",
            "link": "Listing link", "images": "Full-size image URLs (array)",
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

        score = cell(row, "score")
        out.append({
            "id": slug,
            "score": score if score != "" else 0,
            "name": name,
            "provider": src["provider"],
            "type": type_val,
            "region": str(cell(row, "region")).strip(),
            "county": str(cell(row, "county")).strip(),
            "town": str(cell(row, "town")).strip(),
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
        for p in places:
            u = unified.get(p["id"])
            if u:
                p["score"] = u["score"]
                p["scoreBreakdown"] = u.get("breakdown")
                p["scoreWhy"] = u.get("why", "")
                applied += 1
        print(f"  unified scores applied: {applied}/{len(places)}")
        missing = [p["id"] for p in places if p["id"] not in unified]
        if missing:
            print(f"  ! {len(missing)} places missing a unified score: {missing[:10]}")

    # Feature the top few of each provider (by the score now in effect).
    by_provider = {}
    for p in places:
        by_provider.setdefault(p["provider"], []).append(p)
    for group in by_provider.values():
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
    payload = json.dumps(places, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(header + "window.PLACES = " + payload + ";\n", encoding="utf-8")
    print(f"Wrote {len(places)} places to {OUT} ({OUT.stat().st_size // 1024} KB)")

    # Refresh content-hash cache-busting on the HTML asset links.
    stamp_versions()


if __name__ == "__main__":
    main()
