# HumanWrite AI v1

**Make Every Word Sound Naturally Yours.**

A local-first AI text analyzer, humanizer & writing assistant. Paste or upload
text, get honest stylistic analysis, rewrite selected passages in 10 modes,
compare versions side-by-side, and export to TXT, DOCX, or PDF.

## Quick start

**Windows:** double-click `Start-Windows.cmd`, then open
http://127.0.0.1:4322 in your browser (it opens automatically).

**macOS/Linux:** run `./start.sh`, then open http://127.0.0.1:4322.

No account, no cloud, no subscription. Everything runs on your computer.

## What v1 does

- **Editor** — paste/type with live word & character counters, autosave,
  and TXT / DOCX / PDF upload with text extraction.
- **AI Text Analyzer** — sentence-level stylistic flags (long sentences,
  passive voice, formulaic transitions, formal/wordy phrasing, filler,
  repetition) with plain-language explanations. Every result is labelled
  as a *stylistic assessment* — the app never claims to establish
  authorship and never fabricates detector scores.
- **Humanizer** — 10 rewriting modes (Natural, Academic, Professional,
  Conversational, Simple, Creative, Native-Level, Voice Preservation,
  Technical, Minimal) × 5 intensity levels. Rewrite the whole document
  or selected sentences only; accept or reject each suggestion.
- **Offline engine** — a built-in rule-based rewriter/analyzer that always
  works with no API key. Optional cloud providers (OpenAI-compatible,
  Google Gemini, Ollama) for AI-powered rewriting; keys stay on your machine.
- **Compare** — side-by-side original vs revised with word-level diff.
- **Quality panel** — Flesch Reading Ease, Flesch–Kincaid grade, and
  plain-language notes computed locally.
- **Export Center** — TXT, DOCX, PDF (revised, original, or comparison
  report). DOCX/PDF exports are validated on creation.
- **History** — version snapshots with one-click restore.
- **Privacy** — documents and API keys are stored as local JSON files in
  `./data`. Nothing leaves your computer except when you choose a cloud
  AI provider.

## Honest limitations (v1)

- The analyzer describes *writing style*, not authorship. It cannot tell
  you whether a human or an AI wrote a text, and it does not try.
- The offline rewriter applies explicit rules — it is not a large language
  model. For AI-quality rewriting, connect a provider in Settings.
- Not in v1 (see ROADMAP.md): third-party detector integrations
  (GPTZero/Originality.ai/Copyleaks), plagiarism database checks, OCR for
  scanned PDFs, cloud imports, multilingual support, style profiles,
  tracked-changes DOCX.

## Requirements

- Python 3.10–3.13 (3.14+ is too new for some packages)
- Internet only for the one-time package install and for cloud AI providers

## Project layout

```
app.py            Flask backend + API
nlp.py            segmentation, syllables, readability, passive/transitions
analyzer.py       honest stylistic analysis engine
rewriter.py       offline rule-based rewriting (10 modes × 5 intensities)
providers.py      OpenAI / Gemini / Ollama clients + connection test
diffutil.py       word-level diff
store.py          local JSON storage (documents + server-side settings)
export_txt.py / export_docx.py / export_pdf.py    real validated exports
static/           frontend (index.html, style.css, app.js)
tests/            pytest suite (50 tests)
data/             your documents + settings (created on first run)
```

## Tests

```
./venv/bin/python -m pytest tests/ -q
```

## Documentation

- `EASY-SETUP.md` — beginner installation walkthrough
- `ARCHITECTURE.md` — how the system works
- `ROADMAP.md` — what is planned and what is deliberately excluded from v1
