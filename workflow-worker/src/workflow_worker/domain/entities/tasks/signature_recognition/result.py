
from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.common.ocr.result import BaseOCRRecogResult
from workflow_worker.domain.entities.service.ocr import OCRInfoType


class SignOCRRecogResult(BaseOCRRecogResult):
    """OCR recognition result for handwritten signatures."""

    ocr_type: OCRInfoType | None = OCRInfoType.HANDWRITING_OCR_TYPE  # OCR type is handwriting/signature


class SignatureRecognitionJobResult(BaseModel):
    """Output of the signature recognition job."""

    ai_result: list[SignOCRRecogResult]  # raw results from the AI service
    results: list[tuple[str, SignOCRRecogResult]]  # processed output of the signature task
