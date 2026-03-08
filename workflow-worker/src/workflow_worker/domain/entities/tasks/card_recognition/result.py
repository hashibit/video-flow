
from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.common.ocr.result import BaseOCRRecogResult
from workflow_worker.domain.entities.service.ocr import OCRInfoType


class CardOCRRecogResult(BaseOCRRecogResult):
    """OCR recognition result for identity cards."""

    ocr_type: OCRInfoType | None = OCRInfoType.ID_CARD_OCR_TYPE  # card OCR type


class CardRecognitionJobResult(BaseModel):
    """Output of the card recognition job."""

    ai_result: list[CardOCRRecogResult]  # raw results from the AI service
    results: list[tuple[str, CardOCRRecogResult]]  # processed card recognition results
