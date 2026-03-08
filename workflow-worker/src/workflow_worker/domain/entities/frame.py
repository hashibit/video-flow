# pylint: disable=no-name-in-module,no-self-argument
from typing import Any

from pydantic import BaseModel



class Frame(BaseModel):
    """Frame is designed to represent a frame extracted from video.

    Args:
        url (str): the url or local path for frame.
            e.g. http:// or hdfs:// or tos:// or file://
        date (bytes): the encoding data of frame.
        timestamp (float): the timestamp which indicate the location in video.
        height (int): the height of frame.
        width (int): the width of frame.
        channel (int): the channel of frame. e.g. color is 3 and black is 1.
    """
    msg_id: str | None = None
    logger: Any | None = None
    frame_number: int = -1
    url: str | None = None
    rule_id: int | None = 0  # Used for API to classify different rule frames
    data: bytes | str | None = ""
    ts: float = -1
    timestamp: float = -1
    height: int | None = None
    width: int | None = None
    # channel: int | None = -1


class BatchFrame(BaseModel):
    """BatchFrame is designed to represent a list of frames for batch inference.

    Args:
        frames (list[Frame]): the list of frames.
        batch_size (int): the count of frames.
    """
    frames: list[Frame]
    batch_size: int


class ContinuousFrame(BaseModel):
    """
    ContinuousFrame is used to store continuous frames and their corresponding similarity (confidence)
    """

    rule_id: int  # rule_id
    text_index: int  # text_index
    start_frame: Frame
    end_frame: Frame
    avg_similarity: float
    min_similarity: float
    max_similarity: float
    duration: int
