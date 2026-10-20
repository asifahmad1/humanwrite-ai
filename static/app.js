/* HumanWrite AI v1 — vanilla-JS single-page app.
   All data comes from the real backend API. Nothing is hard-coded. */
"use strict";

/* ---------- helpers ---------- */
const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

async function api(path, opts) {
  opts = opts || {};
  const cfg = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) {
    cfg.headers["Content-Type"] = "application/json";
    cfg.body = JSON.stringify(opts.body);
  }
  if (opts.form) cfg.body = opts.form; // FormData for uploads
  let res;
  try {
    res = await fetch(path, cfg);
  } catch (e) {
    throw new Error("Could not reach the HumanWrite AI app. Make sure it is running at http://127.0.0.1:4322 and try again.");
  }
  const ct = res.headers.get("content-type") || "";
  let data = null;
  if (ct.indexOf("application/json") >= 0) {
    try { data = await res.json(); } catch (e) { data = null; }
  }
  if (!res.ok) {
    const msg = (data && data.error) ? data.error
      : ("Request failed (status " + res.status + ").");
    throw new Error(msg);
  }
  return data;
}

function toast(msg, isError) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.className = "toast"; }, 4200);
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleString();
  } catch (e) { return String(iso); }
}

/* ---------- state ---------- */
const state = {
  view: "dashboard",
  docId: localStorage.getItem("hw-doc-id") || null,
  doc: null,
  docs: [],
  analysis: null,
  modes: null,
  intensities: null,
  providers: null,
  roadmap: null,
  modeId: "natural",
  intensity: 3,
  providerKind: "offline",
  rejectedIds: new Set(),
  acceptedIds: new Set(),
  openSentence: -1,
};

const DEMO_TITLE = "Demo document";
const DEMO_TEXT = "Artificial intelligence has significantly revolutionized the educational landscape, providing numerous innovative opportunities for enhancing teaching methodologies and facilitating effective learning experiences.";

/* ---------- theme ---------- */
function initTheme() {
  const saved = localStorage.getItem("hw-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  updateThemeBtn();
  $("#theme-toggle").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("hw-theme", next);
    updateThemeBtn();
  });
}
function updateThemeBtn() {
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  $("#theme-toggle").textContent = dark ? "☀️ Light" : "🌙 Dark";
}

/* ---------- navigation ---------- */
const NEEDS_DOC = ["editor", "analyze", "humanize", "compare", "quality", "export", "history"];

function initNav() {
  $$(".tab").forEach(btn => {
    btn.addEventListener("click", () => showView(btn.dataset.view));
  });
}

async function showView(name) {
  state.view = name;
  $$(".tab").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  $("#view").innerHTML = '<div class="card"><span class="spinner"></span>Loading…</div>';
  try {
    if (NEEDS_DOC.indexOf(name) >= 0 && !state.docId) {
      renderNoDoc();
      return;
    }
    if (NEEDS_DOC.indexOf(name) >= 0) {
      state.doc = await api("/api/documents/" + encodeURIComponent(state.docId));
    }
    const fn = VIEWS[name];
    if (fn) await fn();
  } catch (e) {
    if (String(e.message).indexOf("Document not found") >= 0) {
      state.docId = null; localStorage.removeItem("hw-doc-id");
      renderNoDoc();
      return;
    }
    $("#view").innerHTML = '<div class="card"><div class="banner banner-error">' + esc(e.message) + '</div>'
      + '<div class="btn-row"><button class="btn btn-secondary" data-act="retry">Try again</button></div></div>';
    const r = $('[data-act="retry"]');
    if (r) r.addEventListener("click", () => showView(name));
  }
  window.scrollTo(0, 0);
}

function renderNoDoc() {
  $("#view").innerHTML =
    '<div class="notice"><h2>No document selected</h2>' +
    '<p>Choose an existing document on the Dashboard, or create a new one to get started.</p>' +
    '<div class="btn-row" style="justify-content:center"><button class="btn btn-primary" id="goto-dash">Go to Dashboard</button></div></div>';
  $("#goto-dash").addEventListener("click", () => showView("dashboard"));
}

function docHeader(doc) {
  return '<p class="view-sub">Working on: <strong>' + esc(doc.title) + '</strong> · ' +
    esc(String(doc.word_count)) + ' words</p>';
}

