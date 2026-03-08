# pylint: disable=no-name-in-module,no-self-argument


from pydantic import BaseModel


class AudioMeta(BaseModel):
    """Meta information of an audio.

    Attributes:
        codec (str): codec of the audio, such as mp3, m4a, etc.
        sample_rate (str): sample rate of the audio.
        channels (int): channel number of the audio.
        bits (int): bit number of the audio.
    """

    codec: str
    sample_rate: int
    channels: int
    bits: int

class Word(BaseModel):
    text: str
    start_ts: int
    end_ts: int

class Utterance(BaseModel):
    text: str
    words: list[Word | None] = []
    start_ts: int
    end_ts: int

class Audio(BaseModel):
    """Audio entity.

    Attributes:
        meta (AudioMeta): meta information of the audio.
        url (str): url path of the audio.
        path (str, Optional): path of the audio. Default is None.
    """

    meta: AudioMeta | None = None
    url: str | None = None
    # path: str | None = ""
    text: str | None = None
    utterance: list[Utterance] = []
