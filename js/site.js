/* ============================================================
   Out of Range — shared rendering + page logic.
   Depends on window.PLACES (js/data.js loaded first).
   Data is National Trust holiday lets ranked remotest-first;
   connectivity + feature flags are derived here from `signals`.
   ============================================================ */
(function () {
  "use strict";

  var PLACES = window.PLACES || [];
  var PAGE_SIZE = 24;

  /* ---------- helpers ---------- */
  function esc(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function attr(str) {
    return esc(str).replace(/'/g, "&#39;");
  }

  // iOS (incl. iPad reporting as Mac) → Apple Maps app. Everything else
  // (Android opens the Google Maps app, desktop opens Google Maps web).
  var IS_IOS =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  function mapUrl(lat, lng, name) {
    if (IS_IOS) {
      return "https://maps.apple.com/?ll=" + lat + "," + lng +
        "&q=" + encodeURIComponent(name);
    }
    return "https://www.google.com/maps/search/?api=1&query=" +
      encodeURIComponent(lat + "," + lng);
  }

  function has(place, sub) {
    return place.signals.some(function (s) {
      return s.indexOf(sub) !== -1;
    });
  }

  // Connectivity is the whole point — derive it from the listing signals.
  function conn(p) {
    var wifiNone = !p.wifiListed || has(p, "No Wi-Fi");
    var wifiPatchy = !wifiNone && has(p, "Wi-Fi unreliable");
    return {
      offGrid: has(p, "Off-grid"),
      wifiNone: wifiNone,
      wifiPatchy: wifiPatchy,
      wifiGood: !wifiNone && !wifiPatchy, // WiFi listed and not flagged unreliable
      noSignal: has(p, "mobile signal") || has(p, "phone signal") || has(p, "No reception"),
      noWater: has(p, "No mains water"),
    };
  }

  function feat(p) {
    return {
      island: has(p, "On an island"),
      bothy: has(p, "Bothy"),
      darkSkies: has(p, "Dark skies"),
      lighthouse: has(p, "Lighthouse"),
      hardToReach: has(p, "Hard to reach"),
    };
  }

  var ICON = {
    wifiOff:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 1l22 22"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.58 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>',
    signalOff:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 22l20-20"/><path d="M5 20v-3"/><path d="M9.5 20v-6"/><path d="M14 20v-7.5"/><path d="M18.5 20V8"/></svg>',
    offgrid:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 21l9-15 9 15z"/><path d="M3 21h18"/></svg>',
    pin:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    ext:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>',
    back:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>',
  };

  // image fallback to a gradient when the National Trust CDN image won't load.
  window.imgFallback = function (img) {
    var host = img.parentNode;
    if (host) host.classList.add("media--fallback");
    img.remove();
  };

  function badges(p) {
    var c = conn(p);
    var out = [];
    if (c.offGrid)
      out.push('<span class="badge badge--offgrid">' + ICON.offgrid + "Off-grid power</span>");
    if (c.wifiNone)
      out.push('<span class="badge badge--nowifi">' + ICON.wifiOff + "No WiFi</span>");
    else if (c.wifiPatchy)
      out.push('<span class="badge badge--patchy">' + ICON.wifiOff + "Patchy WiFi</span>");
    if (c.noSignal)
      out.push('<span class="badge badge--nosignal">' + ICON.signalOff + "No/poor signal</span>");
    if (!out.length) return "";
    return '<div class="badges">' + out.join("") + "</div>";
  }

  function media(p, cls) {
    var img = p.images && p.images[0];
    var inner = img
      ? '<img loading="lazy" referrerpolicy="no-referrer" alt="' +
        attr(p.name) + '" src="' + attr(img) +
        '" onerror="imgFallback(this)">'
      : "";
    return '<div class="' + cls + ' media--fallback">' + inner + "</div>";
  }

  function card(p) {
    return (
      '<a class="card" href="place.html?id=' + encodeURIComponent(p.id) + '">' +
      media(p, "card__media") +
      '<span class="card__rank">Score ' + p.score + "</span>" +
      '<div class="card__body">' +
      '<h3 class="card__title">' + esc(p.name) + "</h3>" +
      '<p class="card__loc">' + esc(p.provider) + " · " + esc(p.region) +
      (p.type ? " · " + esc(p.type) : "") + "</p>" +
      '<p class="card__blurb">' + esc(p.blurb) + "</p>" +
      '<div class="card__badges">' + badges(p) + "</div>" +
      "</div>" +
      "</a>"
    );
  }

  function unique(list, key) {
    var seen = {}, out = [];
    list.forEach(function (p) {
      if (p[key] && !seen[p[key]]) { seen[p[key]] = true; out.push(p[key]); }
    });
    return out.sort();
  }

  /* ============================================================
     HOMEPAGE — featured grid
     ============================================================ */
  var featuredGrid = document.getElementById("featured-grid");
  if (featuredGrid) {
    featuredGrid.innerHTML = PLACES.filter(function (p) { return p.featured; })
      .map(card)
      .join("");
  }

  /* ============================================================
     BROWSE — filters + results + pagination
     ============================================================ */
  var resultsEl = document.getElementById("results");
  if (resultsEl) {
    var connectivityFilters = [
      // "WiFi available" intentionally omitted — Out of Range users want disconnection,
      // not connectivity, so the facets surface only remoteness-relevant options.
      { value: "patchywifi", label: "Patchy WiFi", test: function (p) { return conn(p).wifiPatchy; } },
      { value: "nowifi", label: "No WiFi", test: function (p) { return conn(p).wifiNone; } },
      { value: "offgrid", label: "Off-grid power", test: function (p) { return conn(p).offGrid; } },
      { value: "nosignal", label: "No / poor mobile signal", test: function (p) { return conn(p).noSignal; } },
    ];
    var featureFilters = [
      { value: "island", label: "On an island", test: function (p) { return feat(p).island; } },
      { value: "bothy", label: "Bothy / bunkhouse", test: function (p) { return feat(p).bothy; } },
      { value: "darksky", label: "Dark skies", test: function (p) { return feat(p).darkSkies; } },
      { value: "lighthouse", label: "Lighthouse / lookout", test: function (p) { return feat(p).lighthouse; } },
      { value: "hardtoreach", label: "Hard to reach", test: function (p) { return feat(p).hardToReach; } },
    ];
    // "Hide" group: a checked option REMOVES matching places from results.
    var excludeFilters = [
      { value: "bothy", label: "Bothies & bunkhouses", test: function (p) { return feat(p).bothy; } },
    ];
    // Bundle small providers (<=2 listings) under a single "Other" facet in the
    // Provider filter. A place's real `provider` is unchanged everywhere else
    // (cards, detail page, "View on X"); this only groups the browse facet.
    var OTHER_PROVIDER = "Other";
    var providerCounts = {};
    PLACES.forEach(function (p) {
      providerCounts[p.provider] = (providerCounts[p.provider] || 0) + 1;
    });
    function providerGroup(p) {
      return providerCounts[p.provider] > 2 ? p.provider : OTHER_PROVIDER;
    }
    // Distinct facet values: named providers (>2 listings) A–Z, then "Other" last.
    var providers = [], seenProvider = {}, hasOther = false;
    PLACES.forEach(function (p) {
      var g = providerGroup(p);
      if (g === OTHER_PROVIDER) { hasOther = true; return; }
      if (!seenProvider[g]) { seenProvider[g] = true; providers.push(g); }
    });
    providers.sort();
    if (hasOther) providers.push(OTHER_PROVIDER);
    var regions = unique(PLACES, "region");
    var types = unique(PLACES, "type");

    function countWhere(fn) { return PLACES.filter(fn).length; }

    function checkRow(group, value, label, count) {
      return (
        '<label class="check">' +
        '<input type="checkbox" data-group="' + group + '" value="' + attr(value) + '">' +
        "<span>" + esc(label) + "</span>" +
        '<span class="count">' + count + "</span>" +
        "</label>"
      );
    }

    var filtersHost = document.getElementById("filter-controls");
    var html = "";

    html += '<fieldset class="filter-group"><legend>Provider</legend>';
    providers.forEach(function (pr) {
      html += checkRow("provider", pr, pr, countWhere(function (p) { return providerGroup(p) === pr; }));
    });
    html += "</fieldset>";

    html += '<fieldset class="filter-group"><legend>Connectivity</legend>';
    connectivityFilters.forEach(function (c) {
      html += checkRow("connectivity", c.value, c.label, countWhere(c.test));
    });
    html += "</fieldset>";

    html += '<fieldset class="filter-group"><legend>Features</legend>';
    featureFilters.forEach(function (f) {
      html += checkRow("feature", f.value, f.label, countWhere(f.test));
    });
    html += "</fieldset>";

    html += '<fieldset class="filter-group"><legend>Hide</legend>';
    excludeFilters.forEach(function (e) {
      html += checkRow("exclude", e.value, e.label, countWhere(e.test));
    });
    html += "</fieldset>";

    html += '<fieldset class="filter-group"><legend>Stay type</legend>';
    types.forEach(function (t) {
      html += checkRow("type", t, t, countWhere(function (p) { return p.type === t; }));
    });
    html += "</fieldset>";

    html += '<fieldset class="filter-group"><legend>Region</legend>';
    regions.forEach(function (r) {
      html += checkRow("region", r, r, countWhere(function (p) { return p.region === r; }));
    });
    html += "</fieldset>";

    filtersHost.innerHTML = html;

    var searchInput = document.getElementById("search");
    var sortSelect = document.getElementById("sort");
    var countEl = document.getElementById("result-count");
    var moreWrap = document.getElementById("more-wrap");
    var moreBtn = document.getElementById("show-more");

    var shown = PAGE_SIZE;
    var filtered = PLACES.slice();

    function selected(group) {
      return Array.prototype.map.call(
        filtersHost.querySelectorAll('input[data-group="' + group + '"]:checked'),
        function (n) { return n.value; }
      );
    }

    function passGroup(p, values, filters) {
      // OR within a derived group: pass if any selected predicate matches.
      return values.some(function (v) {
        var f = filters.filter(function (x) { return x.value === v; })[0];
        return f && f.test(p);
      });
    }

    function compute() {
      var providerSel = selected("provider");
      var connSel = selected("connectivity");
      var featSel = selected("feature");
      var exclSel = selected("exclude");
      var typeSel = selected("type");
      var regionSel = selected("region");
      var q = (searchInput.value || "").trim().toLowerCase();

      filtered = PLACES.filter(function (p) {
        if (exclSel.length && passGroup(p, exclSel, excludeFilters)) return false;
        if (providerSel.length && providerSel.indexOf(providerGroup(p)) === -1) return false;
        if (connSel.length && !passGroup(p, connSel, connectivityFilters)) return false;
        if (featSel.length && !passGroup(p, featSel, featureFilters)) return false;
        if (typeSel.length && typeSel.indexOf(p.type) === -1) return false;
        if (regionSel.length && regionSel.indexOf(p.region) === -1) return false;
        if (q) {
          var hay = (p.name + " " + p.region + " " + p.county + " " + p.town + " " + p.blurb).toLowerCase();
          if (hay.indexOf(q) === -1) return false;
        }
        return true;
      });

      var sort = sortSelect.value;
      if (sort === "connected") filtered.sort(function (a, b) { return a.score - b.score; });
      else if (sort === "az") filtered.sort(function (a, b) { return a.name.localeCompare(b.name); });
      else filtered.sort(function (a, b) { return b.score - a.score; });
    }

    function draw() {
      var total = filtered.length;
      var slice = filtered.slice(0, shown);

      countEl.textContent =
        total === 0
          ? "No places"
          : "Showing " + Math.min(shown, total) + " of " + total + (total === 1 ? " place" : " places");

      if (total === 0) {
        resultsEl.innerHTML =
          '<div class="empty"><p>No places match those filters.</p>' +
          '<p class="muted">Try removing one — or clear them all to start again.</p></div>';
      } else {
        resultsEl.innerHTML =
          '<div class="card-grid">' + slice.map(card).join("") + "</div>";
      }
      moreWrap.hidden = shown >= total;
    }

    function render() {
      shown = PAGE_SIZE;
      compute();
      draw();
    }

    function applyQuery() {
      var params = new URLSearchParams(window.location.search);
      ["provider", "connectivity", "feature", "exclude", "type", "region"].forEach(function (group) {
        var raw = params.get(group);
        if (!raw) return;
        raw.split(",").forEach(function (val) {
          try {
            var box = filtersHost.querySelector(
              'input[data-group="' + group + '"][value="' + CSS.escape(val) + '"]'
            );
            if (box) box.checked = true;
          } catch (e) { /* ignore malformed query values */ }
        });
      });
    }

    filtersHost.addEventListener("change", render);
    searchInput.addEventListener("input", render);
    sortSelect.addEventListener("change", render);
    moreBtn.addEventListener("click", function () {
      shown += PAGE_SIZE;
      draw();
    });
    document.getElementById("clear-filters").addEventListener("click", function () {
      filtersHost.querySelectorAll("input:checked").forEach(function (n) { n.checked = false; });
      searchInput.value = "";
      render();
    });

    var toggle = document.getElementById("filters-toggle");
    var filtersPanel = document.getElementById("filters");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var open = filtersPanel.getAttribute("data-open") === "true";
        filtersPanel.setAttribute("data-open", String(!open));
        toggle.setAttribute("aria-expanded", String(!open));
      });
    }

    applyQuery();
    render();
  }

  /* ============================================================
     PLACE DETAIL
     ============================================================ */
  var placeRoot = document.getElementById("place-detail");
  if (placeRoot) {
    var id = new URLSearchParams(window.location.search).get("id");
    var place = PLACES.filter(function (p) { return p.id === id; })[0];

    if (!place) {
      document.title = "Place not found — Out of Range";
      placeRoot.innerHTML =
        '<div class="wrap section"><h1>Place not found</h1>' +
        '<p class="muted">We couldn\'t find that place.</p>' +
        '<p><a class="btn btn--ghost" href="browse.html">Browse all places</a></p></div>';
    } else {
      document.title = place.name + " — Out of Range";

      var hasCoords = place.lat != null && place.lng != null;
      var maps = hasCoords ? mapUrl(place.lat, place.lng, place.name) : "";

      var signalChips = place.signals
        .map(function (s) { return '<span class="chip">' + esc(s) + "</span>"; })
        .join("");

      var evidence = place.evidence
        .map(function (q) { return "<li>" + esc(q) + "</li>"; })
        .join("");

      var gallery = (place.images || [])
        .slice(1)
        .map(function (src) {
          return (
            '<div class="gallery__item media--fallback">' +
            '<img loading="lazy" referrerpolicy="no-referrer" alt="' + attr(place.name) +
            '" src="' + attr(src) + '" onerror="imgFallback(this)"></div>'
          );
        })
        .join("");

      // Unified 0-100 remoteness breakdown.
      var bd = place.scoreBreakdown;
      var dims = [
        ["access", "Access", 25], ["signal", "Mobile signal", 20], ["offgrid", "Off-grid", 13],
        ["wifi", "WiFi", 12], ["framing", "Isolation", 12], ["distance", "Distance", 10], ["wild", "Wild setting", 8],
      ];
      var scoreBlock = bd
        ? '<h2 class="block-h">How it scores <span class="score-total">' + place.score + "<small>/100</small></span></h2>" +
          (place.scoreWhy ? '<p class="muted score-why">' + esc(place.scoreWhy) + "</p>" : "") +
          '<div class="scorebars">' +
          dims.map(function (d) {
            var v = bd[d[0]] || 0, cap = d[2], pct = Math.round((v / cap) * 100);
            return '<div class="bar"><span class="bar__label">' + d[1] + "</span>" +
              '<span class="bar__track"><span class="bar__fill" style="inline-size:' + pct + '%"></span></span>' +
              '<span class="bar__val">' + v + "<small>/" + cap + "</small></span></div>";
          }).join("") +
          "</div>"
        : "";

      placeRoot.innerHTML =
        '<header class="place-hero">' +
          media(place, "place-hero__bg") +
          '<div class="wrap place-hero__inner">' +
            '<span class="eyebrow">' + esc(place.provider) + " · " + esc(place.region) +
              (place.type ? " · " + esc(place.type) : "") + "</span>" +
            "<h1>" + esc(place.name) + "</h1>" +
            badges(place) +
          "</div>" +
        "</header>" +
        '<div class="wrap">' +
          '<div class="place-body">' +
            "<div>" +
              '<a class="back-link" href="browse.html">' + ICON.back + "All places</a>" +
              '<div class="prose"><p>' + esc(place.blurb) + "</p></div>" +
              (signalChips
                ? '<h2 class="block-h">What makes it remote</h2>' +
                  '<div class="chips">' + signalChips + "</div>"
                : "") +
              scoreBlock +
              (evidence
                ? '<h2 class="block-h">From the listing</h2><ul class="quotes">' + evidence + "</ul>"
                : "") +
              (place.counter
                ? '<p class="caveat"><strong>Worth knowing:</strong> ' + esc(place.counter) + ".</p>"
                : "") +
              (gallery ? '<div class="gallery">' + gallery + "</div>" : "") +
            "</div>" +
            '<aside class="factbox">' +
              "<h2>The practicals</h2>" +
              '<dl>' +
                fact("Provider", place.provider) +
                fact("Remoteness score", place.score + " / 100") +
                fact("Region", place.region) +
                fact("County", place.county) +
                fact("Nearest town / area", place.town) +
                fact("Postcode", place.postcode) +
                fact("Stay type", place.type) +
              "</dl>" +
              '<div class="connectivity-note"><strong>Connectivity.</strong> ' +
                connText(place) + "</div>" +
              '<div class="factbox__actions">' +
                (place.link
                  ? '<a class="btn btn--primary" href="' + attr(place.link) +
                    '" target="_blank" rel="noopener">' + ICON.ext + "View on " + esc(place.provider) + "</a>"
                  : "") +
                (hasCoords
                  ? '<a class="btn btn--ghost" href="' + attr(maps) +
                    '" target="_blank" rel="noopener">' + ICON.pin + "View on map</a>"
                  : "") +
              "</div>" +
            "</aside>" +
          "</div>" +
        "</div>";
    }
  }

  function connText(p) {
    var c = conn(p);
    var bits = [];
    if (c.wifiNone) bits.push("no WiFi");
    else if (c.wifiPatchy) bits.push("unreliable WiFi");
    if (c.noSignal) bits.push("little or no mobile signal");
    if (c.offGrid) bits.push("off-grid power (solar / generator, no mains)");
    if (c.noWater) bits.push("no mains water");
    var s = bits.length
      ? "Expect " + bits.join(", ") + "."
      : "The listing doesn't flag connectivity problems — assume it's broadly connected.";
    return esc(s) + " Derived from the listing text, not measured — always confirm before you rely on it.";
  }

  function fact(label, value) {
    if (!value && value !== 0) return "";
    return '<div class="fact"><dt>' + esc(label) + "</dt><dd>" + esc(value) + "</dd></div>";
  }
})();
