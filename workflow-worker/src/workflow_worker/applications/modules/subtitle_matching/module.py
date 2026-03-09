import concurrent.futures
import logging
import time
from copy import deepcopy
from typing import Any

import numpy as np

from workflow_worker.domain.entities.frame import BatchFrame, Frame, ContinuousFrame
from workflow_worker.domain.entities.tasks.subtitle_matching.config import (
    EmergencyType,
    SingleSubtitleJobCfg,
    SubtitleJobCfg,
    TextType,
    TimeRangeType,
)
from workflow_worker.domain.entities.tasks.subtitle_matching.result import (
    MissResult,
    RecogSubtitle,
    Subtitle,
    SubtitleJobResult,
)
from workflow_worker.domain.entities.service.ocr import OCRServiceResult, TextBlock
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.subtitle_matching.diff import diff_match_patch
from workflow_worker.services.ai.ocr import GeneralOCRService
from workflow_worker.shared.utils.env import get_env
from workflow_worker.applications.modules.module import ModuleBase
from workflow_worker.applications.modules.model import JobName
from workflow_worker.infrastructure.media_stream.s3client import S3Client
from workflow_worker.applications.workflows.task_context import TaskContext


class SubtitleMatchingModule(ModuleBase):
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self.required_jobs: list[Any] = []
        self.MAX_WORKER = 5

    def parse_task(self, task: Task) -> list[SubtitleJobCfg]:
        """Parse task to dict.

        Args:
            task (Task): task config.

        Returns:
            dict: subtitle job config.
        """
        job_cfg = None
        job_cfgs = []

        # Use scenario mode instead of rule mode for processing here
        for rule_section in task.scenario.rule_sections:
            for rule_point in rule_section.rule_points:
                if rule_point and rule_point.subtitle_cfg:
                    # One point corresponds to one config, currently one section has only one point
                    # Multiple rules use [multiple sections + 1 point] approach
                    configs = []
                    cfg = rule_point.subtitle_cfg
                    for subtitle_text in cfg.texts:
                        config = SingleSubtitleJobCfg(
                            text_index=subtitle_text.text_index,
                            text=subtitle_text.text,
                            threshold=subtitle_text.threshold,
                            time_patchs=[tp for tp in subtitle_text.time_patchs if tp is not None],
                            time_range_type=subtitle_text.time_range_type,
                            emergency_type=subtitle_text.emergency_type,
                            text_type=subtitle_text.text_type,
                            min_text_number=subtitle_text.min_text_number,
                            cumulative_threshold=subtitle_text.cumulative_threshold,
                            continuous_appearance_times=subtitle_text.continuous_appearance_times,
                        )
                        configs.append(config)
                    job_cfg = SubtitleJobCfg(
                        id=task.id, rule_id=rule_section.id, media=task.media, fps=cfg.fps, configs=configs
                    )
                    job_cfgs.append(job_cfg)

        return job_cfgs

    def run(self, job_cfgs: list[SubtitleJobCfg], task_context: TaskContext) -> SubtitleJobResult:
        ################################################################
        # copy from original subtitle_match_ops.py
        ################################################################

        logger = task_context.get_task_logger().getChild("Module.SubtitleMatching")

        result = SubtitleJobResult(ai_result={})

        s3 = S3Client()
        envs = get_env()

        logger.info("before asyncio.run")
        job_results = self.run_all(job_cfgs, task_context, logger=logger)
        logger.info("after asyncio.run")

        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        # job_results = loop.run_until_complete()
        for idx, job_result in enumerate(job_results):
            if job_result is None:
                continue
            job_config = job_cfgs[idx]
            new_miss_results = []
            for i, miss_result in enumerate(job_result.ai_result["subtitle"]):
                miss_result = deepcopy(miss_result)
                img_path = f"task_{self.task_uuid}/rule_{job_config.rule_id}/subtitle/miss_frame_{i}.jpg"
                if miss_result.frame.data:
                    # remove screenshot and url, avoid request tos/oss frequently
                    s3.load_bytes(miss_result.frame.data, img_path, envs.s3_bucket, replace=True)
                    miss_result.frame.url = f"minio://{img_path}"
                    miss_result.frame.data = None
                miss_result.frame.rule_id = job_config.rule_id
                new_miss_results.append(miss_result)
            job_result.ai_result["subtitle"] = new_miss_results

            for k, continuous_frame in enumerate(job_result.ai_result["subtitle_continuous_appear"]):
                start_frame = deepcopy(continuous_frame.start_frame)
                end_frame = deepcopy(continuous_frame.end_frame)
                img_start_path = f"task_{self.task_uuid}/rule_{job_config.rule_id}/subtitle/appear_frame_{k}_start.jpg"
                img_end_path = f"task_{self.task_uuid}/rule_{job_config.rule_id}/subtitle/appear_frame_{k}_end.jpg"
                continuous_frame.start_frame, continuous_frame.end_frame = None, None
                if start_frame.data:
                    s3.load_bytes(start_frame.data, img_start_path, envs.s3_bucket, replace=True)
                    start_frame.data = None
                    start_frame.url = f"minio://{img_start_path}"
                    continuous_frame.start_frame = start_frame
                if end_frame.data:
                    s3.load_bytes(end_frame.data, img_end_path, envs.s3_bucket, replace=True)
                    end_frame.data = None
                    end_frame.url = f"minio://{img_end_path}"
                    continuous_frame.end_frame = end_frame

            if "subtitle_continuous_appear" not in result.ai_result:
                result.ai_result["subtitle_continuous_appear"] = job_result.ai_result["subtitle_continuous_appear"]
            else:
                result.ai_result["subtitle_continuous_appear"].extend(
                    job_result.ai_result["subtitle_continuous_appear"])

            if "subtitle" not in result.ai_result:
                result.ai_result["subtitle"] = job_result.ai_result["subtitle"]
            else:
                result.ai_result["subtitle"].extend(job_result.ai_result["subtitle"])

            result.recog_results.extend(job_result.recog_results)

        return result

    def run_all(self, job_cfgs: list[SubtitleJobCfg], task_context: TaskContext, logger: logging.Logger):
        logger.info(f"Running all subtitle job configs size: {len(job_cfgs)}")

        frame_ch_list = task_context.frame_channels[JobName.SubtitleMatching]
        event_ch_list = task_context.frame_channels[JobName.SubtitleMatching]

        def gen_fut_exception_handler(frame_ch):
            def handle_fut_exception(fut):
                e = fut.exception()
                if e:
                    logger.error(f"frame_ch {frame_ch.id} subtitle algo catch exception: {e}")
                    for ch in (frame_ch_list if isinstance(frame_ch_list, list) else []):
                        # Close frame_channel so other subtitle algo can also receive stop notification
                        ch.mark_close()
                    # Re-raise the exception
                    raise e
                r = fut.result()
                if r:
                    logger.info(f"frame_ch {frame_ch.id} subtitle algo finished successfully.")

            return handle_fut_exception

        assert isinstance(frame_ch_list, list)
        assert isinstance(event_ch_list, list)
        futs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(job_cfgs)) as executor:
            for i, job_config in enumerate(job_cfgs):
                fut = executor.submit(self.run_one, job_config, frame_ch_list[i], event_ch_list[i], task_context, logger=logger)
                fut.add_done_callback(gen_fut_exception_handler(frame_ch_list[i]))
                futs.append(fut)
        job_results = [f.result() for f in futs]
        # print(job_results)
        return job_results

    def run_one(self, job_cfg: SubtitleJobCfg, stream_msg_ch, event_q, task_context: TaskContext, logger: logging.Logger) -> SubtitleJobResult:
        """Parse the config from job_cfg and tracking subtitles.

        Args:
            job_cfg (SubtitleJobCfg): the config parsed from task.
            task_context (TaskContext): The global task context.
            logger (Logger): logger for this job

        Returns:
            SubtitleJobResult: the tacking job result.
        """
        # batch_size = 10
        # cut_count = 3
        batch_size = 1
        fps = job_cfg.fps * batch_size

        media_meta = job_cfg.media.meta
        height = media_meta.height if media_meta is not None else None
        width = media_meta.width if media_meta is not None else None
        # height, width = 1280, 720
        # height, width = 1080, 1920

        tracker = SubtitleMatchingTracker(width or 0, height or 0)
        for config in job_cfg.configs:
            subtitle = Subtitle(
                id=config.text_index,
                rule_id=job_cfg.rule_id,
                recog_time_patchs=config.time_patchs,
                time_range_type=config.time_range_type,
                text_type=config.text_type,
                emergency_type=config.emergency_type,
                text=config.text,
                recog_threshold=config.threshold,
                min_text_number=config.min_text_number or 0,
                continuous_appearance_times=config.continuous_appearance_times
            )
            tracker.register(str(subtitle.id), subtitle)

        stream_msg_gen = stream_msg_ch.output()
        # for batch_frame in gather_batch_frames_from_generator(stream_msg_gen, 1, batch_size):
        for stream_msg in stream_msg_gen:
            if stream_msg.image is None:
                continue
            frame = stream_msg.image
            batch_frame = BatchFrame(frames=[frame], batch_size=1)
            # logger.info(f"get frame from generator. batch size: {batch_frame.batch_size}, "
            #             f"largest frame-id: {batch_frame.frames[-1].frame_number}")
            logger.debug(f"enter msg_id: {stream_msg_ch.id} image-id: {stream_msg.id}")
            t1_ms = (time.time() * 1000)
            tracker.run(batch_frame, logger, stream_msg_ch.id)
            t2_ms = (time.time() * 1000)
            logger.debug(f"{stream_msg_ch.id} tracker.run(batch_frame["
                         f"size: {batch_frame.batch_size}, image-id: {stream_msg.id}"
                         f"]) use time {t2_ms - t1_ms}ms")
            # if c > 10:
            #     break
            # c += 1
        stream_msg_gen.close()
        ai_result_dict: dict[str, Any] = dict()
        ai_result: list[Any] = []
        continuous_appear_frames: list[ContinuousFrame] = []
        # The following for loop currently only has one iteration
        for recog_result in tracker.subtitles.values():
            # text_type==0 is OCR, otherwise it's bottom subtitle. Bottom subtitle needs miss info
            if recog_result.text_type == 0 and recog_result.continuous_appearance_times > 0:
                continuous_image_nums = int(recog_result.continuous_appearance_times / (1 / fps))  # Minimum number of consecutive frames required
                tmp_frames: list[Frame] = []
                sum_similarity = float(0)
                min_similarity = float(0) if len(tracker.all_miss_results) > 0 else float(99999)
                max_similarity = float(0) if len(tracker.all_miss_results) > 0 else float(-1)

                for i in range(len(tracker.all_miss_results)):  # All miss frame recognition results
                    # If tracked continuously, add to array
                    is_miss = recog_result.id in tracker.all_miss_results[i].miss_ids  # Whether it exists in miss_ids
                    if not is_miss:
                        tmp_frames.append(tracker.all_miss_results[i].frame)
                        s = recog_result.similarity_mapper.get(tracker.all_miss_results[i].frame.timestamp, 0)
                        sum_similarity += s
                        max_similarity = max(max_similarity, s)
                        min_similarity = min(min_similarity, s)

                    # If not tracked or tracked but at the last frame, need to check if continuous display duration is met. If not, reset tmp_frames and sum_similarity
                    if is_miss or (not is_miss and i == len(tracker.all_miss_results) - 1):
                        # If continuous appearance duration is met, then requirement is satisfied
                        if len(tmp_frames) >= continuous_image_nums:
                            start_frame = tmp_frames[0]
                            end_frame = tmp_frames[-1]
                            continuous_frame = ContinuousFrame(rule_id=job_cfg.rule_id,
                                                               text_index=recog_result.id,
                                                               start_frame=start_frame,
                                                               end_frame=end_frame,
                                                               avg_similarity=sum_similarity / len(
                                                                   tmp_frames),
                                                               max_similarity=max_similarity,
                                                               min_similarity=min_similarity,
                                                               duration=int(end_frame.timestamp - start_frame.timestamp))
                            continuous_appear_frames.append(continuous_frame)
                            recog_result.total_continuous_appearance_frame += 1
                        tmp_frames = []
                        sum_similarity = float(0)
            else:  # For bottom subtitle, normally emergency is 1, meaning it only needs to appear at least once
                for i in range(len(tracker.ai_result)):  # Only miss frames
                    if recog_result.emergency_type == EmergencyType.AT_LEAST_ONE and recog_result.is_tracked():  # TODO bugfix: check if already tracked
                        if recog_result.id in tracker.ai_result[i].miss_ids:  # Whether the i-th miss frame has this subtitle id missing
                            tracker.ai_result[i].miss_ids.remove(recog_result.id)  # Purpose: if current subtitle has appeared at least once, miss_ids no longer needed, quality check requirement is met
                # For unappeared ones, mark which script didn't appear in the time period
                for i in range(len(tracker.ai_result)):
                    if len(tracker.ai_result[i].miss_ids):
                        ai_result_dict[tracker.ai_result[i].frame.timestamp] = tracker.ai_result[i]
                ai_result = sorted(ai_result_dict.values(), key=lambda x: x.frame.timestamp)
        return SubtitleJobResult(
            ai_result={
                "subtitle": ai_result,  # Miss frame results
                "subtitle_continuous_appear": continuous_appear_frames
            },
            recog_results=list(tracker.subtitles.values()),
        )


