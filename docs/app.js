// Two independent browsing axes over a flat work list (docs/data/tree.json,
// built by pipeline/build_tree.py -- see pipeline/shape.py for the shape).
//
// The data is NOT a nested tree. It is a flat `works` array plus `axes`, each
// axis holding ids into it. That is deliberate: the same works are presented
// four ways -- category flat, category grouped by author, author flat, author
// grouped by category -- and nesting one axis inside the other would scatter an
// author across the tree (Kalidasa's 110 works are filed under 7 domains) and
// leave nowhere to put the 3888 works with no author at all.
//
// So grouping happens here, at render time, not in the builder.

// Always this one path. WHICH tree it resolves to is the server's call --
// `make serve` gives the full catalogue, `make serve-snapshot` substitutes the
// snapshot build (2287 books, with byte sizes) at this same URL. The payload's
// `source` field is how the page knows which it received.
const DATA_URL = "./data/tree.json";

const state = {
  data: null,
  works: new Map(),         // id -> work, built at load time
  allTitledNodes: [],       // flat [{id, title}] over works + axis entries, for the search index
  translitCache: new Map(), // scheme -> Map(id -> transliterated title), filled lazily per scheme
  searchIndex: new Map(),   // scheme -> Map(id -> lowercased transliterated title), same laziness
  searchAuthorIndex: new Map(), // scheme -> Map(work id -> folded author name), so search finds a work by who wrote it

  axis: localStorage.getItem("axis") || "category",  // category | author
  // Optional secondary grouping within a selected node. OFF by default on both
  // axes: the point of the two-axis design is that the primary axis alone reads
  // as a flat list, with the cross-cutting one available on demand.
  groupCategory: localStorage.getItem("groupCategory") === "1", // author axis: group a person's works by domain
  groupAuthor: localStorage.getItem("groupAuthor") === "1",     // category axis: group a sub-domain's works by author
  textOnly: localStorage.getItem("textOnly") === "1",           // hide works with no Unicode text

  selectedId: null,         // "cat:<domain>" | "cat:<domain>/<sub>" | "auth:<name>" | null (= All)
  scheme: "iast",           // devanagari | iast | hk | itrans | slp1
  expanded: new Set(),      // sidebar node ids expanded
  searchQuery: "",
  searchExact: false,
  expandedWorkLists: new Set(), // node ids whose work list is expanded past the cap
  authorOverviewExpanded: false, // author overview showing all entries, not just the top cap
  overviewExpanded: false,  // "All" renders every node in full rather than one-line summaries
};

// Rendering every work as a DOM node is the slow part (11066 works, and single
// sub-domains hold hundreds). Any work list past this length renders capped
// with a "show all" button.
const WORK_LIST_CAP = 300;

// The author overview's landing cap. Same reasoning as above but a smaller
// number, because these are heading-sized blocks rather than list rows: 3408
// of them is a wall, and the 100 with the most texts is the useful first read.
const AUTHOR_OVERVIEW_CAP = 100;

// Search is a walk over ~14k titled strings plus an uncapped re-render of every
// match -- a 1-2 character query is both too broad to be useful and the most
// expensive case to render.
const MIN_SEARCH_QUERY_LENGTH = 3;

function isSearchActive() {
  if (state.searchExact) return state.searchQuery.length > 0;
  return state.searchQuery.length >= MIN_SEARCH_QUERY_LENGTH;
}

// Navigates to an axis node, exiting search mode first. While search is active
// renderMain shows filtered results regardless of state.selectedId, so setting
// it alone would produce no visible change.
function selectNode(id) {
  // Ids carry their axis, and search returns hits from both, so a click can be
  // asking for a node the axis in view does not contain. Follow the id rather
  // than dropping the selection on the floor.
  const wanted = id && id.startsWith("auth:") ? "author" : "category";
  if (id && wanted !== state.axis) setAxis(wanted);
  // Leaving "All" discards its expanded state, so coming back lands on the
  // light summary view again rather than silently rebuilding the whole tree.
  state.overviewExpanded = false;
  state.selectedId = id;
  state.searchQuery = "";
  state.searchExact = false;
  const input = document.getElementById("searchInput");
  if (input) input.value = "";
  const exactToggle = document.getElementById("searchExactToggle");
  if (exactToggle) exactToggle.checked = false;
}

function setAxis(axis) {
  state.axis = axis;
  localStorage.setItem("axis", axis);
  state.selectedId = null;
  state.expanded.clear();
  state.expandedWorkLists.clear();
}

// --- utils

function isExpandAllGesture(ev) {
  // macOS: Option=altKey. Windows/Linux: Alt=altKey. Fallbacks: Shift, Ctrl/Cmd.
  return !!(ev.altKey || ev.shiftKey || ev.ctrlKey || ev.metaKey);
}

// Flat [{id, title}] over every titled thing -- works plus both axes' entries.
// Built once at load time, no transliteration involved; this is the source list
// that ensureSchemeCached()/indexedTitle() lazily transliterate per scheme.
function collectTitledNodes(data) {
  const nodes = [];
  for (const w of data.works) nodes.push({ id: w.id, title: w.title, author: w.author || "" });
  for (const d of data.axes.category) {
    nodes.push({ id: `cat:${d.title}`, title: d.title });
    for (const s of d.children) {
      nodes.push({ id: `cat:${d.title}/${s.title}`, title: s.title });
    }
  }
  for (const a of data.axes.author) {
    nodes.push({ id: `auth:${a.title}`, title: a.title });
  }
  return nodes;
}

// Transliterates every title into `scheme` exactly once, the first time that
// scheme is actually needed, and caches it forever. Devanagari needs no
// transliteration call at all, being the data's native storage script.
function ensureSchemeCached(scheme) {
  if (state.translitCache.has(scheme)) return state.translitCache.get(scheme);
  const map = new Map();
  if (scheme === "devanagari") {
    for (const n of state.allTitledNodes) map.set(n.id, n.title);
  } else {
    for (const n of state.allTitledNodes) {
      map.set(n.id, translitTextUncached(n.title, scheme));
    }
  }
  state.translitCache.set(scheme, map);
  return map;
}

function displayTitle(raw, id) {
  if (state.scheme === "devanagari") return raw;
  if (id != null) {
    const cached = state.translitCache.get(state.scheme);
    if (cached && cached.has(id)) return cached.get(id);
  }
  return translitTextUncached(raw);
}

function translitTextUncached(s, scheme = state.scheme) {
  if (!s) return s;
  if (scheme === "devanagari") return s;
  try {
    return Sanscript.t(s, "devanagari", scheme);
  } catch (e) {
    return s;
  }
}

// Diacritics are stripped from both the index and the query, so `kadambari`
// finds `kādambarī`. Typing IAST diacritics is not a reasonable thing to ask of
// someone searching a romanized corpus, and a reader who does type them still
// matches, since the same folding applies to the query.
function foldDiacritics(s) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function indexedTitleById(id) {
  const scheme = state.scheme;
  let idx = state.searchIndex.get(scheme);
  if (!idx) {
    idx = new Map();
    const titles = ensureSchemeCached(scheme);
    // Devanagari has no diacritics to fold, so folding is a no-op there rather
    // than a special case.
    for (const [nid, t] of titles) idx.set(nid, foldDiacritics(t || ""));
    state.searchIndex.set(scheme, idx);
  }
  return idx.get(id) || "";
}

