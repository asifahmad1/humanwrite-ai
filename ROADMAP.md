# Roadmap — HumanWrite AI v1

What v1 is, what it deliberately is not, and what is planned.

## Implemented in v1

- Paste/type editor with word & character counters and autosave
- TXT / DOCX / PDF upload with text extraction
- Honest stylistic analysis (sentence-level flags + document metrics +
  Flesch Reading Ease / Flesch–Kincaid Grade computed locally)
- Offline rule-based rewriting: 10 modes × 5 intensity levels, selective
  sentence rewriting, per-suggestion accept/reject
- Cloud AI rewriting via OpenAI-compatible, Google Gemini, or Ollama
  (user-configured keys, server-side only, connection test)
- Side-by-side comparison with word-level diff
- Version history with one-click restore (undo via restore)
- Real validated exports: TXT, DOCX, PDF (revised / original / comparison)
- Local-first privacy: everything in `./data` on the user's machine

## Explicitly NOT in v1 (shown as Roadmap in the UI)

These appear in the app's Roadmap section as disabled items so users are
never misled into thinking they exist:

1. **Third-party AI detector integrations** (GPTZero, Originality.ai,
   Copyleaks) — only via officially authorized APIs with terms permitting
   the use case. No scraping, no impersonation, no rate-limit bypass.
   Detector results would be shown as probabilistic signals with known
   limitations — never as verdicts, never promising a score.
2. **Plagiarism database checks** — only via licensed databases or
   authorized third-party APIs; textual similarity would be clearly
   distinguished from plagiarism.
3. **OCR for scanned-image PDFs** — v1 reports "no extractable text" and
   says OCR is roadmap.
4. **Cloud imports** — Google Drive, Google Docs, OneDrive, Dropbox via
   authorized OAuth.
5. **Multilingual analysis/rewriting** — v1 heuristics are English-only;
   English-centric thresholds must never be applied to other languages.
6. **Personal writing-style profiles** — learning tone/vocabulary from the
   user's own samples (with edit/reset/export/delete).
7. **Tracked-changes DOCX export** — revision markup in exported DOCX.
8. **Advanced editing tools** — dedicated grammar checker, paraphraser,
   summarizer, tone changer, citation checker (v1 has basic local
   mechanical checks only, labelled as such).

## Principles for future work

- Never claim authorship attribution; never fabricate detector scores.
- Never modify numbers, citations, quotations, or equations without the
  user's explicit per-change approval.
- Academic-integrity safeguard: a visible setting to disclose AI
  assistance, and flags for potentially unsupported claims.
- Privacy-first: cloud features stay opt-in; local remains the default.
