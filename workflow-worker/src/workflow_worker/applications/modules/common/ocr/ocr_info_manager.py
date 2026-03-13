#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import copy
from typing import Any

from workflow_worker.domain.entities.common.time_patch import TimePatch
from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.tasks.common.ocr.result import OCRTrackingResult
from workflow_worker.domain.entities.service.ocr import (
    IDCardOCRInfo,
    OCRInfo,
    OCRInfoType,
    OCRServiceResult,
)
from workflow_worker.applications.modules.common.ocr.ocr_id_generator import OCRIDChecker, OCRIDGenerator
from workflow_worker.shared.utils.image_calculator import calc_box_area, calc_text_similarity


class OCRInfoManager:
    """OCRInfoManager is responsible for generating OCRInfo tracking result.

    OCRInfoManager is composed of 3 parts with do_detection,do_recognition and
    generation. Before processing, you need to add the necessary detection and
    recognition information through the append_contents method. Then it will
    process all ocr_infos frame by frame and try to generate OCRInfo tracking result.

    1. do_detection func is responsible for filtering all eligible ocr_infos and
    recording the best detection ocr message. It only be triggered when the
    need_detection is set to True.
    2. do_recognition func is responsible for recording the best recognition
    texts. It only be triggered when the need_recognition is set to True.
    3. generation func is responsible for generating OCRInfo tracking result.

    Attributes:
        ocr_type (OCRInfoType): The type of OCR info which manager needs to
            processing. One manager instance only process one type of ocr infos.
        fps (float): The frequency of extracting frames of the video. It used to
            determine when to generate tracking result.
        method (str): The method to compare expect text with recog text.
        need_detection (bool): The flag for judging whether to do_detection.
        need_recognition (bool): The flag for judging whether to do_recognition.
        expected_contents (Dict): The contents to be detected (recognized).
        recognized_contents (Dict): The best contents recognized by OCR service.
        frame (str): The frame being processed.
        frames_count (int): the count of tracking frames.
        ttl (int): The tracking deadline.
        tolerance (int): The maximum number of frames for tracking failure in
            one tracking process.

    """

    def __init__(
        self,
        ocr_type: OCRInfoType,
        fps: float = 2,
        compare_method: str = "nlevenshtein",
        need_detection: bool = True,
        need_recognition: bool = False,
    ) -> None:
        self.ocr_type = ocr_type

        self.fps = fps
        self.tolerance = 2 * self.fps
        self.min_frame_count = 3 * self.fps

        self.method = compare_method
        self.need_recognition = need_recognition
        # need_detection must be True if need_recognition is set to True
        self.need_detection = True if self.need_recognition else need_detection

        self.expected_contents: dict[str, Any] = {}
        self.recognized_contents: dict[str, Any] = {}

        self._reinit()

    def _reinit(self):
        """Re-initializes detection infos and recognition infos after init or generate
        OCRInfo tracking results.
        """
        self.frame = None
        self.frames_count = 0
        self.ttl = self.tolerance
        self.start_time = None
        # Reinit the detection info to default value
        self.max_area = 0.0
        self.max_confidence = 0.0
        self.max_bbox = None
        self.stored_info = None
        self.stored_frame = None

        # Reinit the recognition info to default value
        for recog_contents in self.recognized_contents.values():
            for text in recog_contents["contents"].values():
                text["similarity"] = 0.0
                text["text"] = ""
                text["best_frame"] = None
                text["bbox"] = None

    def append_contents(
        self, tracking_id: str, ocr_contents: dict[str, Any], key_fields: list[str] | None = None
    ) -> None:
        """Register ocr contents into manager.

        Args:
            tracking_id (str): The registered ocr tracking id.
            ocr_contents (Dict): The Text to be recognized. The struction of
                ocr_contents is like:
                {
                    field: {'text': 'xxx', 'similarity_threshold': 0.x}
                }
            key_fields (list[str], Optional): The key fields in ocr_contents.
                Defaults to None.
        """
        if not OCRIDChecker.is_ocr_type_match(tracking_id, self.ocr_type):
            return
        if tracking_id in self.expected_contents:
            return
        if len(ocr_contents) <= 0:
            return
        self.expected_contents[tracking_id] = {}
        self.expected_contents[tracking_id]["contents"] = ocr_contents
        if not isinstance(key_fields, list):
            key_fields = list(ocr_contents.keys())
        self.expected_contents[tracking_id]["key_fields"] = key_fields

        self.recognized_contents[tracking_id] = {}
        self.recognized_contents[tracking_id]["contents"] = {}
        for field in ocr_contents.keys():
            recog_text = {
                "text": "",
                "similarity": 0.0,
                "best_frame": None,
                "bbox": None,
            }
            self.recognized_contents[tracking_id]["contents"][field] = recog_text

    def do_detection(self, ocr_infos: list[OCRInfo], frame: Frame) -> list[OCRInfo]:
        """Filter the ocr_infos and get the type matched ocr info list.

        Calculate the max_area from ocr_infos and compare to history messages,
        then update the history messages.

        Args:
            ocr_infos (list[OCRInfo]): The ocr_infos from processing frame.
            frame (Frame): The frame to processing.

        Returns:
            list[OCRInfo]: The type matched ocr info list.
        """
        filtered_ocr_infos: list[Any] = []

        # If not set need_detection flag, then reject all infos.
        if not self.need_detection:
            return filtered_ocr_infos

        # Filter ocr_infos and push into filtered_ocr_infos.
        for ocr_info in ocr_infos:
            if not isinstance(ocr_info, OCRInfo):
                continue
            passed = self._check_ocr_type(ocr_info)
            if passed:
                filtered_ocr_infos.append(ocr_info)

        # Update history messages.
        for ocr_info in filtered_ocr_infos:
            bbox, bbox_area = self._get_bbox(ocr_info)
            if bbox_area > self.max_area:
                self.max_area = bbox_area
                self.max_confidence = ocr_info.confidence
                self.max_bbox = bbox
                self.stored_info = ocr_info
                self.stored_frame = frame

        return filtered_ocr_infos

    def _check_ocr_type(self, ocr_info: OCRInfo) -> bool:
        """Check the type of ocr_info.

        Args:
            ocr_info (OCRInfo): The ocr_infos from processing frame.

        Returns:
            bool: Return True when the ocr_info's type is OCRInfo and matches the
                tracking_id in expected_contents.
        """
        if not isinstance(ocr_info, OCRInfo):
            return False
        for tracking_id in self.expected_contents:
            if OCRIDChecker.is_ocr_type_match(tracking_id, ocr_info.ocr_type):
                return True
        if self.need_detection:
            if ocr_info.ocr_type == self.ocr_type:
                return True
        return False

    def _get_bbox(self, ocr_info: OCRInfo) -> tuple[list[float] | None, float]:
        """Get the bbox and bbox area of the ocr_info.

        Args:
            ocr_info (OCRInfo): The ocr info detected by ocr magician.

        Returns:
            tuple[list[float], float]: (bbox, bbox_area) The bbox and bbox_area
                extracted from ocr_info.
        """
        bbox_area = 0.1
        bbox = None

        if ocr_info.bbox:
            # Deal with ocr_info which has got the detection bbox,
            # such as doc, id_card.
            bbox = ocr_info.bbox
            bbox_area = calc_box_area(bbox)  # type: ignore[arg-type] # pyright: ignore[reportArgumentType]
        elif ocr_info.text_blocks:
            # Deal with ocr_info which does not have the detection bbox but has
            # got the text_block polygon, such as handwriting and normal ocr.
            for text_block in ocr_info.text_blocks:
                if text_block.text_area and text_block.text_area > bbox_area:
                    bbox_area = text_block.text_area
                    bbox = text_block.polygon
        return bbox, bbox_area

    def do_recognition(self, ocr_infos: list[OCRInfo], frame: Frame) -> None:
        """Match all expected_contents with ocr_infos to find the best match, then using
        message of best match to update history.

        Args:
            ocr_infos (list[OCRInfo]): The ocr_infos from processing frame.
            frame (Frame): The frame to processing.
        """
        if not self.need_recognition:
            return
        for ocr_info in ocr_infos:
            for tracking_id, contents in self.expected_contents.items():
                expected_contents = contents["contents"]
                for field in expected_contents.keys():
                    self._recogition_text(tracking_id, field, ocr_info, frame)

    def _recogition_text(
        self, tracking_id: str, field: str, ocr_info: OCRInfo, frame: Frame
    ) -> None:
        """Match ocr_info with one expected_content and update history.

        Args:
            tracking_id (str): The tracking id of expected_content.
            field (str): The key field to match.
            ocr_info (OCRInfo): The ocr info needs to match.
            frame (Frame): The origin frame to processing.
        """
        recogized_contents = self.recognized_contents[tracking_id]["contents"][field]
        expected_text = self.expected_contents[tracking_id]["contents"][field]["text"]
        for text_block in ocr_info.text_blocks:
            max_similarity = recogized_contents["similarity"]
            # Parse text and similarity_threshold from expected_contents
            similarity = calc_text_similarity(
                expected_text, text_block.text, method=self.method
            )
            # Find out the best matching recog_content, store
            # recoginized content and history similarity
            if similarity > max_similarity:
                recogized_contents["text"] = text_block.text
                recogized_contents["similarity"] = similarity
                recogized_contents["best_frame"] = frame
                recogized_contents["bbox"] = ocr_info.bbox

    def _generate(self, ocr_infos: list[OCRInfo], frame: Frame) -> OCRTrackingResult | None:
        ocr_tracking_result = None
        has_type_match = len(ocr_infos) > 0
        if self.frames_count > 0:
            if has_type_match:
                self.frames_count += 1
                self.ttl = self.tolerance
            else:
                self.ttl -= 1
            if self.ttl <= 0:
                ocr_tracking_result = self._gen_tracking_result(frame)
                self._reinit()
        elif has_type_match:
            self.start_time = frame.timestamp
            self.frames_count += 1
        return ocr_tracking_result

    def _gen_tracking_result(self, frame: Frame) -> OCRTrackingResult | None:
        """Generate tracking result. Generate recognition results first, and generate
        detection results when recognition fails and detection is required.

        Args:
            frame (Frame): The frame to processing.

        Returns:
            OCRTrackingResult | None: The ocr tracking result.
        """
        ocr_tracking_result = None
        if self.need_recognition:
            ocr_tracking_result = self._gen_recog_tracking_result(frame)
        if ocr_tracking_result is None and self.need_detection:
            ocr_tracking_result = self._gen_detect_tracking_result(frame)
        return ocr_tracking_result

    def _gen_recog_tracking_result(self, frame: Frame) -> OCRTrackingResult | None:
        """Generate recognition tracking result. This func scans all expected_contents
        and find the max similar recog contents, then parse OCRTrackingResult from the
        matched recog_contents. If the similarity is low than threshold, return None.

        Args:
            frame (Frame): The frame to processing.

        Returns:
            OCRTrackingResult | None: The ocr tracking result.
        """
        max_similarity = 0.0
        matched_id = None
        best_frame = None
        bbox = None
        for tracking_id in self.expected_contents:
            key_fields = self.expected_contents[tracking_id]["key_fields"]
            expected_contents = self.expected_contents[tracking_id]["contents"]
            recog_contents = self.recognized_contents[tracking_id]["contents"]
            for key_field in key_fields:
                if key_field not in recog_contents:
                    continue
                similarity = recog_contents[key_field]["similarity"]
                threshold = expected_contents[key_field]["similarity_threshold"]
                if similarity > threshold and similarity > max_similarity:
                    max_similarity = similarity
                    matched_id = tracking_id
                    best_frame = recog_contents[key_field]["best_frame"]
                    bbox = recog_contents[key_field]["bbox"]
        if matched_id is None:
            return None
        expected_contents = copy.deepcopy(
            self.expected_contents[matched_id]["contents"]
        )
        recoginized_contents = copy.deepcopy(
            self.recognized_contents[matched_id]["contents"]
        )
        keys = copy.deepcopy(self.expected_contents[matched_id]["key_fields"])
        assert best_frame is not None
        tracking_result = OCRTrackingResult(
            time_patch=TimePatch(start_time=self.start_time or 0.0, end_time=frame.timestamp),
            tracking_id=matched_id,
            expected_contents=expected_contents,
            recoginized_contents=recoginized_contents,
            bbox=bbox,
            frame=best_frame,
            keys=keys,
            confidence=max_similarity,
        )
        return tracking_result

    def _gen_detect_tracking_result(self, frame: Frame) -> OCRTrackingResult | None:
        """Generate detection tracking result. This func parses OCRTrackingResult from
        stored message which has the max confidence or bbox area in do_detection func.
        When the ocr_type is id_card, we parse recoginized_contents from store_info as
        origin_recog_contents.

        Args:
            frame (Frame): The frame to processing.

        Returns:
            OCRTrackingResult | None: The ocr tracking result of detection.
        """
        if not self.need_detection:
            return None
        expected_contents: dict[str, Any] = {}
        recoginized_contents: dict[str, Any] = {}
        tracking_id = OCRIDGenerator.get_detection_ocr_id(self.ocr_type)
        if isinstance(self.stored_info, IDCardOCRInfo):
            for text_block in self.stored_info.text_blocks:
                if text_block is None:
                    continue
                if text_block.name == "name":
                    recoginized_contents["name"] = {
                        "text": text_block.text,
                        "similarity": text_block.text_confidence,
                    }
                elif text_block.name == "id_card_number":
                    recoginized_contents["card_number"] = {
                        "text": text_block.text,
                        "similarity": text_block.text_confidence,
                    }
        assert self.stored_frame is not None
        tracking_result = OCRTrackingResult(
            time_patch=TimePatch(start_time=self.start_time or 0.0, end_time=frame.timestamp),
            tracking_id=tracking_id,
            expected_contents=expected_contents,
            recoginized_contents=recoginized_contents,
            frame=self.stored_frame,
            bbox=self.max_bbox,  # pyright: ignore[reportArgumentType]
            confidence=self.max_confidence,
        )
        return tracking_result

    def process(
        self, ocr_service_result: OCRServiceResult, frame: Frame
    ) -> OCRTrackingResult | None:
        ocr_infos = ocr_service_result.ocr_infos
        self.frame = frame
        filtered_ocr_infos = self.do_detection(ocr_infos, frame)
        self.do_recognition(filtered_ocr_infos, frame)
        tracking_result = self._generate(filtered_ocr_infos, frame)
        return tracking_result

    def over(self) -> OCRTrackingResult | None:
        """Do double check to generate ocr_tacking_result when the video is end.

        Returns:
            OCRTrackingResult | None: The last ocr tracking result.
        """
        if self.frames_count > 0 and self.frame is not None:
            return self._gen_tracking_result(self.frame)
        return None


