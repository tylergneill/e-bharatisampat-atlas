// about.html's only scripted behavior: the theme toggle.
//
// The scheme <select> needs nothing here -- initStaticTranslit() binds its own
// "change" listener, and this page's Devanagari is all hand-written .sa prose,
// with no tree.json titles to re-render.
//
// The theme icons and handler are duplicated from app.js rather than shared,
// because about.html deliberately doesn't load app.js (which expects a sidebar,
// a tree, and tree.json). The inline <script> in the page <head> already applies
// the saved theme before first paint, so this only handles the click and keeps
// the button's label in sync. Both pages read/write the same localStorage
// "theme" key, so a switch here carries over to the tree and back.

import { renderStaticTranslit } from "./translit-static.js";

// about.html's scheme <select> is the single source of truth for which script
// the page is in; initStaticTranslit owns the listener, and this reads the same
// control so a redrawn legend lands in the scheme already on screen. Falls back
// to the scheme initStaticTranslit was seeded with.
function currentScheme() {
  const select = document.getElementById("schemeSelect");
  return select ? select.value : "iast";
}

const SUN_ICON = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 3v2"/><path d="M12 19v2"/><path d="M5 5l1.4 1.4"/><path d="M17.6 17.6L19 19"/><path d="M3 12h2"/><path d="M19 12h2"/><path d="M5 19l1.4-1.4"/><path d="M17.6 6.4L19 5"/></svg>`;
const MOON_ICON = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/></svg>`;

function updateThemeToggleLabel() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const theme = document.documentElement.getAttribute("data-theme") || "dark";
  const icon = theme === "dark" ? SUN_ICON : MOON_ICON;
  const label = theme === "dark" ? "Light" : "Dark";
  btn.innerHTML = `${icon}<span class="toggle-label">${label}</span>`;
}

const themeToggle = document.getElementById("themeToggle");
if (themeToggle) {
  updateThemeToggleLabel();
  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    updateThemeToggleLabel();
  });
}

// ---------------------------------------------------------------------------
// Growth over time
// ---------------------------------------------------------------------------
// docs/data/changelog.json is built by pipeline/build_changelog.py from the
// Unix epoch embedded in each row's thumbnail filename -- the only signal EBS
// carries for when a *record* was added (never to be confused with `publish
// year`, which is the printed edition's date).
//
// A minority of those stamps run years past the item's serial neighbourhood --
// a later touch to the file, not an arrival -- so the pipeline replaces them
// with a neighbourhood estimate. Those are *estimates*, and this file marks
// them: any period holding one gets an asterisk and says so in its tooltip.
// Never let an interpolated date render as though it were measured.
//
// Stacked rather than a single bar because the format mix is the story: the
// site's output swung from mostly-Unicode text in 2022 to overwhelmingly PDF
// scans in 2026.

const CHANGELOG_URL = "./data/changelog.json";

const BANDS = [
  { key: "text_only", label: "text only", cls: "gb-text" },
  { key: "both", label: "text + PDF", cls: "gb-both" },
  { key: "pdf_only", label: "PDF only", cls: "gb-pdf" },
];

// `granularity` is months per group: 1 monthly, 3 quarterly, 12 yearly.
// changelog.json publishes months -- the granularity the three atlases share,
// so sagara-sangama can plot them on one axis -- and the grouping back up to
// quarters or years happens here, at render time. Year is the default because
// 67 monthly bars is a texture, not a reading; the finer grains are for
// looking at a particular stretch.
const growthState = { mode: "cumulative", metric: "count", scope: "text",
                      granularity: 12 };

// Which bands the stack draws, per `scope`. "text-bearing" drops the pdf_only
// band so the two text series are legible against their own scale -- on the
// full stack they are dwarfed by the PDF column from 2023 on, which is exactly
// the finding the default view shows and the reason the filter exists.
function activeBands() {
  return growthState.scope === "text"
    ? BANDS.filter((b) => b.key !== "pdf_only")
    : BANDS;
}

// Bytes, abbreviated. Sizes run to gigabytes and the axis has no room for
// grouped digits. Decimal units (1 MB = 1e6 bytes), which is what a reader
// comparing this against a file listing will expect.
function fmtSize(n) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(0)} MB`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)} KB`;
  return `${n} B`;
}

// One accessor for both measures, so the drawing code never branches on it.
// In `size` the per-band values are bytes of the text as we store it (IAST);
// pdf_only is structurally zero there (a scan carries no text), which the note
// under the chart explains rather than the code hiding.
function bandValues(p) {
  const cumulative = growthState.mode === "cumulative";
  if (growthState.metric === "size") {
    return p[cumulative ? "cumulative_iast_bytes" : "added_iast_bytes"] || {};
  }
  return p[cumulative ? "cumulative" : "added"] || {};
}

function fmtValue(n) {
  return growthState.metric === "size" ? fmtSize(n) : n.toLocaleString();
}

// How many of a period's works sit on an interpolated date rather than a
// measured one. Follows the added/cumulative toggle, so the mark always
// describes the bar actually on screen.
function estimated(p) {
  return growthState.mode === "cumulative"
    ? (p.cumulative_synthetic || 0) : (p.synthetic || 0);
}

// The one sentence that keeps an estimate from reading as a measurement.
// Wording fixed by notes/todo.md; keep the two in step if either changes.
function estNote(est, total) {
  if (!est) return "";
  return `\n\n* ${est.toLocaleString()} of these ${total.toLocaleString()} ` +
    `(${(est / total * 100).toFixed(1)}%) are interpolated based on serial; ` +
    `their actual associated datestamps fall later.`;
}

