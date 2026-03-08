
from typing import Any
from pydantic import BaseModel

from workflow_worker.domain.entities.common.time_patch import TimePatch
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.service.ocr import OCRInfo, OCRInfoType


class OCRTrackingResult(BaseModel):
    """OCRTrackingResult is designed for tracking result from OCRInfoTrackingManager.

    Attributes:
        time_patch (TimePatch): The time_patch for this ocr result in video.
        tracking_id (str): The id of this tracking result.
        expected_contents (Dict): The contents which expected to be recognized.
        recoginized_contents (Dict): The contents which recognized by service.
        frame (Frame): The best frame to show.
        bbox (list[int], Optional): The bbox of the ocr entity in frame.
        prefix (str, Optional): The prefix of documents. Only using in document ocr.
        confidence (float, Optional): The detection (recognition) confidence for frame.
        stored_info (OCRInfo, Optional): The raw ocr infos from ocr service.
    """

    time_patch: TimePatch
    tracking_id: str
    expected_contents: dict[str, Any]
    recoginized_contents: dict[str, Any]
    frame: Frame
    keys: list[str | None] = []
    bbox: list[int | None] | None = None
    prefix: str | None = ""
    confidence: float | None = 0.0
    stored_info: OCRInfo | None = None


class BaseOCRRecogResult(BaseModel):
    """The Base OCR detection & recogition result from ocr info manater.

    Attributes:
        ocr_type (OCRInfoType, Optional): The ocr type for result.
        frame (Frame): The best frame in all ocr time_patch.
        url (str, Optional): The stored url of frame for report.
        time (TimePatch): The time range for result.
        bbox (list[int]): The bbox for ocr in frame.
        detect_confidence (float): The max confidence of detection.
        origin_keys (list[str], Optional): The origin key needs to process.
        origin_texts (list[str], Optional): The origine text for origin key.
        origin_recog_texts (list[str], Optional): The origin recog text in frame.
            Only for IDCard.
        recog_texts (list[str], Optional): The recog text.
        recog_confidence (list[float], Optional): The confidence for recognition.
        recog_bboxes (list[list[int]], Optional): The bbox for recog text.
    """

    ocr_type: OCRInfoType | None = OCRInfoType.BASE_OCR_TYPE
    frame: Frame
    url: str | None = ""  # used in report only
    time: TimePatch
    bbox: list[int]
    detect_confidence: float
    origin_keys: list[str | None] = []  # e.g. ['name', 'id_number']
    origin_texts: list[str | None] = []  # e.g. ['John Smith', '2241412151512x']
    origin_recog_texts: list[str | None] = []
    recog_texts: list[str | None] = []
    recog_confidence: list[float | None] = []
    recog_bboxes: list[list[int | None]] = []
