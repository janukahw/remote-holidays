#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Content-hash cache-busting for the static assets.

Rewrites the `?v=` query on each asset reference in the HTML files to a short
hash of that asset's current contents, so browsers refetch a file only when it
actually changes (and never serve a stale css/js after an edit).

Run after editing css/js:   python tools/bump_version.py
(build_data.py calls stamp() automatically, so data rebuilds restamp too.)
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ["css/styles.css", "js/data.js", "js/site.js"]
PAGES = ["index.html", "browse.html", "place.html"]


def stamp():
    versions = {}
    for a in ASSETS:
        f = ROOT / a
        if f.exists():
            versions[a] = hashlib.sha1(f.read_bytes()).hexdigest()[:8]

    for page in PAGES:
        p = ROOT / page
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        for a, v in versions.items():
            # Match  "css/styles.css"  or  "css/styles.css?v=abcd1234"  (either quote).
            pattern = r'(["\'])' + re.escape(a) + r'(?:\?v=[0-9a-f]+)?\1'
            html = re.sub(pattern, lambda m, a=a, v=v: f"{m.group(1)}{a}?v={v}{m.group(1)}", html)
        p.write_text(html, encoding="utf-8")

    print("  cache-bust versions:", versions)
    return versions


if __name__ == "__main__":
    stamp()