// A round number at or above `n`, and the step between gridlines. Bars are
// scaled against this rather than the raw maximum, so the tallest bar stops at
// a labelled tick instead of the top of the box -- without that the axis would
// have no number to put beside its own ceiling.
function niceScale(n) {
  const pow = Math.pow(10, Math.floor(Math.log10(n)));
  // Steps are tried smallest-first and the first workable one wins, so the
  // axis stays as tight to the data as the tick budget allows. Both bounds
  // matter: without a floor, 11044 would scale to 0/10k/20k -- two labels and
  // half the plot empty; without a ceiling the labels crowd.
  for (const mult of [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10]) {
    const step = mult * pow;
    // Whole numbers only -- these are counts of works, so a 0.5 tick would be
    // meaningless. Never bites at real corpus sizes; guards the tiny-n case.
    if (!Number.isInteger(step)) continue;
    const intervals = Math.ceil(n / step);
    if (intervals >= 3 && intervals <= 5) {
      return { top: intervals * step, step };
    }
  }
  return { top: Math.ceil(n / pow) * pow, step: pow };
}

// Group the oldest-first monthly periods into calendar chunks of `size`
// months: quarters at Jan/Apr/Jul/Oct, years at January.
//
// Anchored to the calendar rather than counted back from the newest month,
// which is what sanskrit-wikisource-atlas's groupEntries does. That suits a
// running changelog, where the question is "what changed in the last N
// months"; here the bars are labelled with the period they cover and a reader
// reads them as years, so a "year" running 2025-09 to 2026-08 would be a
// mislabel. The cost is that the newest and oldest groups can be partial --
// 2026 holds eight months so far -- which is honest: the period is genuinely
// still in progress.
//
// A no-op when the published series is already coarser than the requested
// grouping, which is how this stays correct if `--granularity year` is ever
// what shipped.
function groupPeriods(data, size) {
  const periods = data.periods || [];
  if (size <= 1 || data.granularity !== "month" || periods.length < 2) {
    return periods;
  }
  const groups = [];
  let chunk = [];
  for (const p of periods) {
    // `period` is "YYYY-MM"; the month index floor-divided by the chunk size
    // names the calendar bucket, so 12 gives the year and 3 the quarter.
    const month = Number(p.period.slice(5, 7)) - 1;
    const key = `${p.period.slice(0, 4)}:${Math.floor(month / size)}`;
    if (chunk.length && chunk.key !== key) {
      groups.push(reducePeriods(chunk, size));
      chunk = [];
    }
    chunk.key = key;
    chunk.push(p);
  }
  if (chunk.length) groups.push(reducePeriods(chunk, size));
  return groups;
}

// One period standing for several. The `added_*` fields sum -- they are
// disjoint counts of what arrived in each month -- while every `cumulative_*`
// field is a running total, so the group's is simply the last month's. Mixing
// those two rules up is the one way this can go quietly wrong.
// "2026" at year grouping, "2026-Q3" at quarter -- named for the calendar
// period the group covers, not for the months that happen to carry data. A
// year holding one work is still that year, and labelling it "2021-01" would
// read as a month.
function groupLabel(first, size) {
  const year = first.period.slice(0, 4);
  if (size >= 12) return year;
  const a = Number(first.period.slice(5, 7));
  return `${year}-Q${Math.floor((a - 1) / 3) + 1}`;
}

function reducePeriods(chunk, size) {
  const first = chunk[0], last = chunk[chunk.length - 1];
  // A one-month group still gets the calendar label: a year holding a single
  // work is that year, and returning the period untouched would put
  // "2026-08" on a bar the axis reads as years.
  if (chunk.length === 1) return { ...first, period: groupLabel(first, size) };

  const sumBands = (key) => {
    const out = {};
    for (const b of BANDS) {
      out[b.key] = chunk.reduce((s, p) => s + ((p[key] || {})[b.key] || 0), 0);
    }
    return out;
  };
  const sum = (key) => chunk.reduce((s, p) => s + (p[key] || 0), 0);

  return {
    ...last,
    // Named for the calendar period it covers -- "2026" or "2026-Q3" -- so a
    // bar's label is the thing a reader thinks the bar is, rather than the
    // pair of months that happen to bound it.
    period: groupLabel(first, size),
    date: last.date,
    added: sumBands("added"),
    added_count: sum("added_count"),
    added_text_count: sum("added_text_count"),
    added_chars: sumBands("added_chars"),
    added_chars_total: sum("added_chars_total"),
    added_iast_bytes: sumBands("added_iast_bytes"),
    added_iast_bytes_total: sum("added_iast_bytes_total"),
    synthetic: sum("synthetic"),
    measured: sum("measured"),
    in_snapshot: sum("in_snapshot"),
    scrapeable: sum("scrapeable"),
    missing: sum("missing"),
    old_count: first.old_count,
  };
}