class DocOCRInfoManager(OCRInfoManager):
    def _recogition_text(
        self, tracking_id: str, field: str, ocr_info: OCRInfo, frame: Frame
    ) -> None:
        """Match ocr_info with one expected_content and update history.
        We only match the last few characters to promote matching success ratio as the
        title of document always has prefix in document case.

        Args:
            tracking_id (str): The tracking id of expected_content.
            field (str): The key field to match.
            ocr_info (OCRInfo): The ocr info needs to match.
            frame (Frame): The origin frame to processing.
        """
        recogized_contents = self.recognized_contents[tracking_id]["contents"][field]
        expected_text = self.expected_contents[tracking_id]["contents"][field]["text"]
        for text_block in ocr_info.text_blocks:
            max_similarity = recogized_contents["similarity"]
            # Parse text and similarity_threshold from expected_contents
            recog_text = text_block.text
            if len(recog_text) > len(expected_text):
                recog_text = recog_text[-len(expected_text) :]

            similarity = calc_text_similarity(
                expected_text, recog_text, method=self.method
            )
            # Find out the best matching recog_content, store
            # recoginized content and history similarity
            if similarity > max_similarity:
                recogized_contents["text"] = text_block.text
                recogized_contents["similarity"] = similarity
                recogized_contents["best_frame"] = frame
                recogized_contents["bbox"] = ocr_info.bbox


