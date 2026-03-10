// ── Constants ────────────────────────────────────────────────────────────────

const DXDATA_URL =
  "https://raw.githubusercontent.com/gekichumai/dxrating/main/packages/dxdata/dxdata.json";
const SEGA_URL = "https://maimai.sega.jp/data/maimai_songs.json";

// Rating table (myjian/mai-tools)
// [minAchv, factor, maxAchv|null, maxFactor|null]
const RANK_TABLE = [
  [100.5, 0.224, null, null],
  [100.0, 0.216, 100.4999, 0.222],
  [99.5, 0.211, 99.9999, 0.214],
  [99.0, 0.208, null, null],
  [98.0, 0.203, 98.9999, 0.206],
  [97.0, 0.2, null, null],
  [94.0, 0.168, 96.9999, 0.176],
  [90.0, 0.152, null, null],
  [80.0, 0.136, null, null],
  [75.0, 0.12, 79.9999, 0.128],
  [70.0, 0.112, null, null],
  [60.0, 0.096, null, null],
  [50.0, 0.08, null, null],
  [0.0, 0.016, null, null],
];

const RANK_LABELS = [
  [100.5, "SSS+"],
  [100.0, "SSS"],
  [99.5, "SS+"],
  [99.0, "SS"],
  [98.0, "S+"],
  [97.0, "S"],
  [94.0, "AAA"],
  [90.0, "AA"],
  [80.0, "A"],
  [75.0, "BBB"],
  [70.0, "BB"],
  [60.0, "B"],
  [50.0, "C"],
  [0.0, "D"],
];

const CLEAR_LABELS = { 0: "", 1: "", 2: "", 3: "FC", 4: "FC+", 5: "AP", 6: "AP+" };
const AP_CLEAR_TYPES = new Set([5, 6]);

const RATING_IF_RANKS = [
  { key: "rating_s", rank: "S", minAchv: 97.0 },
  { key: "rating_sp", rank: "S+", minAchv: 98.0 },
  { key: "rating_ss", rank: "SS", minAchv: 99.0 },
  { key: "rating_ssp", rank: "SS+", minAchv: 99.5 },
  { key: "rating_sss", rank: "SSS", minAchv: 100.0 },
  { key: "rating_sssp", rank: "SSS+", minAchv: 100.5 },
];

const ALIAS_TO_DIFF = {
  Basic: "basic",
  Advanced: "advanced",
  Expert: "expert",
  Master: "master",
  "Re:Master": "remaster",
};

// Version name map (v100–v260, source: zetaraku/arcade-songs-fetch)
const VERSION_NAMES = {
  100: "maimai", 110: "maimai PLUS", 120: "GreeN", 130: "GreeN PLUS",
  140: "ORANGE", 150: "ORANGE PLUS", 160: "PiNK", 170: "PiNK PLUS",
  180: "MURASAKi", 185: "MURASAKi PLUS", 190: "MiLK", 195: "MiLK PLUS",
  199: "FiNALE", 200: "maimaiDX", 205: "maimaiDX+", 210: "Splash",
  215: "Splash+", 220: "UNiVERSE", 225: "UNiVERSE+", 230: "FESTiVAL",
  235: "FESTiVAL+", 240: "BUDDiES", 245: "BUDDiES+", 250: "PRiSM",
  255: "PRiSM+", 260: "CiRCLE",
};

function versionName(v) {
  if (typeof v === "string") {
    // dxdata.json may provide version as a string directly
    const num = parseInt(v, 10);
    if (!isNaN(num) && VERSION_NAMES[num]) return VERSION_NAMES[num];
    return v;
  }
  return VERSION_NAMES[v] || (v ? `v${v}` : "");
}

const DIFF_CLASS = {
  Basic: "diff-basic",
  Advanced: "diff-advanced",
  Expert: "diff-expert",
  Master: "diff-master",
  "Re:Master": "diff-remaster",
};

// ── State ────────────────────────────────────────────────────────────────────

let chartConstants = {};
let songCategories = {};
let songVersions = {};

// Song name aliases: cache title (normalized, lowercase) → dxdata title (normalized, lowercase)
const songAliases = {
  "sunday night feat kanata.n": "sunday night feat. kanata.n",
  "sunday night feat. kanata.n": "sunday night feat kanata.n",
  "bad apple!! feat nomico": "bad apple!! feat.nomico",
  "コンティニュー!feat. 藍月なくる": "コンティニュー! feat. 藍月なくる",
  "フェイスフェイク・フェイルセイフ": "フェイクフェイス・フェイルセイフ",
};
// Manual chart data for songs missing from server. Fallback only.
// Key: "title (lowercase)|type|difficulty" → { ilv, version, category }
const chartOverrides = {
  "break the speakers|dx|master": { ilv: 14.7, version: "CiRCLE", category: null },
};

