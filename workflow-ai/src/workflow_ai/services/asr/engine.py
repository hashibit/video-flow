"""ASR engine abstraction.

Wraps FunASR (or any compatible backend) to transcribe an audio URL into
a structured list of utterances with word-level timestamps.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Word:
    text: str
    start_time: int  # milliseconds
    end_time: int
    blank_duration: int = 0
    pronounce: str = ""


@dataclass
class Utterance:
    text: str
    start_time: int
    end_time: int
    definite: bool = True
    words: list[Word] = field(default_factory=list)


@dataclass
class ASRResult:
    id: str
    text: str
    utterances: list[Utterance] = field(default_factory=list)


class ASREngine:
    """Offline ASR engine backed by FunASR.

    Parameters
    ----------
    model:
        Model name recognised by FunASR, e.g. ``"paraformer-zh"``.
    device:
        Inference device: ``"cpu"`` or ``"cuda"``.
    """

    def __init__(self, model: str = "paraformer-zh", device: str = "cpu") -> None:
        self.model_name = model
        self.device = device
        self._pipeline: Any = None

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        try:
            from funasr import AutoModel  # type: ignore[import-untyped]
            self._pipeline = AutoModel(model=self.model_name, device=self.device)
            logger.info("ASR model loaded: %s on %s", self.model_name, self.device)
        except ImportError as exc:
            raise RuntimeError(
                "FunASR is not installed. Install it with: pip install funasr"
            ) from exc

    def transcribe(self, audio_url: str, audio_format: str = "wav") -> ASRResult:
        """Transcribe audio from *audio_url* and return an :class:`ASRResult`."""
        self._load()
        assert self._pipeline is not None

        logger.info("ASR transcribing: %s", audio_url)
        raw = self._pipeline.generate(input=audio_url, batch_size_s=300)

        return self._parse(raw)

    def _parse(self, raw: list[dict]) -> ASRResult:
        utterances: list[Utterance] = []
        full_text_parts: list[str] = []

        for seg in raw:
            text = seg.get("text", "")
            full_text_parts.append(text)
            timestamps = seg.get("timestamp", [])  # list of [start_ms, end_ms] per char

            words: list[Word] = []
            if timestamps:
                for char, (start, end) in zip(text, timestamps):
                    words.append(Word(text=char, start_time=start, end_time=end))

            start_time = timestamps[0][0] if timestamps else 0
            end_time = timestamps[-1][1] if timestamps else 0
            utterances.append(Utterance(
                text=text,
                start_time=start_time,
                end_time=end_time,
                words=words,
            ))

        return ASRResult(
            id="",
            text=" ".join(full_text_parts),
            utterances=utterances,
        )