/* ================= Dashboard ================= */
async function viewDashboard() {
  state.docs = await api("/api/documents");
  const v = $("#view");
  let rows;
  if (!state.docs.length) {
    rows = '<div class="notice"><h2>Welcome to HumanWrite AI</h2>' +
      '<p>You don\'t have any documents yet. Create one below, or try the demo with one click.</p></div>';
  } else {
    rows = '<div class="doc-list">' + state.docs.map(d =>
      '<div class="card doc-card">' +
        '<p class="doc-title">' + esc(d.title) + '</p>' +
        '<p class="doc-meta">' + esc(String(d.word_count)) + ' words · updated ' + esc(fmtDate(d.updated)) + '</p>' +
        '<div class="btn-row">' +
          '<button class="btn btn-primary btn-sm" data-open="' + esc(d.id) + '">Open</button>' +
          '<button class="btn btn-danger btn-sm" data-del="' + esc(d.id) + '">Delete</button>' +
        '</div>' +
      '</div>').join("") + '</div>';
  }
  v.innerHTML =
    '<h2>Your documents</h2>' +
    '<p class="view-sub">Everything is stored on your own computer — nothing is uploaded anywhere.</p>' +
    '<div class="btn-row">' +
      '<button class="btn btn-primary" id="new-doc">+ New document</button>' +
      '<button class="btn btn-secondary" id="demo-doc">✨ Try the demo</button>' +
    '</div>' +
    rows;

  $("#new-doc").addEventListener("click", async () => {
    const title = prompt("Name your new document:", "Untitled document");
    if (title === null) return;
    try {
      const d = await api("/api/documents", { method: "POST", body: { title: title.trim() || "Untitled document" } });
      state.docId = d.id; localStorage.setItem("hw-doc-id", d.id);
      toast("Document created.");
      showView("editor");
    } catch (e) { toast(e.message, true); }
  });

  $("#demo-doc").addEventListener("click", async () => {
    try {
      const d = await api("/api/documents", { method: "POST", body: { title: DEMO_TITLE } });
      await api("/api/documents/" + encodeURIComponent(d.id), { method: "PUT", body: { text: DEMO_TEXT } });
      state.docId = d.id; localStorage.setItem("hw-doc-id", d.id);
      state.analysis = null; state.rejectedIds = new Set(); state.acceptedIds = new Set();
      toast("Demo document created — try Analyze or Humanize.");
      showView("editor");
    } catch (e) { toast(e.message, true); }
  });

  $$("[data-open]", v).forEach(b => b.addEventListener("click", () => {
    state.docId = b.dataset.open; localStorage.setItem("hw-doc-id", state.docId);
    state.analysis = null; state.rejectedIds = new Set(); state.acceptedIds = new Set();
    showView("editor");
  }));

  $$("[data-del]", v).forEach(b => b.addEventListener("click", async () => {
    const id = b.dataset.del;
    const doc = state.docs.find(d => d.id === id);
    if (!confirm('Delete "' + (doc ? doc.title : "this document") + '"? This cannot be undone.')) return;
    try {
      await api("/api/documents/" + encodeURIComponent(id), { method: "DELETE" });
      if (state.docId === id) { state.docId = null; localStorage.removeItem("hw-doc-id"); }
      toast("Document deleted.");
      viewDashboard();
    } catch (e) { toast(e.message, true); }
  }));
}

/* ================= Editor ================= */
let autosaveTimer = null;
async function viewEditor() {
  const doc = state.doc;
  const v = $("#view");
  v.innerHTML =
    '<h2>Editor</h2>' + docHeader(doc) +
    '<div class="card">' +
      '<label class="field-label" for="doc-title">Document title</label>' +
      '<input type="text" id="doc-title" value="' + esc(doc.title) + '" maxlength="120">' +
      '<label class="field-label" for="doc-text">Your text</label>' +
      '<textarea id="doc-text" class="editor" placeholder="Paste or type your text here…">' + esc(doc.text || "") + '</textarea>' +
      '<div class="btn-row" style="align-items:center;justify-content:space-between">' +
        '<span class="hint" id="counters"></span>' +
        '<span class="saved-indicator" id="save-ind">Saved ✓</span>' +
      '</div>' +
    '</div>' +
    '<div class="card">' +
      '<h3>Upload a file</h3>' +
      '<p class="hint">Import text from a TXT, DOCX or PDF file on your computer. ' +
      'If your document already has text, a backup copy is kept in History first.</p>' +
      '<div class="btn-row">' +
        '<input type="file" id="upload-file" accept=".txt,.docx,.pdf" style="width:auto">' +
        '<button class="btn btn-secondary" id="upload-btn">Upload</button>' +
      '</div>' +
      '<div id="upload-result"></div>' +
    '</div>';

  const titleEl = $("#doc-title"), textEl = $("#doc-text");
  const counters = $("#counters"), saveInd = $("#save-ind");

  function wordCount(t) {
    const m = String(t || "").trim().match(/\S+/g);
    return m ? m.length : 0;
  }
  function updateCounters() {
    counters.textContent = wordCount(textEl.value) + " words · " + textEl.value.length + " characters";
  }
  updateCounters();

  function scheduleSave() {
    updateCounters();
    saveInd.classList.remove("saved");
    saveInd.textContent = "Saving…";
    clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(async () => {
      try {
        state.doc = await api("/api/documents/" + encodeURIComponent(state.docId), {
          method: "PUT", body: { title: titleEl.value, text: textEl.value }
        });
        state.analysis = null; // text changed → analysis is stale
        saveInd.classList.add("saved");
        saveInd.textContent = "Saved ✓";
      } catch (e) {
        saveInd.textContent = "Could not save: " + e.message;
      }
    }, 1500);
  }
  textEl.addEventListener("input", scheduleSave);
  titleEl.addEventListener("input", scheduleSave);

  $("#upload-btn").addEventListener("click", async () => {
    const f = $("#upload-file").files[0];
    if (!f) { toast("Choose a file first.", true); return; }
    const out = $("#upload-result");
    out.innerHTML = '<span class="spinner"></span>Reading your file…';
    try {
      const form = new FormData();
      form.append("file", f, f.name);
      const res = await api("/api/documents/" + encodeURIComponent(state.docId) + "/upload",
        { method: "POST", form });
      state.doc = res.document;
      state.analysis = null;
      textEl.value = state.doc.text || "";
      updateCounters();
      saveInd.classList.add("saved");
      saveInd.textContent = "Saved ✓";
      out.innerHTML = '<div class="banner banner-ok">Imported <strong>' + esc(res.filename) + '</strong> — ' +
        esc(String(res.word_count)) + ' words. The document is updated below.</div>';
      toast("File imported: " + res.filename);
    } catch (e) {
      out.innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
    }
  });
}

