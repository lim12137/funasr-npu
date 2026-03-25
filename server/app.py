from __future__ import annotations

import io
import json
import os
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

ENGINE_NAME = "funasr-gguf"


def create_app(model_dir: str | Path | None = None) -> FastAPI:
    resolved_model_dir = Path(model_dir or os.getenv("MODEL_DIR", "/models")).resolve()
    if not resolved_model_dir.is_dir():
        raise FileNotFoundError(f"模型目录不存在或不可访问: {resolved_model_dir}")

    application = FastAPI(title="funasr-npu HTTP API", version="0.1.0")

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "funasr-npu-http-api",
            "model_dir": str(resolved_model_dir),
        }

    @application.post("/asr", response_model=None)
    async def asr(
        audio_file: UploadFile = File(...),
        language: str | None = Form(default=None),
        context: str | None = Form(default=None),
        onnx_provider: str | None = Form(default=None),
    ) -> JSONResponse | dict[str, object]:
        upload_dir = Path(os.getenv("ASR_UPLOAD_DIR", "/tmp/funasr-upload")).resolve()
        suffix = Path(audio_file.filename or "").suffix or ".wav"
        temp_audio_path: Path | None = None

        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            temp_audio_path = upload_dir / f"{uuid4().hex}{suffix}"
            with temp_audio_path.open("wb") as file_handle:
                while chunk := await audio_file.read(1024 * 1024):
                    file_handle.write(chunk)
        except OSError as exc:
            if temp_audio_path and temp_audio_path.exists():
                try:
                    temp_audio_path.unlink()
                except OSError:
                    pass
            return JSONResponse(
                status_code=500,
                content={
                    "code": "UPLOAD_IO_FAILED",
                    "message": f"上传文件落盘失败: {exc}",
                    "engine": ENGINE_NAME,
                },
            )

        try:
            infer_result = _run_asr_command(
                audio_path=temp_audio_path,
                model_dir=resolved_model_dir,
                language=language,
                context=context,
                onnx_provider=onnx_provider,
            )
        except TimeoutError as exc:
            return JSONResponse(
                status_code=504,
                content={
                    "code": "INFERENCE_COMMAND_TIMEOUT",
                    "message": str(exc),
                    "engine": ENGINE_NAME,
                },
            )
        except RuntimeError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "code": "INFERENCE_COMMAND_FAILED",
                    "message": str(exc),
                    "engine": ENGINE_NAME,
                },
            )
        finally:
            if temp_audio_path and temp_audio_path.exists():
                try:
                    temp_audio_path.unlink()
                except OSError:
                    pass

        return {
            "code": "OK",
            "engine": ENGINE_NAME,
            "model_dir": str(resolved_model_dir),
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "result": infer_result,
        }

    @application.websocket("/ws")
    async def websocket_asr(websocket: WebSocket) -> None:
        await _handle_ws_asr(websocket, resolved_model_dir)

    @application.websocket("/")
    async def websocket_asr_root(websocket: WebSocket) -> None:
        await _handle_ws_asr(websocket, resolved_model_dir)

    return application


def _build_asr_command(
    audio_path: Path,
    model_dir: Path,
    language: str | None,
    context: str | None,
    onnx_provider: str | None,
) -> list[str]:
    python_bin = os.getenv("ASR_PYTHON_BIN", "python3")
    infer_script = os.getenv("ASR_INFER_SCRIPT", "/workspace/scripts/run-funasr-infer.py")
    repo_dir = os.getenv("FUNASR_REPO_DIR", "/workspace/Fun-ASR-GGUF")

    command = [
        python_bin,
        infer_script,
        "--repo-dir",
        repo_dir,
        "--model-dir",
        str(model_dir),
        "--audio-path",
        str(audio_path),
        "--output-json",
    ]

    final_provider = onnx_provider or os.getenv("ASR_ONNX_PROVIDER")
    if final_provider:
        command.extend(["--onnx-provider", final_provider])

    vulkan_enable = os.getenv("ASR_VULKAN_ENABLE")
    if vulkan_enable:
        command.extend(["--vulkan-enable", vulkan_enable])

    if language:
        command.extend(["--language", language])
    if context:
        command.extend(["--context", context])

    return command


def _parse_json_output(stdout: str) -> dict[str, object]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("推理命令输出中未找到可解析 JSON")


def _parse_ws_json_frame(payload: str, frame_name: str) -> dict[str, object]:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{frame_name}不是合法 JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{frame_name}必须是 JSON 对象")
    return parsed


def _select_ws_subprotocol(websocket: WebSocket) -> str | None:
    header_value = websocket.headers.get("sec-websocket-protocol")
    if not header_value:
        return None
    candidates = [value.strip() for value in header_value.split(",") if value.strip()]
    for candidate in candidates:
        if candidate.lower() == "binary":
            return "binary"
    return None


def _parse_audio_fs(payload: dict[str, object]) -> int:
    value = payload.get("audio_fs")
    if value is None:
        return 16000
    if isinstance(value, (int, float)):
        parsed = int(value)
        return parsed if parsed > 0 else 16000
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            parsed = int(stripped)
            return parsed if parsed > 0 else 16000
    return 16000


def _is_riff_wave(payload: bytes) -> bool:
    return len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WAVE"