// The author, folded the same way, kept in its own index rather than appended
// to the title one: `indexedTitleById` also backs exact match, and a work whose
// title and author sat in one string could never be matched exactly by either.
// Only works have one -- an author axis entry IS the name, already indexed as
// its title.
function indexedAuthorById(id) {
  const scheme = state.scheme;
  let idx = state.searchAuthorIndex.get(scheme);
  if (!idx) {
    idx = new Map();
    for (const n of state.allTitledNodes) {
      if (!n.author) continue;
      idx.set(n.id, foldDiacritics(translitTextUncached(n.author, scheme)));
    }
    state.searchAuthorIndex.set(scheme, idx);
  }
  return idx.get(id) || "";
}

// --- axis access
//
// Both axes present the same interface to the renderer: a list of top-level
// entries, each with a title, stats, optional children, and the work ids it
// holds. That symmetry is the whole point -- neither axis is privileged.

function axisEntries() {
  return state.axis === "category"
    ? state.data.axes.category
    : state.data.axes.author;
}

// `axis` overrides the one in view, for search, which scans both.
function nodeIdFor(entry, parent, axis = state.axis) {
  if (axis === "author") return `auth:${entry.title}`;
  return parent ? `cat:${parent.title}/${entry.title}` : `cat:${entry.title}`;
}

// Every work id under a node, whether it is a domain (sum of its sub-domains),
// a sub-domain, or an author.
function workIdsOf(entry) {
  if (entry.work_ids) return entry.work_ids;
  return (entry.children || []).flatMap((c) => c.work_ids);
}

function findNode(id) {
  if (id == null) return null;
  for (const entry of axisEntries()) {
    if (nodeIdFor(entry) === id) return { entry, parent: null };
    for (const child of (entry.children || [])) {
      if (nodeIdFor(child, entry) === id) return { entry: child, parent: entry };
    }
  }
  return null;
}

// Half the catalogue is scans with no searchable text (5509 of 11066 are PDF
// only), which is dead weight if you came here to read. The filter applies to
// the work lists, not to the sidebar counts -- those describe the catalogue,
// and silently restating them under a filter would make the two disagree.
function textOnlyFiltered(works) {
  return state.textOnly ? works.filter((w) => w.text) : works;
}

function worksOf(entry) {
  return textOnlyFiltered(workIdsOf(entry).map((i) => state.works.get(i)).filter(Boolean));
}

// --- rendering

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on") && k.length > 2 && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(n.dataset, v);
    else n.setAttribute(k, v);
  }
  for (const kid of kids) {
    if (kid == null) continue;
    if (typeof kid === "string") n.appendChild(document.createTextNode(kid));
    else n.appendChild(kid);
  }
  return n;
}