/* ================= Analyze ================= */
async function viewAnalyze() {
  const doc = state.doc;
  const v = $("#view");
  const text = (doc.text || "").trim();
  v.innerHTML = '<h2>Analyze</h2>' + docHeader(doc) +
    '<div class="banner banner-honesty">This is a <strong>stylistic assessment</strong>: it points out writing patterns that often appear in machine-generated text. ' +
    'It does <strong>not</strong> determine who or what wrote your text.</div>' +
    '<div class="btn-row"><button class="btn btn-primary" id="analyze-btn">🔍 Analyze text</button></div>' +
    '<div id="analysis-out"></div>';

  $("#analyze-btn").addEventListener("click", async () => runAnalysis(true));
  if (!text) {
    $("#analysis-out").innerHTML = '<div class="notice"><p>There is no text to analyze yet. Add some text in the Editor first.</p></div>';
    return;
  }
  if (state.analysis) renderAnalysis(state.analysis);
}

async function runAnalysis(manual) {
  const out = $("#analysis-out");
  out.innerHTML = '<div class="card"><span class="spinner"></span>Analyzing your text…</div>';
  try {
    const res = await api("/api/documents/" + encodeURIComponent(state.docId) + "/analyze", { method: "POST" });
    state.analysis = res;
    renderAnalysis(res);
    if (manual) toast("Analysis complete.");
  } catch (e) {
    out.innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
  }
}

function sentenceClass(s) {
  let hasMH = false, hasLow = false;
  (s.flags || []).forEach(f => {
    if (f.strength === "high" || f.strength === "medium") hasMH = true;
    else hasLow = true;
  });
  if (hasMH) return "flagged-amber";
  if (hasLow) return "flagged-low";
  return "";
}

function renderAnalysis(res) {
  const out = $("#analysis-out");
  const m = res.metrics || {};
  const sentencesHtml = (res.sentences || []).map((s, i) =>
    '<span class="sentence ' + sentenceClass(s) + '" data-si="' + i + '" title="Click to see the observations for this sentence">' +
      esc(s.text) + '</span>').join(" ");
  const chips =
    '<div class="chips">' +
    '<span class="chip">' + esc(String(m.word_count || 0)) + ' words</span>' +
    '<span class="chip">' + esc(String(m.sentence_count || 0)) + ' sentences</span>' +
    '<span class="chip">Avg. sentence: ' + esc(String(m.avg_sentence_length || 0)) + ' words</span>' +
    '<span class="chip">' + esc(String(m.total_flags || 0)) + ' observations</span>' +
    '</div>';
  const docNotes = (res.doc_notes || []).map(n =>
    '<li><strong>' + esc(n.label) + '</strong> <span class="strength-badge strength-' + esc(n.strength) + '">' + esc(n.strength) + '</span><br>' +
    '<span class="hint">' + esc(n.detail) + '</span></li>').join("");

  out.innerHTML =
    '<div class="banner banner-honesty"><strong>Important:</strong> ' + esc(res.disclaimer || "") + '</div>' +
    '<div class="card"><h3>Sentence-by-sentence observations</h3>' +
      '<p class="hint">Sentences with a yellow background show stronger patterns. ' +
      'Underlined sentences show milder ones. Click any sentence for details.</p>' +
      '<div id="sent-list" style="font-size:15px;line-height:2">' + sentencesHtml + '</div>' +
      '<div id="flag-panel"></div>' +
    '</div>' +
    '<div class="card"><h3>Whole-document observations</h3>' +
      (docNotes ? '<ul class="note-list">' + docNotes + '</ul>' : '<p class="hint">No whole-document observations.</p>') +
    '</div>' +
    '<div class="card"><h3>Summary</h3>' + chips + '</div>';

  $$("#sent-list .sentence", out).forEach(el => {
    el.addEventListener("click", () => {
      const i = parseInt(el.dataset.si, 10);
      state.openSentence = (state.openSentence === i) ? -1 : i;
      renderFlagPanel(out, res);
    });
  });
}

function renderFlagPanel(out, res) {
  const panel = $("#flag-panel", out);
  $$("#sent-list .sentence", out).forEach(el => el.classList.remove("selected-sent"));
  if (state.openSentence < 0 || !res.sentences[state.openSentence]) { panel.innerHTML = ""; return; }
  const s = res.sentences[state.openSentence];
  const el = $('#sent-list .sentence[data-si="' + state.openSentence + '"]', out);
  if (el) el.classList.add("selected-sent");
  const flags = (s.flags || []).map(f =>
    '<div class="flag-item"><strong>' + esc(f.label) + '</strong>' +
    '<span class="strength-badge strength-' + esc(f.strength) + '">' + esc(f.strength) + '</span><br>' +
    '<span class="hint">' + esc(f.detail) + '</span></div>').join("");
  panel.innerHTML = '<div class="flag-panel"><h3 style="margin-top:0">Sentence ' + (state.openSentence + 1) +
    (flags ? '</h3>' + flags : '</h3><p class="hint">No patterns flagged in this sentence — it reads naturally.</p>') + '</div>';
}

/* ================= Humanize ================= */
async function ensureModes() {
  if (!state.modes) {
    const r = await api("/api/modes");
    state.modes = r.modes || [];
    state.intensities = r.intensities || [];
  }
}
async function ensureProviders() {
  state.providers = await api("/api/settings");
}
function intensityLabel(level) {
  const f = (state.intensities || []).find(x => x.level === level);
  return f ? f.label : ("Level " + level);
}

