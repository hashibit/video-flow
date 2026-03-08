
from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.common.ocr.result import BaseOCRRecogResult
from workflow_worker.domain.entities.service.ocr import OCRInfoType


class DocOCRRecogResult(BaseOCRRecogResult):
    """OCR recognition result for documents."""

    ocr_type: OCRInfoType | None = OCRInfoType.DOC_OCR_TYPE  # OCR type is document


class DocumentRecognitionJobResult(BaseModel):
    """Output of the document recognition job."""

    ai_result: list[DocOCRRecogResult]  # raw detection & recognition results from the AI service
    results: list[tuple[str, DocOCRRecogResult]]  # processed output of the document recognition task