function formatBytes(bytes) {
  if (bytes == null) return "";
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

// transliterated_bytes (IAST) is the primary size figure: raw_bytes includes
// markup overhead, and content_bytes is Devanagari, which runs ~1.9x IAST bytes
// for the same text and so is not intuitively comparable.
function contentSizeBytes(stats) {
  if (!stats) return null;
  if (stats.transliterated_bytes) return stats.transliterated_bytes;
  if (stats.content_bytes != null) return stats.content_bytes;
  return stats.raw_bytes ?? null;
}

// Stats text. Sizes are optional and usually absent (the metadata build has
// none at all), so this leads with counts and appends a size only when one
// exists -- and never implies a size of zero where the figure is simply absent.
// The stats a node should display right now. Under the TXT-only filter the
// sidebar has to agree with the list beside it, so the count becomes the node's
// `text_count` -- precomputed by the builder, so no walk is needed.
//
// The byte totals carry over unchanged, because they are already a text-only
// figure: a work gets `sizes` only by being fetched and measured, and only
// text-bearing works ever are (shape.py summarize()). Nothing in tree.json has
// sizes without text, so the filter cannot narrow the population the bytes were
// summed over -- there is nothing to narrow. Zeroing them here used to blank
// the size out of every row the moment TXT was switched on.
function visibleStats(stats) {
  if (!state.textOnly || !stats) return stats;
  return { ...stats, count: stats.text_count ?? 0 };
}

// `labelSize` spells the figures out in full, for the tooltips: how many of the
// works actually carry Unicode text, since the bytes measure that text and not
// the PDFs the same works may also carry. The rows beside them stay terse --
// they are tight on width, and the qualifier would repeat down every line.
//
//   row                  (70 texts, 9.6 MB)
//   tooltip              (70 texts, of which 43 are txt totaling 9.6 MB)
//   tooltip, TXT filter  (43 texts, 9.6 MB)
//
// Without it the row reads as though all 70 were measured. Half the catalogue
// is scans with no text at all. Under the TXT filter the qualifier goes away
// again, because there `count` already IS the text count.
function formatStats(stats, { includeSize = true, labelSize = false } = {}) {
  if (!stats) return "";
  const parts = [];
  if (stats.count != null) parts.push(`${stats.count} ${stats.count === 1 ? "text" : "texts"}`);
  if (includeSize && stats.sized) {
    // Just the size. It used to read "53.6 MB over 184" when `sized` fell short
    // of `count`, flagging the measurement as partial -- but the denominator
    // invited the wrong comparison (against every work, including the PDF-only
    // ones that can never have a text size) and the coverage gap is temporary:
    // tier 3 is still filling it in, and nothing publishes until it has.
    const size = formatBytes(contentSizeBytes(stats));
    if (size && !labelSize) {
      parts.push(size);
    } else if (size) {
      // Under the TXT filter `count` IS the text count, so there is nothing to
      // qualify -- "22 texts, of which 22 are txt" and "22 texts, 2.4 MB txt"
      // both just restate it. Fall back to the plain size.
      const texts = stats.text_count;
      parts.push(texts != null && texts !== stats.count
        ? `of which ${texts} ${texts === 1 ? "is" : "are"} txt totaling ${size}`
        : size);
    }
  }
  return parts.length ? `(${parts.join(", ")})` : "";
}

function renderSidebarTree() {
  const host = document.getElementById("sidebarTree");
  host.innerHTML = "";

  for (const entry of axisEntries()) {
    const node = renderSidebarNode(entry, null, 0);
    if (node) host.appendChild(node);
  }

  const allStats = visibleStats(state.data.all_stats);
  const allStatsEl = document.getElementById("allStats");
  if (allStatsEl) allStatsEl.textContent = formatStats(allStats);

  const allRowEl = document.getElementById("allRow");
  if (allRowEl) {
    allRowEl.title = `All ${formatStats(allStats, { labelSize: true })}`;
    allRowEl.classList.toggle("selected", state.selectedId == null);
    // Option/Shift-click on "All" opens every top-level node at once, the
    // gesture the hint under this row already advertises. One level is the
    // whole job: the category axis nests exactly one deep (domain ->
    // sub-domain) and the author axis does not nest at all, so there is no
    // deeper recursion for this to do -- unlike the sibling atlas, whose
    // arbitrarily deep tree needs the same gesture on every arrow.
    const expandAllTopLevel = () => {
      for (const entry of axisEntries()) {
        if (state.textOnly && !(entry.stats?.text_count)) continue;
        if (!(entry.children || []).length) continue;
        state.expanded.add(nodeIdFor(entry, null));
      }
    };

    allRowEl.onclick = (ev) => {
      if (isExpandAllGesture(ev)) expandAllTopLevel();
      selectNode(null);
      renderSidebarTree();
      renderMain();
      closeSidebarIfMobile();
    };
    bindLongPressExpand(allRowEl, () => {
      expandAllTopLevel();
      selectNode(null);
      renderSidebarTree();
      renderMain();
    });
  }

}

function renderSidebarNode(entry, parent, depth) {
  const id = nodeIdFor(entry, parent);
  // A node with nothing left under the filter drops out rather than sitting
  // there as "(0 works)" -- under TXT only the sidebar is a map of what you can
  // actually reach, and 3888 of the author axis's entries have no text at all.
  if (state.textOnly && !(entry.stats?.text_count)) return null;
  const kids = entry.children || [];
  const isExpanded = state.expanded.has(id);

  const toggleNode = (expandAll) => {
    if (state.expanded.has(id)) {
      state.expanded.delete(id);
    } else {
      state.expanded.add(id);
      if (expandAll) for (const c of kids) state.expanded.add(nodeIdFor(c, entry));
    }
    renderSidebarTree();
    renderMain();
  };

  // Three cases, and depth is what separates them:
  //   - has children  -> a real arrow, clickable
  //   - nested leaf    -> the bullet, which marks it as sitting UNDER its
  //                       parent and lines it up with its siblings
  //   - top-level leaf -> a narrow blank spacer. The whole author axis is
  //                       childless at depth 0, so a bullet there marked
  //                       nothing and every row paid 28px of indent for an
  //                       affordance that does nothing.
  const toggleArrow = kids.length
    ? el("span", {
        class: "toggleArrow",
        onclick: (ev) => {
          ev.stopPropagation();
          toggleNode(isExpandAllGesture(ev));
        },
      }, isExpanded ? "▾" : "▸")
    : el("span", {
        class: "toggleArrow toggleArrowStatic" + (depth ? "" : " toggleArrowLeaf"),
      }, depth ? "·" : "");
  if (kids.length) bindLongPressExpand(toggleArrow, () => toggleNode(true));

  const statsText = formatStats(visibleStats(entry.stats));
  const statsTooltip = formatStats(visibleStats(entry.stats), { labelSize: true });
  // On the author axis, say how far this person's work spreads across the
  // category tree -- the fact the old nested build could not express at all.
  const spread = state.axis === "author" && (entry.domains || []).length > 1
    ? `Filed under ${entry.domains.length} categories: ${entry.domains.map((d) => translitTextUncached(d)).join("; ")}`
    : "";
  const label = displayTitle(entry.title, id);

  const row = el("div", {
    class: "row" + (state.selectedId === id ? " selected" : "")
      + (entry.unknown || entry.uncategorized ? " absentValue" : ""),
    title: spread ? `${spread}\n${label} ${statsTooltip}` : `${label} ${statsTooltip}`,
    onclick: () => {
      selectNode(id);
      renderSidebarTree();
      renderMain();
      closeSidebarIfMobile();
    },
  },
    toggleArrow,
    el("span", { class: depth === 0 ? "title topLevel" : "title" }, label),
    // A scatter marker: this author appears under more than one category.
    spread ? el("span", { class: "small", style: "margin-left:6px; opacity:0.55;" }, `↔${entry.domains.length}`) : null,
    statsText ? el("span", { class: depth === 0 ? "small topLevel" : "small", style: "margin-left:auto; padding-left:10px; opacity:0.7;" }, statsText) : null,
  );

  const wrap = el("div", { class: depth ? "indent" : "" }, row);
  if (kids.length && isExpanded) {
    for (const c of kids) {
      const child = renderSidebarNode(c, entry, depth + 1);
      if (child) wrap.appendChild(child);
    }
  }
  return wrap;
}

// The one fact a work carries that the surrounding view does not already
// state. Browsing by category, every work on screen sits under its own
// sub-domain heading, so the category is given and the author is the news;
// browsing by author the reverse holds, and repeating the author on every row
// under an author heading says nothing. The secondary grouping supplies the
// other axis as a heading of its own, so the row goes quiet there.
function crossAxisLabel(work) {
  if (secondaryGrouping()) return null;
  if (state.axis === "author") return categoryLabel(work);
  return work.author ? displayTitle(work.author, null) : null;
}

// domain + sub-domain, minus the sub-domains that only restate their parent:
// every domain has a `<domain>sambaddhapustakani` catch-all, and 23 of the 116
// pairs repeat the domain stem that way. Where the sub-domain is a real
// distinction -- agamah holds tantrasastram, vaikhanasam, saktam -- it is the
// half worth reading, so both are shown.
function categoryLabel(work) {
  const domain = work.domain;
  const sub = work.sub_domain;
  if (!domain) return sub ? displayTitle(sub, null) : null;
  const redundant = !sub || sub === domain || sub.includes(domain.slice(0, -1));
  if (redundant) return displayTitle(domain, null);
  return `${displayTitle(domain, null)} › ${displayTitle(sub, null)}`;
}

// One work: title, link out, and whatever metadata it carries.
function renderWorkLi(work) {
  const li = el("li", { class: "pageLi" });

  // The reader endpoint doubles as the structure flag: `read_chapter` means the
  // site paginates the work by chapter, i.e. a real table of contents exists;
  // `readbook3` means one flat text. Nothing else in the catalogue carries a
  // signal about internal navigation.
  const hasToc = work.text === "read_chapter";

  // The title goes to the metadata page: it names the work, and the work is not
  // any one of its formats. Reaching a format is the badges' job below.
  li.appendChild(el("a", {
    href: metadataUrl(work),
    target: "_blank",
    rel: "noopener",
    class: "pageLink",
  }, displayTitle(work.title, work.id)));

  const bits = [];
  const cross = crossAxisLabel(work);
  if (cross) bits.push(cross);
  if (work.publish_year) bits.push(String(work.publish_year));
  if (work.sizes) {
    const size = formatBytes(contentSizeBytes(work.sizes));
    if (size) bits.push(size);
  }
  if (bits.length) {
    li.appendChild(el("span", { class: "small", style: "margin-left:8px; opacity:0.7;" }, bits.join(" · ")));
  }

  const badges = el("span", { class: "small", style: "margin-left:8px;" });
  // TOC is a property of the text, not a format of its own -- there is nothing
  // separate to open -- so it stays an unlinked marker.
  if (hasToc) badges.appendChild(el("span", { class: "badge", title: "Has a chapter-by-chapter table of contents on the site" }, "TOC"));

  const pdfHref = pdfUrl(work);
  if (pdfHref) {
    badges.appendChild(el("a", {
      href: pdfHref,
      target: "_blank",
      rel: "noopener",
      class: "badge badgeLink",
      title: "Open the scanned PDF on ebharatisampat.in",
    }, "PDF"));
  }

  const textHref = textUrl(work);
  if (textHref) {
    badges.appendChild(el("a", {
      href: textHref,
      target: "_blank",
      rel: "noopener",
      class: "badge badgeLink",
      title: hasToc
        ? "Open the Unicode text on ebharatisampat.in (chapter by chapter)"
        : "Open the Unicode text on ebharatisampat.in",
    }, "text"));
  }

  // The locally cached text, served by `serve_docs.py --fulltext`. Two
  // conditions, both required: the build saw the text on disk (`has_text`),
  // and this server is actually offering it (FULLTEXT_MODE). On the published
  // site the second is false and this badge never renders -- which is the
  // point, since the text is not ours to republish.
  if (FULLTEXT_MODE && work.has_text) {
    badges.appendChild(el("a", {
      href: `/text/${work.serial}`,
      target: "_blank",
      rel: "noopener",
      class: "badge badgeLink badgeLocal",
      title: "Open the locally cached plain text (this machine only)",
    }, "txt"));
  }

  // Present in the catalogue but scraped to nothing -- a real entry with no
  // content behind it in this snapshot, not a missing book. See
  // notes/snapshot-defects.md.
  if (work.empty_in_snapshot) badges.appendChild(el("span", { class: "badge badgeWarn", title: "This book scraped to an empty file in the snapshot" }, "empty"));
  if (badges.childNodes.length) li.appendChild(badges);

  return li;
}

// Rebuilt from the id, exactly as pipeline/parse_metadata.py does -- the tree
// deliberately ships no urls, since every one is derivable. The snapshot build
// stores the decoded id, so its works need re-encoding.
function encodedId(work) {
  if (work.id_encoded) return work.id_encoded;
  // The metadata build already stores the base64 form; the snapshot build
  // stores the decoded number.
  return /^\d+$/.test(work.id) ? btoa(work.id) : work.id;
}

const SITE_ROOT = "https://www.ebharatisampat.in";

// Text and PDF are two distinct documents, not two renderings of one, and 3912
// works have both. So each gets its own link off the badge; the title goes to
// the metadata page, which is the one page that describes the work itself
// rather than a single format of it.
function textUrl(work) {
  const id = encodedId(work);
  if (work.text === "readbook3") {
    // One constant pageno across every readbook3 link in the corpus -- a
    // session/view token, not a page number.
    return `${SITE_ROOT}/readbook3.php?bookid=${id}&pageno=MjI0MjQyNjk5NTk=`;
  }
  if (work.text === "read_chapter") return `${SITE_ROOT}/read_chapter.php?bookid=${id}`;
  return null;
}

function pdfUrl(work) {
  return work.pdf ? `${SITE_ROOT}/ebook/index.php?bookid=${encodedId(work)}` : null;
}

function metadataUrl(work) {
  return `${SITE_ROOT}/readSearch.php?id=${encodedId(work)}`;
}

// --- links out to the source
//
// The source offers two views of a category, and they are good at different
// things, so a category header gets BOTH rather than us picking for the reader:
//
//   search  search.php   COMPLETE, but a flat paginated list and nothing more.
//   browse  unicodetype.php  INCOMPLETE, but genuinely interactive -- the
//           reader can narrow by author, sub-category, publisher, language,
//           set the page size, and export.
//
// "Incomplete" is measured, and narrower than an earlier version of this
// comment claimed. All 33 categories were compared on 2026-08-20:
//
//   - The listing holds TEXT-BEARING works only, so its count must be compared
//     against our `text_count`, never our total. Comparing 151 against our 399
//     for उपवेदाः -- as this comment once did -- mixes in 163 PDF-only works
//     and invents a shortfall that is not there.
//   - Against `text_count` it is EXACT in 18 of 33 categories and within 5% in
//     25. काव्यानि: listing 590, our txt 590.
//   - The real shortfall is corpus-wide: the listing holds 4214 where we count
//     5557 text-bearing works (-24%), and it is concentrated -- दर्शनानि
//     (1579 -> 908), वेदाङ्गानि (864 -> 502) and वेदः (209 -> 46) hold 1196 of
//     the 1343 missing.
//   - The category filter is NOT the cause. The 33 per-category counts sum to
//     exactly 4214, the unfiltered listing's own total. The works are absent
//     from the shelf before any filtering happens.
//
// So the browse link is faithful to its source; the source's shelf is short.
// The About page states this, which is the contribution -- a reader on the
// site alone gets the reduced view with nothing telling them so.

const SEARCH_TYPE_MAX_LENGTH = 100; // the form's own maxlength on `ebs`

// `type` values come from the search form's own `<select name="type">`:
// book | author | pub | cat | id. Anything else falls through to a book-name
// search -- a silent wrong answer rather than an error, which is why
// pipeline/check_source_links.py asserts `type` is still honored.
function siteSearchUrl(value, type) {
  if (!value || value.length > SEARCH_TYPE_MAX_LENGTH) return null;
  return `${SITE_ROOT}/search.php?ebs=${encodeURIComponent(value)}&type=${type}`;
}

// Every facet parameter on the listings is an EXCLUSION list -- the site's own
// JS sends the *unchecked* boxes (`site-structure.md` §3). So to show one
// value you name all the others, and the two inversions cancel: the reader
// lands on a page with exactly their value ticked, and every facet then works
// normally under their clicks.
//
// NEVER pass the literal `All`, on any facet. It is treated as just another
// value to exclude, and on `sub_cat` it silently costs works (151 -> 48 when
// measured). An omitted parameter is the correct way to say "no filter".
function listingComplementUrl(values, selected, extra = {}) {
  const others = values.filter((v) => v !== selected);
  // Excluding everything returns 0, and so does an empty `cat=` -- both mean
  // "no listing to show" rather than "the whole collection".
  if (!others.length) return null;
  const params = new URLSearchParams({ cat: others.join(","), ...extra });
  return `${SITE_ROOT}/unicodetype.php?${params}`;
}

// The listing filtered to one category: exclude the other 32.
function categoryBrowseUrl(domain) {
  const domains = (state.data.axes.category || []).map((d) => d.title);
  return listingComplementUrl(domains, domain);
}

// NO sub-category link exists, and the reason is a source defect rather than a
// choice -- measured 2026-08-20.
//
// The `sub_cat` complement does not work, unlike the `cat` one. Excluding a
// category's other sub-domains returns far fewer works than the listing's own
// facet claims: उपवेदाः shows आयुर्वेदः (107), गान्धर्ववेदः (1), धनुर्वेदः (3),
// स्थापत्यवेदः (40), summing to its 151 -- but the complements return 32, 0, 0
// and 16, summing to 48. The site's own JS hits this too: clicking आयुर्वेदः in
// the panel lands on 32 while the label still reads 107.
//
// It is not a vocabulary mismatch. Passing only the four values the listing
// itself offers gives the same 48, so it is not caused by our two extra
// PDF-only sub-domains (अर्थवेदः, चित्रकला) -- though those matter separately:
// unknown values in `cat` are harmlessly IGNORED, while unknown values in
// `sub_cat` are not, dropping 107 to 32. That asymmetry is worth remembering
// before trusting any other facet's complement.
//
// So a sub-category browse link would land the reader on roughly a third of the
// works, with the page's own sidebar contradicting it. Search cannot help
// either (no `type=sub_cat`). Sub-categories therefore get nothing, and this
// Atlas's own tree is the accurate view of them.

// Which links a node gets, in render order.
//
//   category      search + browse
//   sub-category  neither -- the source supports neither route; see above
//   author        search only. The listing's author facet would need all 3407
//                 names in the URL (~451 KB) to name one person's complement,
//                 which the site does not handle at that scale.
//
// The absence buckets get nothing on either axis -- `unknown` author and
// `uncategorized` sub-domain name a gap in the data, not a value the source
// can be filtered by.
function nodeSourceLinks(entry, parent) {
  if (entry.unknown || entry.uncategorized) return [];

  if (state.axis === "author") {
    const href = siteSearchUrl(entry.title, "author");
    return href ? [{ label: "search txt+pdf", href, kind: "search" }] : [];
  }

  if (parent) return [];

  const links = [];
  const search = siteSearchUrl(entry.title, "cat");
  if (search) links.push({ label: "search txt+pdf", href: search, kind: "search" });
  const browse = categoryBrowseUrl(entry.title);
  if (browse) links.push({ label: "browse txt", href: browse, kind: "browse" });
  return links;
}

// Tooltips carry the same distinction the About page explains at length. The
// browse one states the shortfall as the source's, because it is.
const SOURCE_LINK_TITLES = {
  search: {
    category: "Search ebharatisampat.in for this category — the source's complete list",
    author: "Search ebharatisampat.in for this author — the source's complete list",
  },
  browse: {
    category: "Browse this category on ebharatisampat.in, with the source's own filters "
      + "(author, sub-category, publisher). Lists Unicode texts only, so compare it "
      + "against the txt count, not the total — and note the source's listing is "
      + "missing ~24% of its texts overall. See this Atlas's About page.",
  },
};

function sourceLinkTitle(kind) {
  if (kind === "search") {
    return SOURCE_LINK_TITLES.search[state.axis === "author" ? "author" : "category"];
  }
  return SOURCE_LINK_TITLES.browse.category;
}

// A list of works, capped, with an optional secondary grouping applied.
function renderWorkList(works, nodeId) {
  const grouping = secondaryGrouping();
  if (grouping) return renderGroupedWorks(works, nodeId, grouping);

  const block = el("div", {});
  const expanded = state.expandedWorkLists.has(nodeId);
  const shown = expanded ? works : works.slice(0, WORK_LIST_CAP);
  const ul = el("ul", { class: "pageList" });
  for (const w of shown) ul.appendChild(renderWorkLi(w));
  block.appendChild(ul);

  if (works.length > shown.length) {
    block.appendChild(el("button", {
      type: "button",
      class: "expandAllButton",
      onclick: () => {
        state.expandedWorkLists.add(nodeId);
        renderMain();
      },
    }, `Show all ${works.length}`));
  }
  return block;
}

// Which secondary grouping is active, if any. Each axis groups by the OTHER
// one -- that symmetry is the design: whichever way you are browsing, the
// cross-cutting dimension is one toggle away.
function secondaryGrouping() {
  if (state.axis === "category" && state.groupAuthor) return "author";
  if (state.axis === "author" && state.groupCategory) return "category";
  return null;
}

// The source links a grouping heading carries. A heading names a value on the
// OTHER axis than the one being browsed -- grouping categories by author names
// an author, and vice versa -- so it gets that axis's links, not the current
// one's. `nodeSourceLinks` keys off `state.axis`, which is the wrong way round
// here, hence the separate builder.
//
// Sub-domain headings get nothing: `sub_cat` is only meaningful under its
// parent domain, and the site has no per-sub-category page to point at.
function groupHeadingLinks(label, grouping) {
  if (!label || label === state.data.unknown_author
      || label === state.data.uncategorized_sub) return [];

  if (grouping === "author") {
    const href = siteSearchUrl(label, "author");
    return href ? [{ label: "search txt+pdf", href, kind: "search" }] : [];
  }

  const links = [];
  const search = siteSearchUrl(label, "cat");
  if (search) links.push({ label: "search txt+pdf", href: search, kind: "search" });
  const browse = categoryBrowseUrl(label);
  if (browse) links.push({ label: "browse txt", href: browse, kind: "browse" });
  return links;
}

// A group heading plus its work count. `depth` 0 is a top-level heading, 1 a
// sub-heading indented beneath one.
function groupHeading(label, count, { depth = 0, absent = false, grouping = null } = {}) {
  const links = depth ? [] : groupHeadingLinks(label, grouping);
  return el("div", {
    class: "block panelTitle groupHeading"
      + (depth ? " groupSubHeading" : "")
      + (absent ? " absentValue" : ""),
    style: `margin-top:${depth ? 8 : 12}px;`,
  },
    displayTitle(label, null),
    el("span", { class: "small", style: "font-weight:normal; margin-left:8px; opacity:0.7;" },
      `(${count} ${count === 1 ? "text" : "texts"})`),
    ...links.map((link) => el("a", {
      href: link.href,
      target: "_blank",
      rel: "noopener",
      class: "badge badgeLink",
      style: "font-weight:normal; margin-left:8px;",
      // The grouping heading names the other axis, so the tooltip has to
      // describe that axis rather than the one `sourceLinkTitle` assumes.
      title: link.kind === "search"
        ? SOURCE_LINK_TITLES.search[grouping === "author" ? "author" : "category"]
        : SOURCE_LINK_TITLES.browse.category,
    }, link.label)),
  );
}

function renderGroupedWorks(works, nodeId, grouping) {
  // The category grouping is two-level, because the taxonomy is: grouping a
  // person's works by domain alone hid the distinction that matters most for a
  // prolific author. Kalidasa's 110 works give 7 domain headings, the largest
  // reading "kavyani, 91 works" -- while the sub-domains underneath it separate
  // 47 plays from 41 verse from 2 prose. The author grouping stays flat; author
  // has no second level.
  const nested = grouping === "category";
  const unknown = state.data.unknown_author;

  // domain -> sub-domain -> works, collapsing to a single level for authors.
  const groups = new Map();
  for (const w of works) {
    const key = nested ? (w.domain || "") : (w.author || unknown);
    const subKey = nested ? (w.sub_domain || state.data.uncategorized_sub || "") : "";
    if (!groups.has(key)) groups.set(key, new Map());
    const subs = groups.get(key);
    if (!subs.has(subKey)) subs.set(subKey, []);
    subs.get(subKey).push(w);
  }

  // Unknown sorts last on the author grouping: it is a real bucket, but it is
  // an absence of attribution rather than a person, so it does not belong
  // interleaved alphabetically among named authors.
  const byLabel = (a, b) => {
    if (a === unknown) return 1;
    if (b === unknown) return -1;
    return a.localeCompare(b);
  };
  const keys = [...groups.keys()].sort(byLabel);

  // The cap applies to the grouped path too, counted in works rather than
  // groups: darsanani grouped by author is 2661 works across 1129 headings
  // (~20k DOM nodes), which renders in ~200ms -- tolerable, but it is the same
  // unbounded growth the flat cap exists to prevent. Whole groups are kept
  // intact rather than truncated mid-group. Nesting does not move this: the
  // worst author on the axis is Sankaracarya at 7 domains + 12 sub-domains.
  const block = el("div", {});
  const expanded = state.expandedWorkLists.has(nodeId);
  let shown = 0;
  let truncated = 0;

  for (const key of keys) {
    const subs = groups.get(key);
    let total = 0;
    for (const members of subs.values()) total += members.length;

    if (!expanded && shown >= WORK_LIST_CAP) {
      truncated += total;
      continue;
    }
    shown += total;

    block.appendChild(groupHeading(key, total, { absent: key === unknown, grouping }));

    if (!nested) {
      const ul = el("ul", { class: "pageList" });
      for (const w of subs.get("")) ul.appendChild(renderWorkLi(w));
      block.appendChild(ul);
      continue;
    }

    // Always name the sub-domain, even when a domain holds only one. It is not
    // derivable from its parent -- kavyani holds natakam, padyam, gadyam and a
    // catch-all -- so suppressing it leaves the reader unable to tell which one
    // a lone work is filed under, and makes the same domain render differently
    // from one author to the next.
    const subKeys = [...subs.keys()].sort(byLabel);
    for (const subKey of subKeys) {
      const members = subs.get(subKey);
      block.appendChild(groupHeading(subKey, members.length, { depth: 1 }));
      const ul = el("ul", { class: "pageList" });
      for (const w of members) ul.appendChild(renderWorkLi(w));
      block.appendChild(ul);
    }
  }

  if (truncated) {
    block.appendChild(el("button", {
      type: "button",
      class: "expandAllButton",
      onclick: () => {
        state.expandedWorkLists.add(nodeId);
        renderMain();
      },
    }, `Show all ${works.length} texts (${truncated} more)`));
  }
  return block;
}

function renderNodeBlock(entry, parent, { isSearch = false, depth = 0 } = {}) {
  const id = nodeIdFor(entry, parent);
  const block = el("div", { class: "block" });

  // Shallower headers must paint OVER deeper ones, so a descendant scrolls
  // underneath its ancestor's pinned header instead of through it. Without an
  // explicit order the later (deeper) header wins on DOM order alone, which is
  // exactly backwards. Mirrors the sibling atlas.
  const header = el("div", {
    class: "panelTitle sticky-header"
      + (entry.unknown || entry.uncategorized ? " absentValue" : ""),
    dataset: { stickyDepth: String(depth) },
    style: `z-index:${1000 - depth};`,
  },
    displayTitle(entry.title, id),
    el("span", { class: "small", style: "font-weight:normal; margin-left:8px;" }, formatStats(visibleStats(entry.stats))),
    // The source's own views of this node -- which ones exist depends on the
    // axis and depth; see nodeSourceLinks.
    ...nodeSourceLinks(entry, parent).map((link) => el("a", {
      href: link.href,
      target: "_blank",
      rel: "noopener",
      class: "badge badgeLink",
      style: "font-weight:normal; margin-left:8px;",
      title: sourceLinkTitle(link.kind),
    }, link.label)),
  );
  block.appendChild(header);

  // On the author axis, name the categories this person's work spans. This is
  // the fact the nested build hid: browsing to Kalidasa under one domain gave
  // no hint that six more held his work.
  if (state.axis === "author" && (entry.domains || []).length > 1) {
    block.appendChild(el("div", { class: "small", style: "margin-bottom:8px; opacity:0.75;" },
      `Filed under ${entry.domains.length} categories: `
      + entry.domains.map((d) => translitTextUncached(d)).join(", ")));
  }

  const kids = (entry.children || [])
    .filter((c) => !state.textOnly || c.stats?.text_count);
  if (kids.length && !isSearch) {
    for (const c of kids) block.appendChild(renderNodeBlock(c, entry, { depth: depth + 1 }));
  }

  const own = entry.work_ids ? worksOf(entry) : [];
  if (own.length) {
    block.appendChild(renderWorkList(own, id));
  } else if (state.textOnly && (entry.work_ids || []).length) {
    // Say why the list is empty. Without this the filter looks like an empty
    // category, and the header's count (which describes the catalogue) appears
    // to contradict the blank space under it.
    block.appendChild(el("div", { class: "small", style: "opacity:0.7; margin-bottom:8px;" },
      `None of these ${entry.work_ids.length} texts have Unicode text — turn off "TXT only" to see them.`));
  }

  return block;
}

// The initial view: one row per top-level axis entry. Cheap, and it is the
// shape that makes the axis switch legible -- 33 domains vs 3408 authors.
function renderOverview() {
  const block = el("div", {});
  const entries = axisEntries();

  // The author axis is long enough that an unfiltered dump is not a useful
  // landing view -- lead with the ones holding the most, and say so.
  const isAuthor = state.axis === "author";
  // Under the filter, an entry holding no text is not a thin result -- it is
  // nothing to click -- so it leaves the overview as it leaves the sidebar.
  const visible = state.textOnly
    ? entries.filter((e) => e.stats?.text_count)
    : entries;
  const ranked = isAuthor
    ? [...visible].sort((a, b) => (visibleStats(b.stats).count) - (visibleStats(a.stats).count))
    : visible;
  // The cap is a landing-view convenience, not a limit: 3408 author blocks is
  // not a useful first screen, but the rest are one click away rather than
  // reachable only through search.
  const capped = isAuthor && !state.authorOverviewExpanded && ranked.length > AUTHOR_OVERVIEW_CAP;
  const shown = capped ? ranked.slice(0, AUTHOR_OVERVIEW_CAP) : ranked;

  // Both controls live here, above the list they act on: "Expand all" swaps
  // these one-line summaries for the full nested render, and "Show all" lifts
  // the author cap. Same place on both axes, so the landing view always says
  // what it is showing and how to see more.
  const controls = el("div", { class: "overviewControls" });

  if (isAuthor) {
    controls.appendChild(el("span", { class: "small", style: "opacity:0.75;" },
      `${visible.length} authors${state.textOnly ? " with Unicode text" : ""}. `
      + (capped
        ? `Showing the ${AUTHOR_OVERVIEW_CAP} with the most texts.`
        : "Showing all, most texts first.")));
  }

  if (capped) {
    controls.appendChild(el("button", {
      type: "button",
      class: "expandAllButton",
      onclick: () => {
        state.authorOverviewExpanded = true;
        renderMain();
      },
    }, `Show all ${ranked.length} authors`));
  }

  // Expanding builds thousands of nodes, so the way back has to be visible --
  // otherwise the only exit from a 4-second render is navigating away.
  controls.appendChild(el("button", {
    type: "button",
    class: "expandAllButton",
    onclick: () => {
      state.overviewExpanded = !state.overviewExpanded;
      renderMain();
    },
  }, state.overviewExpanded ? "Collapse all" : "Expand all"));

  block.appendChild(controls);

  // Expanded: render each node the same way drilling into it does, so "All"
  // becomes the whole tree rather than a list of links to it.
  if (state.overviewExpanded) {
    for (const entry of shown) block.appendChild(renderNodeBlock(entry, null));
    return block;   // controls already appended above, so Collapse stays reachable
  }

  for (const entry of shown) {
    const id = nodeIdFor(entry);
    const subCount = (entry.children || []).length;
    block.appendChild(el("div", {
      class: "block panelTitle" + (entry.unknown ? " absentValue" : ""),
      style: "cursor:pointer;",
      onclick: () => {
        selectNode(id);
        renderSidebarTree();
        renderMain();
      },
    },
      displayTitle(entry.title, id),
      el("span", { class: "small", style: "font-weight:normal; margin-left:8px;" }, formatStats(visibleStats(entry.stats))),
      subCount ? el("span", { class: "small", style: "font-weight:normal; margin-left:8px; opacity:0.6;" }, `${subCount} sub-categories`) : null,
      (entry.domains || []).length > 1
        ? el("span", { class: "small", style: "font-weight:normal; margin-left:8px; opacity:0.55;" }, `↔ ${entry.domains.length} categories`)
        : null,
    ));
  }

  return block;
}

function renderMain() {
  const host = document.getElementById("content");
  host.innerHTML = "";

  if (isSearchActive()) {
    host.appendChild(renderSearchResults());
    positionStickyHeaders(host);
    return;
  }

  if (state.selectedId == null) {
    host.appendChild(renderOverview());
    positionStickyHeaders(host);
    return;
  }

  const found = findNode(state.selectedId);
  if (!found) {
    host.innerHTML = "<div class='block'>Not found.</div>";
    return;
  }
  host.appendChild(renderNodeBlock(found.entry, found.parent));
  positionStickyHeaders(host);
}

function positionStickyHeaders(host) {
  const headers = host.querySelectorAll(".sticky-header");
  for (const header of headers) {
    let offset = 0;
    let node = header.parentElement;
    while (node && node !== host) {
      const ancestorHeader = node.querySelector(":scope > .sticky-header");
      if (ancestorHeader && ancestorHeader !== header) {
        offset += ancestorHeader.getBoundingClientRect().height;
      }
      node = node.parentElement;
    }
    header.style.top = `${offset}px`;
  }
}

// --- search
//
// Searches works by title, and axis entries by name, across the whole corpus
// regardless of which node is selected.

function currentSearchMatcher() {
  const q = foldDiacritics(state.searchQuery);
  // Author as well as title: looking for a text by who wrote it is as ordinary
  // as looking for it by name, and the author axis only helps if you already
  // know the name is an author's. Exact mode compares each field whole, so
  // `kalidasa` exactly-matches his works without also matching every title that
  // happens to contain the string.
  if (state.searchExact) {
    return (id) => indexedTitleById(id) === q || indexedAuthorById(id) === q;
  }
  return (id) => indexedTitleById(id).includes(q) || indexedAuthorById(id).includes(q);
}

// Every entry on one axis that matches, with the ids the renderer needs. Both
// axes are searched regardless of which is being browsed: a name is a name, and
// requiring the reader to guess which axis holds their query -- then switch to
// it before typing -- makes search useless for exactly the case it is best at,
// not knowing where a thing is filed.
function axisEntryHits(axis, matches) {
  const hits = [];
  const entries = axis === "category" ? state.data.axes.category : state.data.axes.author;
  for (const entry of entries) {
    if (matches(nodeIdFor(entry, null, axis))) hits.push({ entry, parent: null, axis });
    for (const c of (entry.children || [])) {
      if (matches(nodeIdFor(c, entry, axis))) hits.push({ entry: c, parent: entry, axis });
    }
  }
  return hits;
}

function renderSearchResults() {
  const matches = currentSearchMatcher();
  const block = el("div", {});

  // The axis in view first: it is the one the reader is working in, so its hits
  // are the ones they are most likely to have meant.
  const other = state.axis === "category" ? "author" : "category";
  const entryHits = [
    ...axisEntryHits(state.axis, matches),
    ...axisEntryHits(other, matches),
  ];

  const workHits = textOnlyFiltered(state.data.works.filter((w) => matches(w.id)));

  if (!entryHits.length && !workHits.length) {
    return el("div", { class: "block" }, "No results found.");
  }

  // One heading per axis, so a hit's axis is stated rather than inferred --
  // otherwise a lone name under a heading reading "Categories" is a lie, and
  // clicking it silently switches axes with no warning it was going to.
  let first = true;
  for (const axis of [state.axis, other]) {
    const hits = entryHits.filter((h) => h.axis === axis);
    if (!hits.length) continue;
    block.appendChild(el("div", {
      class: "panelTitle",
      style: first ? "" : "margin-top:14px;",
    },
      axis === "category" ? "Categories" : "Authors",
      el("span", { class: "small", style: "font-weight:normal; margin-left:8px;" }, `(${hits.length})`)));
    first = false;
    for (const { entry, parent } of hits) {
      const id = nodeIdFor(entry, parent, axis);
      block.appendChild(el("div", {
        class: "block panelTitle",
        style: "cursor:pointer;",
        onclick: () => {
          selectNode(id);
          updateAxisControls();
          renderSidebarTree();
          renderMain();
        },
      },
        displayTitle(entry.title, id),
        el("span", { class: "small", style: "font-weight:normal; margin-left:8px;" }, formatStats(visibleStats(entry.stats))),
      ));
    }
  }

  if (workHits.length) {
    block.appendChild(el("div", { class: "panelTitle", style: "margin-top:14px;" },
      "Works",
      el("span", { class: "small", style: "font-weight:normal; margin-left:8px;" }, `(${workHits.length})`)));
    block.appendChild(renderWorkList(workHits, "search"));
  }

  return block;
}

// --- wiring

async function loadData() {
  const r = await fetch(DATA_URL);
  if (!r.ok) throw new Error(`Failed to load ${DATA_URL}: ${r.status}`);
  state.data = await r.json();

  state.works = new Map(state.data.works.map((w) => [w.id, w]));
  state.allTitledNodes = collectTitledNodes(state.data);
  state.translitCache = new Map();
  state.searchIndex = new Map();
  state.searchAuthorIndex = new Map();
  // Warm only the default scheme; every other one is transliterated lazily on
  // first switch -- see ensureSchemeCached.
  ensureSchemeCached(state.scheme);

  state.selectedId = null;

  // Only the snapshot build is worth naming in the header -- it is the
  // surprising state (a fifth of the catalogue), while the full build is what a
  // visitor should assume they are looking at.
  const updatedEl = document.getElementById("dataUpdated");
  if (updatedEl) {
    updatedEl.textContent = state.data.source === "snapshot" ? "snapshot data" : "";
    updatedEl.title = state.data.source === "snapshot"
      ? "The third-party snapshot: 21% of the catalogue, but with measured text sizes."
      : "";
  }
}

const SUN_ICON = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 3v2"/><path d="M12 19v2"/><path d="M5 5l1.4 1.4"/><path d="M17.6 17.6L19 19"/><path d="M3 12h2"/><path d="M19 12h2"/><path d="M5 19l1.4-1.4"/><path d="M17.6 6.4L19 5"/></svg>`;
const MOON_ICON = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/></svg>`;

function updateThemeToggleLabel() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  btn.innerHTML = dark ? SUN_ICON : MOON_ICON;
  btn.title = dark ? "Switch to light theme" : "Switch to dark theme";
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 800px)").matches;
}

function openSidebar() {
  document.getElementById("sidenav")?.classList.add("open");
  // `open`, not `visible`: the stylesheet shows the backdrop on `.open`, so the
  // old class name meant the backdrop never painted -- and an invisible
  // backdrop cannot be clicked, which is why tapping outside did nothing.
  document.getElementById("sidebarBackdrop")?.classList.add("open");
  document.getElementById("sidebarToggle")?.setAttribute("aria-expanded", "true");
  // Body itself scrolls at this breakpoint, so the mainpane's own overflow is
  // not enough to stop the page scrolling behind an open sidebar.
  document.body.classList.add("sidebar-open-lock");
}

function closeSidebar() {
  document.getElementById("sidenav")?.classList.remove("open");
  document.getElementById("sidebarBackdrop")?.classList.remove("open");
  document.getElementById("sidebarToggle")?.setAttribute("aria-expanded", "false");
  document.body.classList.remove("sidebar-open-lock");
}

function closeSidebarIfMobile() {
  if (isMobileLayout()) closeSidebar();
}

function applySidebarWidth(px) {
  document.documentElement.style.setProperty("--sidebar-width", `${px}px`);
}

function initSidebarResizer() {
  const resizer = document.getElementById("sidebarResizer");
  if (!resizer) return;
  const saved = localStorage.getItem("sidebarWidth");
  if (saved) applySidebarWidth(parseInt(saved, 10));

  let dragging = false;
  const onMove = (ev) => {
    if (!dragging) return;
    const x = (ev.touches ? ev.touches[0].clientX : ev.clientX);
    const px = Math.max(180, Math.min(640, x));
    applySidebarWidth(px);
    localStorage.setItem("sidebarWidth", String(px));
  };
  const stop = () => { dragging = false; document.body.style.userSelect = ""; };

  resizer.addEventListener("mousedown", (ev) => { dragging = true; ev.preventDefault(); document.body.style.userSelect = "none"; });
  resizer.addEventListener("touchstart", () => { dragging = true; }, { passive: true });
  window.addEventListener("mousemove", onMove);
  window.addEventListener("touchmove", onMove, { passive: true });
  window.addEventListener("mouseup", stop);
  window.addEventListener("touchend", stop);
}

// Long-press on touch devices stands in for Option/Shift-click, which touch has
// no equivalent of.
function bindLongPressExpand(element, onExpandAll) {
  let timer = null;
  const clear = () => { if (timer) { clearTimeout(timer); timer = null; } };
  element.addEventListener("touchstart", () => {
    clear();
    timer = setTimeout(() => { timer = null; onExpandAll(); }, 500);
  }, { passive: true });
  element.addEventListener("touchend", clear);
  element.addEventListener("touchmove", clear);
  element.addEventListener("touchcancel", clear);
}

function initUI() {
  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.searchQuery = searchInput.value.trim();
      renderMain();
    });
  }

  const exactToggle = document.getElementById("searchExactToggle");
  if (exactToggle) {
    exactToggle.addEventListener("change", () => {
      state.searchExact = exactToggle.checked;
      renderMain();
    });
  }

  const schemeSelect = document.getElementById("schemeSelect");
  if (schemeSelect) {
    const saved = localStorage.getItem("scheme");
    if (saved) { state.scheme = saved; schemeSelect.value = saved; }
    schemeSelect.addEventListener("change", () => {
      state.scheme = schemeSelect.value;
      localStorage.setItem("scheme", state.scheme);
      ensureSchemeCached(state.scheme);
      renderSidebarTree();
      renderMain();
    });
  }

  // The axis switch. Two peers, not a primary and a filter.
  for (const axis of ["category", "author"]) {
    const btn = document.getElementById(`axis-${axis}`);
    if (!btn) continue;
    btn.addEventListener("click", () => {
      setAxis(axis);
      updateAxisControls();
      renderSidebarTree();
      renderMain();
    });
  }

  const groupToggle = document.getElementById("groupToggle");
  if (groupToggle) {
    groupToggle.addEventListener("change", () => {
      if (state.axis === "category") {
        state.groupAuthor = groupToggle.checked;
        localStorage.setItem("groupAuthor", groupToggle.checked ? "1" : "0");
      } else {
        state.groupCategory = groupToggle.checked;
        localStorage.setItem("groupCategory", groupToggle.checked ? "1" : "0");
      }
      renderMain();
    });
  }

  const textOnlyToggle = document.getElementById("textOnlyToggle");
  if (textOnlyToggle) {
    textOnlyToggle.checked = state.textOnly;
    textOnlyToggle.addEventListener("change", () => {
      state.textOnly = textOnlyToggle.checked;
      localStorage.setItem("textOnly", textOnlyToggle.checked ? "1" : "0");
      renderSidebarTree();
      renderMain();
    });
  }

  const themeToggle = document.getElementById("themeToggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      const next = dark ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      updateThemeToggleLabel();
    });
    updateThemeToggleLabel();
  }

  // The brand is a "start over" control, so it reloads rather than resetting in
  // place. A soft reset left axis, grouping, filters, expansion and scroll
  // exactly where they were, which is the opposite of what clicking the title
  // reads as. Reloading re-reads tree.json too, so it also picks up a rebuilt
  // data file without a manual refresh.
  const brand = document.getElementById("brandTitle");
  if (brand) {
    brand.addEventListener("click", () => {
      window.location.href = window.location.pathname;
    });
  }

  document.getElementById("sidebarToggle")?.addEventListener("click", () => {
    const open = document.getElementById("sidenav")?.classList.contains("open");
    if (open) closeSidebar(); else openSidebar();
  });
  document.getElementById("sidebarBackdrop")?.addEventListener("click", closeSidebar);

  initSidebarResizer();
}

// Reflects the current axis in the controls: which axis button is active, and
// what the group toggle means right now (it groups by whichever axis is NOT
// selected, so its label changes with the axis).
function updateAxisControls() {
  for (const axis of ["category", "author"]) {
    document.getElementById(`axis-${axis}`)?.classList.toggle("active", state.axis === axis);
  }
  const groupToggle = document.getElementById("groupToggle");
  const groupLabel = document.getElementById("groupToggleLabel");
  if (groupToggle) {
    groupToggle.checked = state.axis === "category" ? state.groupAuthor : state.groupCategory;
  }
  if (groupLabel) {
    groupLabel.textContent = state.axis === "category" ? "group by author" : "group by category";
    groupLabel.title = state.axis === "category"
      ? "Group each sub-category's texts under their author"
      : "Group each author's texts under the category they are filed in";
  }
}

// docs/VERSION is `__key__ = "value"` lines, not a bare version string -- code,
// data, and content versions are tracked separately.
async function loadVersion() {
  try {
    const r = await fetch("./VERSION");
    if (!r.ok) return;
    const text = await r.text();
    const read = (key) => (text.match(new RegExp(`__${key}__\\s*=\\s*"([^"]*)"`)) || [])[1];
    const code = read("code_version");
    const el = document.getElementById("appVersion");
    if (el && code) {
      el.textContent = `v${code}`;
      const content = read("content_version");
      if (content) el.title = `Corpus snapshot ${content}`;
    }
  } catch (e) { /* version display is optional */ }
}