async function viewHumanize() {
  const doc = state.doc;
  const v = $("#view");
  v.innerHTML = '<h2>Humanize</h2>' + docHeader(doc) +
    '<div class="banner banner-honesty">Rewriting produces <strong>suggestions only</strong> — nothing changes until you choose "Accept" and then "Apply accepted".</div>' +
    '<div id="hum-body"><div class="card"><span class="spinner"></span>Loading…</div></div>';
  try {
    await ensureModes();
    await ensureProviders();
    if (!state.analysis) {
      $("#hum-body").innerHTML = '<div class="card"><span class="spinner"></span>Reading your sentences…</div>';
      try {
        state.analysis = await api("/api/documents/" + encodeURIComponent(state.docId) + "/analyze", { method: "POST" });
      } catch (e) {
        $("#hum-body").innerHTML = '<div class="banner banner-error">' + esc(e.message) +
          '</div><p class="hint">Add some text in the Editor first.</p>';
        return;
      }
    }
    renderHumanizeForm();
  } catch (e) {
    $("#hum-body").innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
  }
}

function providerOptions() {
  const p = (state.providers && state.providers.providers) || {};
  const defs = [
    { kind: "offline", label: "Offline engine", sub: "Built in — works without the internet and never sends your text anywhere." },
    { kind: "openai", label: "OpenAI-compatible", sub: p.openai && p.openai.configured ? ("Configured · " + (p.openai.model || "model set")) : "Not configured" },
    { kind: "gemini", label: "Gemini", sub: p.gemini && p.gemini.configured ? ("Configured · " + (p.gemini.model || "model set")) : "Not configured" },
    { kind: "ollama", label: "Ollama (local AI)", sub: p.ollama && p.ollama.configured ? ("Configured · " + (p.ollama.model || "model set")) : "Not configured" },
  ];
  return defs.map(d =>
    '<label class="mode-card' + (state.providerKind === d.kind ? " selected" : "") + '">' +
    '<input type="radio" name="provider" value="' + d.kind + '"' + (state.providerKind === d.kind ? " checked" : "") + '> ' +
    '<span class="mode-name">' + esc(d.label) + '</span>' +
    '<p class="mode-desc">' + esc(d.sub) + '</p></label>').join("");
}

function providerHint() {
  const p = (state.providers && state.providers.providers) || {};
  if (state.providerKind === "offline") return "";
  const entry = p[state.providerKind];
  if (entry && entry.configured) return "";
  const names = { openai: "OpenAI-compatible", gemini: "Gemini", ollama: "Ollama" };
  return '<div class="banner banner-error" style="margin:10px 0 0">' + esc(names[state.providerKind]) +
    ' is not set up yet. <button class="btn btn-secondary btn-sm" id="goto-settings">Open Settings</button> ' +
    'or choose the Offline engine above.</div>';
}