let allScores = [];
let filteredScores = [];
let sortCol = "rating";
let sortAsc = false;
let activeTab = "all";

// B50 state
let b50NewCount = 2;
let b50IgnoreNewer = false;
let b50Combined = false;

// ── Rating functions ─────────────────────────────────────────────────────────

function getFactor(achievement) {
  const achv = Math.min(achievement, 100.5);
  for (const [minA, factor, maxA, maxFactor] of RANK_TABLE) {
    if (achv >= minA) {
      if (maxA !== null && achv >= maxA) return maxFactor;
      return factor;
    }
  }
  return 0.0;
}

function getRating(internalLevel, achievement) {
  const achv = Math.min(achievement, 100.5);
  return Math.floor(Math.abs(internalLevel) * achv * getFactor(achv));
}

function getRankLabel(achievement) {
  const achv = Math.min(achievement, 100.5);
  for (const [threshold, label] of RANK_LABELS) {
    if (achv >= threshold) return label;
  }
  return "D";
}

function parseLevel(value) {
  const s = String(value || "").trim();
  if (s.endsWith("+")) {
    const n = parseFloat(s.slice(0, -1));
    return isNaN(n) ? 0 : n + 0.7;
  }
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

// Normalize fullwidth/special chars for matching (cache vs dxdata differences)
function normalizeTitle(s) {
  return s
    .normalize("NFC")      // compose decomposed chars (e.g. タ+゙ → ダ)
    .replace(/～/g, "~")   // fullwidth tilde → regular
    .replace(/＆/g, "&")   // fullwidth ampersand
    .replace(/　/g, " ")   // fullwidth space
    .replace(/？/g, "?")   // fullwidth question mark
    .replace(/！/g, "!")   // fullwidth exclamation
    .replace(/：/g, ":")   // fullwidth colon
    .replace(/＃/g, "#")   // fullwidth hash → regular
    .replace(/[\u2018\u2019]/g, "'") // smart quotes → straight apostrophe
    .replace(/[\u201C\u201D]/g, '"') // smart double quotes → straight
    .trim();
}

// Extract [DX]/[ST] from title and return cleaned title + type hint
function parseTitle(rawTitle) {
  const m = rawTitle.match(/\[(DX|ST|SD)\]\s*/i);
  if (m) {
    return {
      cleanTitle: rawTitle.replace(m[0], "").trim(),
      typeHint: m[1].toUpperCase() === "DX" ? "dx" : "std", // ST and SD both map to std
    };
  }
  return { cleanTitle: rawTitle, typeHint: null };
}

// Lookup helper: try typeHint first, then both types
function _lookupInStore(store, titleLower, alias, typeHint) {
  const diff = ALIAS_TO_DIFF[alias] || alias.toLowerCase();
  if (typeHint) {
    const v = store[`${titleLower}|${typeHint}|${diff}`];
    if (v != null) return { value: v, matchedType: typeHint };
  }
  for (const t of ["dx", "std"]) {
    const v = store[`${titleLower}|${t}|${diff}`];
    if (v != null) return { value: v, matchedType: t };
  }
  return null;
}

// Try raw title first, then with [DX]/[ST]/[SD] stripped, then song alias
function lookupChart(store, rawTitleLower, cleanTitleLower, alias, typeHint) {
  return _lookupInStore(store, rawTitleLower, alias, typeHint)
    ?? _lookupInStore(store, cleanTitleLower, alias, typeHint)
    ?? (songAliases[cleanTitleLower]
      ? _lookupInStore(store, songAliases[cleanTitleLower], alias, typeHint)
      : null);
}

// Lookup override data for a chart (fallback when server data missing)
function lookupOverride(titleLower, alias, typeHint) {
  const diff = ALIAS_TO_DIFF[alias] || alias.toLowerCase();
  if (typeHint) {
    const o = chartOverrides[`${titleLower}|${typeHint}|${diff}`];
    if (o) return { ...o, matchedType: typeHint };
  }
  for (const t of ["dx", "std"]) {
    const o = chartOverrides[`${titleLower}|${t}|${diff}`];
    if (o) return { ...o, matchedType: t };
  }
  return null;
}

// maimai DX version names that indicate DX era (v200+)
const DX_VERSIONS = new Set([
  "maimaiでらっくす", "maimaiでらっくす PLUS",
  "Splash", "Splash PLUS",
  "UNiVERSE", "UNiVERSE PLUS",
  "FESTiVAL", "FESTiVAL PLUS",
  "BUDDiES", "BUDDiES PLUS",
  "PRiSM", "PRiSM PLUS",
  "CiRCLE",
]);

// Ordered list of all maimai versions (oldest → newest) for B50 sorting
const VERSION_ORDER = [
  "maimai", "maimai PLUS", "GreeN", "GreeN PLUS",
  "ORANGE", "ORANGE PLUS", "PiNK", "PiNK PLUS",
  "MURASAKi", "MURASAKi PLUS", "MiLK", "MiLK PLUS", "FiNALE",
  "maimaiでらっくす", "maimaiでらっくす PLUS",
  "Splash", "Splash PLUS",
  "UNiVERSE", "UNiVERSE PLUS",
  "FESTiVAL", "FESTiVAL PLUS",
  "BUDDiES", "BUDDiES PLUS",
  "PRiSM", "PRiSM PLUS",
  "CiRCLE",
];
const VERSION_RANK = {};
VERSION_ORDER.forEach((v, i) => { VERSION_RANK[v] = i; });

function chartTypeFromVersion(versionStr) {
  if (!versionStr) return "";
  return DX_VERSIONS.has(versionStr) ? "DX" : "ST";
}

function getVersionRank(versionStr) {
  return VERSION_RANK[versionStr] ?? -1;
}

// ── Data fetching ────────────────────────────────────────────────────────────

async function fetchChartData() {
  const status = document.getElementById("status");

  try {
    const res = await fetch(DXDATA_URL);
    const data = await res.json();

    for (const song of data.songs || []) {
      const title = normalizeTitle(song.title || "").toLowerCase();
      if (song.category) {
        songCategories[title] = song.category;
      }
      for (const sheet of song.sheets || []) {
        const type = (sheet.type || "").toLowerCase();
        const diff = (sheet.difficulty || "").toLowerCase();
        const key = `${title}|${type}|${diff}`;
        const ilv = sheet.internalLevelValue;
        if (ilv != null) {
          chartConstants[key] = ilv;
        }
        if (sheet.version) {
          songVersions[key] = sheet.version;
        }
      }
    }
    status.textContent = "Chart data loaded. Upload your cache file.";
  } catch (e) {
    console.warn("Failed to fetch chart data:", e);
    status.textContent = "Chart data unavailable (offline?). Upload your cache file — ratings will use display levels.";
  }

  // Try SEGA API for genre data (may fail due to CORS)
  try {
    const res = await fetch(SEGA_URL);
    const data = await res.json();
    for (const entry of data) {
      const title = normalizeTitle(entry.title || "").toLowerCase();
      if (entry.catcode && !songCategories[title]) {
        songCategories[title] = entry.catcode;
      }
    }
  } catch (_) {
    // CORS or network error — genre will use dxdata categories or be empty
  }
}

// ── Cache parsing ────────────────────────────────────────────────────────────

function parseCache(arrayBuffer) {
  const compressed = new Uint8Array(arrayBuffer);
  const raw = pako.inflateRaw(compressed);
  const text = new TextDecoder().decode(raw);
  return JSON.parse(text);
}

// ── Score processing ─────────────────────────────────────────────────────────

function processScores(cache) {
  const scores = [];

  for (const [, meta] of Object.entries(cache.level_metadata || {})) {
    const rawTitle = meta.title || "";
    const { cleanTitle, typeHint } = parseTitle(rawTitle);
    const rawTitleLower = normalizeTitle(rawTitle).toLowerCase();
    const cleanTitleLower = normalizeTitle(cleanTitle).toLowerCase();
    const aliasTitle = songAliases[cleanTitleLower];
    const genre = songCategories[cleanTitleLower] || songCategories[rawTitleLower] || (aliasTitle && songCategories[aliasTitle]) || "";

    for (const diff of meta.difficulties || []) {
      const stats = diff.stats || {};
      const plays = stats.completePlays || 0;
      if (plays === 0) continue;

      const alias = diff.alias || "";
      const value = diff.value || "";
      const acc = stats.achievementRate || 0;
      const ct = stats.clearType || 0;

      const lvMatch = lookupChart(chartConstants, rawTitleLower, cleanTitleLower, alias, typeHint);
      const override = !lvMatch ? lookupOverride(cleanTitleLower, alias, typeHint) : null;
      const internalLv = lvMatch ? lvMatch.value : (override?.ilv ?? parseLevel(value));

      const verMatch = lookupChart(songVersions, rawTitleLower, cleanTitleLower, alias, typeHint);
      const version = verMatch ? verMatch.value : (override?.version ?? "");

      // Determine chart type: from [DX]/[ST] prefix, matched sheet type, or version era
      let chartType = "";
      if (typeHint) {
        chartType = typeHint === "dx" ? "DX" : "ST";
      } else if (lvMatch || override) {
        const mt = (lvMatch || override).matchedType;
        chartType = mt === "dx" ? "DX" : "ST";
      } else if (version) {
        chartType = chartTypeFromVersion(version);
      }

      const baseRating = getRating(internalLv, acc);
      const apBonus = AP_CLEAR_TYPES.has(ct) ? 1 : 0;
      const totalRating = baseRating + apBonus;

      // Rating-if columns
      const ratingIf = {};
      for (const { key, minAchv } of RATING_IF_RANKS) {
        if (acc >= minAchv) {
          ratingIf[key] = null;
        } else {
          const hypothetical = getRating(internalLv, minAchv);
          ratingIf[key] = hypothetical - baseRating;
        }
      }

      scores.push({
        name: cleanTitle,
        chartType,
        version,
        genre,
        playcount: plays,
        difficulty: alias,
        level: internalLv,
        levelFromServer: !!(lvMatch || override?.ilv),
        clear: CLEAR_LABELS[ct] || "",
        accuracy: acc,
        rank: getRankLabel(acc),
        rating: totalRating,
        internalLv,
        ...ratingIf,
      });
    }
  }

  // Deduplicate: same song+difficulty → keep highest rating
  const best = new Map();
  for (const s of scores) {
    const key = `${s.name.toLowerCase()}|${s.chartType}|${s.difficulty}`;
    const existing = best.get(key);
    if (!existing || s.rating > existing.rating) {
      best.set(key, s);
    }
  }

  return Array.from(best.values());
}

// ── Table rendering ──────────────────────────────────────────────────────────

function renderTable() {
  const tbody = document.getElementById("score-body");
  const info = document.getElementById("table-info");

  // Sort
  const col = sortCol;
  filteredScores.sort((a, b) => {
    let va = a[col], vb = b[col];
    if (va == null) va = -Infinity;
    if (vb == null) vb = -Infinity;
    if (typeof va === "string") {
      const cmp = va.localeCompare(vb);
      return sortAsc ? cmp : -cmp;
    }
    return sortAsc ? va - vb : vb - va;
  });

  // Build rows
  const fragment = document.createDocumentFragment();
  filteredScores.forEach((s, i) => {
    const tr = document.createElement("tr");
    tr.className = DIFF_CLASS[s.difficulty] || "";

    const cells = [
      i + 1,
      s.chartType,
      versionName(s.version),
      s.genre,
      s.playcount,
      s.name,
      s.levelFromServer ? s.level.toFixed(1) : s.level.toFixed(0),
      s.clear,
      s.accuracy.toFixed(4) + "%",
      s.rank,
      s.rating,
    ];

    for (const val of cells) {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    }

    // Rating-if columns
    for (const { key } of RATING_IF_RANKS) {
      const td = document.createElement("td");
      const gain = s[key];
      if (gain != null && gain > 0) {
        td.textContent = "+" + gain;
        td.className = "gain";
      }
      tr.appendChild(td);
    }

    fragment.appendChild(tr);
  });

  tbody.innerHTML = "";
  tbody.appendChild(fragment);
  info.textContent = `${filteredScores.length} scores`;
}

function applyFilters() {
  const query = document.getElementById("search").value.toLowerCase();
  const checkedDiffs = new Set(
    Array.from(document.querySelectorAll('#diff-filters input:checked'))
      .map(cb => cb.value)
  );

  filteredScores = allScores.filter(s => {
    if (!checkedDiffs.has(s.difficulty)) return false;
    if (query && !s.name.toLowerCase().includes(query)) return false;
    return true;
  });

  renderTable();
}

// ── Best 50 ─────────────────────────────────────────────────────────────────

function computeBest50() {
  // Collect unique versions present in scores
  const versionSet = new Set();
  for (const s of allScores) {
    if (s.version && getVersionRank(s.version) >= 0) {
      versionSet.add(s.version);
    }
  }

  // Sort versions by rank (newest first)
  const sortedVersions = Array.from(versionSet).sort((a, b) => getVersionRank(b) - getVersionRank(a));

  // Update version list display
  const listEl = document.getElementById("b50-version-list");
  if (listEl) {
    const newVers = sortedVersions.slice(0, b50NewCount);
    const oldVers = sortedVersions.slice(b50NewCount);
    listEl.textContent = `New: ${newVers.map(versionName).join(", ") || "—"}  |  Old: ${oldVers.length} versions`;
  }

  const newVersions = new Set(sortedVersions.slice(0, b50NewCount));

  // Determine max allowed version rank (for ignore-newer feature)
  let maxRank = Infinity;
  if (b50IgnoreNewer && newVersions.size > 0) {
    maxRank = Math.max(...Array.from(newVersions).map(v => getVersionRank(v)));
  }

  // Filter scores that have a known version
  const eligible = allScores.filter(s => {
    const rank = getVersionRank(s.version);
    if (rank < 0) return false;
    if (b50IgnoreNewer && rank > maxRank) return false;
    return true;
  });

  // Split into new/old and sort by rating desc
  const newScores = eligible
    .filter(s => newVersions.has(s.version))
    .sort((a, b) => b.rating - a.rating)
    .slice(0, 15);

  const oldScores = eligible
    .filter(s => !newVersions.has(s.version))
    .sort((a, b) => b.rating - a.rating)
    .slice(0, 35);

  return { newScores, oldScores };
}

function renderB50() {
  const { newScores, oldScores } = computeBest50();

  const newSum = newScores.reduce((s, x) => s + x.rating, 0);
  const oldSum = oldScores.reduce((s, x) => s + x.rating, 0);
  const total = newSum + oldSum;

  document.getElementById("b50-new-sum").textContent = newSum;
  document.getElementById("b50-old-sum").textContent = oldSum;
  document.getElementById("b50-total").innerHTML = `<strong>${total}</strong>`;
  document.getElementById("b50-new-avg").textContent = newScores.length ? (newSum / newScores.length).toFixed(1) : "0";
  document.getElementById("b50-old-avg").textContent = oldScores.length ? (oldSum / oldScores.length).toFixed(1) : "0";
  const totalCount = newScores.length + oldScores.length;
  document.getElementById("b50-total-avg").textContent = totalCount ? (total / totalCount).toFixed(1) : "0";

  // Build row list — separate (NEW block then OLD block) or combined (single sorted list)
  let rows;
  if (b50Combined) {
    const all = [
      ...newScores.map(s => ({ ...s, pool: "NEW" })),
      ...oldScores.map(s => ({ ...s, pool: "OLD" })),
    ].sort((a, b) => b.rating - a.rating);
    rows = all.map((s, i) => ({ ...s, idx: i + 1 }));
  } else {
    rows = [
      ...newScores.map((s, i) => ({ ...s, pool: "NEW", idx: i + 1 })),
      ...oldScores.map((s, i) => ({ ...s, pool: "OLD", idx: i + 1 })),
    ];
  }

  const tbody = document.getElementById("b50-body");
  const fragment = document.createDocumentFragment();

  for (const s of rows) {
    const tr = document.createElement("tr");
    tr.className = DIFF_CLASS[s.difficulty] || "";

    // # column
    const tdIdx = document.createElement("td");
    tdIdx.textContent = s.idx;
    tr.appendChild(tdIdx);

    // Pool column
    const tdPool = document.createElement("td");
    tdPool.textContent = s.pool;
    tdPool.className = s.pool === "NEW" ? "pool-new" : "pool-old";
    tr.appendChild(tdPool);

    // Rest of columns (same as all-scores)
    const cells = [
      s.chartType,
      versionName(s.version),
      s.genre,
      s.playcount,
      s.name,
      s.levelFromServer ? s.level.toFixed(1) : s.level.toFixed(0),
      s.clear,
      s.accuracy.toFixed(4) + "%",
      s.rank,
      s.rating,
    ];

    for (const val of cells) {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    }

    // Rating-if columns
    for (const { key } of RATING_IF_RANKS) {
      const td = document.createElement("td");
      const gain = s[key];
      if (gain != null && gain > 0) {
        td.textContent = "+" + gain;
        td.className = "gain";
      }
      tr.appendChild(td);
    }

    fragment.appendChild(tr);
  }

  tbody.innerHTML = "";
  tbody.appendChild(fragment);
}

async function exportB50Image() {
  const btn = document.getElementById("b50-export");
  const capture = document.getElementById("b50-capture");

  btn.disabled = true;
  btn.textContent = "Exporting...";

  // Temporarily add exporting class for background/padding
  capture.classList.add("exporting");

  try {
    const canvas = await html2canvas(capture, {
      backgroundColor: "#1a1a2e",
      scale: 2,
    });

    const link = document.createElement("a");
    link.download = "best50.png";
    link.href = canvas.toDataURL("image/png");
    link.click();
  } catch (err) {
    console.error("Export failed:", err);
    alert("Export failed. Check console for details.");
  } finally {
    capture.classList.remove("exporting");
    btn.disabled = false;
    btn.textContent = "Export as Image";
  }
}

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll(".tab").forEach(t => {
    t.classList.toggle("active", t.dataset.tab === tab);
  });
  document.getElementById("tab-all").classList.toggle("hidden", tab !== "all");
  document.getElementById("tab-b50").classList.toggle("hidden", tab !== "b50");

  if (tab === "b50" && allScores.length > 0) {
    renderB50();
  }
}

