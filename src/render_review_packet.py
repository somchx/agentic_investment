"""Embeds data/review_sample.json into a standalone HTML review packet for
publishing as an Artifact. Free, no LLM calls -- just templating.

Usage:
    python3 render_review_packet.py
"""

import json

IN_PATH = "../data/review_sample.json"
OUT_PATH = "../data/review_packet.html"

TEMPLATE = """<title>Filing Verification Sample</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #EEF1EF;
  --surface: #FFFFFF;
  --surface-2: #F5F7F5;
  --ink: #1B2430;
  --ink-soft: #55606B;
  --ink-faint: #8891998C;
  --border: #DCE1DD;
  --accent: #2F6F62;
  --accent-soft: #E4EEEA;
  --mono-bg: #F3F6F3;
  --status-supported: #2F8F5B;
  --status-supported-bg: #E4F3EA;
  --status-weakened: #A5761E;
  --status-weakened-bg: #F6EDDC;
  --status-broken: #B23A2E;
  --status-broken-bg: #F7E4E1;
  --status-missing: #5D6773;
  --status-missing-bg: #E7E9EB;
  --status-structural: #524CA3;
  --status-structural-bg: #E9E7F5;
  --shadow: 0 1px 2px rgba(27,36,48,0.04), 0 4px 14px rgba(27,36,48,0.06);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12161A;
    --surface: #181E24;
    --surface-2: #1E252B;
    --ink: #E7EAEA;
    --ink-soft: #A6ADB4;
    --ink-faint: #6B747C;
    --border: #2A323A;
    --accent: #5CB09C;
    --accent-soft: #1E2E2A;
    --mono-bg: #14191E;
    --status-supported: #4CAF7D;
    --status-supported-bg: #1B2E24;
    --status-weakened: #D6A544;
    --status-weakened-bg: #332A18;
    --status-broken: #E0756B;
    --status-broken-bg: #33201E;
    --status-missing: #99A2AB;
    --status-missing-bg: #23282D;
    --status-structural: #9C98DE;
    --status-structural-bg: #24213A;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 4px 14px rgba(0,0,0,0.35);
  }
}
:root[data-theme="dark"] {
  --bg: #12161A;
  --surface: #181E24;
  --surface-2: #1E252B;
  --ink: #E7EAEA;
  --ink-soft: #A6ADB4;
  --ink-faint: #6B747C;
  --border: #2A323A;
  --accent: #5CB09C;
  --accent-soft: #1E2E2A;
  --mono-bg: #14191E;
  --status-supported: #4CAF7D;
  --status-supported-bg: #1B2E24;
  --status-weakened: #D6A544;
  --status-weakened-bg: #332A18;
  --status-broken: #E0756B;
  --status-broken-bg: #33201E;
  --status-missing: #99A2AB;
  --status-missing-bg: #23282D;
  --status-structural: #9C98DE;
  --status-structural-bg: #24213A;
  --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 4px 14px rgba(0,0,0,0.35);
}

* { box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--ink);
  font-family: "IBM Plex Sans", -apple-system, sans-serif;
  margin: 0;
  line-height: 1.55;
}
.wrap { display: flex; max-width: 1180px; margin: 0 auto; }

nav {
  width: 240px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  align-self: flex-start;
  height: 100vh;
  overflow-y: auto;
  padding: 32px 18px 32px 28px;
  border-right: 1px solid var(--border);
}
nav .progress {
  font-family: "IBM Plex Mono", monospace;
  font-size: 13px;
  color: var(--ink-soft);
  margin-bottom: 18px;
  font-variant-numeric: tabular-nums;
}
nav .progress-bar {
  height: 4px;
  background: var(--surface-2);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 6px;
}
nav .progress-fill {
  height: 100%;
  background: var(--accent);
  width: 0%;
  transition: width 0.3s ease;
}
nav a {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--ink-soft);
  text-decoration: none;
  font-size: 13.5px;
  padding: 6px 0;
  border-bottom: 1px solid transparent;
}
nav a:hover { color: var(--ink); }
nav a span.count {
  font-family: "IBM Plex Mono", monospace;
  color: var(--ink-faint);
  font-size: 12px;
}

main { flex: 1; min-width: 0; padding: 48px 40px 80px; }

header.masthead { margin-bottom: 40px; max-width: 640px; }
header.masthead .eyebrow {
  font-family: "IBM Plex Mono", monospace;
  font-size: 12.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}
header.masthead h1 {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 34px;
  font-weight: 600;
  margin: 0 0 14px;
  text-wrap: balance;
}
header.masthead p {
  color: var(--ink-soft);
  font-size: 15px;
  margin: 0 0 8px;
}
header.masthead .method {
  margin-top: 20px;
  padding: 14px 16px;
  background: var(--surface-2);
  border-radius: 8px;
  border: 1px solid var(--border);
  font-size: 13.5px;
  color: var(--ink-soft);
}
header.masthead .method b { color: var(--ink); }

section.category { margin-bottom: 44px; scroll-margin-top: 24px; }
section.category h2 {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 21px;
  font-weight: 600;
  margin: 0 0 4px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
section.category h2 .n {
  font-family: "IBM Plex Mono", monospace;
  font-size: 13px;
  font-weight: 400;
  color: var(--ink-faint);
}
section.category .cat-desc {
  font-size: 13.5px;
  color: var(--ink-soft);
  margin: 0 0 18px;
  max-width: 62ch;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--stripe, var(--accent));
  border-radius: 10px;
  padding: 20px 22px;
  margin-bottom: 14px;
  box-shadow: var(--shadow);
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}
.card h3 {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 17px;
  font-weight: 600;
  margin: 0 0 2px;
}
.card .claim {
  font-size: 13.5px;
  color: var(--ink-soft);
  margin: 0 0 10px;
}
.pill {
  display: inline-block;
  font-family: "IBM Plex Mono", monospace;
  font-size: 11.5px;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  padding: 3px 9px;
  border-radius: 999px;
  white-space: nowrap;
  background: var(--pill-bg, var(--accent-soft));
  color: var(--pill-fg, var(--accent));
}
.stats {
  display: flex;
  gap: 22px;
  flex-wrap: wrap;
  font-size: 13.5px;
  margin: 12px 0;
  font-variant-numeric: tabular-nums;
}
.stats .stat b {
  display: block;
  font-family: "IBM Plex Mono", monospace;
  font-size: 14px;
  color: var(--ink);
}
.stats .stat span { color: var(--ink-faint); font-size: 12px; }

blockquote {
  font-family: "IBM Plex Mono", monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--ink-soft);
  background: var(--mono-bg);
  border-left: 3px solid var(--border);
  margin: 12px 0;
  padding: 10px 14px;
  border-radius: 0 6px 6px 0;
  overflow-x: auto;
  white-space: pre-wrap;
}
.note-text {
  font-size: 13.5px;
  color: var(--ink-soft);
  margin: 10px 0;
}
.note-text b { color: var(--ink); }

.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
  flex-wrap: wrap;
}
.filing-link {
  color: var(--accent);
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.filing-link:hover { text-decoration: underline; }

.review {
  display: flex;
  align-items: center;
  gap: 10px;
}
.review label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-soft);
  cursor: pointer;
}
.review input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
  cursor: pointer;
}
.review input[type="text"] {
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 13px;
  padding: 5px 9px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--ink);
  width: 220px;
}
.review input[type="text"]:focus, .review input[type="checkbox"]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.card.is-reviewed { opacity: 0.62; }

@media (max-width: 860px) {
  .wrap { flex-direction: column; }
  nav { position: static; height: auto; width: auto; border-right: none; border-bottom: 1px solid var(--border); }
  main { padding: 32px 20px 60px; }
}
</style>

<div class="wrap">
  <nav>
    <div class="progress">
      <span id="progress-label">0 / 0 reviewed</span>
      <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
    </div>
    <div id="nav-links"></div>
  </nav>
  <main>
    <header class="masthead">
      <div class="eyebrow">Financial Reason-Tracking Prototype &middot; Verification Sample</div>
      <h1>Filing Verification Sample</h1>
      <p>30 cases pulled from the pipeline's own extraction, stratified across every status
      and failure mode it produces. Each case links to the actual SEC filing &mdash;
      open it and check the claim yourself.</p>
      <div class="method"><b>What this is:</b> every quoted excerpt and value below came from
      an AI-assisted pass (Claude reading primary filing text and citing itself) &mdash;
      not independent human labeling. Checking the box only records that <i>you</i> looked
      at the filing and agree; it's stored in this browser only.</div>
    </header>
    <div id="categories"></div>
  </main>
</div>

<script id="review-data" type="application/json">__DATA__</script>
<script>
const data = JSON.parse(document.getElementById('review-data').textContent);

const CATEGORY_META = {
  "Supported":      { stripe: "var(--status-supported)",  pillBg: "var(--status-supported-bg)",  pillFg: "var(--status-supported)",
                       desc: "Reason currently passes its threshold." },
  "Weakened":       { stripe: "var(--status-weakened)",   pillBg: "var(--status-weakened-bg)",   pillFg: "var(--status-weakened)",
                       desc: "Missed the threshold but within the 50%-of-threshold buffer." },
  "Broken":         { stripe: "var(--status-broken)",      pillBg: "var(--status-broken-bg)",     pillFg: "var(--status-broken)",
                       desc: "Missed the threshold by more than the buffer allows." },
  "Missing / Not enough data": { stripe: "var(--status-missing)", pillBg: "var(--status-missing-bg)", pillFg: "var(--status-missing)",
                       desc: "No usable evidence for this metric -- confirms the pipeline abstains rather than guessing." },
  "Needs human eyes (automated citation search failed)": { stripe: "var(--status-broken)", pillBg: "var(--status-broken-bg)", pillFg: "var(--status-broken)",
                       desc: "The automated check couldn't confirm its own number in the primary filing text -- these need a human look most." },
  "Restatement":    { stripe: "var(--status-structural)", pillBg: "var(--status-structural-bg)", pillFg: "var(--status-structural)",
                       desc: "The same period's figure was reported differently across filings over time." },
  "Tag/definition conflict (not a restatement)": { stripe: "var(--status-structural)", pillBg: "var(--status-structural-bg)", pillFg: "var(--status-structural)",
                       desc: "Two different accounting concepts, not two versions of the same number." },
  "Real anomaly (financing event, not a data problem)": { stripe: "var(--status-structural)", pillBg: "var(--status-structural-bg)", pillFg: "var(--status-structural)",
                       desc: "A large, real change in the underlying business, confirmed by reading the filing." },
  "Data artifact (filer's own XBRL tagging error)": { stripe: "var(--status-structural)", pillBg: "var(--status-structural-bg)", pillFg: "var(--status-structural)",
                       desc: "The filer's own XBRL tagging is internally inconsistent." },
};

const REASON_LABEL = {
  revenue_growth: "Revenue growth must exceed 10% YoY",
  operating_margin: "Operating margin must stay at or above 20%",
  debt_growth: "Long-term debt must not grow more than 15% YoY",
};

function caseId(r, i) {
  return (r.ticker || "case") + "-" + (r.reason_key || i) + "-" + i;
}

function fmtNum(n) {
  return Math.round(n).toLocaleString("en-US");
}

const byCategory = {};
data.forEach((r, i) => {
  const cat = r.review_category;
  (byCategory[cat] = byCategory[cat] || []).push({ ...r, _id: caseId(r, i) });
});

const navEl = document.getElementById('nav-links');
const catsEl = document.getElementById('categories');
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

Object.entries(byCategory).forEach(([cat, entries]) => {
  const meta = CATEGORY_META[cat] || {};
  const id = slug(cat);

  const a = document.createElement('a');
  a.href = '#' + id;
  a.innerHTML = `<span>${cat}</span><span class="count">${entries.length}</span>`;
  navEl.appendChild(a);

  const section = document.createElement('section');
  section.className = 'category';
  section.id = id;
  section.innerHTML = `<h2>${cat} <span class="n">${entries.length}</span></h2>
    <p class="cat-desc">${meta.desc || ''}</p>`;

  entries.forEach(r => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.setProperty('--stripe', meta.stripe || 'var(--accent)');
    card.dataset.id = r._id;

    const title = r.reason_key ? `${r.ticker} &mdash; ${REASON_LABEL[r.reason_key] || r.reason_key}` : r.ticker;
    const claim = r.description ? `<p class="claim">${r.description}</p>` : '';

    let stats = '';
    if (r.xbrl_pipeline_value != null || r.live_status) {
      stats = '<div class="stats">';
      if (r.live_status) stats += `<div class="stat"><span>Pipeline status</span><b>${r.live_status}</b></div>`;
      if (r.xbrl_pipeline_value != null) stats += `<div class="stat"><span>Pipeline value</span><b>$${fmtNum(r.xbrl_pipeline_value)}</b></div>`;
      if (r.live_computed_value != null) stats += `<div class="stat"><span>Computed</span><b>${(r.live_computed_value*100).toFixed(1)}%</b></div>`;
      stats += '</div>';
    }

    const quote = r.quoted_text ? `<blockquote>&ldquo;${r.quoted_text}&rdquo;</blockquote>` : '';
    const note = r.note ? `<p class="note-text"><b>Note:</b> ${r.note}</p>` : '';
    const diagnosis = r.diagnosis ? `<p class="note-text"><b>Why the automated check failed:</b> ${r.diagnosis}</p>` : '';

    const filingLabel = r.filing_form && r.accession_number ? `${r.filing_form} &middot; ${r.accession_number}` : 'View filing';
    const link = r.filing_url ? `<a class="filing-link" href="${r.filing_url}" target="_blank" rel="noopener">Open filing &rarr; <span style="color:var(--ink-faint); font-weight:400; font-family:'IBM Plex Mono',monospace; font-size:12px;">${filingLabel}</span></a>` : '<span></span>';

    card.innerHTML = `
      <div class="card-top">
        <div><h3>${title}</h3>${claim}</div>
        <span class="pill" style="--pill-bg:${meta.pillBg}; --pill-fg:${meta.pillFg};">${cat.split('(')[0].trim()}</span>
      </div>
      ${stats}
      ${quote}
      ${note}
      ${diagnosis}
      <div class="card-foot">
        ${link}
        <div class="review">
          <label><input type="checkbox" class="reviewed-box"> Reviewed</label>
          <input type="text" class="notes-input" placeholder="Notes (saved locally)">
        </div>
      </div>
    `;
    section.appendChild(card);
  });

  catsEl.appendChild(section);
});

// Per-viewer local persistence only -- never assumed to be the record.
function storageKey(id, field) { return 'review:' + id + ':' + field; }

function loadState() {
  document.querySelectorAll('.card').forEach(card => {
    const id = card.dataset.id;
    let checked = false, notes = '';
    try {
      checked = localStorage.getItem(storageKey(id, 'reviewed')) === '1';
      notes = localStorage.getItem(storageKey(id, 'notes')) || '';
    } catch (e) { /* private mode / blocked storage -- just render unreviewed */ }
    const box = card.querySelector('.reviewed-box');
    const input = card.querySelector('.notes-input');
    box.checked = checked;
    input.value = notes;
    card.classList.toggle('is-reviewed', checked);
  });
  updateProgress();
}

function updateProgress() {
  const boxes = document.querySelectorAll('.reviewed-box');
  const done = document.querySelectorAll('.reviewed-box:checked').length;
  document.getElementById('progress-label').textContent = `${done} / ${boxes.length} reviewed`;
  document.getElementById('progress-fill').style.width = boxes.length ? (100 * done / boxes.length) + '%' : '0%';
}

document.addEventListener('change', e => {
  if (e.target.classList.contains('reviewed-box')) {
    const card = e.target.closest('.card');
    card.classList.toggle('is-reviewed', e.target.checked);
    try { localStorage.setItem(storageKey(card.dataset.id, 'reviewed'), e.target.checked ? '1' : '0'); } catch (err) {}
    updateProgress();
  }
});
document.addEventListener('input', e => {
  if (e.target.classList.contains('notes-input')) {
    const card = e.target.closest('.card');
    try { localStorage.setItem(storageKey(card.dataset.id, 'notes'), e.target.value); } catch (err) {}
  }
});

loadState();
</script>
"""


def run() -> None:
    with open(IN_PATH) as f:
        sample = json.load(f)
    html = TEMPLATE.replace("__DATA__", json.dumps(sample))
    with open(OUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH} ({len(sample)} cases embedded)")


if __name__ == "__main__":
    run()
