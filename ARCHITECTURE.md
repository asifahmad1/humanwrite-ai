# Architecture — HumanWrite AI v1

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (vanilla JS SPA)                                   │
│  static/index.html · style.css · app.js                     │
│  Dashboard / Editor / Analyze / Humanize / Compare /        │
│  Quality / Export / Settings / History                      │
└───────────────────────┬─────────────────────────────────────┘
                        │ JSON over HTTP (127.0.0.1:4322)
┌───────────────────────▼─────────────────────────────────────┐
│  Flask backend (app.py)                                     │
│  Documents · Upload · Analyze · Rewrite · Versions ·        │
│  Diff · Export · Settings · Modes · Roadmap                 │
└───┬──────────┬───────────┬──────────────┬──────────┬────────┘
    │          │           │              │          │
┌───▼───┐ ┌────▼────┐ ┌────▼──────┐ ┌─────▼─────┐ ┌──▼────────┐
│nlp.py │ │analyzer │ │rewriter.py│ │providers  │ │ exports   │
│segment│ │ .py     │ │ 10 modes  │ │.py        │ │ txt/docx/ │
│syllabl│ │ flags + │ │ × 5 inten-│ │ openai/   │ │ pdf +     │
│readab │ │ metrics │ │ sities,   │ │ gemini/   │ │ validate  │
│passive│ │ honest  │ │ protected │ │ ollama    │ │           │
│transit│ │ framing │ │ spans     │ │           │ │           │
└───────┘ └─────────┘ └───────────┘ └───────────┘ └───────────┘
                        │
              ┌─────────▼──────────┐
              │ store.py → ./data  │
              │ documents/*.json   │
              │ settings.json      │
              │ exports/<id>/*     │
              └────────────────────┘
```

## Module responsibilities

- **nlp.py** — Deterministic text utilities: abbreviation-aware sentence
  segmentation (with char offsets), paragraph splitting, word tokenizing,
  heuristic syllable counting, Flesch Reading Ease / Flesch–Kincaid Grade,
  passive-voice regex detection (be-verb + participle, incl. irregulars),
  a weighted transition-phrase lexicon (~50 phrases), a formal→plain word
  map plus phrase swaps and filler list, trigram repetition, and basic
  mechanical checks (repeated words, spacing). No ML, no network.
- **analyzer.py** — Builds sentence-level flags
  (`long_sentence`, `passive_voice`, `transition`, `formality`, `filler`,
  `repetition`, `short_sentence`) and document-level notes (`uniformity`,
  `passive_overuse`, repeated trigrams/openers). Every response carries
  the `DISCLAIMER`: stylistic assessment only, no authorship claims, no
  detector scores. Metrics are computed, never invented.
- **rewriter.py** — Offline rewriting engine. Protected spans (numbers,
  citation markers like `[1]` / `(Author, 2020)`, quoted text) are masked
  before rewriting and restored after, so they are never altered.
  Transforms: phrase swaps ("in order to"→"to"), formal→plain words
  ("utilize"→"use"), filler removal, passive→active ("X was verbed by Y"
  → "Y verbed X"), long-sentence splitting, contractions (conversational
  mode), AI abbreviation after first use. Mode × intensity selects the
  pipeline; every change is reported in `notes`.
- **providers.py** — Provider-neutral AI: OpenAI-compatible
  (`/chat/completions`), Google Gemini (`generateContent`), Ollama
  (`/api/generate`). `rewrite_with_provider` sends numbered sentences
  with a strict preservation system prompt and expects JSON back;
  `test_connection` does a minimal round-trip. All failures raise
  `ProviderError` with the real message. Keys come from `SettingsStore`
  (server-side only).
- **diffutil.py** — Word-token diff via `difflib.SequenceMatcher`
  → `{eq, del, ins}` ops for the comparison view.
- **store.py** — `DocumentStore` (CRUD over `./data/documents/*.json`,
  safe-id filenames) and `SettingsStore` (`./data/settings.json`;
  `public_view()` redacts API keys for the browser).
- **export_txt/docx/pdf.py** — Real exports built in memory; DOCX uses
  python-docx native objects, PDF uses reportlab platypus. Each has a
  `validate_*` function that re-opens the bytes and checks content;
  the API refuses to serve exports that fail validation.
- **app.py** — Flask app factory `create_app(data_root=None)` (tests inject
  a temp dir), JSON error handlers, and the routes listed in README.
  Version history: snapshots pushed before every text mutation
  (upload, manual edit, apply, restore), capped at 30.

## Data flow: rewrite

1. `POST /rewrite` {mode, intensity, provider_kind, sentence_indexes?}
2. Backend re-segments the stored text; offline → `rewrite_text_offline`,
   cloud → `providers.rewrite_with_provider` (requires configured provider).
3. Suggestions stored as `doc.pending` (nothing applied yet).
4. `POST /suggestions/apply` {suggestion_ids} → text rebuilt from
   sentences with accepted replacements; version snapshot pushed;
   `pending` cleared.

## Security / privacy model

- Local-first: all state in `./data` on the user's machine.
- API keys live in `settings.json` (server side); `GET /api/settings`
  never returns them.
- Uploads limited to 10 MB and TXT/DOCX/PDF only.
- Cloud providers are only contacted when the user explicitly picks one
  and has configured it; otherwise everything is offline.

## Honesty invariants (tested)

1. Analysis output contains no authorship verdicts and no numeric
   "AI probability" scores — enforced by construction (no such code
   path exists) and by `test_no_authorship_claim_anywhere`.
2. Rewriting never alters numbers, citations, or quotations —
   `test_numbers_citations_quotes_preserved`.
3. No hard-coded responses: the demo sentence is transformed by the
   same rules as any input — `test_demo_sentence_improved_not_hardcoded`.