function renderHumanizeForm() {
  const doc = state.doc;
  const sentences = state.analysis.sentences || [];
  const modeCards = (state.modes || []).map(m =>
    '<label class="mode-card' + (state.modeId === m.id ? " selected" : "") + '">' +
    '<input type="radio" name="mode" value="' + esc(m.id) + '"' + (state.modeId === m.id ? " checked" : "") + '> ' +
    '<span class="mode-name">' + esc(m.name) + '</span><p class="mode-desc">' + esc(m.description) + '</p></label>').join("");

  const flaggedIdx = sentences.filter(s => (s.flags || []).length).map(s => s.index);
  const pickerItems = sentences.map(s =>
    '<label class="picker-item"><input type="checkbox" class="sent-check" value="' + s.index + '" checked> ' +
    '<span><strong>Sentence ' + (s.index + 1) + ':</strong> ' + esc(s.text) +
    ((s.flags || []).length ? ' <span class="flagged-dot">● flagged</span>' : '') + '</span></label>').join("");

  $("#hum-body").innerHTML =
    '<div class="card"><h3>1 · Choose a rewriting style</h3>' +
      '<div class="mode-grid">' + modeCards + '</div>' +
      '<h3>2 · Rewriting intensity: <span id="int-label">' + esc(intensityLabel(state.intensity)) + '</span></h3>' +
      '<input type="range" id="intensity" min="1" max="5" step="1" value="' + state.intensity + '" aria-label="Rewriting intensity from 1 to 5">' +
      '<h3>3 · Choose the rewriting engine</h3>' +
      '<div class="mode-grid" id="provider-grid">' + providerOptions() + '</div>' +
      '<div id="provider-hint">' + providerHint() + '</div>' +
    '</div>' +
    '<div class="card"><h3>4 · Choose sentences to rewrite</h3>' +
      '<div class="btn-row">' +
        '<button class="btn btn-secondary btn-sm" id="sel-all">Select all</button>' +
        '<button class="btn btn-secondary btn-sm" id="sel-flagged">Select flagged only</button>' +
      '</div>' +
      (pickerItems ? '<div class="picker-list">' + pickerItems + '</div>'
        : '<div class="notice"><p>No sentences found. Add text in the Editor first.</p></div>') +
      '<div class="btn-row"><button class="btn btn-primary" id="rewrite-btn">✨ Rewrite selected sentences</button></div>' +
    '</div>' +
    '<div id="sugg-out"></div>';

  $$('input[name="mode"]').forEach(r => r.addEventListener("change", () => {
    state.modeId = r.value;
    $$('input[name="mode"]').forEach(x => x.closest(".mode-card").classList.toggle("selected", x.checked));
  }));
  $("#intensity").addEventListener("input", e => {
    state.intensity = parseInt(e.target.value, 10);
    $("#int-label").textContent = intensityLabel(state.intensity);
  });
  $$('input[name="provider"]').forEach(r => r.addEventListener("change", () => {
    state.providerKind = r.value;
    $$('input[name="provider"]').forEach(x => x.closest(".mode-card").classList.toggle("selected", x.checked));
    $("#provider-hint").innerHTML = providerHint();
    const g = $("#goto-settings");
    if (g) g.addEventListener("click", () => showView("settings"));
  }));
  const gs0 = $("#goto-settings");
  if (gs0) gs0.addEventListener("click", () => showView("settings"));

  $("#sel-all").addEventListener("click", () => $$(".sent-check").forEach(c => { c.checked = true; }));
  $("#sel-flagged").addEventListener("click", () => {
    const set = new Set(flaggedIdx);
    $$(".sent-check").forEach(c => { c.checked = set.has(parseInt(c.value, 10)); });
    if (!set.size) toast("No sentences were flagged in the last analysis.", true);
  });

  $("#rewrite-btn").addEventListener("click", async () => {
    const idx = $$(".sent-check").filter(c => c.checked).map(c => parseInt(c.value, 10));
    if (!idx.length) { toast("Select at least one sentence to rewrite.", true); return; }
    const out = $("#sugg-out");
    out.innerHTML = '<div class="card"><span class="spinner"></span>Rewriting with ' +
      esc(state.providerKind === "offline" ? "the offline engine" : state.providerKind) + '… this can take a moment.</div>';
    try {
      const res = await api("/api/documents/" + encodeURIComponent(state.docId) + "/rewrite", {
        method: "POST",
        body: { mode: state.modeId, intensity: state.intensity, provider_kind: state.providerKind, sentence_indexes: idx },
      });
      state.doc = await api("/api/documents/" + encodeURIComponent(state.docId));
      state.rejectedIds = new Set(); state.acceptedIds = new Set();
      renderSuggestions(res, res.suggestions || []);
      toast("Rewrite complete — review the suggestions below.");
    } catch (e) {
      out.innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
    }
  });

  // Resume pending suggestions from a previous session
  if (doc.pending && doc.pending.suggestions && doc.pending.suggestions.length) {
    renderSuggestions(doc.pending, doc.pending.suggestions);
  }
}

function renderSuggestions(meta, suggestions) {
  state.rejectedIds = new Set(); state.acceptedIds = new Set();
  const out = $("#sugg-out");
  const visible = () => suggestions.filter(s => !state.rejectedIds.has(s.id));
  const paint = () => {
    const list = visible();
    if (!list.length) {
      out.innerHTML = '<div class="card"><p class="hint">No suggestions left to review.</p>' +
        '<div class="btn-row"><button class="btn btn-secondary" id="discard-btn">Discard all</button></div></div>';
      $("#discard-btn").addEventListener("click", discardAll);
      return;
    }
    const cards = list.map(s => {
      const accepted = state.acceptedIds.has(s.id);
      return '<div class="sugg-card' + (accepted ? " sugg-accepted" : "") + '" data-sid="' + esc(s.id) + '">' +
        '<p class="hint" style="margin:0">Sentence ' + (s.sentence_index + 1) + '</p>' +
        '<p class="sugg-text"><strong>Original:</strong> ' + esc(s.original) + '</p>' +
        (s.changed
          ? '<p class="sugg-text"><strong>Suggested:</strong> <span class="arrow">→</span> ' + esc(s.rewritten) + '</p>' +
            ((s.notes && s.notes.length)
              ? '<p class="hint" style="margin-bottom:2px"><strong>What changed:</strong></p><ul class="sugg-notes">' +
                s.notes.map(n => '<li>' + esc(n) + '</li>').join("") + '</ul>'
              : '')
          : '<p class="unchanged-note">No changes suggested for this sentence — it already reads well.</p>') +
        '<div class="sugg-actions">' +
          (s.changed ? '<button class="btn btn-primary btn-sm" data-accept="' + esc(s.id) + '"' + (accepted ? " disabled" : "") + '>' +
            (accepted ? "Accepted ✓" : "Accept") + '</button>' : '') +
          '<button class="btn btn-secondary btn-sm" data-reject="' + esc(s.id) + '">Reject</button>' +
        '</div></div>';
    }).join("");
    out.innerHTML =
      '<div class="card"><h3>Suggestions</h3>' +
      '<p class="hint">Rewritten with <strong>' + esc(meta.used_provider || "offline") + '</strong> · mode: ' +
      esc(meta.mode || state.modeId) + ' · intensity ' + esc(String(meta.intensity || state.intensity)) +
      '. ' + esc(meta.note || "") + '</p>' +
      '<p class="hint">Accept the ones you like, reject the rest, then apply them all at once.</p>' +
      cards +
      '<div class="btn-row">' +
        '<button class="btn btn-primary" id="apply-btn">Apply accepted (<span id="acc-count">' + state.acceptedIds.size + '</span>)</button>' +
        '<button class="btn btn-secondary" id="discard-btn">Discard all</button>' +
      '</div></div>';

    $$("[data-accept]", out).forEach(b => b.addEventListener("click", () => {
      state.acceptedIds.add(b.dataset.accept);
      paint();
    }));
    $$("[data-reject]", out).forEach(b => b.addEventListener("click", () => {
      state.rejectedIds.add(b.dataset.reject);
      paint();
    }));
    $("#apply-btn").addEventListener("click", async () => {
      if (!state.acceptedIds.size) { toast("Accept at least one suggestion first.", true); return; }
      if (!confirm("Apply " + state.acceptedIds.size + " accepted suggestion(s) to your document?")) return;
      try {
        state.doc = await api("/api/documents/" + encodeURIComponent(state.docId) + "/suggestions/apply", {
          method: "POST", body: { suggestion_ids: Array.from(state.acceptedIds) }
        });
        state.analysis = null;
        toast("Accepted suggestions applied.");
        showView("compare");
      } catch (e) { toast(e.message, true); }
    });
    $("#discard-btn").addEventListener("click", discardAll);
  };
  async function discardAll() {
    if (!confirm("Discard all pending suggestions? Your text will not change.")) return;
    try {
      await api("/api/documents/" + encodeURIComponent(state.docId) + "/suggestions/discard", { method: "POST" });
      state.doc = await api("/api/documents/" + encodeURIComponent(state.docId));
      toast("Suggestions discarded.");
      renderHumanizeForm();
    } catch (e) { toast(e.message, true); }
  }
  paint();
}

