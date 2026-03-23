from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

PLACEHOLDER_MESSAGE = "当前镜像仅提供服务骨架，未接入真实推理引擎"


class ASRRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    audio_url: str | None = None
    audio_base64: str | None = None


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

    @application.post("/asr", status_code=501)
    def asr(_: ASRRequest) -> dict[str, str]:
        return {
            "code": "NOT_IMPLEMENTED",
            "message": PLACEHOLDER_MESSAGE,
            "engine": "none",
        }

    return application
