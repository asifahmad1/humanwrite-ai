"""Tests for analyzer.py — honest stylistic analysis, no authorship claims."""

from analyzer import DISCLAIMER, analyze_text
from tests.conftest import DEMO_SENTENCE


def test_disclaimer_present_and_honest():
    result = analyze_text(DEMO_SENTENCE)
    assert "disclaimer" in result
    d = result["disclaimer"].lower()
    assert "do not establish" in d or "does not establish" in d
    assert "ai" in d


def test_demo_sentence_gets_flags():
    result = analyze_text(DEMO_SENTENCE)
    assert len(result["sentences"]) == 1
    types = {f["type"] for f in result["sentences"][0]["flags"]}
    # The demo sentence is formal/wordy with transitions.
    assert "formality" in types or "transition" in types


def test_no_authorship_claim_anywhere():
    text = ("The experiment was conducted carefully. Furthermore, the results "
            "were analyzed thoroughly. The data was processed by the team.")
    result = analyze_text(text)
    blob = str(result).lower()
    assert "ai-generated" not in blob
    assert "written by ai" not in blob
    assert "detector" not in blob
    assert "probability" not in blob or "authorship" not in blob


def test_metrics_sane():
    result = analyze_text("The cat sat on the mat. Dogs bark loudly at night.")
    m = result["metrics"]
    assert m["word_count"] == 11
    assert m["sentence_count"] == 2
    assert m["flesch_reading_ease"] > 80
    assert m["paragraph_count"] == 1


def test_passive_flagged():
    result = analyze_text("The report was written by the team.")
    types = {f["type"] for f in result["sentences"][0]["flags"]}
    assert "passive_voice" in types


def test_long_sentence_flagged():
    long_text = " ".join(["word"] * 45) + "."
    result = analyze_text(long_text)
    types = {f["type"] for f in result["sentences"][0]["flags"]}
    assert "long_sentence" in types


def test_empty_text_rejected_by_api(client, doc_id):
    resp = client.post(f"/api/documents/{doc_id}/analyze", json={"text": "  "})
    assert resp.status_code == 400
