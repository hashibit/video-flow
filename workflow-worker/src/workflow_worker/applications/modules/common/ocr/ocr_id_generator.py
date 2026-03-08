#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Any

from workflow_worker.domain.entities.service.ocr import OCRInfoType


class OCRIDGenerator:
    """ID generator for OCR-related operations"""

    def __init__(self) -> None:

        # OCRIDGenerator starting ID and prefix
        ocr_types = [
            "ID_CARD",
            "HANDWRITING",
            "DOC",
            "EMPLOYEE_CARD",
            "PRACTICING_CERTIFICATE",
        ]
        for ocr_type in ocr_types:
            l_ocr_type = ocr_type.lower()
            # Set OCRIDGenerator starting ID to 0
            setattr(self, l_ocr_type + "_ocr_id", 0)
            # OCRIDGenerator cache area
            setattr(self, l_ocr_type + "_cache", dict())
            # Set ID prefix for OCR sub-events
            ocr_info_type = getattr(OCRInfoType, ocr_type + "_OCR_TYPE").value
            setattr(self, l_ocr_type + "_prefix", f"v{ocr_info_type}")

        self.ocr_mapper = {
            "documents": "doc",
            "id_card": "id_card",
            "employee_card": "employee_card",
            "practicing_certificate": "practicing_certificate",
            "sign": "handwriting",
        }

    @staticmethod
    def get_detection_ocr_id(ocr_type: OCRInfoType | str) -> str:
        """Generate the detection id for the given OCR type. Each OCR type maps to a fixed id.

        Args:
            ocr_type (OCRInfoType | str): OCR type; accepts either an OCRInfoType enum or its value string.

        Returns:
            str: The detection id for the OCR type.
        """
        if isinstance(ocr_type, OCRInfoType):
            return f"v{ocr_type.value}xx"
        if isinstance(ocr_type, str):
            return f"v{ocr_type}xx"
        return "v301xx"

    def get_ocr_id(
        self, ocr_field: str | None = None, contents: dict[str, Any] | None = None
    ) -> tuple[str, bool]:
        """Generate a tracking_id for the given OCR info. Returns the same id if already generated.

        Args:
            ocr_field (str, optional): The field name of this OCR entry in the config. Defaults to None.
            contents (Dict, optional): Detailed information for this OCR entry. Defaults to None.

        Raises:
            TypeError: If ocr_field is not a str.
            ValueError: If ocr_field is out of the allowed range.
            TypeError: If contents is not a dict.
            ValueError: If contents is empty.

        Returns:
            tuple[str, bool]: The generated tracking_id for this OCR entry,
                and whether this tracking_id was already generated before.
        """

        if not isinstance(ocr_field, str):
            raise TypeError(
                f"The type of ocr_filed must be str, " f"not {type(ocr_field)}."
            )

        if ocr_field not in self.ocr_mapper:
            raise ValueError(f"Unsupport ocr id of {ocr_field}.")

        if not isinstance(contents, dict):
            raise TypeError(
                f"The type of contents must be dict, " f"not {type(contents)}."
            )

        if len(contents) <= 0:
            raise ValueError("Contents cannot be empty.")

        ocr_type = self.ocr_mapper[ocr_field]
        ocr_id = getattr(self, ocr_type + "_ocr_id")
        prefix = getattr(self, ocr_type + "_prefix")
        cache = getattr(self, ocr_type + "_cache")

        is_repeated = True
        content_fileds = ""
        for key, value in contents.items():
            content_fileds += value["text"]
        if content_fileds not in cache:
            ocr_id += 1
            is_repeated = False
            tracking_id = f"{prefix}{ocr_id:02d}"
            cache[content_fileds] = tracking_id
        else:
            tracking_id = cache[content_fileds]

        setattr(self, ocr_type + "_ocr_id", ocr_id)
        setattr(self, ocr_type + "_cache", cache)

        return tracking_id, is_repeated


class OCRIDChecker:
    """Checker class for OCR IDs — validates whether an id matches a given OCR type."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def is_ocr_type_match(tracking_id: str, ocr_type: OCRInfoType | str) -> bool:
        """Check whether tracking_id matches the given OCR type.

        Args:
            tracking_id (str): The tracking id to check.
            ocr_type (OCRInfoType | str): The OCR type to match against.

        Returns:
            bool: True if tracking_id matches the OCR type.
        """
        if not isinstance(tracking_id, str):
            return False
        if len(tracking_id) != 6:
            return False
        tracking_id_prefix = tracking_id[:4]
        if isinstance(ocr_type, OCRInfoType):
            return tracking_id_prefix == "v" + ocr_type.value
        if isinstance(ocr_type, str):
            return tracking_id_prefix == ocr_type
        return False

    @classmethod
    def is_ocr_type_correct(
        cls, tracking_id: str, ocr_types: list[OCRInfoType]
    ) -> bool:
        """Verify whether tracking_id belongs to one of the given OCR types.

        Args:
            tracking_id (str): The tracking id to verify.
            ocr_types (list[OCRInfoType]): List of OCR types to match against.

        Returns:
            bool: True if tracking_id matches any of the given OCR types.
        """
        is_type_correct = False
        for ocr_type in ocr_types:
            is_type_correct |= cls.is_ocr_type_match(tracking_id, ocr_type)
        return is_type_correct

    @classmethod
    def get_ocr_type(cls, tracking_id: str):
        """Return the OCR type for the given tracking_id; returns None for invalid ids."""
        for ocr_type in OCRInfoType:
            if cls.is_ocr_type_match(tracking_id, ocr_type):
                return ocr_type
        return None

    @classmethod
    def get_ocr_name(cls, tracking_id: str):
        """Return the OCR type name corresponding to the given tracking_id."""
        ocr_type = cls.get_ocr_type(tracking_id)
        return OCRInfoType.get_ocr_info_name(ocr_type)
