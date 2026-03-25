import io
import json
import subprocess
from pathlib import Path
import wave

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


def _write_minimal_wav(path: Path, sample_rate: int = 16000) -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_writer:
        wav_writer.setnchannels(1)
        wav_writer.setsampwidth(2)
        wav_writer.setframerate(sample_rate)
        wav_writer.writeframes(b"\x00\x00")
    path.write_bytes(buffer.getvalue())


def test_healthz_returns_ok(tmp_path: Path) -> None:
    app = create_app(model_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_asr_returns_structured_error_when_upload_dir_creation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()

    upload_dir = (tmp_path / "uploads").resolve()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(upload_dir))

    app = create_app(model_dir=model_dir)
    client = TestClient(app, raise_server_exceptions=False)

    original_mkdir = Path.mkdir

    def fake_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        if self.resolve() == upload_dir:
            raise OSError("mocked mkdir failure")
        original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.mkdir", fake_mkdir)

    response = client.post(
        "/asr",
        files={"audio_file": ("mkdir-failed.wav", b"RIFF....", "audio/wav")},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "UPLOAD_IO_FAILED"
    assert "mocked mkdir failure" in body["message"]
    assert body["engine"] == "funasr-gguf"


def test_asr_cleans_temp_file_when_upload_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()

    upload_dir = (tmp_path / "uploads").resolve()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(upload_dir))

    class FixedUUID:
        hex = "fixed-audio-id"

    expected_temp_audio_path = upload_dir / "fixed-audio-id.wav"
    unlink_attempted = False

    app = create_app(model_dir=model_dir)
    client = TestClient(app, raise_server_exceptions=False)

    original_open = Path.open
    original_unlink = Path.unlink

    class FailingWriter:
        def __init__(self, target_path: Path) -> None:
            self.target_path = target_path

        def __enter__(self) -> "FailingWriter":
            self.target_path.touch(exist_ok=True)
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def write(self, _: bytes) -> int:
            raise OSError("mocked write failure")

    def fake_open(self: Path, mode: str = "r", *args: object, **kwargs: object) -> object:
        if self.resolve() == expected_temp_audio_path and mode == "wb":
            return FailingWriter(self)
        return original_open(self, mode, *args, **kwargs)

    def fake_unlink(self: Path, *args: object, **kwargs: object) -> None:
        nonlocal unlink_attempted
        if self.resolve() == expected_temp_audio_path:
            unlink_attempted = True
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr("server.app.uuid4", lambda: FixedUUID())
    monkeypatch.setattr("pathlib.Path.open", fake_open)
    monkeypatch.setattr("pathlib.Path.unlink", fake_unlink)

    response = client.post(
        "/asr",
        files={"audio_file": ("write-failed.wav", b"RIFF....", "audio/wav")},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "UPLOAD_IO_FAILED"
    assert "mocked write failure" in body["message"]
    assert body["engine"] == "funasr-gguf"
    assert unlink_attempted or not expected_temp_audio_path.exists()


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


def test_asr_converts_non_wav_with_ffmpeg_and_cleans_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(upload_dir))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    converted_path: Path | None = None
    source_path: Path | None = None

    def fake_convert(src_path: Path, dst_path: Path, sample_rate: int) -> None:
        nonlocal converted_path, source_path
        source_path = src_path
        converted_path = dst_path
        assert sample_rate == 16000
        _write_minimal_wav(dst_path, sample_rate)

    captured_audio_path: Path | None = None

    def fake_run_asr_command(
        audio_path: Path,
        model_dir: Path,
        language: str | None,
        context: str | None,
        onnx_provider: str | None,
    ) -> dict[str, object]:
        nonlocal captured_audio_path
        captured_audio_path = audio_path
        assert audio_path.suffix == ".wav"
        assert audio_path.read_bytes()[:4] == b"RIFF"
        return {"text": "mp3 ok"}

    monkeypatch.setattr("server.app._convert_to_wav_with_ffmpeg", fake_convert, raising=False)
    monkeypatch.setattr("server.app._run_asr_command", fake_run_asr_command)

    response = client.post(
        "/asr",
        files={"audio_file": ("demo.mp3", b"FAKE_MP3_CONTENT", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert captured_audio_path is not None
    assert converted_path is not None
    assert source_path is not None
    assert captured_audio_path == converted_path
    assert not source_path.exists()
    assert not converted_path.exists()


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


def test_asr_returns_structured_error_when_command_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(tmp_path / "uploads"))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    def fake_run(_: list[str], capture_output: bool, text: bool, timeout: int) -> object:
        raise FileNotFoundError("python3 not found")

    monkeypatch.setattr("server.app.subprocess.run", fake_run)

    response = client.post(
        "/asr",
        files={"audio_file": ("cannot-start.wav", b"RIFF....", "audio/wav")},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "INFERENCE_COMMAND_FAILED"
    assert "python3 not found" in body["message"]


def test_asr_timeout_response_not_overridden_by_cleanup_unlink_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(tmp_path / "uploads"))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    def fake_run(_: list[str], capture_output: bool, text: bool, timeout: int) -> object:
        raise subprocess.TimeoutExpired(cmd=["python3", "infer.py"], timeout=timeout)

    original_unlink = Path.unlink

    def fake_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.suffix == ".wav":
            raise OSError("mocked unlink failure")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr("server.app.subprocess.run", fake_run)
    monkeypatch.setattr("pathlib.Path.unlink", fake_unlink)

    response = client.post(
        "/asr",
        files={"audio_file": ("timeout.wav", b"RIFF....", "audio/wav")},
    )

    assert response.status_code == 504
    body = response.json()
    assert body["code"] == "INFERENCE_COMMAND_TIMEOUT"


def test_ws_asr_accepts_is_speaking_false_end_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(tmp_path / "uploads"))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    captured_audio_path: Path | None = None

    def fake_run_asr_command(
        audio_path: Path,
        model_dir: Path,
        language: str | None,
        context: str | None,
        onnx_provider: str | None,
    ) -> dict[str, object]:
        nonlocal captured_audio_path
        captured_audio_path = audio_path
        wav_bytes = audio_path.read_bytes()
        assert wav_bytes[:4] == b"RIFF"
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_reader:
            assert wav_reader.getnchannels() == 1
            assert wav_reader.getsampwidth() == 2
            assert wav_reader.getframerate() == 16000
            assert wav_reader.readframes(wav_reader.getnframes()) == b"abc123"
        assert language == "zh"
        assert context is None
        assert onnx_provider is None
        return {"text": "离线识别成功"}

    monkeypatch.setattr("server.app._run_asr_command", fake_run_asr_command)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(
            json.dumps(
                {
                    "mode": "offline",
                    "wav_name": "demo.wav",
                    "wav_format": "wav",
                    "audio_fs": 16000,
                    "language": "zh",
                    "hotwords": "阿里巴巴 20",
                }
            )
        )
        websocket.send_bytes(b"abc")
        websocket.send_bytes(b"123")
        websocket.send_text(json.dumps({"is_speaking": False}))
        result = websocket.receive_json()

    assert result["text"] == "离线识别成功"
    assert result["mode"] == "offline"
    assert result["wav_name"] == "demo.wav"
    assert result["wav_format"] == "wav"
    assert result["audio_fs"] == 16000
    assert result["hotwords"] == "阿里巴巴 20"
    assert captured_audio_path is not None
    assert not captured_audio_path.exists()


def test_ws_asr_accepts_is_finished_true_end_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(tmp_path / "uploads"))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    def fake_run_asr_command(
        audio_path: Path,
        model_dir: Path,
        language: str | None,
        context: str | None,
        onnx_provider: str | None,
    ) -> dict[str, object]:
        wav_bytes = audio_path.read_bytes()
        assert wav_bytes[:4] == b"RIFF"
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_reader:
            assert wav_reader.getnchannels() == 1
            assert wav_reader.getsampwidth() == 2
            assert wav_reader.getframerate() == 16000
            assert wav_reader.readframes(wav_reader.getnframes()) == b"xyzz"
        return {"text": "finished 帧也能识别"}

    monkeypatch.setattr("server.app._run_asr_command", fake_run_asr_command)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(
            json.dumps(
                {
                    "mode": "offline",
                    "wav_name": "finished.pcm",
                    "wav_format": "pcm",
                    "audio_fs": 16000,
                    "hotwords": {"北京": 30},
                }
            )
        )
        websocket.send_bytes(b"xyzz")
        websocket.send_text(json.dumps({"is_finished": True}))
        result = websocket.receive_json()

    assert result["text"] == "finished 帧也能识别"
    assert result["mode"] == "offline"
    assert result["wav_name"] == "finished.pcm"
    assert result["hotwords"] == {"北京": 30}


