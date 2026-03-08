from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.service.ocr import OCRInfoType, OCRServiceResult
from workflow_worker.services.ai.ocr.general import GeneralOCRService

# These strings are Chinese text printed on physical identity cards;
# they must remain in Chinese to match OCR output from real documents.
_CARD_TYPE_RULES: tuple[tuple[str, OCRInfoType], ...] = (
    ("展业证", OCRInfoType.PRACTICING_CERTIFICATE_OCR_TYPE),   # "practicing certificate"
    ("执业证", OCRInfoType.PRACTICING_CERTIFICATE_OCR_TYPE),   # "practicing license"
    ("工作证", OCRInfoType.EMPLOYEE_CARD_OCR_TYPE),            # "employee card"
    ("工号",   OCRInfoType.EMPLOYEE_CARD_OCR_TYPE),            # "employee number"
)
_KEYWORD_TO_TYPE: dict[str, OCRInfoType] = dict(_CARD_TYPE_RULES)


def _classify_card_type(text_blocks) -> OCRInfoType | None:
    return next(
        (_KEYWORD_TO_TYPE[tb.text] for tb in text_blocks if tb.text in _KEYWORD_TO_TYPE),
        None,
    )


class MultiCardOCRService(GeneralOCRService):
    """Multi-card OCR strategy workaround for employee cards and practicing certificates."""

    def __init__(
        self,
        name="multi_card_ocr_service",
        version="v1",
        description="Multi Card OCR service",
    ):
        super().__init__(name, version, description)

    def predict(self, frame: Frame) -> OCRServiceResult:
        ocr_result = super().predict(frame)
        for ocr_info in ocr_result.ocr_infos:
            card_type = _classify_card_type(ocr_info.text_blocks)
            if card_type is not None:
                ocr_info.ocr_type = card_type
        return ocr_result