function drawGrowth(data, chartEl) {
  const periods = groupPeriods(data, growthState.granularity);
  const bands = activeBands();
  // The scale follows the bands actually drawn, not the period's own total --
  // otherwise filtering to text-bearing would leave every bar short against a
  // ceiling set by the PDF column that is no longer on screen.
  const totalOf = (p) => {
    const v = bandValues(p);
    return bands.reduce((sum, b) => sum + (v[b.key] || 0), 0);
  };
  const dataMax = Math.max(...periods.map(totalOf), 1);
  const { top: max, step } = niceScale(dataMax);

  chartEl.innerHTML = "";
  const chart = document.createElement("div");
  // Dense once the columns are thinner than a comfortable bar: tightens the
  // gap and squares the caps, so 67 monthly columns read as a profile rather
  // than as hairlines separated by mostly-gap.
  const dense = periods.length > 30;
  chart.className = "gb-chart" + (dense ? " gb-dense" : "");
  // Label about a dozen columns, whatever the granularity. Every monthly
  // label overprints its neighbours -- the tooltip still names the period
  // exactly, so the axis only has to carry enough to orient.
  const labelEvery = Math.max(1, Math.round(periods.length / 12));

  // The axis is a column of labels plus full-width gridlines behind the bars.
  // Both are built from the same tick list so a label can never drift from the
  // line it names.
  const axis = document.createElement("div");
  axis.className = "gb-axis";
  const ticks = [];
  for (let v = 0; v <= max; v += step) ticks.push(v);
  for (const v of [...ticks].reverse()) {
    const t = document.createElement("div");
    t.className = "gb-tick";
    t.style.bottom = `${(v / max) * 100}%`;
    t.textContent = fmtValue(v);
    axis.appendChild(t);
  }
  chart.appendChild(axis);

  const grid = document.createElement("div");
  grid.className = "gb-grid";
  grid.setAttribute("aria-hidden", "true");
  for (const v of ticks) {
    const line = document.createElement("div");
    line.className = "gb-line";
    line.style.bottom = `${(v / max) * 100}%`;
    grid.appendChild(line);
  }
  chart.appendChild(grid);

  periods.forEach((p, i) => {
    const col = document.createElement("div");
    col.className = "gb-col";

    const stack = document.createElement("div");
    stack.className = "gb-stack";
    // Bands are stacked bottom-up in BANDS order; each is sized as a share of
    // the tallest period so columns stay comparable.
    const values = bandValues(p);
    for (const band of [...bands].reverse()) {
      const v = values[band.key] || 0;
      if (!v) continue;
      const seg = document.createElement("div");
      seg.className = `gb-seg ${band.cls}`;
      seg.style.height = `${(v / max) * 100}%`;
      seg.title = `${p.period} — ${band.label}: ${fmtValue(v)}`;
      stack.appendChild(seg);
    }

    const total = totalOf(p);
    const est = estimated(p);
    col.innerHTML = "";
    col.appendChild(stack);
    const lbl = document.createElement("div");
    lbl.className = "gb-year";
    // The last column is labelled too, but only where the regular cadence has
    // not already put one beside it, which would overprint at the right edge.
    const showTick = i % labelEvery === 0
      || (i === periods.length - 1
          && (periods.length - 1) % labelEvery > labelEvery / 2);
    // Ticks land every few months, so the year alone would print twice over
    // and read as a duplicate. "2021-07" is the honest label at this density,
    // and the tooltip still carries the full period either way.
    if (showTick) lbl.textContent = p.period;
    // The estimate marker rides on the label, so a suppressed label would
    // silently drop it. It belongs to a period, not to a tick -- at month
    // density it would print on the twelfth of the periods it describes and
    // imply the other eleven were measured. The note under the chart and the
    // tooltip carry it instead.
    if (est && showTick && !dense) {
      const star = document.createElement("span");
      star.className = "gb-est";
      star.textContent = "*";
      lbl.appendChild(star);
    }
    col.appendChild(lbl);
    const unit = growthState.metric === "size" ? "" : " works";
    col.title =
      `${p.period} — ${growthState.mode === "cumulative" ? "total" : "added"}: ` +
      `${fmtValue(total)}${unit}\n` +
      bands.map((b) => `  ${b.label}: ${fmtValue(values[b.key] || 0)}`).join("\n") +
      // The count of works behind a size bar: without it a short bar reads as
      // "little text here" when it can equally mean "not yet fetched".
      (growthState.metric === "size"
        ? `\n\n  measured from ${(growthState.mode === "cumulative"
            ? p.cumulative_measured : p.measured).toLocaleString()} fetched texts`
        : "") +
      // Against the item count, never the bar's own value: `est` counts works
      // with an interpolated date, so "207 of 2.0 GB" compares a count to a
      // size and lands at a meaningless 0.0%.
      estNote(est, growthState.mode === "cumulative"
        ? (p.cumulative_count || 0) : (p.added_count || 0));
    chart.appendChild(col);
  });
  chartEl.appendChild(chart);
}

function renderGrowth(data, chartEl) {
  drawGrowth(data, chartEl);
  for (const btn of document.querySelectorAll("#growthControls button")) {
    // String(...) on both sides: granularity is a number in state and a
    // string in the DOM, and === across the two would never match.
    const on = String(growthState[btn.dataset.axis]) === btn.dataset.value;
    btn.classList.toggle("gb-on", on);
    btn.setAttribute("aria-pressed", String(on));
  }
  const pdfBox = document.getElementById("growthShowPdf");
  if (pdfBox) pdfBox.checked = growthState.scope === "all";
  // The legend follows the scope filter: a key for a band that is not drawn
  // would claim a colour the chart is not using.
  const shown = new Set(activeBands().map((b) => b.cls));
  for (const key of document.querySelectorAll(".gb-legend .gb-key")) {
    const swatch = key.querySelector(".gb-swatch");
    key.hidden = swatch ? !shown.has([...swatch.classList]
      .find((c) => c !== "gb-swatch")) : false;
  }
  const note = document.getElementById("growthSizeNote");
  if (note) note.hidden = growthState.metric !== "size";
}

