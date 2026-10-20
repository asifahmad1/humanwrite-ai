"""Flask backend for HumanWrite AI v1.

Run locally:  python app.py   ->  http://127.0.0.1:4322

Local-first: documents and settings live in ./data as JSON. Provider API
keys are stored server-side only and never sent to the browser.

Honesty contract (from the master prompt):
- Analysis reports *stylistic* patterns with uncertainty; it NEVER claims
  to establish authorship and NEVER fabricates detector scores.
- Rewriting preserves numbers, citations and quotations (protected spans).
- Every feature performs real computation; no hard-coded demo responses.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

import providers
from analyzer import analyze_text
from diffutil import word_diff
from nlp import split_paragraphs, split_sentences, words
from rewriter import (
    INTENSITY_LABELS,
    MODES,
    rewrite_text_offline,
)
from store import DocumentStore, SettingsStore, new_id

BASE_DIR = Path(__file__).resolve().parent
PORT = 4322

_ALLOWED_UPLOAD = {".txt", ".docx", ".pdf"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _json_body(required: bool = True):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        if required:
            return None, (jsonify({"error": "Request body must be JSON"}), 400)
        return {}, None
    return data, None


def _blank_doc(title: str) -> dict:
    did = new_id("d")
    return {
        "id": did,
        "title": title,
        "text": "",
        "created": "",
        "updated": "",
        "versions": [],
        "pending": None,
    }


def _push_version(doc: dict, label: str) -> dict:
    """Snapshot current text into version history (cap 30)."""
    version = {
        "id": new_id("v"),
        "label": label,
        "at": doc.get("updated") or "",
        "text": doc.get("text", ""),
        "word_count": len(words(doc.get("text", ""))),
    }
    doc.setdefault("versions", []).append(version)
    doc["versions"] = doc["versions"][-30:]
    return version


def _public_doc(doc: dict, include_text: bool = True) -> dict:
    out = {
        "id": doc["id"],
        "title": doc.get("title", ""),
        "updated": doc.get("updated", ""),
        "created": doc.get("created", ""),
        "word_count": len(words(doc.get("text", ""))),
        "char_count": len(doc.get("text", "")),
        "versions": [
            {"id": v["id"], "label": v.get("label", ""), "at": v.get("at", ""),
             "word_count": v.get("word_count", 0),
             "preview": (v.get("text", "") or "")[:120]}
            for v in doc.get("versions", [])
        ],
        "has_pending": bool(doc.get("pending")),
    }
    if include_text:
        out["text"] = doc.get("text", "")
        out["pending"] = doc.get("pending")
    return out


def _extract_upload(filename: str, data: bytes) -> str:
    """Extract text from an uploaded TXT/DOCX/PDF. Raises ValueError."""
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_UPLOAD:
        raise ValueError(
            f"Unsupported file type {suffix!r} — upload TXT, DOCX or PDF.")
    if suffix == ".txt":
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode the text file.")
    if suffix == ".docx":
        from docx import Document
        doc = Document(BytesIO(data))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    # .pdf
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    text = "\n\n".join(p.strip() for p in parts if p.strip())
    if not text.strip():
        raise ValueError(
            "No extractable text found in this PDF. Scanned-image PDFs need "
            "OCR, which is on the roadmap and not in v1.")
    return text


def create_app(data_root: str | Path | None = None) -> Flask:
    root = Path(data_root) if data_root else BASE_DIR / "data"
    root.mkdir(parents=True, exist_ok=True)
    (root / "exports").mkdir(parents=True, exist_ok=True)

    documents = DocumentStore(root)
    settings = SettingsStore(root)

    app = Flask(__name__, static_folder=str(BASE_DIR / "static"),
                static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = _MAX_UPLOAD_BYTES

    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def _method_not_allowed(_e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(413)
    def _too_large(_e):
        return jsonify({"error": "File too large (max 10 MB)"}), 413

    def _get_doc(did: str):
        doc = documents.get(did)
        if doc is None:
            return None, (jsonify({"error": "Document not found"}), 404)
        return doc, None

    def _provider_cfg(kind: str) -> dict:
        stored = settings.get()["providers"].get(kind, {})
        return {
            "kind": kind,
            "model": stored.get("model", ""),
            "api_key": stored.get("api_key", ""),
            "base_url": stored.get("base_url", ""),
        }

    # -- documents ---------------------------------------------------------
    @app.post("/api/documents")
    def api_create_document():
        data, err = _json_body()
        if err:
            return err
        title = str(data.get("title", "")).strip() or "Untitled document"
        doc = _blank_doc(title[:120])
        documents.save(doc)
        return jsonify(_public_doc(doc)), 201

    @app.get("/api/documents")
    def api_list_documents():
        return jsonify(documents.list())

    @app.get("/api/documents/<did>")
    def api_get_document(did):
        doc, err = _get_doc(did)
        if err:
            return err
        return jsonify(_public_doc(doc))

    @app.put("/api/documents/<did>")
    def api_update_document(did):
        doc, err = _get_doc(did)
        if err:
            return err
        data, berr = _json_body()
        if berr:
            return berr
        if "title" in data:
            doc["title"] = str(data["title"])[:120]
        if "text" in data and isinstance(data["text"], str):
            if data["text"] != doc.get("text", ""):
                _push_version(doc, "Before manual edit")
                doc["text"] = data["text"]
        documents.save(doc)
        return jsonify(_public_doc(doc))

    @app.delete("/api/documents/<did>")
    def api_delete_document(did):
        if not documents.delete(did):
            return jsonify({"error": "Document not found"}), 404
        return jsonify({"ok": True})

    # -- upload ------------------------------------------------------------
    @app.post("/api/documents/<did>/upload")
    def api_upload(did):
        doc, err = _get_doc(did)
        if err:
            return err
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded (field name 'file')"}), 400
        f = request.files["file"]
        filename = f.filename or "upload"
        try:
            text = _extract_upload(filename, f.read())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001 — report, don't crash
            return jsonify({"error": f"Could not read file: {exc}"}), 400
        if doc.get("text", "").strip():
            _push_version(doc, f"Before importing {filename}")
        doc["text"] = text
        _push_version(doc, f"Imported {filename}")
        documents.save(doc)
        return jsonify({
            "filename": filename,
            "word_count": len(words(text)),
            "char_count": len(text),
            "paragraph_count": len(split_paragraphs(text)),
            "document": _public_doc(doc),
        })

    # -- analyze -----------------------------------------------------------
    @app.post("/api/documents/<did>/analyze")
    def api_analyze(did):
        doc, err = _get_doc(did)
        if err:
            return err
        data, _ = _json_body(required=False)
        text = (data or {}).get("text", doc.get("text", ""))
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "No text to analyze"}), 400
        if len(text) > 200_000:
            return jsonify({"error": "Text too long (max 200,000 characters)"}), 400
        return jsonify(analyze_text(text))

    # -- rewrite -----------------------------------------------------------
    @app.post("/api/documents/<did>/rewrite")
    def api_rewrite(did):
        doc, err = _get_doc(did)
        if err:
            return err
        data, berr = _json_body()
        if berr:
            return berr
        mode = str(data.get("mode", "natural")).lower()
        if mode not in MODES:
            return jsonify({"error": f"Unknown mode: {mode!r}"}), 400
        try:
            intensity = int(data.get("intensity", 3))
        except (TypeError, ValueError):
            return jsonify({"error": "'intensity' must be an integer 1-5"}), 400
        if not 1 <= intensity <= 5:
            return jsonify({"error": "'intensity' must be between 1 and 5"}), 400
        provider_kind = str(data.get("provider_kind", "offline")).lower()
        if provider_kind not in ("offline", "openai", "gemini", "ollama"):
            return jsonify({"error": f"Unknown provider: {provider_kind!r}"}), 400

        sentences = split_sentences(doc.get("text", ""))
        if not sentences:
            return jsonify({"error": "No text to rewrite"}), 400
        indexes = data.get("sentence_indexes")
        if indexes is not None:
            try:
                selected = sorted({int(i) for i in indexes
                                   if 0 <= int(i) < len(sentences)})
            except (TypeError, ValueError):
                return jsonify({"error": "'sentence_indexes' must be integers"}), 400
            if not selected:
                return jsonify({"error": "No valid sentences selected"}), 400
        else:
            selected = list(range(len(sentences)))

        used_provider = "offline"
        note = "Rewritten with the built-in offline engine (no AI provider)."
        try:
            if provider_kind == "offline":
                results = rewrite_text_offline(
                    doc["text"], mode, intensity, selected)
            else:
                cfg = _provider_cfg(provider_kind)
                stored = settings.get()["providers"].get(provider_kind, {})
                if not stored.get("configured"):
                    return jsonify({"error": f"'{provider_kind}' provider is not "
                                             "configured — add credentials in "
                                             "Settings, or use the offline engine."}), 400
                target = [sentences[i]["text"] for i in selected]
                ai_results = providers.rewrite_with_provider(
                    cfg, target, mode, intensity)
                # Map provider results (0..n of selected) back to doc indexes.
                results = []
                for r, doc_index in zip(ai_results, selected):
                    r = dict(r)
                    r["index"] = doc_index
                    r["original"] = sentences[doc_index]["text"]
                    results.append(r)
                used_provider = provider_kind
                note = f"Rewritten with {provider_kind}."
        except providers.ProviderError as exc:
            return jsonify({"error": str(exc)}), 502

        suggestions = []
        for r in results:
            suggestions.append({
                "id": new_id("s"),
                "sentence_index": r["index"],
                "original": r["original"],
                "rewritten": r["rewritten"],
                "notes": r.get("notes", []),
                "changed": bool(r.get("changed")),
                "accepted": False,
            })
        doc["pending"] = {
            "id": new_id("rw"),
            "mode": mode,
            "intensity": intensity,
            "used_provider": used_provider,
            "note": note,
            "suggestions": suggestions,
        }
        documents.save(doc)
        return jsonify({
            "pending_id": doc["pending"]["id"],
            "used_provider": used_provider,
            "note": note,
            "suggestions": suggestions,
        })

    @app.post("/api/documents/<did>/suggestions/apply")
    def api_apply_suggestions(did):
        doc, err = _get_doc(did)
        if err:
            return err
        data, berr = _json_body()
        if berr:
            return berr
        pending = doc.get("pending")
        if not pending:
            return jsonify({"error": "No pending suggestions"}), 400
        wanted = data.get("suggestion_ids")
        if not isinstance(wanted, list) or not wanted:
            return jsonify({"error": "'suggestion_ids' must be a non-empty list"}), 400
        by_id = {s["id"]: s for s in pending["suggestions"]}
        chosen = [by_id[i] for i in wanted if i in by_id and by_id[i]["changed"]]
        if not chosen:
            return jsonify({"error": "No valid changed suggestions selected"}), 400

        sentences = split_sentences(doc.get("text", ""))
        repl = {s["sentence_index"]: s["rewritten"] for s in chosen}
        new_parts = []
        for i, s in enumerate(sentences):
            new_parts.append(repl.get(i, s["text"]))
        new_text = " ".join(new_parts)

        _push_version(doc, f"Rewrite applied ({pending['mode']}, "
                           f"intensity {pending['intensity']}, "
                           f"{len(chosen)} suggestion(s), "
                           f"via {pending['used_provider']})")
        doc["text"] = new_text
        for s in pending["suggestions"]:
            if s["id"] in {c["id"] for c in chosen}:
                s["accepted"] = True
        doc["pending"] = None
        documents.save(doc)
        return jsonify(_public_doc(doc))

    @app.post("/api/documents/<did>/suggestions/discard")
    def api_discard_suggestions(did):
        doc, err = _get_doc(did)
        if err:
            return err
        doc["pending"] = None
        documents.save(doc)
        return jsonify({"ok": True})

    # -- versions (history / undo) -----------------------------------------
    @app.post("/api/documents/<did>/versions/restore")
    def api_restore_version(did):
        doc, err = _get_doc(did)
        if err:
            return err
        data, berr = _json_body()
        if berr:
            return berr
        vid = data.get("version_id")
        version = next((v for v in doc.get("versions", []) if v["id"] == vid), None)
        if version is None:
            return jsonify({"error": "Version not found"}), 404
        _push_version(doc, "Before restore")
        doc["text"] = version["text"]
        _push_version(doc, f"Restored: {version.get('label', '')}")
        documents.save(doc)
        return jsonify(_public_doc(doc))

    # -- diff ---------------------------------------------------------------
    @app.post("/api/diff")
    def api_diff():
        data, err = _json_body()
        if err:
            return err
        a = data.get("a", "")
        b = data.get("b", "")
        if not isinstance(a, str) or not isinstance(b, str):
            return jsonify({"error": "'a' and 'b' must be strings"}), 400
        return jsonify({"ops": word_diff(a, b)})

    # -- export -------------------------------------------------------------
    @app.post("/api/documents/<did>/export")
    def api_export(did):
        doc, err = _get_doc(did)
        if err:
            return err
        data, berr = _json_body()
        if berr:
            return berr
        fmt = str(data.get("format", "")).lower()
        if fmt not in ("txt", "docx", "pdf"):
            return jsonify({"error": "'format' must be one of: txt, docx, pdf"}), 400
        kind = str(data.get("kind", "revised")).lower()
        if kind not in ("original", "revised", "comparison"):
            return jsonify({"error": "'kind' must be original, revised or comparison"}), 400

        if kind == "original":
            versions = doc.get("versions", [])
            text = versions[0]["text"] if versions else doc.get("text", "")
            original_text = text
        elif kind == "comparison":
            versions = doc.get("versions", [])
            original_text = versions[0]["text"] if versions else doc.get("text", "")
            text = doc.get("text", "")
        else:
            text = doc.get("text", "")
            original_text = text

        title = doc.get("title", "Untitled")
        try:
            if fmt == "txt":
                import export_txt
                payload = export_txt.export_txt(title, text, kind)
                validation = {"ok": bool(payload.strip()),
                              "checks": [{"name": "non_empty",
                                          "passed": bool(payload.strip())}]}
            elif fmt == "docx":
                import export_docx
                payload = export_docx.export_docx(title, text, kind, original_text)
                validation = export_docx.validate_docx(payload)
            else:
                import export_pdf
                payload = export_pdf.export_pdf(title, text, kind, original_text)
                validation = export_pdf.validate_pdf(payload)
        except Exception as exc:  # noqa: BLE001 — report, don't crash
            return jsonify({"error": f"Export failed: {exc}"}), 500

        if not validation.get("ok"):
            failed = [c for c in validation.get("checks", []) if not c.get("passed")]
            detail = "; ".join(c.get("detail", c.get("name", "")) for c in failed[:3])
            return jsonify({"error": f"Export validation failed: {detail}"}), 500

        out_dir = root / "exports" / doc["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "document"
        filename = f"{slug}-{kind}.{fmt}"
        (out_dir / filename).write_bytes(payload)
        return jsonify({
            "ok": True,
            "filename": filename,
            "validation": validation,
            "download_url": f"/api/download/{doc['id']}?kind={kind}&format={fmt}",
        })

    @app.get("/api/download/<did>")
    def api_download(did):
        kind = request.args.get("kind", "revised")
        fmt = request.args.get("format", "txt")
        if fmt not in ("txt", "docx", "pdf"):
            return jsonify({"error": "Unknown format"}), 404
        out_dir = root / "exports" / did
        if not out_dir.is_dir():
            return jsonify({"error": "No exports found for this document"}), 404
        candidates = sorted(out_dir.glob(f"*-{kind}.{fmt}"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            return jsonify({"error": "No exports found for this document"}), 404
        return send_file(candidates[0], as_attachment=True,
                         download_name=candidates[0].name)

    # -- modes --------------------------------------------------------------
    @app.get("/api/modes")
    def api_modes():
        return jsonify({
            "modes": [
                {"id": mid, "name": m["name"], "description": m["description"]}
                for mid, m in MODES.items()
            ],
            "intensities": [
                {"level": lvl, "label": label}
                for lvl, label in INTENSITY_LABELS.items()
            ],
        })

    # -- settings -----------------------------------------------------------
    @app.get("/api/settings")
    def api_get_settings():
        return jsonify(settings.public_view())

    @app.post("/api/settings")
    def api_set_settings():
        data, err = _json_body()
        if err:
            return err
        provider = str(data.get("provider", "")).lower()
        if provider not in ("openai", "gemini", "ollama"):
            return jsonify({"error": "'provider' must be one of: openai, gemini, ollama"}), 400
        config = data.get("config")
        if not isinstance(config, dict):
            return jsonify({"error": "'config' must be an object"}), 400
        try:
            entry = settings.set_provider(provider, config)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "configured": bool(entry.get("configured"))})

    @app.post("/api/settings/test")
    def api_test_settings():
        data, err = _json_body()
        if err:
            return err
        provider = str(data.get("provider", "")).lower()
        if provider not in ("openai", "gemini", "ollama"):
            return jsonify({"error": "'provider' must be one of: openai, gemini, ollama"}), 400
        stored = settings.get()["providers"].get(provider, {})
        if not stored.get("configured"):
            return jsonify({"ok": False, "error": f"'{provider}' provider is not "
                                                   "configured — add credentials in Settings."})
        try:
            providers.test_connection(_provider_cfg(provider))
        except providers.ProviderError as exc:
            return jsonify({"ok": False, "error": str(exc)})
        return jsonify({"ok": True})

    # -- roadmap info --------------------------------------------------------
    @app.get("/api/roadmap")
    def api_roadmap():
        return jsonify({
            "note": "These features are planned for future versions and are "
                    "not in v1. They are shown in the UI as Roadmap items.",
            "items": [
                "Third-party AI detector integrations (GPTZero, Originality.ai, Copyleaks) via authorized APIs",
                "Plagiarism database checks via licensed APIs",
                "OCR for scanned-image PDFs",
                "Cloud imports (Google Drive, OneDrive, Dropbox)",
                "Multilingual analysis and rewriting beyond English",
                "Personal writing-style profiles learned from your samples",
                "Tracked-changes DOCX export",
            ],
        })

    # -- frontend -----------------------------------------------------------
    @app.get("/")
    def index():
        index_path = BASE_DIR / "static" / "index.html"
        if index_path.exists():
            return send_from_directory(str(BASE_DIR / "static"), "index.html")
        return (
            "<html><head><title>HumanWrite AI</title></head>"
            "<body style='font-family:sans-serif;padding:40px'>"
            "<h1>HumanWrite AI v1</h1>"
            "<p>Backend is running. The frontend (static/index.html) is not installed yet.</p>"
            "<p>API: <code>/api/documents</code> · <code>/api/modes</code> · "
            "<code>/api/settings</code> · <code>/api/roadmap</code></p>"
            "</body></html>"
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=PORT)
