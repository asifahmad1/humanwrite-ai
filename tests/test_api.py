"""API end-to-end tests for HumanWrite AI v1."""

from tests.conftest import DEMO_SENTENCE


def _make_doc_with_text(client, text):
    did = client.post("/api/documents", json={"title": "Flow doc"}).get_json()["id"]
    client.put(f"/api/documents/{did}", json={"text": text})
    return did


def test_create_and_list_documents(client):
    r = client.post("/api/documents", json={"title": "My essay"})
    assert r.status_code == 201
    did = r.get_json()["id"]
    docs = client.get("/api/documents").get_json()
    assert any(d["id"] == did for d in docs)


def test_update_text_creates_version(client, doc_id):
    client.put(f"/api/documents/{doc_id}", json={"text": "Hello world."})
    doc = client.get(f"/api/documents/{doc_id}").get_json()
    assert doc["text"] == "Hello world."
    assert len(doc["versions"]) >= 1


def test_full_flow_analyze_rewrite_apply(client):
    did = _make_doc_with_text(client, DEMO_SENTENCE)

    # Analyze.
    ar = client.post(f"/api/documents/{did}/analyze")
    assert ar.status_code == 200
    analysis = ar.get_json()
    assert analysis["sentences"]
    assert "disclaimer" in analysis
    assert analysis["metrics"]["word_count"] > 0

    # Rewrite offline (no provider configured).
    rr = client.post(f"/api/documents/{did}/rewrite", json={
        "mode": "natural", "intensity": 3, "provider_kind": "offline"})
    assert rr.status_code == 200
    body = rr.get_json()
    assert body["used_provider"] == "offline"
    assert body["suggestions"]
    sug = body["suggestions"][0]
    assert sug["rewritten"] != sug["original"]

    # Apply the suggestion.
    pr = client.post(f"/api/documents/{did}/suggestions/apply",
                     json={"suggestion_ids": [sug["id"]]})
    assert pr.status_code == 200
    doc = pr.get_json()
    assert doc["text"] != DEMO_SENTENCE
    assert not doc["has_pending"]

    # Version history grew.
    assert len(doc["versions"]) >= 2


def test_selective_rewrite(client):
    did = _make_doc_with_text(
        client, "Simple opening line. We utilize this method in order to improve.")
    rr = client.post(f"/api/documents/{did}/rewrite", json={
        "mode": "natural", "intensity": 3, "provider_kind": "offline",
        "sentence_indexes": [0]})
    sugs = rr.get_json()["suggestions"]
    assert len(sugs) == 1
    assert sugs[0]["sentence_index"] == 0


def test_rewrite_requires_configured_provider(client):
    did = _make_doc_with_text(client, DEMO_SENTENCE)
    rr = client.post(f"/api/documents/{did}/rewrite", json={
        "mode": "natural", "intensity": 3, "provider_kind": "openai"})
    assert rr.status_code == 400
    assert "not configured" in rr.get_json()["error"].lower()


def test_restore_version(client):
    did = _make_doc_with_text(client, "Version one text here.")
    client.put(f"/api/documents/{did}", json={"text": "Version two text here."})
    doc = client.get(f"/api/documents/{did}").get_json()
    target = next(v for v in doc["versions"] if "Version one" in v["preview"])
    rr = client.post(f"/api/documents/{did}/versions/restore",
                     json={"version_id": target["id"]})
    assert rr.status_code == 200
    assert "Version one" in rr.get_json()["text"]


def test_diff_endpoint(client):
    r = client.post("/api/diff", json={"a": "the cat sat", "b": "the dog sat"})
    assert r.status_code == 200
    ops = r.get_json()["ops"]
    types = [o["type"] for o in ops]
    assert "del" in types and "ins" in types


def test_modes_endpoint(client):
    r = client.get("/api/modes")
    body = r.get_json()
    assert len(body["modes"]) == 10
    assert len(body["intensities"]) == 5


def test_export_txt(client):
    did = _make_doc_with_text(client, DEMO_SENTENCE)
    r = client.post(f"/api/documents/{did}/export",
                    json={"format": "txt", "kind": "revised"})
    assert r.status_code == 200
    dl = client.get(r.get_json()["download_url"])
    assert dl.status_code == 200
    assert len(dl.data) > 50


def test_export_docx_validated(client):
    did = _make_doc_with_text(client, DEMO_SENTENCE)
    r = client.post(f"/api/documents/{did}/export",
                    json={"format": "docx", "kind": "comparison"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["validation"]["ok"] is True
    dl = client.get(body["download_url"])
    assert dl.data[:2] == b"PK"  # zip container


def test_export_pdf_validated(client):
    did = _make_doc_with_text(client, DEMO_SENTENCE)
    r = client.post(f"/api/documents/{did}/export",
                    json={"format": "pdf", "kind": "revised"})
    assert r.status_code == 200
    assert r.get_json()["validation"]["ok"] is True
    dl = client.get(r.get_json()["download_url"])
    assert dl.data[:4] == b"%PDF"


def test_upload_txt(client, doc_id, tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("First paragraph.\n\nSecond paragraph here.", encoding="utf-8")
    with open(p, "rb") as fh:
        r = client.post(f"/api/documents/{doc_id}/upload",
                        data={"file": (fh, "sample.txt")})
    assert r.status_code == 200
    assert r.get_json()["word_count"] == 5


def test_upload_rejects_bad_type(client, doc_id, tmp_path):
    p = tmp_path / "evil.exe"
    p.write_bytes(b"MZ")
    with open(p, "rb") as fh:
        r = client.post(f"/api/documents/{doc_id}/upload",
                        data={"file": (fh, "evil.exe")})
    assert r.status_code == 400


def test_settings_redact_keys(client):
    client.post("/api/settings", json={
        "provider": "openai",
        "config": {"api_key": "sk-secret-123", "model": "gpt-4o-mini"}})
    public = client.get("/api/settings").get_json()
    blob = str(public)
    assert "sk-secret-123" not in blob
    assert public["providers"]["openai"]["configured"] is True


def test_roadmap_endpoint(client):
    r = client.get("/api/roadmap")
    items = r.get_json()["items"]
    assert any("GPTZero" in i for i in items)
    assert any("OCR" in i for i in items)