async function loadGrowth() {
  const chartEl = document.getElementById("growthChart");
  if (!chartEl) return;
  try {
    const r = await fetch(CHANGELOG_URL);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    if (!data.periods?.length) throw new Error("empty");

    const controls = document.getElementById("growthControls");
    if (controls) {
      controls.addEventListener("click", (ev) => {
        const btn = ev.target.closest("button[data-value]");
        if (!btn) return;
        const { axis, value } = btn.dataset;
        growthState[axis] = axis === "granularity" ? Number(value) : value;
        renderGrowth(data, chartEl);
      });
      // The PDF band is a checkbox rather than a pair of buttons: it is one
      // band on or off, not a choice between two views, and the default is off
      // because the two text series are dwarfed once it is drawn.
      const pdfBox = document.getElementById("growthShowPdf");
      if (pdfBox) {
        pdfBox.addEventListener("change", () => {
          growthState.scope = pdfBox.checked ? "all" : "text";
          renderGrowth(data, chartEl);
        });
      }
    }

    renderGrowth(data, chartEl);
  } catch (e) {
    chartEl.textContent = "Growth data unavailable.";
    console.log("Could not load changelog:", e);
  }
}

loadGrowth();

// The About page's one outbound link to the parent project.
//
// This is the mirror image of the parent's docs/local-links.js: that file ships
// the published Atlas URLs and rewrites them down to ports 8001-8003 when it is
// itself served locally. Here there is a single link going the other way, up to
// the parent, so a whole rewrite pass would be overkill -- the markup carries
// the production URL (the file that ships is the file that is deployed) and we
// swap in the local parent only when this Atlas is being served from localhost.
// Port 8000 matches the parent's serve_docs.py and Makefile, where 8002 is us.
const PARENT_LOCAL_PORT = 8000;

// Host test copied from the parent's local-links.js, deliberately identical.
function isLocal(hostname) {
  return hostname === "localhost"
      || hostname === "127.0.0.1"
      || hostname === "[::1]"
      || hostname === "::1"
      || hostname.endsWith(".localhost");
}

if (isLocal(location.hostname)) {
  const parentLink = document.getElementById("parentLink");
  if (parentLink) {
    parentLink.href = `http://${location.hostname}:${PARENT_LOCAL_PORT}/`;
    parentLink.dataset.localized = "true";  // visible in devtools, as in the parent
  }
}

// ---------------------------------------------------------------------------
// Category mix over time
// ---------------------------------------------------------------------------
// The same monthly periods as the stack above, but asking *what* arrived
// rather than how much. Lines rather than a stack: stacking hides a category's
// own shape behind whatever sits below it, and the finding here is the shape --
// early intake ran one subject at a time (वेदाङ्गानि through 2021, then
// दर्शनानि), where recent months spread across the whole shelf.
//
// `added_domains` is published sparse, one {domain: count} per period, with a
// ranked `domains` list beside it. This file picks how many to name; the
// pipeline deliberately does not, because the number is set by how many hues
// the palette can hold apart, which is a rendering question.

// Set by the palette, not by the data: --cm-1..8 are eight distinguishable
// hues, and "other" is a gray outside that run rather than one of them. So
// eight named lines is the ceiling; a ninth would mean an invented hue.
//
// The distribution offers no cut of its own to prefer instead. The only real
// cliff is 46% between #3 and #4, far too few to be useful, and ranks 7-11 sit
// within a few percent of each other -- so wherever this lands it splits a
// smooth run, and it may as well land where the palette runs out.
const CM_TOP_N = 8;
const CM_OTHER = "__other__";

// The chart is drawn into a fixed viewBox and scaled by the page, so these are
// user units, not pixels. Left padding holds the tick column, bottom the month
// labels.
const CM_VIEW = { w: 1000, h: 300, left: 48, right: 8, top: 10, bottom: 24 };

const categoryState = { mode: "added", granularity: 3 };
// Which series the reader has switched off, by domain name -- kept outside the
// redraw so a granularity change does not silently switch them back on.
const categoryHidden = new Set();

// Sum a list of periods' `added_domains` into one. Only the added counts sum;
// a cumulative view is a running total taken afterwards, over the grouped
// periods, so grouping and accumulation never have to agree about order.
function mergeDomains(chunk) {
  const out = {};
  for (const p of chunk) {
    for (const [name, n] of Object.entries(p.added_domains || {})) {
      out[name] = (out[name] || 0) + n;
    }
  }
  return out;
}

// Group monthly periods into calendar chunks, exactly as groupPeriods does for
// the bar chart -- same anchoring, same partial-period honesty -- but carrying
// only the fields this chart reads. Kept separate rather than folded into
// reducePeriods because that function sums a fixed list of scalar fields and
// `added_domains` is a map; teaching it both rules is how the band totals and
// the category totals would drift apart.
function groupDomainPeriods(data, size) {
  const periods = data.periods || [];
  if (!periods.length) return [];
  if (size <= 1 || data.granularity !== "month") {
    return periods.map((p) => ({ period: p.period,
                                 domains: { ...(p.added_domains || {}) } }));
  }
  const groups = [];
  let chunk = [];
  const flush = () => {
    if (chunk.length) {
      groups.push({ period: groupLabel(chunk[0], size),
                    domains: mergeDomains(chunk) });
    }
  };
  for (const p of periods) {
    const month = Number(p.period.slice(5, 7)) - 1;
    const key = `${p.period.slice(0, 4)}:${Math.floor(month / size)}`;
    if (chunk.length && chunk.key !== key) { flush(); chunk = []; }
    chunk.key = key;
    chunk.push(p);
  }
  flush();
  return groups;
}

