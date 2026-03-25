#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Fun-ASR-GGUF inference and print JSON result.")
    parser.add_argument("--repo-dir", required=True, help="Fun-ASR-GGUF repository directory")
    parser.add_argument("--model-dir", required=True, help="Model directory containing onnx/gguf/tokens files")
    parser.add_argument("--audio-path", required=True, help="Input audio file path")
    parser.add_argument("--language", default=None, help="Language hint")
    parser.add_argument("--context", default=None, help="Optional context prompt")
    parser.add_argument(
        "--onnx-provider",
        default=None,
        help="ONNX provider (CPU/NPU/CUDA/DML/TRT). If omitted, use env ASR_ONNX_PROVIDER (default CPU).",
    )
    parser.add_argument("--vulkan-enable", default="1", help="Whether to enable GPU path in llama backend")
    parser.add_argument("--encoder", default=None, help="Override encoder model path")
    parser.add_argument("--ctc", default=None, help="Override ctc model path")
    parser.add_argument("--decoder", default=None, help="Override decoder gguf path")
    parser.add_argument("--tokens", default=None, help="Override tokens path")
    parser.add_argument("--hotwords-path", default=None, help="Optional hotwords txt path")
    parser.add_argument("--output-json", action="store_true", help="Print JSON only")
    return parser.parse_args()


def _resolve_first_existing(base_dir: Path, candidates: Iterable[str], override: str | None) -> str:
    if override:
        path = Path(override)
        if not path.is_absolute():
            path = base_dir / path
        if path.exists():
            return str(path.resolve())
        raise FileNotFoundError(f"文件不存在: {path}")

    for candidate in candidates:
        path = base_dir / candidate
        if path.exists():
            return str(path.resolve())
    raise FileNotFoundError(f"模型文件不存在，候选: {', '.join(candidates)}")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_onnx_provider(cli_value: str | None) -> str:
    if cli_value and cli_value.strip():
        return cli_value.strip()
    env_value = os.getenv("ASR_ONNX_PROVIDER")
    if env_value and env_value.strip():
        return env_value.strip()
    return "CPU"


def _resolve_npu_execution_provider() -> str:
    return (os.getenv("ASR_NPU_EXECUTION_PROVIDER") or "CANNExecutionProvider").strip() or "CANNExecutionProvider"


def _normalize_provider(value: str) -> str:
    return value.strip().upper()


def _wants_npu_provider(provider: str) -> bool:
    normalized = _normalize_provider(provider)
    return normalized in {"NPU", "ASCEND", "CANN", "CANNEXECUTIONPROVIDER"}


def _ensure_onnxruntime_provider_available(target_provider: str) -> list[str]:
    try:
        import onnxruntime
    except ImportError as exc:  # pragma: no cover - runtime only
        raise RuntimeError(f"未安装 onnxruntime（无法选择 {target_provider}）: {exc}") from exc

    try:
        available = list(onnxruntime.get_available_providers())
    except Exception as exc:  # pragma: no cover - runtime only
        raise RuntimeError(f"读取 onnxruntime providers 失败: {exc}") from exc

    if target_provider not in available:
        raise RuntimeError(
            f"请求使用 {target_provider} 但运行时不可用。onnxruntime.get_available_providers()={available}"
        )

    return available


def _patch_funasr_gguf_for_npu(npu_ep: str) -> None:
    import onnxruntime

    from fun_asr_gguf.inference import ctc_decoder as ctc_decoder_module
    from fun_asr_gguf.inference import encoder as encoder_module

    if getattr(encoder_module.AudioEncoder, "_funasr_npu_patched", False):
        return

    original_encoder_initialize = encoder_module.AudioEncoder._initialize_session
    original_ctc_initialize = ctc_decoder_module.CTCDecoder._initialize_session

    def encoder_initialize_session(self) -> None:  # type: ignore[no-untyped-def]
        if self.onnx_provider not in {"NPU", "ASCEND", "CANN", "CANNEXECUTIONPROVIDER"}:
            return original_encoder_initialize(self)

        session_opts = onnxruntime.SessionOptions()
        session_opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        session_opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
        session_opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            self.dml_pad_to = min(int(getattr(self, "dml_pad_to", 0)), 1)
        except Exception:
            self.dml_pad_to = 1

        providers = [npu_ep, "CPUExecutionProvider"]
        encoder_module.logger.info(
            f"[Encoder] 加载模型: {os.path.basename(self.model_path)} (Providers: {providers})"
        )

        self.sess = onnxruntime.InferenceSession(self.model_path, sess_options=session_opts, providers=providers)

        in_type = self.sess.get_inputs()[0].type
        self.input_dtype = encoder_module.np.float16 if "float16" in in_type else encoder_module.np.float32
        self.warmup()

    def ctc_initialize_session(self) -> None:  # type: ignore[no-untyped-def]
        if self.onnx_provider not in {"NPU", "ASCEND", "CANN", "CANNEXECUTIONPROVIDER"}:
            return original_ctc_initialize(self)

        session_opts = onnxruntime.SessionOptions()
        session_opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        session_opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
        session_opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            self.dml_pad_to = min(int(getattr(self, "dml_pad_to", 0)), 1)
        except Exception:
            self.dml_pad_to = 1

        providers = [npu_ep, "CPUExecutionProvider"]
        ctc_decoder_module.logger.info(f"[CTC] 加载模型: {os.path.basename(self.model_path)} (Providers: {providers})")

        self.sess = onnxruntime.InferenceSession(self.model_path, sess_options=session_opts, providers=providers)

        in_type = self.sess.get_inputs()[0].type
        self.input_dtype = ctc_decoder_module.np.float16 if "float16" in in_type else ctc_decoder_module.np.float32

    encoder_module.AudioEncoder._initialize_session = encoder_initialize_session
    ctc_decoder_module.CTCDecoder._initialize_session = ctc_initialize_session
    encoder_module.AudioEncoder._funasr_npu_patched = True