class IDCardOCRInfoManager(OCRInfoManager):
    def do_detection(self, ocr_infos: list[OCRInfo], frame: Frame) -> list[OCRInfo]:
        """Filter the ocr_infos and get the type matched ocr info list.

        Calculate the max_area from ocr_infos and compare to history messages,
        then update the history messages.

        We use detection_confidence of ocr_info to compare rather than bbox area.

        Args:
            ocr_infos (list[OCRInfo]): The ocr_infos from processing frame.
            frame (Frame): The frame to processing.

        Returns:
            list[OCRInfo]: The type matched ocr info list.
        """
        filtered_ocr_infos: list[Any] = []

        # If not set need_detection flag, then reject all infos.
        if not self.need_detection:
            return filtered_ocr_infos

        # Filter ocr_infos and push into filtered_ocr_infos.
        for ocr_info in ocr_infos:
            if not isinstance(ocr_info, OCRInfo):
                continue
            passed = self._check_ocr_type(ocr_info)
            if passed:
                filtered_ocr_infos.append(ocr_info)

        # Update history messages.
        for ocr_info in filtered_ocr_infos:
            bbox, bbox_area = self._get_bbox(ocr_info)
            confidence = ocr_info.confidence
            if confidence == 0:
                confidence = ocr_info.detection_confidence
            if confidence > self.max_confidence:
                self.max_area = bbox_area
                self.max_confidence = confidence
                self.max_bbox = bbox
                self.stored_info = ocr_info
                self.stored_frame = frame

        return filtered_ocr_infos