// The series list: the top N categories by overall size, in rank order, plus
// one fold-in. Rank comes from the whole catalogue rather than from what is on
// screen, so a granularity change cannot reassign a colour -- colour follows
// the category, never its position in the current view.
function categorySeries(data) {
  const ranked = (data.domains || []).map((d) => d.name);
  const named = ranked.slice(0, CM_TOP_N);
  const series = named.map((name, i) => ({
    key: name, label: name, sanskrit: true, color: `var(--cm-${i + 1})`,
  }));
  if (ranked.length > named.length) {
    series.push({ key: CM_OTHER, label: "other", sanskrit: false,
                  color: "var(--cm-other)",
                  members: ranked.slice(CM_TOP_N) });
  }
  return series;
}

// Per-period values for one series, oldest first. "other" is everything not
// named, summed -- computed from the period's own map rather than from a
// subtraction against the period total, so a category missing from the ranking
// (which cannot happen, but would be silent) shows up as a gap rather than as
// phantom "other" works.
function seriesValues(series, periods, named) {
  const raw = periods.map((p) => {
    if (series.key !== CM_OTHER) return p.domains[series.key] || 0;
    let sum = 0;
    for (const [name, n] of Object.entries(p.domains)) {
      if (!named.has(name)) sum += n;
    }
    return sum;
  });
  if (categoryState.mode !== "cumulative") return raw;
  let run = 0;
  return raw.map((v) => (run += v));
}

function svgEl(name, attrs = {}) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function drawCategories(data, chartEl) {
  const periods = groupDomainPeriods(data, categoryState.granularity);
  const series = categorySeries(data);
  const named = new Set(series.filter((s) => s.key !== CM_OTHER)
                              .map((s) => s.key));
  const shown = series.filter((s) => !categoryHidden.has(s.key));

  const values = new Map();
  for (const s of series) values.set(s.key, seriesValues(s, periods, named));

  // The scale follows only the visible series, so switching the dominant
  // category off actually opens up the smaller ones -- which is the whole
  // reason the legend is clickable.
  const dataMax = Math.max(
    1, ...shown.flatMap((s) => values.get(s.key)));
  const { top: max, step } = niceScale(dataMax);

  const { w, h, left, right, top, bottom } = CM_VIEW;
  const plotW = w - left - right, plotH = h - top - bottom;
  // A single period would divide by zero; it plots as one dot at mid-width.
  const xAt = (i) => periods.length < 2
    ? left + plotW / 2
    : left + (i / (periods.length - 1)) * plotW;
  const yAt = (v) => top + plotH - (v / max) * plotH;

  chartEl.innerHTML = "";
  const svg = svgEl("svg", {
    class: "cm-chart", viewBox: `0 0 ${w} ${h}`,
    preserveAspectRatio: "none", role: "img",
    "aria-label": "Items added per period, by category",
  });
  // `preserveAspectRatio: none` would stretch the text with the box, so the
  // height is pinned in CSS-free terms here: the page scales width only.
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

  for (let v = 0; v <= max; v += step) {
    const y = yAt(v);
    svg.appendChild(svgEl("line", {
      class: "cm-grid" + (v === 0 ? " cm-base" : ""),
      x1: left, x2: w - right, y1: y, y2: y,
    }));
    const label = svgEl("text", {
      class: "cm-tick", x: left - 8, y: y + 4, "text-anchor": "end",
    });
    label.textContent = v.toLocaleString();
    svg.appendChild(label);
  }

  // About a dozen labels whatever the grain, matching the bar chart's rule --
  // every monthly label would overprint, and the tooltip names the period
  // exactly in any case.
  const labelEvery = Math.max(1, Math.round(periods.length / 12));
  periods.forEach((p, i) => {
    if (i % labelEvery !== 0 && i !== periods.length - 1) return;
    // The last period is always labelled, unless the regular cadence has just
    // put one next to it.
    if (i === periods.length - 1 && (periods.length - 1) % labelEvery !== 0
        && (periods.length - 1) % labelEvery <= labelEvery / 2) return;
    const t = svgEl("text", {
      class: "cm-tick", x: xAt(i), y: h - bottom + 18, "text-anchor": "middle",
    });
    t.textContent = p.period;
    svg.appendChild(t);
  });

  // Dots only where they can be told apart. At month grain 67 markers a line
  // merge into the stroke and cost 500 nodes; the crosshair carries the
  // per-period read either way.
  const dots = periods.length <= 30;
  for (const s of series) {
    const g = svgEl("g", { class: "cm-series" });
    if (categoryHidden.has(s.key)) g.setAttribute("hidden", "");
    const vals = values.get(s.key);
    const d = vals.map((v, i) => `${i ? "L" : "M"}${xAt(i).toFixed(1)} ` +
                                 `${yAt(v).toFixed(1)}`).join(" ");
    g.appendChild(svgEl("path", { class: "cm-line", d, stroke: s.color }));
    if (dots) {
      vals.forEach((v, i) => {
        g.appendChild(svgEl("circle", {
          class: "cm-dot", cx: xAt(i), cy: yAt(v), r: 4, fill: s.color,
        }));
      });
    }
    svg.appendChild(g);
  }

  const cursor = svgEl("line", {
    class: "cm-cursor", y1: top, y2: top + plotH, x1: -10, x2: -10,
  });
  cursor.setAttribute("visibility", "hidden");
  svg.appendChild(cursor);

  chartEl.appendChild(svg);
  attachCategoryCursor(chartEl, svg, cursor, {
    periods, series, values, xAt, left, plotW,
  });
}