def main() -> int:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    model_dir = Path(args.model_dir).resolve()
    audio_path = Path(args.audio_path).resolve()

    if not repo_dir.is_dir():
        print(f"[ERROR] repo 目录不存在: {repo_dir}", file=sys.stderr)
        return 2
    if not model_dir.is_dir():
        print(f"[ERROR] model 目录不存在: {model_dir}", file=sys.stderr)
        return 2
    if not audio_path.is_file():
        print(f"[ERROR] 音频文件不存在: {audio_path}", file=sys.stderr)
        return 2

    sys.path.insert(0, str(repo_dir))
    os.chdir(repo_dir)

    from fun_asr_gguf import ASREngineConfig, FunASREngine

    resolved_provider = _resolve_onnx_provider(args.onnx_provider)
    normalized_provider = _normalize_provider(resolved_provider)
    if _wants_npu_provider(normalized_provider):
        npu_ep = _resolve_npu_execution_provider()
        try:
            _ensure_onnxruntime_provider_available(npu_ep)
        except RuntimeError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 3
        _patch_funasr_gguf_for_npu(npu_ep)
        normalized_provider = "NPU"

    encoder_onnx_path = _resolve_first_existing(
        model_dir,
        ["Fun-ASR-Nano-Encoder-Adaptor.int4.onnx", "Fun-ASR-Nano-Encoder-Adaptor.fp16.onnx"],
        args.encoder,
    )
    ctc_onnx_path = _resolve_first_existing(
        model_dir,
        ["Fun-ASR-Nano-CTC.int4.onnx", "Fun-ASR-Nano-CTC.fp16.onnx"],
        args.ctc,
    )
    decoder_gguf_path = _resolve_first_existing(
        model_dir,
        ["Fun-ASR-Nano-Decoder.q5_k.gguf", "Fun-ASR-Nano-Decoder.q4_k.gguf"],
        args.decoder,
    )
    tokens_path = _resolve_first_existing(model_dir, ["tokens.txt"], args.tokens)

    hotwords = []
    if args.hotwords_path:
        hotwords_path = Path(args.hotwords_path)
        if not hotwords_path.is_absolute():
            hotwords_path = repo_dir / hotwords_path
        if hotwords_path.exists():
            hotwords = [
                line.strip()
                for line in hotwords_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]

    config = ASREngineConfig(
        encoder_onnx_path=encoder_onnx_path,
        ctc_onnx_path=ctc_onnx_path,
        decoder_gguf_path=decoder_gguf_path,
        tokens_path=tokens_path,
        hotwords=hotwords,
        onnx_provider=normalized_provider,
        vulkan_enable=_parse_bool(args.vulkan_enable),
        verbose=False,
    )

    engine = FunASREngine(config)
    try:
        result = engine.transcribe(
            str(audio_path),
            language=args.language,
            context=args.context,
            verbose=False,
            srt=False,
            segment_size=60.0,
            overlap=2.0,
        )
    finally:
        engine.cleanup()

    payload = {
        "text": result.text,
        "segments": result.segments,
        "ctc_text": result.ctc_text,
        "hotwords": result.hotwords,
        "timings": {
            "encode": result.timings.encode,
            "ctc": result.timings.ctc,
            "radar": result.timings.radar,
            "prepare": result.timings.prepare,
            "inject": result.timings.inject,
            "llm_generate": result.timings.llm_generate,
            "align": result.timings.align,
            "integrate": result.timings.integrate,
            "total": result.timings.total,
        },
    }

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
