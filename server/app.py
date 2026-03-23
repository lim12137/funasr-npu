from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile
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
        upload_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(audio_file.filename or "").suffix or ".wav"
        temp_audio_path = upload_dir / f"{uuid4().hex}{suffix}"

        try:
            with temp_audio_path.open("wb") as file_handle:
                while chunk := await audio_file.read(1024 * 1024):
                    file_handle.write(chunk)

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
            if temp_audio_path.exists():
                temp_audio_path.unlink()

        return {
            "code": "OK",
            "engine": ENGINE_NAME,
            "model_dir": str(resolved_model_dir),
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "result": infer_result,
        }

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

    if completed.returncode != 0:
        stderr_text = (completed.stderr or "").strip()
        stdout_text = (completed.stdout or "").strip()
        reason = stderr_text or stdout_text or "无输出"
        raise RuntimeError(f"推理命令失败（exit={completed.returncode}）: {reason}")

    return _parse_json_output(completed.stdout or "")