def _wrap_pcm_to_wav(payload: bytes, audio_fs: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_writer:
        wav_writer.setnchannels(1)
        wav_writer.setsampwidth(2)
        wav_writer.setframerate(audio_fs)
        wav_writer.writeframes(payload)
    return buffer.getvalue()


def _coerce_to_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def _is_ws_finished_frame(frame_payload: dict[str, object]) -> bool:
    speaking = _coerce_to_bool(frame_payload.get("is_speaking"))
    finished = _coerce_to_bool(frame_payload.get("is_finished"))
    return speaking is False or finished is True


def _get_optional_text(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


async def _handle_ws_asr(websocket: WebSocket, model_dir: Path) -> None:
    subprotocol = _select_ws_subprotocol(websocket)
    await websocket.accept(subprotocol=subprotocol)

    temp_audio_path: Path | None = None
    ws_config: dict[str, object] = {}
    audio_buffer = bytearray()

    try:
        first_frame = await websocket.receive_text()
        ws_config = _parse_ws_json_frame(first_frame, "首帧配置")
        wav_name = str(ws_config.get("wav_name") or f"{uuid4().hex}.wav")
        wav_format = str(ws_config.get("wav_format") or Path(wav_name).suffix.lstrip(".") or "wav")
        mode = str(ws_config.get("mode") or "offline")
        audio_fs = _parse_audio_fs(ws_config)

        while True:
            frame = await websocket.receive()
            frame_type = frame.get("type")
            if frame_type == "websocket.disconnect":
                return

            frame_bytes = frame.get("bytes")
            if isinstance(frame_bytes, (bytes, bytearray)):
                audio_buffer.extend(frame_bytes)
                continue

            frame_text = frame.get("text")
            if isinstance(frame_text, str):
                frame_payload = _parse_ws_json_frame(frame_text, "结束帧")
                if _is_ws_finished_frame(frame_payload):
                    break
    except WebSocketDisconnect:
        return
    except ValueError as exc:
        await websocket.send_json({"code": "WS_BAD_REQUEST", "message": str(exc), "engine": ENGINE_NAME})
        await websocket.close(code=1003)
        return

    if not audio_buffer:
        await websocket.send_json(
            {"code": "WS_BAD_REQUEST", "message": "未接收到音频二进制数据", "engine": ENGINE_NAME}
        )
        await websocket.close(code=1003)
        return

    upload_dir = Path(os.getenv("ASR_UPLOAD_DIR", "/tmp/funasr-upload")).resolve()
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        audio_bytes = bytes(audio_buffer)
        if _is_riff_wave(audio_bytes):
            payload = audio_bytes
        else:
            payload = _wrap_pcm_to_wav(audio_bytes, audio_fs)
        temp_audio_path = upload_dir / f"{uuid4().hex}.wav"
        temp_audio_path.write_bytes(payload)
    except OSError as exc:
        await websocket.send_json(
            {"code": "UPLOAD_IO_FAILED", "message": f"音频落盘失败: {exc}", "engine": ENGINE_NAME}
        )
        await websocket.close(code=1011)
        return

    language = _get_optional_text(ws_config, "language")
    context = _get_optional_text(ws_config, "context")
    onnx_provider = _get_optional_text(ws_config, "onnx_provider")

    try:
        infer_result = _run_asr_command(
            audio_path=temp_audio_path,
            model_dir=model_dir,
            language=language,
            context=context,
            onnx_provider=onnx_provider,
        )
    except TimeoutError as exc:
        await websocket.send_json(
            {"code": "INFERENCE_COMMAND_TIMEOUT", "message": str(exc), "engine": ENGINE_NAME}
        )
        await websocket.close(code=1011)
        return
    except RuntimeError as exc:
        await websocket.send_json(
            {"code": "INFERENCE_COMMAND_FAILED", "message": str(exc), "engine": ENGINE_NAME}
        )
        await websocket.close(code=1011)
        return
    finally:
        if temp_audio_path and temp_audio_path.exists():
            try:
                temp_audio_path.unlink()
            except OSError:
                pass

    await websocket.send_json(
        {
            "code": "OK",
            "engine": ENGINE_NAME,
            "text": str(infer_result.get("text", "")),
            "mode": mode,
            "wav_name": wav_name,
            "wav_format": wav_format,
            "audio_fs": ws_config.get("audio_fs"),
            "hotwords": ws_config.get("hotwords"),
            "result": infer_result,
        }
    )


def _run_asr_command(
    audio_path: Path,
    model_dir: Path,
    language: str | None,
    context: str | None,
    onnx_provider: str | None,
) -> dict[str, object]:
    command = _build_asr_command(
        audio_path=audio_path,
        model_dir=model_dir,
        language=language,
        context=context,
        onnx_provider=onnx_provider,
    )

    timeout_seconds = int(os.getenv("ASR_COMMAND_TIMEOUT_SECONDS", "600"))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"推理命令超时（>{timeout_seconds}s）: {' '.join(command)}") from exc
    except OSError as exc:
        raise RuntimeError(f"推理命令启动失败: {exc}") from exc

    if completed.returncode != 0:
        stderr_text = (completed.stderr or "").strip()
        stdout_text = (completed.stdout or "").strip()
        reason = stderr_text or stdout_text or "无输出"
        raise RuntimeError(f"推理命令失败（exit={completed.returncode}）: {reason}")

    return _parse_json_output(completed.stdout or "")