class SubtitleMatchingTracker:
    def __init__(self, width: int, height: int) -> None:
        self.split_num = 10
        self.max_distance = height / 4
        self.grid_size = height / self.split_num
        # {"id": Subtitle}
        self.subtitles: dict[str, Any] = {}
        self.service = GeneralOCRService()
        self.excutor = diff_match_patch()
        self.excutor.Diff_EditCost = 6
        self.conflict_maps: dict[str, Any] = {}
        self.ai_result: list[Any] = []  # MissResult, missing frames
        self.all_miss_results: list[Any] = []  # All MissResult
        self.table = {
            ord(f): ord(t)
            for f, t in zip("，！？【】（）％＃＠＆１２３４５６７８９０：；", ",!?[]()%#@&1234567890:;")
        }

    def register(self, id: str, subtitle: Subtitle):
        if id in self.subtitles:
            return
        self.subtitles[id] = subtitle
        subtitle.mask = [False] * len(subtitle.text)
        subtitle.text = subtitle.text.translate(self.table)

    def _get_match_mask2(
            self, a_text: str, b_text: str
    ) -> tuple[list[bool], float, str]:
        a_text = a_text.strip()
        mask = np.full((len(a_text)), False)
        if len(a_text) == 0:
            return mask.tolist(), 0, ''
        '''
        diffs shows the diff between two strings.
        1. flag=0: identical part
        2. flag=-1: missing characters
        3. flag=1: extra characters
        e.g.: "abcdebb", "aabcdfbb"
        diffs=[(1, 'a'), (0, 'abcd'), (-1, 'e'), (1, 'f'), (0, 'bb')]
        '''
        diffs = self.excutor.diff_main(a_text, b_text)
        index = 0
        for diff_flag, diff in diffs:
            if diff_flag == 0:
                end_index = index + len(diff)
                mask[index:end_index] = True
                index = end_index
            elif diff_flag < 0:
                index += len(diff)
            else:
                continue
        # Record indices where mask is True
        indices = np.argwhere(mask).flatten().tolist()
        text = ''
        if indices:
            text_length = 1
            pos = 1
            start = 0
            lo, hi = -1, -1
            while True:
                if pos >= len(indices):
                    break
                if indices[pos] - indices[pos - 1] - 1 > 4:  # If gap between characters exceeds 4, need to recalculate, otherwise consider as continuous
                    start = pos
                else:
                    if indices[pos] - indices[start] + 1 > text_length:
                        lo, hi = indices[start], indices[pos]
                        text_length = hi - lo + 1
                pos += 1
            if hi > lo >= 0:
                for i in range(lo):
                    mask[i] = False
                for i in range(hi + 1, len(mask)):
                    mask[i] = False
                text = a_text[lo:hi + 1]
        # Return mask matching details and matching degree
        return mask.tolist(), sum(mask) / len(mask), text

    def _get_match_mask(
            self, module_text: str, recog_text: str
    ) -> tuple[list[bool], float]:
        mask = np.full((len(module_text)), False)
        if len(recog_text) > len(module_text) or len(recog_text) <= 2:
            return mask.tolist(), 0.0
        '''
        diffs shows the diff between two strings.
        1. flag=0: identical part
        2. flag=-1: missing characters
        3. flag=1: extra characters
        e.g.: "abcdebb", "aabcdfbb"
        diffs=[(1, 'a'), (0, 'abcd'), (-1, 'e'), (1, 'f'), (0, 'bb')]
        '''
        diffs = self.excutor.diff_main(module_text, recog_text)
        # self.excutor.diff_cleanupEfficiency(diffs)
        index = 0
        for diff_flag, diff in diffs:
            if diff_flag == 0:
                end_index = index + len(diff)
                mask[index:end_index] = True
                index = end_index
            elif diff_flag < 0:
                index += len(diff)
            else:
                continue
        # Record indices where mask is True
        indices = np.argwhere(mask).flatten().tolist()
        text_length = -1
        if indices:
            text_length = 1
            pos = 1
            start = 0
            lo, hi = -1, -1
            while True:
                if pos >= len(indices):
                    break
                if indices[pos] - indices[pos - 1] - 1 > 4:  # If gap between characters exceeds 4, need to recalculate, otherwise consider as continuous
                    start = pos
                else:
                    if indices[pos] - indices[start] + 1 > text_length:
                        lo, hi = indices[start], indices[pos]
                        text_length = hi - lo + 1
                pos += 1
            if hi > lo >= 0:
                for i in range(lo):
                    mask[i] = False
                for i in range(hi + 1, len(mask)):
                    mask[i] = False
        # Return mask matching details and matching degree
        return mask.tolist(), sum(mask) / max(text_length, len(recog_text))

    def run(self, frames: BatchFrame, logger: logging.Logger, msg_id:str):
        miss_results_per_frame = []
        match_results_per_frame = []
        for frame in frames.frames:
            valid_subtitles = self._get_valid_subtitles(frame)  # Filter subtitles that need to appear in the specified frame
            if not valid_subtitles:
                continue
            # OCR recognition, regardless of whether it's needed text
            frame.msg_id=msg_id
            frame.logger=logger
            ocr_result = self.service.predict(frame)
            # Filter out low confidence results, divide into 10 rows, aggregate OCR results
            loc_text_blocks = self._calc_text_loc_index(ocr_result)
            # Important!
            miss_ids, match_results = self._get_match_result(
                frame, loc_text_blocks, valid_subtitles
            )
            # if len(miss_ids) > 0:
            #     from workflow_worker.shared.utils.frame import decode_image
            #     cv_img = decode_image(frame.data)
            #     import cv2

            #     cv2.imwrite(f"test{frame.timestamp}.jpg", cv_img)
            # frame.data = None
            miss_results_per_frame.append(MissResult(miss_ids=list(miss_ids), frame=frame))
            match_results_per_frame.append(match_results)
        # Important! Merge detection results of a batch of frames
        self._get_best_track_result(miss_results_per_frame, match_results_per_frame)

    def _get_best_track_result(
            self,
            miss_results_per_frame: list[MissResult],
            match_results_per_frame: list[list[Subtitle]],
    ):
        # No recognition result, return directly
        if len(miss_results_per_frame) <= 0:
            return
        best_miss_results = miss_results_per_frame[0]
        best_match_results = match_results_per_frame[0]
        # Select the frame with the least miss in this batch as result, when batch_size=1, there's only one frame here
        for i in range(1, len(miss_results_per_frame)):
            if len(miss_results_per_frame[i].miss_ids) < len(
                    best_miss_results.miss_ids
            ):
                best_miss_results = miss_results_per_frame[i]
                best_match_results = match_results_per_frame[i]

        if len(best_miss_results.miss_ids) > 0:
            self.ai_result.append(best_miss_results)
        self.all_miss_results.append(best_miss_results)

        # Merge detection results
        for best_match_result in best_match_results:
            id = best_match_result.id
            origin_subtitle = self.subtitles[str(id)]
            origin_subtitle.similarity_mapper = best_match_result.similarity_mapper
            origin_subtitle.miss_frame_times = best_match_result.miss_frame_times
            if id in best_miss_results.miss_ids:
                continue
            mask = np.array(best_match_result.mask) | np.array(origin_subtitle.mask)
            origin_subtitle.x_min = min(origin_subtitle.x_min, best_match_result.x_min)
            origin_subtitle.y_min = min(origin_subtitle.y_min, best_match_result.y_min)
            origin_subtitle.x_max = max(origin_subtitle.x_max, best_match_result.x_max)
            origin_subtitle.y_max = max(origin_subtitle.y_max, best_match_result.y_max)
            origin_subtitle.mask = mask.flatten().tolist()

    def _get_valid_subtitles(self, frame: Frame):
        valid_subtitles = {}
        frame_time = frame.timestamp
        for subtitle in self.subtitles.values():
            if subtitle.emergency_type == EmergencyType.AT_LEAST_ONE:  # Appear at least once, if appeared before and meets threshold, no need to detect afterwards
                if sum(subtitle.mask) / len(subtitle.text) >= subtitle.recog_threshold:
                    continue
            if subtitle.time_range_type == TimeRangeType.ALL_VIDEO:
                subtitle.total_frames_count += 1
                valid_subtitles[subtitle.id] = deepcopy(subtitle)
                valid_subtitles[subtitle.id].mask = [False] * len(subtitle.text)
                continue
            for time_patch in subtitle.recog_time_patchs:
                if time_patch.is_in(frame_time):
                    subtitle.total_frames_count += 1
                    valid_subtitles[subtitle.id] = deepcopy(subtitle)
                    valid_subtitles[subtitle.id].mask = [False] * len(subtitle.text)
                    break
        return valid_subtitles

    def _calc_text_loc_index(self, ocr_result: OCRServiceResult):
        loc_text_blocks: dict[int, list[Any]] = {}
        for ocr_info in ocr_result.ocr_infos:
            for text_block in ocr_info.text_blocks:
                if text_block.text_confidence <= 0.75:
                    continue
                text_block.text = text_block.text.translate(self.table)
                y_min = min(text_block.polygon[1::2])
                index = int(y_min / self.grid_size)  # Divide video height into 10 parts, place subtitle at corresponding position based on its height
                if index not in loc_text_blocks:
                    loc_text_blocks[index] = []
                loc_text_blocks[index].append(text_block)
        return loc_text_blocks

    def _build_match_map2(
            self,
            frame: Frame,
            loc_text_blocks: dict[int, list[TextBlock]],
            valid_subtitles: dict[str, Subtitle],
    ):
        '''
            New map building algorithm
        '''

        start_index = 0
        end_index = self.split_num + 1
        check_text_blocks = []
        all_text = ''
        for index in range(start_index, end_index):
            check_text_blocks.extend(loc_text_blocks.get(index, []))
        for item in check_text_blocks:
            all_text += item.text

        match_map: dict[str, Any] = {}
        for subtitle in valid_subtitles.values():
            module_text = subtitle.text
            if len(module_text) == 0:
                continue
            cur_text = all_text
            if len(module_text) < len(all_text):
                _, _, txt = self._get_match_mask2(cur_text, module_text)
                cur_text = txt
            mask, similarity, _ = self._get_match_mask2(module_text, cur_text)
            if subtitle.text_type == TextType.PART_TEXT:
                if similarity < subtitle.recog_threshold / 2:
                    clip_index = len(module_text) // 2
                    recover_index = clip_index if len(module_text) % 2 == 0 else clip_index + 1
                    rotation_module_text = module_text[clip_index:] + module_text[:clip_index]
                    rotation_mask, rotation_similarity, _ = self._get_match_mask2(rotation_module_text, cur_text)
                    if rotation_similarity < subtitle.recog_threshold / 2:
                        continue
                    recover_mask = rotation_mask[recover_index:] + rotation_mask[:recover_index]
                    mask, similarity = recover_mask, rotation_similarity
            else:
                if similarity < subtitle.recog_threshold:
                    continue

            index = 0
            match_map[str(subtitle.id)] = [RecogSubtitle(
                id=subtitle.id,
                origin_text=module_text,
                recog_text='',  # unused
                x_min=9999999,  # unused
                y_min=9999999,  # unused
                x_max=9999999,  # unused
                y_max=9999999,  # unused
                mask=mask,
                similarity=similarity,
                frame_time=0,  # unused
            )]
        return match_map

    def _build_match_map(
            self,
            frame: Frame,
            loc_text_blocks: dict[int, list[TextBlock]],
            valid_subtitles: dict[str, Subtitle],
    ):
        # {text_block: [RecogSubtitle]}
        temp_map: dict[Any, Any] = {}
        for subtitle in valid_subtitles.values():  # Iterate over subtitles that need to be detected
            # Origine check range is [0, self.split_num -1]
            start_index = 0
            end_index = self.split_num + 1
            # Shrink check range if subtitle has been recogition before
            # if subtitle.x_max != -1:
            #     start_index = int(subtitle.y_min / self.grid_size) - 1
            #     end_index = int(subtitle.y_max / self.grid_size) + 1
            # Get all text blocks in check range
            check_text_blocks = []
            for index in range(start_index, end_index):
                check_text_blocks.extend(loc_text_blocks.get(index, []))

            for check_text_block in check_text_blocks:
                recog_text = check_text_block.text
                # if len(recog_text) < subtitle.min_text_number:
                #     continue
                module_text = subtitle.text
                # Important! Compare recognition result with text for similarity. If sentence breaking is severe, similarity will drop significantly.
                # E.g.: module_text='[full Chinese welcome text]', recog_text='[abbreviated text]', result only 0.44
                # mask True means matched
                mask, similarity = self._get_match_mask(module_text, recog_text)
                if similarity < 0.8:
                    if subtitle.text_type == TextType.PART_TEXT:
                        # Try reversing and testing again, mainly for scrolling subtitles that may be inverted front to back
                        clip_index = len(module_text) // 2
                        recover_index = (
                            clip_index if len(module_text) % 2 == 0 else clip_index + 1
                        )
                        rotation_module_text = (
                                module_text[clip_index:] + module_text[:clip_index]
                        )
                        rotation_mask, rotation_similarity = self._get_match_mask(
                            rotation_module_text, recog_text
                        )
                        if rotation_similarity < 0.8:
                            continue
                        recover_mask = (
                                rotation_mask[recover_index:]
                                + rotation_mask[:recover_index]
                        )
                        mask, similarity = recover_mask, rotation_similarity
                    else:
                        continue
                if check_text_block not in temp_map:
                    temp_map[check_text_block] = []
                temp_map[check_text_block].append(  # The same recognized result may be matched by multiple given subtitles
                    RecogSubtitle(
                        id=subtitle.id,
                        origin_text=module_text,
                        recog_text=recog_text,
                        x_min=min(check_text_block.polygon[0::2]),
                        y_min=min(check_text_block.polygon[1::2]),
                        x_max=max(check_text_block.polygon[0::2]),
                        y_max=max(check_text_block.polygon[1::2]),
                        mask=mask,
                        similarity=similarity,
                        frame_time=frame.timestamp,
                    )
                )
        # {id:list[RecogSubtitle]}
        match_map: dict[str, Any] = {}
        # Sort recog_subtitles by similarity & lens diff
        for text_block, recog_subtitles in temp_map.items():
            if len(recog_subtitles) <= 0:
                continue
            recog_subtitles.sort(
                key=lambda x: (x.similarity, len(x.recog_text) - len(x.origin_text)),
                reverse=True,
            )
            max_similarity = recog_subtitles[0].similarity
            conflict_subtitles = []
            for recog_subtitle in recog_subtitles:
                if recog_subtitle.similarity == max_similarity:
                    conflict_subtitles.append(recog_subtitle)
            if len(conflict_subtitles) > 1:
                self.conflict_maps[text_block] = conflict_subtitles
            else:
                match_id = recog_subtitles[0].id
                if match_id not in match_map:
                    match_map[match_id] = []
                match_map[match_id].append(recog_subtitles[0])
        return match_map

    def _get_match_result(
            self,
            frame: Frame,
            loc_text_blocks: dict[int, list[TextBlock]],
            valid_subtitles: dict[str, Subtitle],
    ):
        """Get miss_ids and match_result.

        1. miss_ids is the list of subtitle's id which recog similarity is less than
        threshold in frame.
        2. match_results is the list of recog_subtitle which recog similarity is greater
        than threshold. Every match_result in match_results has got the match similarity
        , mask and location of text.

        Args:
            loc_text_blocks (dict[str, list[TextBlock]]): _description_
            valid_subtitles (dict[str, Subtitle]): _description_
        """
        if get_env().is_use_new_algorithm == '':
            match_map = self._build_match_map(frame, loc_text_blocks, valid_subtitles)
        else:
            match_map = self._build_match_map2(frame, loc_text_blocks, valid_subtitles)

        miss_ids = set()
        valid_ids = set()
        for id, recog_subtitles in match_map.items():
            subtitle = valid_subtitles[id]
            if len(recog_subtitles) <= 0:
                continue
            mask = np.array(subtitle.mask)
            # Merge detection results by id
            if subtitle.x_max == -1:  # Select the result with highest matching degree for current subtitle to detect and assign
                recog_subtitles.sort(key=lambda x: sum(x.mask), reverse=True)
                recog_subtitle = recog_subtitles[0]
                subtitle.mask = recog_subtitle.mask
                subtitle.x_min = min(subtitle.x_min, recog_subtitle.x_min)
                subtitle.y_min = min(subtitle.y_min, recog_subtitle.y_min)
                subtitle.x_max = max(subtitle.x_max, recog_subtitle.x_max)
                subtitle.y_max = max(subtitle.y_max, recog_subtitle.y_max)
                subtitle.similaritys.append(recog_subtitle.similarity)
            for recog_subtitle in recog_subtitles:
                mask |= np.array(recog_subtitle.mask)
                subtitle.x_min = min(subtitle.x_min, recog_subtitle.x_min)
                subtitle.y_min = min(subtitle.y_min, recog_subtitle.y_min)
                subtitle.x_max = max(subtitle.x_max, recog_subtitle.x_max)
                subtitle.y_max = max(subtitle.y_max, recog_subtitle.y_max)
                subtitle.similaritys.append(recog_subtitle.similarity)
            subtitle.mask = mask.tolist()

        # do conflict match
        for recog_subtitles in self.conflict_maps.values():
            max_cover_ratio_diff = 0
            match_recog_subtitle = None
            for recog_subtitle in recog_subtitles:
                subtitle = valid_subtitles[recog_subtitle.id]
                origin_mask = np.array(subtitle.mask)
                recog_mask = np.array(recog_subtitle.mask)
                if sum(origin_mask & recog_mask) > 0:  # Skip already recognized parts
                    continue
                # Add the one with most recognition
                if subtitle.text_type == TextType.ALL_TEXT:
                    cover_ratio_diff = self._calc_cover_ratio_diff(
                        origin_mask, recog_mask, True
                    )
                else:
                    cover_ratio_diff = self._calc_cover_ratio_diff(
                        origin_mask,
                        recog_mask,
                        False,
                        subtitle.min_text_number,
                    )
                if cover_ratio_diff > max_cover_ratio_diff:
                    max_cover_ratio_diff = cover_ratio_diff
                    match_recog_subtitle = recog_subtitle
            # Merge result
            if match_recog_subtitle:
                subtitle = valid_subtitles[match_recog_subtitle.id]
                subtitle.mask = (
                        np.array(subtitle.mask) | np.array(match_recog_subtitle.mask)
                ).tolist()
                subtitle.x_min = min(subtitle.x_min, match_recog_subtitle.x_min)
                subtitle.y_min = min(subtitle.y_min, match_recog_subtitle.y_min)
                subtitle.x_max = max(subtitle.x_max, match_recog_subtitle.x_max)
                subtitle.y_max = max(subtitle.y_max, match_recog_subtitle.y_max)
                subtitle.similaritys.append(match_recog_subtitle.similarity)

        self.conflict_maps = {}

        # OCR matching all means calculating the proportion of recognized text in each frame of video to the entire text to be tested.
        # This tests all the text, if below threshold then it doesn't meet the requirement.
        #
        # Bottom subtitle scrolls, so only partial text may appear in one frame. In this case similarity rule cannot be calculated like OCR.
        # Need to judge the proportion of matching between recognized text and text to be tested in current frame. If below threshold then it doesn't meet requirement.
        # Calculate similarity, return miss and recognize results.
        for subtitle in valid_subtitles.values():
            mask = np.array(subtitle.mask)

            if subtitle.text_type == TextType.ALL_TEXT:
                total_similarity = sum(mask) / len(subtitle.text)  # OCR
            else:
                total_similarity, text_length = self._calc_confidence(
                    mask.tolist())  # Calculate the proportion of matched characters to the longest matching string, i.e., similarity. E.g., a:abcd b:bd matches 2 characters, total length bcd=3, result 2/3
                if text_length < subtitle.min_text_number:
                    total_similarity = -1
            if total_similarity >= subtitle.recog_threshold:
                valid_ids.add(subtitle.id)
                # TODO: If recognition result is needed, it can be recorded via mask array. The mask array here is the recognition result of the current frame
            else:
                subtitle.miss_frame_times.append(frame.timestamp)
            subtitle.similarity_mapper[frame.timestamp] = total_similarity  # As long as emergency_type=0, similarity values for all time frames will be recorded
        miss_ids.update(set(valid_subtitles.keys()) - valid_ids)  # Record the id of subtitles that don't meet requirements, i.e., text_index
        return miss_ids, list(valid_subtitles.values())

    def _calc_cover_ratio_diff(
            self,
            origin_mask: np.ndarray,
            recog_mask: np.ndarray,
            is_full_text: bool = True,
            min_text_number: int = 0,
    ):
        """Calculate the cover_ratio_diff alias confidence.

        1. For the all_text type, the cover_ratio_diff is union_ratio - origin_ratio.
        2. For the part_text type, find the longest match text of union_text and origin
        text and calculate the cover ratio diff.
        """
        cover_ratio_diff = 0.0
        if is_full_text:
            origin_confidence = sum(origin_mask) / len(origin_mask)
            # Union origin_mask & origin mask and calculate cover_ratio.
            union_confidence = sum(origin_mask | recog_mask) / len(origin_mask)
            cover_ratio_diff = union_confidence - origin_confidence
        else:
            # Calculate cover ratio for origin mask.
            origin_confidence, origin_text_length = self._calc_confidence(
                origin_mask.tolist()
            )
            # If the longest match text's length less than threshold, set to 0.
            if origin_text_length < min_text_number:
                origin_confidence = 0.0

            # Union mask
            union_mask = origin_mask | recog_mask
            # Calculate cover ratio for union mask.
            union_confidence, union_text_length = self._calc_confidence(
                union_mask.tolist()
            )
            if union_text_length < min_text_number:
                union_confidence = 0.0
            # cover_ratio_diff is max(cover_ratio diff, added_text/len(text)).
            cover_ratio_diff = max(
                union_confidence - origin_confidence,
                (sum(union_mask) - sum(origin_mask)) / len(origin_mask),
            )

        return cover_ratio_diff

    def _calc_confidence(self, mask: list[bool]):
        start_index, end_index = self._find_longest_text(mask)
        selected_mask = mask[start_index:end_index]
        if len(selected_mask) <= 0:
            return 0.0, 0.0
        text_length = end_index - start_index + 1
        confidence = sum(selected_mask) / len(selected_mask)

        # Check rotation conditions
        clip_index = len(mask) // 2
        rotation_mask = mask[clip_index:] + mask[:clip_index]
        rotation_start_index, rotation_end_index = self._find_longest_text(
            rotation_mask
        )
        rotation_selected_mask = rotation_mask[rotation_start_index:rotation_end_index]
        if len(rotation_selected_mask) <= 0:
            return 0.0, 0.0
        rotation_text_length = rotation_end_index - rotation_start_index + 1
        rotation_confidence = sum(rotation_selected_mask) / len(rotation_mask)
        if rotation_confidence > confidence:
            return rotation_confidence, rotation_text_length
        return confidence, text_length

    def _find_longest_text(self, mask: list[bool], ttl: int = 3):
        res_start_index = res_end_index = 0
        res_ttl = tmp_ttl = ttl
        if len(mask) <= 0:
            return res_start_index, res_end_index
        start_index = end_index = 0
        has_found = False
        for i in range(len(mask)):
            if not has_found:
                if mask[i]:
                    has_found = True
                    tmp_ttl = ttl
                    start_index = end_index = i
            else:
                if not mask[i]:
                    if tmp_ttl <= 0:
                        has_found = False
                        now_length = end_index - start_index + 1
                        res_length = res_end_index - res_start_index + 1
                        if now_length > res_length:
                            res_end_index = end_index
                            res_start_index = start_index
                            res_ttl = tmp_ttl
                        continue
                    else:
                        tmp_ttl -= 1
                else:
                    tmp_ttl = ttl
                end_index += 1
        now_length = end_index - start_index + 1
        res_length = res_end_index - res_start_index + 1
        if now_length > res_length:
            res_end_index = end_index
            res_start_index = start_index
            res_ttl = tmp_ttl
        return res_start_index, res_end_index - (ttl - res_ttl)

