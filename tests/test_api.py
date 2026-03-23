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


def test_asr_invokes_real_command_and_cleans_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    upload_dir = tmp_path / "uploads"

    monkeypatch.setenv("ASR_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("ASR_PYTHON_BIN", "python3")
    monkeypatch.setenv("ASR_INFER_SCRIPT", "/workspace/scripts/run-funasr-infer.py")
    monkeypatch.setenv("FUNASR_REPO_DIR", "/workspace/Fun-ASR-GGUF")
    monkeypatch.setenv("ASR_COMMAND_TIMEOUT_SECONDS", "60")

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    captured_audio_path: Path | None = None

    def fake_run(cmd: list[str], capture_output: bool, text: bool, timeout: int) -> object:
        nonlocal captured_audio_path
        assert cmd[0] == "python3"
        assert cmd[1] == "/workspace/scripts/run-funasr-infer.py"
        assert "--repo-dir" in cmd
        assert "--model-dir" in cmd
        assert "--audio-path" in cmd

        audio_path = Path(cmd[cmd.index("--audio-path") + 1])
        assert audio_path.exists()
        captured_audio_path = audio_path

        class Result:
            returncode = 0
            stdout = '{"text":"识别成功","segments":[]}\n'
            stderr = ""

        return Result()

    monkeypatch.setattr("server.app.subprocess.run", fake_run)

    response = client.post(
        "/asr",
        files={"audio_file": ("demo.wav", b"RIFF....", "audio/wav")},
        data={"language": "中文", "context": "测试上下文"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "OK"
    assert body["engine"] == "funasr-gguf"
    assert body["result"]["text"] == "识别成功"
    assert captured_audio_path is not None
    assert not captured_audio_path.exists()


def test_asr_returns_error_when_command_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(tmp_path / "uploads"))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    def fake_run(_: list[str], capture_output: bool, text: bool, timeout: int) -> object:
        class Result:
            returncode = 2
            stdout = ""
            stderr = "mocked infer failed"

        return Result()

    monkeypatch.setattr("server.app.subprocess.run", fake_run)

    response = client.post(
        "/asr",
        files={"audio_file": ("broken.wav", b"RIFF....", "audio/wav")},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "INFERENCE_COMMAND_FAILED"
    assert "mocked infer failed" in body["message"]


def test_create_app_requires_existing_model_directory(tmp_path: Path) -> None:
    missing_model_dir = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        create_app(model_dir=missing_model_dir)
