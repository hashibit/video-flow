# pylint: disable=no-name-in-module,no-self-argument

from typing import Any
from pydantic import BaseModel


class Word(BaseModel):
    """Word entity in the dialogue from AUC service.

    Attributes:
        text (str): text of the word. Note that this is not equal to one chinese
            character, but also can be a word or a number.
        start (int): start timestamp of the word in the audio.
        end (int): end timestamp of the word in the audio.
    """

    text: str
    start_time: int
    end_time: int


class Utterance(BaseModel):
    """Utterance entity in the dialogue from AUC service.

    Attributes:
        text (str): text of the whole utterance.
        words (list[Word]): list of words in the utterance.
        start (int): start timestamp of the utterance in the audio.
        end (int): end timestamp of the utterance in the audio.
        speaker (str): speaker of the utterance. Default is empty string.
        gender (str): gender of the utterance speaker. Default is empty string.
    """

    words: list[Word]
    text: str
    speaker: str | None = ""
    gender: str | None = ""
    start_time: int
    end_time: int

    def __init__(self, **data) -> None:

        if data["words"] and isinstance(data["words"][0], dict):
            new_words: list[dict[str, Any]] = []
            text = data["text"]
            i = 0
            word: dict[str, Any] = {}
            for word in data["words"]:
                while text[i : i + len(word["text"])] != word["text"]:
                    start_time = 0 if not new_words else new_words[-1]["end_time"]
                    end_time = word["start_time"]
                    new_words.append(
                        {
                            "text": text[i],
                            "start_time": start_time,
                            "end_time": end_time,
                        }
                    )
                    i += 1
                new_words.append(word)
                i += len(word["text"])
            while i < len(text):
                start_time = 0 if not data["words"] else data["words"][-1]["end_time"]
                end_time = word["start_time"]
                new_words.append(
                    {"text": text[i], "start_time": start_time, "end_time": end_time}
                )
                i += 1

            data["words"] = new_words
        super().__init__(**data)

    def __getitem__(self, key: int | slice) -> "Utterance":
        if isinstance(key, int):
            return Utterance(
                words=[self.words[key]],
                text=self.words[key].text,
                start_time=self.words[key].start_time,
                end_time=self.words[key].end_time,
            )

        if isinstance(key, slice):
            if key.start is not None and key.start >= len(self.words):
                return Utterance(words=[], text="", start_time=-1, end_time=-1)

            words = self.words[key]
            return Utterance(
                words=words,
                text="".join([word.text for word in words]),
                start_time=words[0].start_time,
                end_time=words[-1].end_time,
            )

        raise KeyError("only allowed int or slice as key")

    def __setitem__(self, key: int | slice, val: "str | list[str]") -> None:
        if isinstance(key, int):
            self.words[key].text = val  # type: ignore[assignment] # pyright: ignore[reportAttributeAccessIssue]
            return

        if isinstance(key, slice):
            replace_utterance = self[key]

            if len(replace_utterance) == len(val):
                start = key.start or 0
                stop = key.stop or len(self.words)
                for i in range(start, stop):
                    self.words[i].text = val[i - start]  # type: ignore[index]
                return

            replace_words = []
            start_time = replace_utterance.start_time
            end_time = replace_utterance.end_time
            step = int((end_time - start_time) / len(val))
            for i, chr in enumerate(val):
                word = Word(
                    text=chr,  # type: ignore[arg-type]
                    start_time=start_time + i * step,
                    end_time=start_time + (i + 1) * step,
                )
                replace_words.append(word)
            self.words[key] = replace_words
            return

        raise KeyError("only allowed int or slice as key")

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        return len(self.words)

    def __hash__(self) -> int:
        return hash(self.__str__())

    def __eq__(self, o: object) -> bool:
        if isinstance(o, str):
            return self.__str__() == o

        if isinstance(o, Utterance):
            return self.__str__() == o.__str__()

        raise ValueError(
            "UtteranceInfo can only compare with [str, UtteranceInfo] object"
        )


class Dialogue(BaseModel):
    """Dialogue entity from AUC service.

    Attributes:
        text (str): text of the whole dialogue.
        words (list[Word]): list of words in the dialogue.
        utterances (list[Utterance]): list of utterances in the dialogue.
        num_speaker (int): speaker number in this dialogue. Default is -1.
    """

    text: str

    utterances: list[Utterance] = []
    num_speaker: int | None = -1

    @property
    def words(self) -> list[Word]:
        _words = []
        for utterance in self.utterances:
            _words.extend(utterance.words)
        return _words

    @property
    def start_time(self) -> int:
        return self.words[0].start_time

    @property
    def end_time(self) -> int:
        return self.words[-1].end_time

    def __getitem__(self, key: int | slice) -> Utterance:
        if isinstance(key, int):
            return Utterance(
                words=[self.words[key]],
                text=self.words[key].text,
                start_time=self.words[key].start_time,
                end_time=self.words[key].end_time,
            )

        if isinstance(key, slice):
            if key.start is not None and key.start >= len(self.words):
                return Utterance(words=[], text="", start_time=-1, end_time=-1)

            words = self.words[key]
            return Utterance(
                words=words,
                text="".join([word.text for word in words]),
                start_time=words[0].start_time,
                end_time=words[-1].end_time,
            )

        raise TypeError("only allowed int or slice as key")

    def __setitem__(self, key: int | slice, val: "str | list[str]") -> None:
        if isinstance(key, int):
            self.words[key].text = val  # type: ignore[assignment] # pyright: ignore[reportAttributeAccessIssue]
            return

        if isinstance(key, slice):
            replace_utterance = self[key]

            if len(replace_utterance) == len(val):
                start = key.start or 0
                stop = key.stop or len(self.words)
                for i in range(start, stop):
                    self.words[i].text = val[i - start]  # type: ignore[index]
                return

            replace_words = []
            start_time = replace_utterance.start_time
            end_time = replace_utterance.end_time
            step = int((end_time - start_time) / len(val))
            for i, chr in enumerate(val):
                word = Word(
                    text=chr,  # type: ignore[arg-type]
                    start_time=start_time + i * step,
                    end_time=start_time + (i + 1) * step,
                )
                replace_words.append(word)
            self.words[key] = replace_words
            return

        raise KeyError("only allowed int or slice as key")

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        return len(self.words)