/* ================= Compare ================= */
function splitParagraphs(t) {
  return String(t || "").split(/\n\s*\n/).map(p => p.trim()).filter(p => p.length);
}

async function viewCompare() {
  const doc = state.doc;
  const v = $("#view");
  const versions = doc.versions || [];
  const original = versions.length ? versions[0].text || "" : doc.text || "";
  const current = doc.text || "";
  v.innerHTML = '<h2>Compare</h2>' + docHeader(doc) +
    '<p class="view-sub">Original = the very first saved version · Current = your latest text.</p>' +
    '<div class="compare-cols">' +
      '<div><h3>Original (first version)</h3><div class="compare-pane">' + esc(original || "(empty)") + '</div></div>' +
      '<div><h3>Current text</h3><div class="compare-pane">' + esc(current || "(empty)") + '</div></div>' +
    '</div>' +
    '<h3>Word-level changes</h3>' +
    '<div class="card diff"><div id="diff-out"><span class="spinner"></span>Computing differences…</div></div>' +
    '<p class="hint"><span style="background:var(--red-bg);color:var(--red);padding:0 6px;border-radius:4px">removed text</span> is shown with a strikethrough; ' +
    '<span style="background:var(--green-bg);color:var(--green);padding:0 6px;border-radius:4px">added text</span> is shown in green.</p>';

  try {
    const parasA = splitParagraphs(original), parasB = splitParagraphs(current);
    const n = Math.max(parasA.length, parasB.length);
    const jobs = [];
    for (let i = 0; i < n; i++) {
      const a = parasA[i] || "", b = parasB[i] || "";
      jobs.push(api("/api/diff", { method: "POST", body: { a, b } }));
    }
    const results = await Promise.all(jobs);
    let anyChange = false;
    const html = results.map((r, i) => {
      const ops = (r && r.ops) || [];
      const inner = ops.map(o => {
        if (o.type === "del") { anyChange = true; return '<del class="diff-del">' + esc(o.text) + '</del>'; }
        if (o.type === "ins") { anyChange = true; return '<ins class="diff-ins">' + esc(o.text) + '</ins>'; }
        return esc(o.text);
      }).join("");
      return '<div class="diff-para"><p class="hint" style="margin:0 0 6px">Paragraph ' + (i + 1) + '</p><div class="diff-output">' + inner + '</div></div>';
    }).join("");
    $("#diff-out").innerHTML = anyChange ? html
      : '<p class="hint">The original and current text are identical — no changes yet.</p>';
  } catch (e) {
    $("#diff-out").innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
  }
}

/* ================= Quality ================= */
async function viewQuality() {
  const doc = state.doc;
  const v = $("#view");
  v.innerHTML = '<h2>Quality</h2>' + docHeader(doc) +
    '<p class="view-sub">Plain-language observations about readability. These describe the text, not the writer.</p>' +
    '<div id="q-out"><div class="card"><span class="spinner"></span>Measuring readability…</div></div>';
  try {
    if (!state.analysis) {
      state.analysis = await api("/api/documents/" + encodeURIComponent(state.docId) + "/analyze", { method: "POST" });
    }
    const m = state.analysis.metrics || {};
    const notes = state.analysis.quality_notes || [];
    $("#q-out").innerHTML =
      '<div class="banner banner-honesty"><strong>Important:</strong> ' + esc(state.analysis.disclaimer || "") + '</div>' +
      '<div class="card"><h3>Readability</h3><div class="metric-grid">' +
        '<div class="metric"><p class="m-value">' + esc(String(m.flesch_reading_ease)) + '</p><p class="m-label">Flesch Reading Ease — ' + esc(String(m.flesch_ease_label || "")) + ' (higher = easier to read)</p></div>' +
        '<div class="metric"><p class="m-value">' + esc(String(m.flesch_kincaid_grade)) + '</p><p class="m-label">Flesch–Kincaid grade level — the US school grade this text reads at</p></div>' +
        '<div class="metric"><p class="m-value">' + esc(String(m.avg_sentence_length)) + '</p><p class="m-label">Average words per sentence</p></div>' +
        '<div class="metric"><p class="m-value">' + esc(String(m.passive_count)) + '</p><p class="m-label">Passive-voice sentences found</p></div>' +
      '</div></div>' +
      '<div class="card"><h3>Observations</h3>' +
        (notes.length ? '<ul class="note-list">' + notes.map(n => '<li>' + esc(n) + '</li>').join("") + '</ul>'
          : '<p class="hint">No additional observations.</p>') +
      '</div>';
  } catch (e) {
    $("#q-out").innerHTML = '<div class="banner banner-error">' + esc(e.message) +
      '</div><p class="hint">Add some text in the Editor first.</p>';
  }
}