# The following are commented-out test fixtures using real Chinese financial regulatory subtitles.
# The Chinese text values are example on-screen text from Chinese financial product videos
# (fund names, risk ratings, legal disclaimers) and must remain in Chinese to be realistic test data.
# test_subtitle1 = Subtitle(
#     id=1,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="基金名称",
#     recog_threshold=0.8,
#     min_text_number=-1
# )

# test_subtitle2 = Subtitle(
#     id=2,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="基金etc.级风险,(根据公司内部etc.级评价)",
#     recog_threshold=0.8,
#     min_text_number=-1
# )

# test_subtitle3 = Subtitle(
#     id=2,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="适合投资者Type",
#     recog_threshold=0.8,
#     min_text_number=-1
# )

# test_subtitle3 = Subtitle(
#     id=3,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="工银科创ETF联接(A/C)",
#     recog_threshold=0.8,
#     min_text_number=-1
# )

# test_subtitle4 = Subtitle(
#     id=4,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="中高风险(R4)",
#     recog_threshold=0.8,
#     min_text_number=-1
# )
# test_subtitle5 = Subtitle(
#     id=5,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="中风险(R3)",
#     recog_threshold=0.8,
#     min_text_number=-1
# )
# test_subtitle6 = Subtitle(
#     id=6,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="风险承受能力At/In(C4)及以上的投资者",
#     recog_threshold=0.8,
#     min_text_number=-1
# )
# test_subtitle7 = Subtitle(
#     id=7,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="风险承受能力At/InC3及以上的投资者",
#     recog_threshold=0.8,
#     min_text_number=-1
# )
# test_subtitle8 = Subtitle(
#     id=8,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="风险承受能力At/InC5及以上的投资者",
#     recog_threshold=0.8,
#     min_text_number=-1
# )
# test_subtitle9 = Subtitle(
#     id=9,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="锂电池ETF",
#     recog_threshold=0.8,
#     min_text_number=-1
# )