def test_ws_root_accepts_binary_subprotocol_and_wraps_pcm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(tmp_path / "uploads"))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    captured_audio_path: Path | None = None

    def fake_run_asr_command(
        audio_path: Path,
        model_dir: Path,
        language: str | None,
        context: str | None,
        onnx_provider: str | None,
    ) -> dict[str, object]:
        nonlocal captured_audio_path
        captured_audio_path = audio_path
        wav_bytes = audio_path.read_bytes()
        assert wav_bytes[:4] == b"RIFF"
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_reader:
            assert wav_reader.getnchannels() == 1
            assert wav_reader.getsampwidth() == 2
            assert wav_reader.getframerate() == 16000
            assert wav_reader.readframes(wav_reader.getnframes()) == b"\x01\x02\x03\x04"
        return {"text": "root pcm ok"}

    monkeypatch.setattr("server.app._run_asr_command", fake_run_asr_command)

    with client.websocket_connect("/", subprotocols=["binary"]) as websocket:
        assert websocket.accepted_subprotocol == "binary"
        websocket.send_text(
            json.dumps(
                {
                    "mode": "offline",
                    "wav_name": "root-raw.pcm",
                    "wav_format": "pcm",
                    "audio_fs": 16000,
                }
            )
        )
        websocket.send_bytes(b"\x01\x02\x03\x04")
        websocket.send_text(json.dumps({"is_speaking": False}))
        result = websocket.receive_json()

    assert result["text"] == "root pcm ok"
    assert result["wav_format"] == "pcm"
    assert captured_audio_path is not None
    assert not captured_audio_path.exists()