// ── Event setup ──────────────────────────────────────────────────────────────

function setupEvents() {
  // File upload
  const fileInput = document.getElementById("file-input");
  const uploadArea = document.getElementById("upload-area");

  fileInput.addEventListener("change", (e) => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
  });

  // Drag and drop
  uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = "#7c5cbf";
  });
  uploadArea.addEventListener("dragleave", () => {
    uploadArea.style.borderColor = "";
  });
  uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = "";
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });

  // Search
  document.getElementById("search").addEventListener("input", applyFilters);

  // Difficulty filters
  document.querySelectorAll("#diff-filters input").forEach(cb => {
    cb.addEventListener("change", applyFilters);
  });

  // Tabs
  document.querySelectorAll(".tab").forEach(t => {
    t.addEventListener("click", () => switchTab(t.dataset.tab));
  });

  // B50 settings
  document.getElementById("b50-new-count").addEventListener("change", (e) => {
    b50NewCount = parseInt(e.target.value, 10);
    if (allScores.length > 0) renderB50();
  });

  document.getElementById("b50-ignore-newer").addEventListener("change", (e) => {
    b50IgnoreNewer = e.target.checked;
    if (allScores.length > 0) renderB50();
  });

  document.getElementById("b50-display-mode").addEventListener("change", (e) => {
    b50Combined = e.target.value === "combined";
    if (allScores.length > 0) renderB50();
  });

  // B50 export
  document.getElementById("b50-export").addEventListener("click", exportB50Image);

  // Column sort
  document.querySelectorAll("#score-table th[data-col]").forEach(th => {
    th.addEventListener("click", () => {
      const col = th.dataset.col;
      if (col === "#") return;

      if (sortCol === col) {
        sortAsc = !sortAsc;
      } else {
        sortCol = col;
        sortAsc = col === "name" || col === "chartType" || col === "version" || col === "genre";
      }

      // Update header classes
      document.querySelectorAll("#score-table th").forEach(h => {
        h.classList.remove("sorted", "asc", "desc");
      });
      th.classList.add("sorted", sortAsc ? "asc" : "desc");

      renderTable();
    });
  });
}

function handleFile(file) {
  const status = document.getElementById("status");
  status.textContent = "Parsing cache...";

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const cache = parseCache(e.target.result);
      allScores = processScores(cache);
      filteredScores = [...allScores];

      document.getElementById("upload-section").classList.add("hidden");
      document.getElementById("tab-bar").classList.remove("hidden");
      document.getElementById("controls").classList.remove("hidden");
      document.getElementById("table-section").classList.remove("hidden");
      document.getElementById("b50-ignore-label").classList.remove("hidden");

      // Default sort: rating descending
      sortCol = "rating";
      sortAsc = false;
      renderTable();

      status.textContent = `Loaded ${allScores.length} scores.`;
    } catch (err) {
      console.error(err);
      status.textContent = "Error: could not parse cache file. Make sure it's a valid AstroDX cache.";
    }
  };
  reader.readAsArrayBuffer(file);
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  setupEvents();
  await fetchChartData();
}

init();