/* ================= Export ================= */
async function viewExport() {
  const doc = state.doc;
  const v = $("#view");
  v.innerHTML = '<h2>Export</h2>' + docHeader(doc) +
    '<p class="view-sub">Download your document in three formats, from three versions of the text. ' +
    '"Revised" is your current text, "Original" is the very first version, "Comparison" shows both.</p>' +
    '<div class="card"><h3>Download a file</h3><div class="export-grid" id="export-grid"></div>' +
    '<div id="export-result" style="margin-top:12px"></div></div>' +
    '<div class="card"><h3>Copy to clipboard</h3>' +
    '<div class="btn-row"><button class="btn btn-secondary" id="copy-revised">📋 Copy revised text</button></div>' +
    '<div id="copy-result"></div></div>';

  const grid = $("#export-grid");
  const fmts = [["txt", "TXT"], ["docx", "DOCX"], ["pdf", "PDF"]];
  const kinds = [["revised", "Revised"], ["original", "Original"], ["comparison", "Comparison report"]];
  grid.innerHTML = fmts.map(f => kinds.map(k =>
    '<button class="btn btn-secondary" data-fmt="' + f[0] + '" data-kind="' + k[0] + '">' + f[1] + ' · ' + k[1] + '</button>'
  ).join("")).join("");

  $$("#export-grid button", grid).forEach(b => b.addEventListener("click", async () => {
    const out = $("#export-result");
    out.innerHTML = '<span class="spinner"></span>Preparing your ' + esc(b.dataset.fmt.toUpperCase()) + ' file…';
    try {
      const res = await api("/api/documents/" + encodeURIComponent(state.docId) + "/export", {
        method: "POST", body: { format: b.dataset.fmt, kind: b.dataset.kind }
      });
      const checks = (res.validation && res.validation.checks || [])
        .map(c => esc(c.name) + ": " + (c.passed ? "passed ✓" : "FAILED")).join(" · ");
      out.innerHTML = '<div class="banner banner-ok"><strong>' + esc(res.filename) +
        '</strong> is ready — your download should start now.<br><span class="hint">Validation: ' +
        esc(checks || "ok") + '</span></div>';
      const a = document.createElement("a");
      a.href = res.download_url;
      a.download = res.filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => a.remove(), 2000);
    } catch (e) {
      out.innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
    }
  }));

  $("#copy-revised").addEventListener("click", async () => {
    const out = $("#copy-result");
    try {
      await navigator.clipboard.writeText(doc.text || "");
      out.innerHTML = '<div class="banner banner-ok">Revised text copied to your clipboard ✓</div>';
    } catch (e) {
      out.innerHTML = '<div class="banner banner-error">Could not copy automatically. Select the text in the Editor and copy it manually.</div>';
    }
  });
}

/* ================= Settings ================= */
async function viewSettings() {
  const v = $("#view");
  v.innerHTML = '<h2>Settings</h2>' +
    '<p class="view-sub">Connect an AI provider for rewriting, or keep using the built-in offline engine.</p>' +
    '<div id="set-body"><div class="card"><span class="spinner"></span>Loading settings…</div></div>' +
    '<div class="card"><h3>Privacy</h3><p>Everything runs on your computer. Documents and keys are stored locally in the app\'s data folder and never leave your machine except when you choose a cloud AI provider.</p></div>';
  try {
    await ensureProviders();
    renderSettingsForm();
  } catch (e) {
    $("#set-body").innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
  }
}

function providerCard(kind, title, fields, helpText) {
  const p = (state.providers && state.providers.providers) || {};
  const cur = p[kind] || {};
  const configured = cur.configured;
  const inputs = fields.map(f => {
    const val = f.name === "api_key" ? "" : (cur[f.name] || "");
    return '<label class="field-label" for="set-' + kind + '-' + f.name + '">' + esc(f.label) + '</label>' +
      '<input type="' + f.type + '" id="set-' + kind + '-' + f.name + '" value="' + esc(val) + '" placeholder="' + esc(f.placeholder || "") + '"' +
      (f.name === "api_key" ? ' autocomplete="off"' : "") + '>';
  }).join("");
  return '<div class="card"><h3>' + esc(title) + ' <span class="status-pill ' + (configured ? "status-on" : "status-off") + '">' +
    (configured ? "Configured ✓" : "Not configured") + '</span></h3>' +
    '<p class="hint">' + esc(helpText) + '</p>' + inputs +
    '<div class="btn-row">' +
      '<button class="btn btn-primary btn-sm" data-save="' + kind + '">Save</button>' +
      '<button class="btn btn-secondary btn-sm" data-test="' + kind + '">Test connection</button>' +
    '</div><div class="test-result" id="test-' + kind + '"></div></div>';
}

