from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


def test_healthz_returns_ok(tmp_path: Path) -> None:
    app = create_app(model_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_asr_returns_placeholder_not_implemented(tmp_path: Path) -> None:
    app = create_app(model_dir=tmp_path)
    client = TestClient(app)

    response = client.post("/asr", json={"audio_url": "https://example.com/demo.wav"})

    assert response.status_code == 501
    body = response.json()
    assert body["code"] == "NOT_IMPLEMENTED"
    assert "未接入真实推理引擎" in body["message"]


def test_create_app_requires_existing_model_directory(tmp_path: Path) -> None:
    missing_model_dir = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        create_app(model_dir=missing_model_dir)