// A `?q=` in the URL preloads the search box, so another page can deep-link a
// specific title into this Atlas -- the parent's federated search sends every
// result row here, which is the only way a hit over there reaches the item's
// own collection. `?exact=1` additionally turns on exact mode, matching the
// whole transliterated title rather than any substring; the parent uses it
// because it knows the exact title it linked.
//
// Read once at startup and NOT written back as the user types: the query is a
// handoff, not a synced piece of state, and rewriting the URL on every
// keystroke would bury the page in history entries.
function applyQueryFromURL() {
  const params = new URLSearchParams(location.search);
  const q = (params.get("q") || "").trim();
  if (!q) return;
  const input = document.getElementById("searchInput");
  if (input) input.value = q;
  state.searchQuery = q.toLowerCase();
  if (params.get("exact") === "1") {
    state.searchExact = true;
    const exactToggle = document.getElementById("searchExactToggle");
    if (exactToggle) exactToggle.checked = true;
  }
}

// Is this server offering the local corpus text? Only `serve_docs.py
// --fulltext` answers /text/, so one cheap probe settles it -- and on GitHub
// Pages it 404s, leaving every `txt` badge unrendered. Deliberately a runtime
// question rather than a build-time one: the same docs/ is deployed either
// way, and nothing about the published files changes.
let FULLTEXT_MODE = false;

async function detectFulltextMode() {
  try {
    const res = await fetch("/text/", { method: "HEAD" });
    // 404 with this exact marker means the route EXISTS but the serial did
    // not resolve -- i.e. fulltext mode is on. A plain static server has no
    // /text/ route at all and answers without it.
    FULLTEXT_MODE = res.headers.get("X-Fulltext-Mode") === "on";
  } catch {
    FULLTEXT_MODE = false;   // offline, file://, or no server at all
  }
}

(async function main() {
  initUI();
  try {
    await detectFulltextMode();
    await loadData();
  } catch (e) {
    document.getElementById("content").innerHTML =
      `<div class='block'>Failed to load data: ${e.message}</div>`;
    return;
  }
  applyQueryFromURL();
  updateAxisControls();
  renderSidebarTree();
  renderMain();
  loadVersion();
})();