function renderSettingsForm() {
  $("#set-body").innerHTML = '<div class="provider-grid">' +
    providerCard("openai", "OpenAI-compatible", [
      { name: "base_url", label: "Base URL", type: "url", placeholder: "https://api.openai.com/v1" },
      { name: "model", label: "Model", type: "text", placeholder: "e.g. gpt-4o-mini" },
      { name: "api_key", label: "API key", type: "password", placeholder: "Leave blank to keep the saved key" },
    ], "Works with OpenAI and any service that uses the same API format (for example Azure OpenAI or a local server).") +
    providerCard("gemini", "Google Gemini", [
      { name: "model", label: "Model", type: "text", placeholder: "e.g. gemini-2.0-flash" },
      { name: "api_key", label: "API key", type: "password", placeholder: "Leave blank to keep the saved key" },
    ], "Uses your Google AI Studio API key. Your text is sent to Google only when you choose Gemini for rewriting.") +
    providerCard("ollama", "Ollama (runs on your computer)", [
      { name: "base_url", label: "Base URL", type: "url", placeholder: "http://localhost:11434" },
      { name: "model", label: "Model", type: "text", placeholder: "e.g. llama3.1" },
    ], "Free, open AI models running on your own machine via Ollama. Nothing leaves your computer.") +
  '</div>';

  $$("[data-save]").forEach(b => b.addEventListener("click", async () => {
    const kind = b.dataset.save;
    const cfg = {};
    ["base_url", "model", "api_key"].forEach(f => {
      const el = $("#set-" + kind + "-" + f);
      if (el) cfg[f] = el.value;
    });
    b.disabled = true;
    try {
      const res = await api("/api/settings", { method: "POST", body: { provider: kind, config: cfg } });
      await ensureProviders();
      renderSettingsForm();
      toast(res.configured ? "Saved — provider is configured ✓" : "Saved. Add the missing details to finish setup.");
    } catch (e) { toast(e.message, true); }
    b.disabled = false;
  }));

  $$("[data-test]").forEach(b => b.addEventListener("click", async () => {
    const kind = b.dataset.test;
    const out = $("#test-" + kind);
    out.innerHTML = '<span class="spinner"></span>Testing…';
    try {
      const res = await api("/api/settings/test", { method: "POST", body: { provider: kind } });
      out.innerHTML = res.ok
        ? '<span class="status-pill status-on">Connection works ✓</span>'
        : '<span class="status-pill status-off">Failed</span> <span class="hint">' + esc(res.error || "Unknown error") + '</span>';
    } catch (e) {
      out.innerHTML = '<span class="status-pill status-off">Failed</span> <span class="hint">' + esc(e.message) + '</span>';
    }
  }));
}

/* ================= History ================= */
async function viewHistory() {
  const doc = state.doc;
  const v = $("#view");
  v.innerHTML = '<h2>History &amp; roadmap</h2>' + docHeader(doc) +
    '<div class="card"><h3>Version history</h3><div id="ver-list"></div></div>' +
    '<div class="card"><h3>Roadmap — planned for later versions</h3>' +
    '<p class="hint">These features are <strong>not</strong> in v1. They appear here so you know what is coming — nothing is faked or simulated.</p>' +
    '<div id="roadmap-list"><span class="spinner"></span>Loading roadmap…</div></div>';

  const versions = (doc.versions || []).slice().reverse();
  $("#ver-list").innerHTML = versions.length
    ? versions.map(x =>
      '<div class="version-row"><div><strong>' + esc(x.label) + '</strong><br>' +
      '<span class="hint">' + esc(fmtDate(x.at)) + ' · ' + esc(String(x.word_count)) + ' words</span>' +
      '<p class="version-preview">' + esc(x.preview || "") + (x.preview && x.preview.length >= 120 ? "…" : "") + '</p></div>' +
      '<button class="btn btn-secondary btn-sm" data-restore="' + esc(x.id) + '">Restore</button></div>').join("")
    : '<p class="hint">No earlier versions yet — a backup is saved automatically each time your text changes.</p>';

  $$("[data-restore]").forEach(b => b.addEventListener("click", async () => {
    const ver = versions.find(x => x.id === b.dataset.restore);
    if (!confirm('Restore "' + (ver ? ver.label : "this version") + '"? Your current text will be backed up first.')) return;
    try {
      state.doc = await api("/api/documents/" + encodeURIComponent(state.docId) + "/versions/restore", {
        method: "POST", body: { version_id: b.dataset.restore }
      });
      state.analysis = null;
      toast("Version restored.");
      viewHistory();
    } catch (e) { toast(e.message, true); }
  }));

  try {
    if (!state.roadmap) state.roadmap = await api("/api/roadmap");
    $("#roadmap-list").innerHTML =
      '<p class="hint">' + esc(state.roadmap.note || "") + '</p>' +
      (state.roadmap.items || []).map(i =>
        '<div class="roadmap-item">' + esc(i) + '<span class="roadmap-badge">Roadmap · not in v1</span></div>').join("");
  } catch (e) {
    $("#roadmap-list").innerHTML = '<div class="banner banner-error">' + esc(e.message) + '</div>';
  }
}

/* ---------- view registry & boot ---------- */
const VIEWS = {
  dashboard: viewDashboard,
  editor: viewEditor,
  analyze: viewAnalyze,
  humanize: viewHumanize,
  compare: viewCompare,
  quality: viewQuality,
  export: viewExport,
  history: viewHistory,
  settings: viewSettings,
};

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initNav();
  showView("dashboard");
});