// One crosshair naming every visible series at the period under the pointer.
// With eight lines a per-dot tooltip would mean hunting for a 4px target, and
// the comparison a reader wants is across series at one date.
function attachCategoryCursor(chartEl, svg, cursor, ctx) {
  const { periods, series, values, xAt, left, plotW } = ctx;
  const wrap = chartEl.closest(".cm-wrap") || chartEl;
  let tip = wrap.querySelector(".cm-tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "cm-tip";
    tip.hidden = true;
    wrap.appendChild(tip);
  }

  const hide = () => { tip.hidden = true; cursor.setAttribute("visibility", "hidden"); };

  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("pointermove", (ev) => {
    const box = svg.getBoundingClientRect();
    if (!box.width) return;
    // The SVG scales to the page width, so the pointer's client offset has to
    // be mapped back into viewBox units before it can be compared to xAt.
    const ux = (ev.clientX - box.left) / box.width * CM_VIEW.w;
    const frac = periods.length < 2 ? 0
      : (ux - left) / plotW * (periods.length - 1);
    const i = Math.max(0, Math.min(periods.length - 1, Math.round(frac)));

    cursor.setAttribute("x1", xAt(i));
    cursor.setAttribute("x2", xAt(i));
    cursor.setAttribute("visibility", "visible");

    const rows = series
      .filter((s) => !categoryHidden.has(s.key))
      .map((s) => ({ s, v: values.get(s.key)[i] }))
      // Largest first, so the tooltip is ordered by what the reader is
      // looking at rather than by the fixed palette order. A series at zero
      // is dropped: at month grain most of the eight are, every month.
      .filter((r) => r.v > 0)
      .sort((a, b) => b.v - a.v);

    tip.innerHTML = "";
    const head = document.createElement("div");
    head.className = "cm-tip-head";
    head.textContent = periods[i].period;
    tip.appendChild(head);
    if (!rows.length) {
      const none = document.createElement("div");
      none.className = "cm-tip-row";
      none.textContent = "nothing added";
      tip.appendChild(none);
    }
    for (const { s, v } of rows) {
      const row = document.createElement("div");
      row.className = "cm-tip-row";
      const sw = document.createElement("span");
      sw.className = "cm-swatch";
      sw.style.background = s.color;
      row.appendChild(sw);
      const name = document.createElement("span");
      // The Sanskrit names go through the page's transliteration scheme like
      // every other title; "other" is English and must not.
      if (s.sanskrit) name.className = "sa";
      name.textContent = s.label;
      row.appendChild(name);
      const val = document.createElement("span");
      val.className = "cm-tip-val";
      val.textContent = v.toLocaleString();
      row.appendChild(val);
      tip.appendChild(row);
    }
    // Same reason as the legend: these rows are built per pointer-move, long
    // after initStaticTranslit walked the page.
    renderStaticTranslit(currentScheme(), tip);
    tip.hidden = false;

    // Placed against the wrapper, and flipped to the left of the cursor once
    // it would otherwise run off the right edge.
    const wrapBox = wrap.getBoundingClientRect();
    const x = ev.clientX - wrapBox.left;
    const flip = x + tip.offsetWidth + 18 > wrapBox.width;
    tip.style.left = `${Math.max(0, flip ? x - tip.offsetWidth - 14 : x + 14)}px`;
    tip.style.top = `${Math.max(0, ev.clientY - wrapBox.top - tip.offsetHeight / 2)}px`;
  });
}

// The legend doubles as the series filter, so it is built from the same list
// the chart draws and rebuilt with it.
function renderCategoryLegend(data, chartEl) {
  const legend = document.getElementById("categoryLegend");
  if (!legend) return;
  legend.innerHTML = "";
  for (const s of categorySeries(data)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cm-key";
    const on = !categoryHidden.has(s.key);
    btn.setAttribute("aria-pressed", String(on));
    const sw = document.createElement("span");
    sw.className = "cm-swatch";
    sw.style.background = s.color;
    btn.appendChild(sw);
    const name = document.createElement("span");
    if (s.sanskrit) name.className = "sa";
    name.textContent = s.label;
    // "other" says what it holds; the named keys do not need it.
    btn.title = s.members
      ? `${s.members.length} smaller categories, summed`
      : s.label;
    btn.appendChild(name);
    btn.addEventListener("click", () => {
      if (categoryHidden.has(s.key)) categoryHidden.delete(s.key);
      // Never let the last series be switched off -- an empty plot has no
      // scale and no way back except another click on a key the reader can
      // no longer see the point of.
      else if (categoryHidden.size < categorySeries(data).length - 1) {
        categoryHidden.add(s.key);
      } else return;
      renderCategories(data, chartEl);
    });
    legend.appendChild(btn);
  }
  // initStaticTranslit runs once at load, over the DOM as it stood then. These
  // keys are built afterwards and on every redraw, so they carry raw
  // Devanagari until this puts them into the reader's chosen scheme.
  renderStaticTranslit(currentScheme(), legend);
}

function renderCategories(data, chartEl) {
  // A redraw replaces the plot the open tooltip was describing, so it has to
  // go with it -- otherwise a control click leaves last frame's numbers
  // sitting over the new lines.
  const stale = document.querySelector(".cm-tip");
  if (stale) stale.hidden = true;
  drawCategories(data, chartEl);
  renderCategoryLegend(data, chartEl);
  for (const btn of document.querySelectorAll("#categoryControls button")) {
    const on = String(categoryState[btn.dataset.axis]) === btn.dataset.value;
    btn.classList.toggle("gb-on", on);
    btn.setAttribute("aria-pressed", String(on));
  }
}

