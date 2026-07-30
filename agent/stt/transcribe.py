from pathlib import Path

from faster_whisper import WhisperModel

from agent import config

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def transcribe(audio_path: Path) -> str:
    segments, _info = _get_model().transcribe(str(audio_path))
    return " ".join(segment.text.strip() for segment in segments).strip()
