"""Pytest fixtures for HumanWrite AI v1."""

from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(data_root=tmp_path / "data")
    app.config.update({"TESTING": True})
    with app.test_client() as c:
        yield c


@pytest.fixture()
def doc_id(client):
    resp = client.post("/api/documents", json={"title": "Test doc"})
    assert resp.status_code == 201
    return resp.get_json()["id"]


DEMO_SENTENCE = (
    "Artificial intelligence has significantly revolutionized the educational "
    "landscape, providing numerous innovative opportunities for enhancing "
    "teaching methodologies and facilitating effective learning experiences."
)
