"""Dialogue post-processing pipeline with composable processor stages."""

from abc import ABC, abstractmethod
from functools import reduce

from pypinyin import lazy_pinyin  # pyright: ignore[reportMissingImports]

from workflow_worker.domain.entities.dialogue import Dialogue


class DialogueProcessor(ABC):
    """Abstract base for a single dialogue transformation step."""

    @abstractmethod
    def process(self, dialogue: Dialogue) -> Dialogue: ...

    def __or__(self, other: DialogueProcessor) -> Pipeline:
        return Pipeline([self, other])


class Pipeline(DialogueProcessor):
    """Chains multiple DialogueProcessors left-to-right via reduce."""

    def __init__(self, steps: list[DialogueProcessor]):
        self.steps = steps

    def __or__(self, other: DialogueProcessor) -> Pipeline:
        return Pipeline(self.steps + [other])

    def process(self, dialogue: Dialogue) -> Dialogue:
        return reduce(lambda d, step: step.process(d), self.steps, dialogue)


class PinyinCorrectionProcessor(DialogueProcessor):
    """Replaces near-homophone sequences using pinyin edit-distance of 1."""

    def __init__(
        self,
        pinyin_words: list[str] | None = None,
        white_list: list[str] | None = None,
    ):
        self.pinyin_words = list(pinyin_words) if pinyin_words else []
        self.white_list = set(white_list) if white_list else set()

    def _is_near_homophone(self, cur: str, candidate: str) -> bool:
        cur_py = "".join(lazy_pinyin(cur))
        can_py = "".join(lazy_pinyin(candidate))
        return (
            len(cur_py) == len(can_py)
            and sum(a != b for a, b in zip(cur_py, can_py)) <= 1
        )

    def process(self, dialogue: Dialogue) -> Dialogue:
        idx = 0
        while idx < len(dialogue):
            for word in self.pinyin_words:
                end = idx + len(word)
                if end > len(dialogue):
                    continue
                cur = str(dialogue[idx:end])
                if cur in self.white_list:
                    idx += len(word)
                    break
                if cur != word and self._is_near_homophone(cur, word):
                    dialogue[idx:end] = word
                    break
            idx += 1
        return dialogue


class MistakeCorrectionProcessor(DialogueProcessor):
    """Replaces known misspellings via a correction lookup table."""

    def __init__(self, correction_table: dict[str, str] | None = None):
        self.correction_table = dict(correction_table) if correction_table else {}

    def process(self, dialogue: Dialogue) -> Dialogue:
        i = 0
        while i < len(dialogue):
            for word, new_word in self.correction_table.items():
                end = i + len(word)
                if end <= len(dialogue) and dialogue[i:end] == word:
                    dialogue[i:end] = new_word
            i += 1
        return dialogue


# ── Backward-compatible free-function wrappers ────────────────────────────────

def rewrite_dialogue_pinyin(
    dialogue: Dialogue,
    pinyin_words: list[str] | None = None,
    white_list: list[str] | None = None,
) -> Dialogue:
    return PinyinCorrectionProcessor(pinyin_words, white_list).process(dialogue)


def rewrite_dialogue_mistake(
    dialogue: Dialogue,
    error_word_correction_table: dict[str, str] | None = None,
) -> Dialogue:
    return MistakeCorrectionProcessor(error_word_correction_table).process(dialogue)
