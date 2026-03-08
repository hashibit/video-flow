# pylint: disable=no-name-in-module,no-self-argument

from enum import Enum

from pydantic import BaseModel


class OCRInfoType(Enum):
    """OCRInfoType represents all OCR types that appear in IDRS project."""

    BASE_OCR_TYPE = "300"
    # DOC_OCR_TYPE represents Financial related documents
    DOC_OCR_TYPE = "301"
    # HANDWRITING_OCR_TYPE represents Customer's signature
    HANDWRITING_OCR_TYPE = "302"
    # IDCARD_OCR_TYPE represents Resident Identity Card
    ID_CARD_OCR_TYPE = "303"
    # EMPLOYEE_CARD_OCR_TYPE represents Employee Card
    EMPLOYEE_CARD_OCR_TYPE = "304"
    # PRACTICING_CERTIFICATE_OCR_TYPE represents Practicing Certificate
    PRACTICING_CERTIFICATE_OCR_TYPE = "305"
    # GENERAL_OCR_TYPE represents the origin OCR Info
    GENERAL_OCR_TYPE = "306"

    @classmethod
    def get_ocr_info_type(cls, ocr_info_type):
        for info_type in cls:
            if info_type.value == ocr_info_type:
                return info_type
            if info_type.name.lower() == f"{ocr_info_type}_ocr_type":
                return info_type
        return None

    @classmethod
    def get_ocr_info_name(cls, ocr_info_type):
        ocr_type = ocr_info_type
        if isinstance(ocr_info_type, str):
            ocr_type = cls.get_ocr_info_type(ocr_info_type)
        mapper = {
            cls.DOC_OCR_TYPE: "document",
            cls.ID_CARD_OCR_TYPE: "id_card",
            cls.EMPLOYEE_CARD_OCR_TYPE: "employee_card",
            cls.PRACTICING_CERTIFICATE_OCR_TYPE: "practicing_certificate",
            cls.HANDWRITING_OCR_TYPE: "handwriting",
        }
        if ocr_type is None:
            return ""
        return mapper.get(ocr_type, "")


class TextBlock(BaseModel):
    """TextBlock is designed to represent text block.

    Attributes:
        text (str): Recognized text.
        polygon (list[float], Optional): The point's coordinate of polygon surrounding
            the text block.
        text_confidence (float): The confidence of the recognized text.
        character_confidences (list[float]): The confidence list for the
            recognized characters.
        name (str, Optional): The name of the text block.
    """

    text: str
    polygon: list[float] = []
    text_confidence: float
    character_confidences: list[float] = []
    name: str | None = ""

    def __repr__(self):
        """Returns representation of the object."""
        return (
            f"{self.__class__.__name__}("
            + ",".join(f"{k}={v!r}" for k, v in self.__dict__.items())
            + ")"
        )

    def __hash__(self):
        return hash(str(sorted(self.polygon)) + self.text)

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    @property
    def corner_count(self):
        """Number of corners."""
        return len(self.polygon) // 2

    @property
    def y(self):
        """Approximate the y coordinate of the text middle line."""
        return sum(self.polygon[1::2]) / self.corner_count

    @property
    def text_area(self):
        """Area of the text block."""
        area = 0
        for i in range(self.corner_count):
            j = (i + 1) % self.corner_count
            # x_i * y_j - x_j * y_i
            area += self.polygon[2 * i] * self.polygon[2 * j + 1]
            area -= self.polygon[2 * j] * self.polygon[2 * i + 1]
        area /= 2
        return area

    @property
    def character_area(self):
        """Approximate area of the character in the text block."""
        return self.text_area / len(self.text)


class OCRInfo(BaseModel):
    """OCRInfo is designed to represent optical character recognition
    information.

    Attributes:
        ocr_type (OCRInfoType): The id for the ocr information to represent the type
            of ocr_info.
        bbox (list[float], Optional): The bounding box of the
        polygon (list[float], Optional): The point's coordinate of polygon surrounding
            the target object.
        confidence (float, Optional): The detection confidence of the target object.
        text_blocks (list[TextBlock], Optional): A list of text blocks.
    """

    ocr_type: OCRInfoType
    bbox: list[float] = []
    polygon: list[float] = []
    confidence: float | None = 0
    text_blocks: list[TextBlock] = []

    def __repr__(self):
        """Returns representation of the object."""
        return (
            f"{self.__class__.__name__}("
            + ",".join(f"{k}={v!r}" for k, v in self.__dict__.items())
            + ")"
        )


class IDCardOCRInfo(OCRInfo):
    """IDCardOCRInfo is designed to represent ID Card optical character
    recognition information.

    Attributes:
        ocr_type (OCRInfoType): The type for the ocr infomation of the ID Card.
        bbox (list[float], Optional): The bounding box of the ID Card.
        polygon (list[float], Optional): The polygon surrounding the ID Card.
        confidence (float, Optional): The avg confidence of the extract info of
            the ID Card.
        text_blocks (list[TextBlock], Optional): A list of text blocks.
        side (int): The side of the ID Card.
        detection_confidence (float, Optional): The confidence of the detection of
            the ID Card.
        face_polygon (list[float], Optional): The polygon surrounding the face in
            the ID Card.
    """

    side: int
    detection_confidence: float | None = 1.0
    face_polygon: list[float] = []
    name_mapper = {
        "name": "Name",
        "gender": "Gender",
        "race": "Ethnicity",
        "year": "Year",
        "month": "Month",
        "day": "Day",
        "address": "Address",
        "id_card_number": "ID Number",
        "issued_by": "Issuing Authority",
        "valid_date": "Valid Until",
    }

    def __repr__(self):
        """Returns representation of the object."""
        return (
            f"{self.__class__.__name__}("
            + ",".join(f"{k}={v!r}" for k, v in self.__dict__.items())
            + ")"
        )

    def get_detail(self):
        detail = ""
        if self.side == 2:
            return detail
        if self.text_blocks:
            for text_block in self.text_blocks:
                if text_block.name is None:
                    continue
                prefix = self.name_mapper[text_block.name]
                detail += f"{prefix}: {text_block.text}\n"
        return detail

    @property
    def name(self):
        if self.side == 1 and self.text_blocks:
            for text_block in self.text_blocks:
                if text_block.name == "name":
                    return text_block.text
        return ""

    @property
    def id_number(self):
        if self.side == 1 and self.text_blocks:
            for text_block in self.text_blocks:
                if text_block.name == "id_card_number":
                    return text_block.text
        return ""


class OCRServiceResult(BaseModel):
    """Ocr Result from Ocr service."""

    ocr_infos: list[OCRInfo]
