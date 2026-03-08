"""Base class for batch OCR services."""
from abc import ABC, abstractmethod

from workflow_worker.domain.entities.frame import BatchFrame, Frame
from workflow_worker.domain.entities.service.ocr import OCRServiceResult
from workflow_worker.services.ai.service import GRPCService, require_cache


class BatchOCRService(GRPCService, ABC):
    """Base for OCR services that process frames individually within a BatchFrame.

    Subclasses implement predict() for single-frame logic; run() is provided here.
    """

    @abstractmethod
    def predict(self, frame: Frame) -> OCRServiceResult:
        pass

    @require_cache
    def run(self, frames: BatchFrame) -> list[OCRServiceResult]:  # pyright: ignore[reportIncompatibleMethodOverride]
        return [self.predict(frame) for frame in frames.frames]