# test_subtitle10 = Subtitle(
#     id=10,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.ALL_TEXT,
# text="版权申明:本场直播仅限于基金管理Person与合作平台开展宣传推广之目的,禁止第三方机构单独摘引、截取Or以其他不恰When方式转播。",
#     recog_threshold=0.8,
#     min_text_number=-1
# )

# test_subtitle11 = Subtitle(
#     id=11,
#     recog_time_patchs=[TimePatch(start_time=0, end_time=10)],
#     time_range_type=TimeRangeType.ALL_VIDEO,
#     text_type=TextType.PART_TEXT,
# text="本场直播嘉宾投资观点仅供参考，不代表任何投资建议Or承诺，基金有风险，投资需谨慎。基金管理Person依照恪尽职守、诚实守信、谨慎勤勉的原则管理And运用基金财产，但不保证基金一定盈利，也不保证最低收益。本次直播中可能提及的锂电池ETF基金，本基金属于股票型基金，风险与收益高于混合型基金、债券型基金与货币市场基金。本基金为指数基金，主要采用完全复制策略。根据《工银瑞信基金管理公司基金风险etc.级评价体系》,本基金的风险评级为中风险(R4),适合风险承受能力At/InC4及以上的投资者进行投资,通过代销机构购买本产品的，请以代销机构风险评价etc.级Result为准。基金过往业绩不预示未来表现，基金管理Person管理的其他基金的业绩并不构成基金业绩表现的保证。投资者投资基金前应认真阅读",
#     recog_threshold=0.8,
#     min_text_number=10
# )
# client = SubtitleMatchingTracker(width=720, height=1280)
# client.register(test_subtitle1.id, test_subtitle1)
# client.register(test_subtitle2.id, test_subtitle2)
# client.register(test_subtitle3.id, test_subtitle3)
# client.register(test_subtitle4.id, test_subtitle4)
# client.register(test_subtitle5.id, test_subtitle5)
# # client.register(test_subtitle6.id, test_subtitle6)
# client.register(test_subtitle7.id, test_subtitle7)
# client.register(test_subtitle8.id, test_subtitle8)
# client.register(test_subtitle9.id, test_subtitle9)
# client.register(test_subtitle10.id, test_subtitle10)
# client.register(test_subtitle11.id, test_subtitle11)

# frames1 = BatchFrame(
#     frames=[
#         Frame(
#             timestamp=0,
#             height=1280,
#             width=720,
#         )
#     ],
#     batch_size=1,
# )
# frames2 = BatchFrame(
#     frames=[
#         Frame(
#             timestamp=1,
#             height=1280,
#             width=720,
#         )
#     ],
#     batch_size=1,
# )
# frames3 = BatchFrame(
#     frames=[
#         Frame(
#             timestamp=2,
#             height=1280,
#             width=720,
#         )
#     ],
#     batch_size=1,
# )
# client.run(frames1)
# client.run(frames2)
# client.run(frames3)
# print(client.ai_result)
# for subtitle in client.subtitles.values():
#     print(subtitle)