async function loadCategories() {
  const chartEl = document.getElementById("categoryChart");
  if (!chartEl) return;
  try {
    const r = await fetch(CHANGELOG_URL);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    if (!data.periods?.length || !data.domains?.length) throw new Error("empty");

    // How many lines are named is a function of CM_TOP_N, which this file owns,
    // so the sentence is written in rather than authored and cannot go stale
    // when that changes. The size of the "other" fold is left as prose: it is
    // just the ranking's length minus this, and naming it told the reader
    // nothing they needed.
    const top = document.getElementById("cmTopCount");
    if (top) top.textContent = `${CM_TOP_N} largest`;

    const controls = document.getElementById("categoryControls");
    if (controls) {
      controls.addEventListener("click", (ev) => {
        const btn = ev.target.closest("button[data-value]");
        if (!btn) return;
        const { axis, value } = btn.dataset;
        categoryState[axis] = axis === "granularity" ? Number(value) : value;
        renderCategories(data, chartEl);
      });
    }

    renderCategories(data, chartEl);
  } catch (e) {
    chartEl.textContent = "Category data unavailable.";
    console.log("Could not load category mix:", e);
  }
}

loadCategories();

// ---------------------------------------------------------------------------
// Serial bands on the calendar
// ---------------------------------------------------------------------------
// The serial table's third view of the same corpus, and the one the table
// itself cannot give: its rows are evenly spaced, so a ten-month stall between
// two bands looks exactly like a one-month cadence. Here each band is a bar at
// the month it was mostly filled, on a continuous monthly axis, so the stalls
// are gaps.
//
// That month is the MEDIAN of the band's addition dates, not its last one. A
// band has no real closing date: the max is when someone last backfilled a gap
// in that range, which runs backwards against the previous band 7 times in 25
// (band 2501 last grew Nov 2022, band 3001 May 2022). The median is the only
// one of min/median/max monotonic across all 26 bands, so it is the only one
// that can sit on a time axis without the sequence appearing to reverse.
//
// `serial_bands` comes from build_changelog, which gets it from
// audit.serial_band_rows -- the same function that renders the table, so the
// band width and the median-`added` end date cannot drift between the two.
//
// The stack is ordinal, not categorical: structured -> flat -> PDF-only is a
// ranking by how much of the item is readable, and it reuses the growth
// chart's accent ramp because it splits the same corpus the same way. "Unused"
// is off the ramp entirely -- it is the absence of a record, not a fourth
// grade of one.

const SN_VIEW = { w: 1000, h: 260, left: 48, right: 10, top: 10, bottom: 24 };

// Segments bottom-up: what each band turned out to hold, and nothing else.
// A fourth "unused" segment used to ride on top, hatched, showing the band's
// headroom against its own 500 -- but drawn as part of the stack it read as a
// fourth kind of content, and on the many bands that filled little of their
// range the hatching dominated the bar and buried the real contents.
const SN_BANDS = [
  { key: "structured", label: "structured text", cls: "sn-structured" },
  { key: "flat", label: "unstructured text", cls: "sn-text" },
  { key: "pdf_only", label: "PDF only", cls: "sn-pdf" },
];

// A month holding two bands draws them across this multiple of a single bar's
// width, separated by SN_PAIR_GUTTER. Both exist to keep "two bands land in
// this month" visually distinct from "one does" -- see the width comment below.
const SN_PAIR_SPREAD = 1.5;
const SN_PAIR_GUTTER = 2.5;

// "2021-02" -> months since epoch, so two band-ends can be subtracted and a
// month can be placed on a continuous axis. Sliced rather than parsed for the
// reason monthYear() gives: an ISO date read as UTC can land in the wrong
// month locally.
function monthIndex(period) {
  return Number(period.slice(0, 4)) * 12 + Number(period.slice(5, 7)) - 1;
}

// `text` in the row is every text-bearing item and `structured` is a subset of
// it, so the flat-text segment is the difference. Stacking the two as
// published would count the structured ones twice and overrun the band.
function snSegments(row) {
  return {
    structured: row.structured || 0,
    flat: Math.max(0, (row.text || 0) - (row.structured || 0)),
    pdf_only: row.pdf_only || 0,
  };
}

// How many bands land in each month. A month holding two splits its slot
// between them, so the layout needs the count before it places either.
function monthCounts(dated) {
  const counts = new Map();
  for (const band of dated) {
    const m = monthIndex(band.end);
    counts.set(m, (counts.get(m) || 0) + 1);
  }
  return counts;
}