def test_ws_asr_converts_mp3_with_ffmpeg_and_cleans_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("ASR_UPLOAD_DIR", str(upload_dir))

    app = create_app(model_dir=model_dir)
    client = TestClient(app)

    converted_path: Path | None = None
    source_path: Path | None = None

    def fake_convert(src_path: Path, dst_path: Path, sample_rate: int) -> None:
        nonlocal converted_path, source_path
        source_path = src_path
        converted_path = dst_path
        assert sample_rate == 16000
        _write_minimal_wav(dst_path, sample_rate)

    captured_audio_path: Path | None = None

    def fake_run_asr_command(
        audio_path: Path,
        model_dir: Path,
        language: str | None,
        context: str | None,
        onnx_provider: str | None,
    ) -> dict[str, object]:
        nonlocal captured_audio_path
        captured_audio_path = audio_path
        assert audio_path.read_bytes()[:4] == b"RIFF"
        return {"text": "ws mp3 ok"}

    monkeypatch.setattr("server.app._convert_to_wav_with_ffmpeg", fake_convert, raising=False)
    monkeypatch.setattr("server.app._run_asr_command", fake_run_asr_command)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(
            json.dumps(
                {
                    "mode": "offline",
                    "wav_name": "demo.mp3",
                    "wav_format": "mp3",
                    "audio_fs": 16000,
                }
            )
        )
        websocket.send_bytes(b"FAKE_MP3_BYTES")
        websocket.send_text(json.dumps({"is_finished": True}))
        result = websocket.receive_json()

    assert result["text"] == "ws mp3 ok"
    assert converted_path is not None
    assert source_path is not None
    assert captured_audio_path == converted_path
    assert not source_path.exists()
    assert not converted_path.exists()
