from typing import Any

from pydantic import BaseModel


class DetectedBannedWord(BaseModel):
    """Detected Banned Words

    Attributes:
        start_time (int): start time of the utterance
        banned_word (str): banned word
        text (str): text of the utterance
    """

    start_time: int
    end_time: int
    banned_word: str
    text: str


class BannedWordDetectionResult(BaseModel):
    """Banned Word Detection Result

    Attributes:
        id (int): id of rule point
        detected_banned_words (list[DetectedBannedWord]): result list of detected banned words
    """

    id: int
    detected_banned_words: list[DetectedBannedWord] = []


class BannedWordDetectionJobResult(BaseModel):
    """Banned Word Detection Job Result

    Attributes:
        banned_word_detection_results (list[BannedWordDetectionResult]): result list of banned word detection
        ai_result (dict[str, Any]): AI service result
    """

    banned_word_detection_results: list[BannedWordDetectionResult] = []
    ai_result: dict[str, Any]