function drawSerialTimeline(bands, chartEl) {
  const dated = bands.filter((b) => b.end);
  if (!dated.length) throw new Error("no dated bands");

  const first = monthIndex(dated[0].end);
  const last = monthIndex(dated[dated.length - 1].end);
  // The axis spans every month between the first and last band's median,
  // whether or not anything happened in it -- which is the whole construction.
  // One month of padding each side so the end bars are not flush to the frame.
  const lo = first - 1, hi = last + 1;
  const span = Math.max(1, hi - lo);

  // Every bar is drawn against the band width, so bar heights are comparable
  // and the hatched headroom is legible as a share. A band that somehow ran
  // over its width would still fit.
  // Against the full band width, not the tallest bar: the bars are only
  // comparable to each other if every one is read against the same 500 the
  // site could have issued, and a short bar meaning "this band went mostly
  // unfilled" is the whole reading the chart is for.
  const width = Math.max(...dated.map((b) => b.works + (b.unused || 0)), 1);
  const { top: max, step } = niceScale(width);

  const { w, h, left, right, top, bottom } = SN_VIEW;
  const plotW = w - left - right, plotH = h - top - bottom;
  const xAt = (m) => left + ((m - lo) / span) * plotW;
  const yAt = (v) => top + plotH - (v / max) * plotH;
  // A bar sits inside its month slot with air either side. The whole
  // construction is that the months around a bar are empty, so a bar filling
  // its slot edge-to-edge erases the gap it is supposed to sit in -- at a full
  // slot the 2023 and 2026 clusters merged into slabs.
  //
  // Sized for the ordinary month, which holds one band. The three months
  // holding two narrow those two locally rather than every bar on the chart
  // paying for them -- dividing globally took every bar to 4.6px, at which
  // width the stack's three steps stop being separable at all.
  const slot = plotW / span;
  const barW = Math.min(12, Math.max(5, slot * 0.7));

  chartEl.innerHTML = "";
  const svg = svgEl("svg", {
    class: "sn-chart", viewBox: `0 0 ${w} ${h}`, role: "img",
    "aria-label": "Each 500-serial band at the month it was mostly filled",
  });

  for (let v = 0; v <= max; v += step) {
    const y = yAt(v);
    svg.appendChild(svgEl("line", {
      class: "sn-grid" + (v === 0 ? " sn-base" : ""),
      x1: left, x2: w - right, y1: y, y2: y,
    }));
    const t = svgEl("text", {
      class: "sn-tick", x: left - 8, y: y + 4, "text-anchor": "end",
    });
    t.textContent = v.toLocaleString();
    svg.appendChild(t);
  }

  // Year ticks rather than a label per bar: the bars are irregularly spaced by
  // construction, so labelling each would crowd exactly where the clusters
  // are. January of each year covered.
  for (let m = Math.ceil(lo / 12) * 12; m <= hi; m += 12) {
    const x = xAt(m);
    const t = svgEl("text", {
      class: "sn-tick", x, y: h - bottom + 18, "text-anchor": "middle",
    });
    t.textContent = String(Math.floor(m / 12));
    svg.appendChild(t);
  }

  // Bands sharing a month are nudged apart rather than drawn on top of each
  // other -- three pairs do, and a hidden bar would misreport the month as
  // holding one band.
  const perMonth = monthCounts(dated);
  const drawn = new Map();

  for (const band of dated) {
    const m = monthIndex(band.end);
    const n = perMonth.get(m);
    const seen = drawn.get(m) || 0;
    drawn.set(m, seen + 1);
    // A shared month splits its own slot between its bands, so the pair still
    // reads as sitting in one month rather than spilling into the empty ones
    // either side. Every other bar keeps the full width.
    //
    // The split is not an even division of `barW`: at (barW-1)/2 each half came
    // out ~5.5px, close enough to a lone 12px bar that a two-band month was
    // indistinguishable from a one-band one. Widening the pair's footprint past
    // the single-bar width, and separating the halves by a visible gutter
    // rather than 1px, is what makes "two land here" read at a glance.
    const w = n > 1 ? Math.max(4, (barW * SN_PAIR_SPREAD - SN_PAIR_GUTTER * (n - 1)) / n) : barW;
    // Centre the group on the month: one bar sits on it, two straddle it.
    const offset = (seen - (n - 1) / 2) * (w + SN_PAIR_GUTTER);
    const x = xAt(m) + offset - w / 2;

    const g = svgEl("g");
    const segs = snSegments(band);
    let acc = 0;
    for (const seg of SN_BANDS) {
      const v = segs[seg.key];
      if (!v) continue;
      const y0 = yAt(acc + v), y1 = yAt(acc);
      const rect = svgEl("rect", {
        class: `sn-seg ${seg.cls}`, x, y: y0, width: w,
        height: Math.max(1, y1 - y0),
      });
      // The 2px surface gap between stacked segments needs a bar wide enough
      // to survive it -- on a narrow bar a 2px stroke each side leaves nothing
      // of the fill. Below that the ramp's steps separate on their own.
      if (w < 8) rect.setAttribute("stroke-width", "0.75");
      g.appendChild(rect);
      acc += v;
    }
    const title = svgEl("title");
    title.textContent =
      `serials ${band.lo.toLocaleString()}\u2013${band.hi.toLocaleString()} ` +
      `\u2014 mostly filled by ${band.end}\n` +
      SN_BANDS.map((s) => `  ${s.label}: ${segs[s.key].toLocaleString()}`)
        .join("\n") +
      `\n  ${band.works.toLocaleString()} of ${width.toLocaleString()} ` +
      `serials filled`;
    g.appendChild(title);
    svg.appendChild(g);
  }

  chartEl.appendChild(svg);
  return { dated, width };
}

async function loadSerialTimeline() {
  const chartEl = document.getElementById("serialTimeline");
  if (!chartEl) return;
  try {
    const r = await fetch(CHANGELOG_URL);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const bands = data.serial_bands;
    if (!bands?.length) throw new Error("no serial_bands");

    drawSerialTimeline(bands, chartEl);
  } catch (e) {
    chartEl.textContent = "Serial band data unavailable.";
    console.log("Could not load serial bands:", e);
  }
}

loadSerialTimeline();
