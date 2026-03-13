"""
Person Tracking Processor

Processes person tracking results and generates reports.
"""

from typing import Any, cast

from workflow_worker.domain.entities.common.time_patch import TimePatch
from workflow_worker.domain.entities.frame import BatchFrame, Frame
from workflow_worker.domain.entities.tasks.person_tracking.config import SinglePersonTrackingJobCfg
from workflow_worker.domain.entities.tasks.person_tracking.report import (
    HumanTackReportResult,
    ReportPerson,
)
from workflow_worker.domain.entities.tasks.person_tracking.result import PersonTrackingJobResult
from workflow_worker.domain.entities.service.human_tracking import PersonTrackingResult
from workflow_worker.domain.entities.task import Participant, Task
from workflow_worker.services.ai.feat.service import FeatService
from workflow_worker.services.ai.det.service import DetService
from workflow_worker.shared.utils.common import time_transport
from workflow_worker.shared.utils.frame import (
    decode_image,
    encode_image,
    get_data_from_url,
    get_image_bytes,
    get_storage_url,
)
from workflow_worker.shared.logging._logging import get_logger

logger = get_logger(__name__)


class PersonTrackingProcessor:
    """Processor for person tracking job results."""

    def __init__(self) -> None:
        self.task_uuid: int | None = None
        self.video_duration = 0.0
        self.relation: dict[str, list[dict[str, Any]]] = {}
        self.identity_mapper: dict[str, dict[str, Any] | None] = {}
        self.verification_threshold = 0.75

    def run(
        self,
        cfg: SinglePersonTrackingJobCfg,
        task: Task,
        human_tracking_job_result: PersonTrackingJobResult,
    ) -> HumanTackReportResult:
        """Run reporter to get a report for rule point.

        Args:
            cfg: Single person tracking job configuration
            task: The origin task object
            human_tracking_job_result: Human track result

        Returns:
            HumanTackReportResult: result of human track
        """
        self.task_uuid = task.id
        assert task.media.meta is not None, "media metadata must be set before running processor"
        self.video_duration = float(task.media.meta.duration or 0.0)
        threshold = cfg.verification_threshold
        if threshold > 0:
            self.verification_threshold = threshold
        result = self._process(cfg, task, human_tracking_job_result)
        return result

    def _process(
        self,
        cfg: SinglePersonTrackingJobCfg,
        task: Task,
        tracking_result: PersonTrackingJobResult,
    ):
        """Real do the human track report.

        This function parses tracking sequences from tracking results and parses
        participant sequences from participants, then tries to assign identity to
        tracking sequences using identity mapper which is built from tracking_result
        & participants. After that, this function gathers all matched tracking
        sequences, and does all five checkings controlled by params. At the end,
        builds the report and returns it.

        Args:
            cfg: Same frame cfg
            task: The origin task object
            tracking_result: Human track result

        Returns:
            Result of the human track
        """
        # Parse tracking sequences from tracking result
        tracking_sequences = self._get_tracking_sequences(tracking_result.results, cfg)

        # Parse participant sequences from task.participants
        participants = [p for p in task.participants if p is not None]
        participant_sequences = self._get_participant_sequences(participants)

        # Build the mapper between tracking_sequences and participant_sequences
        self._get_identity_mapper(tracking_sequences, participant_sequences)

        report: dict[str, Any] = {"reasons": [], "status": 0}
        report["result"] = {
            "cumulative_number": -1,
            "persons": [],
            "strangers": [],
            "lost_participants": [],
            "ratio_participants": [],
            "max_participants": [],
        }

        # Get all matched tracking sequences
        self._get_all_ts(tracking_sequences, participant_sequences, report)

        # Do the check for all checkings
        cumulative_number = cfg.cumulative_number
        if cumulative_number > 0:
            self._get_cumulative_number(tracking_sequences, cumulative_number, report)

        ratio = cfg.ratio
        if ratio >= 0:
            self._get_ratio_warning(
                ratio, tracking_sequences, participant_sequences, report
            )

        lost_warning_threshold = cfg.lost_warning_threshold
        if lost_warning_threshold >= 0:
            self._get_lost_warning(
                lost_warning_threshold,
                tracking_sequences,
                participant_sequences,
                report,
            )

        num_of_people = cfg.num_of_people
        if num_of_people >= 0:
            self._get_max_num_warning(num_of_people, tracking_sequences, report)

        stranger_warning_flag = cfg.stranger_warning_flag
        if stranger_warning_flag:
            self._get_stranger_warning(tracking_sequences, report)

        # Parse report
        result_data: dict[str, Any] = report["result"]
        result = HumanTackReportResult(
            cumulative_number=cast(int, result_data["cumulative_number"]),
            persons=cast(list[ReportPerson], result_data["persons"]),
            strangers=cast(list[ReportPerson], result_data["strangers"]),
            lost_participants=cast(list[ReportPerson], result_data["lost_participants"]),
            max_participants=cast(list[ReportPerson], result_data["max_participants"]),
            ratio_participants=cast(list[ReportPerson], result_data["ratio_participants"]),
            status=str(report["status"]),
            reasons=cast(list[str], report["reasons"]),
        )

        return result

    def _get_reversed_time_patchs(
        self, time_patchs: list[TimePatch]
    ) -> list[TimePatch]:
        """Reverse the time patches.

        Get time periods except time_patchs.

        Args:
            time_patchs: The origin time patches.

        Returns:
            The reversed time patches.
        """
        reversed_time_patchs = []
        loop_start_time = 0.0
        for time_patch in time_patchs:
            start_time = time_patch.start_time
            end_time = time_patch.end_time
            if loop_start_time != start_time:
                ts = TimePatch(start_time=loop_start_time, end_time=loop_start_time)
                ts.update_end_time(start_time)
                reversed_time_patchs.append(ts)
            loop_start_time = end_time
        if loop_start_time < self.video_duration:
            ts = TimePatch(start_time=loop_start_time, end_time=loop_start_time)
            ts.update_end_time(self.video_duration)
            reversed_time_patchs.append(ts)
        return reversed_time_patchs

    def _get_tracking_sequences(
        self,
        tracking_results: list[PersonTrackingResult],
        cfg: SinglePersonTrackingJobCfg,
    ):
        """Parse tracking sequences from tracking_results.

        Args:
            tracking_results: The tracking result from job.

        Returns:
            The tracking sequences.
        """
        tracking_sequences = {}
        min_interval = cfg.min_time_interval * 1000

        for tracking_result in tracking_results:
            time_patchs = []
            for p in tracking_result.time_patchs:
                start_time = p.start_time * p._calc_time_scale(p.time_unit or "ms")
                end_time = p.end_time * p._calc_time_scale(p.time_unit or "ms")
                if end_time - start_time > min_interval:
                    time_patchs.append(p)

            if not time_patchs:
                continue

            tracking_id = tracking_result.tracking_id
            bbox = tracking_result.bbox

            lost_time_patchs = self._get_reversed_time_patchs(time_patchs)
            face_bytes = None
            face_bbox = None
            if isinstance(bbox, list) and len(bbox) == 4:
                img_bytes = get_image_bytes(tracking_result.frame)
                if isinstance(img_bytes, bytes):
                    cv_img = decode_image(img_bytes)
                    x1, y1, x2, y2 = bbox
                    face_img = cv_img[y1:y2, x1:x2, :]  # pyright: ignore[reportOptionalSubscript]
                    face_bbox = [0, 0, x2 - x1 - 1, y2 - y1 - 1]
                    face_bytes = encode_image(face_img)
            tracking_sequence = {
                "lost_time_patchs": lost_time_patchs,
                "face_frame": Frame(url="", data=face_bytes),
                "face_bbox": face_bbox,
                "identity": tracking_id,
                "requirement": "00",
            }
            tracking_sequences[tracking_id] = tracking_sequence
        return tracking_sequences

    def _get_participant_sequences(self, participant_infos: list[Participant]):
        """Parse participant sequences from task.participants.

        Args:
            participant_infos: The participant info from task.

        Returns:
            The parsed tracking sequences.
        """
        participant_sequences = {}
        for participant_info in participant_infos:
            identity = participant_info.role
            url = participant_info.picture or ""
            img_bytes = get_data_from_url(url)
            face_bbox = None
            if img_bytes:
                frames = BatchFrame(frames=[Frame(url=url)], batch_size=1)
                detection_service = DetService()
                detection_results = detection_service.run(frames)
                if detection_results and detection_results[0] and detection_results[0].face_infos and \
                        detection_results[0].face_infos[0]:
                    face_info = detection_results[0].face_infos[0]
                    face_bbox = face_info.face_bbox
            participant_sequences[identity] = {
                "lost_time_patchs": None,
                "face_frame": Frame(url="", data=img_bytes),
                "face_bbox": face_bbox,
                "identity": identity,
                "requirement": participant_info.requirement,
            }
        return participant_sequences

    def _fill_relation(
        self,
        tracking_sequences: dict[str, dict[str, Any]],
        participant_sequences: dict[str, dict[str, Any]],
    ):
        """Build the matched mapper between tracking_sequences and participant_sequences.

        Args:
            tracking_sequences: The parsed tracking_sequences
            participant_sequences: The parsed participant_sequences
        """
        feat_service = FeatService()
        for t_identity, t_message in tracking_sequences.items():
            for p_identity, p_message in participant_sequences.items():
                tracking_face_frame = t_message["face_frame"]
                tracking_face_bbox = t_message["face_bbox"]
                participant_face_frame = p_message["face_frame"]
                participant_face_bbox = p_message["face_bbox"]
                if tracking_face_frame is None or participant_face_frame is None:
                    continue
                similarity = feat_service._get_similarity(
                    participant_face_frame,
                    tracking_face_frame,
                    participant_face_bbox,
                    tracking_face_bbox,
                )
                if similarity > self.verification_threshold:
                    if p_identity not in self.relation:
                        self.relation[p_identity] = []
                    self.relation[p_identity].append(
                        {"t_identity": t_identity, "similarity": similarity}
                    )

    def _get_identity_mapper(
        self,
        tracking_sequences: dict[str, dict[str, Any]],
        participant_sequences: dict[str, dict[str, Any]],
    ):
        """Build the tracking identity mapper.

        Args:
            tracking_sequences: The parsed tracking_sequences
            participant_sequences: The parsed participant_sequences
        """
        self._fill_relation(tracking_sequences, participant_sequences)

        occupied_identity = set()
        for p_identity, t_messages in self.relation.items():
            t_messages.sort(key=lambda x: x["similarity"], reverse=True)
            matched_t_message = None
            for t_message in t_messages:
                t_identity = t_message["t_identity"]
                if t_identity in occupied_identity:
                    continue
                matched_t_message = t_message
                occupied_identity.add(t_identity)
                break
            self.identity_mapper[p_identity] = matched_t_message

        for t_identity in tracking_sequences:
            if t_identity in occupied_identity:
                continue
            self.identity_mapper[t_identity] = {
                "t_identity": t_identity,
                "similarity": 1,
            }

    def _get_all_ts(self, tracking_sequences, participant_sequences, report):
        """Get all matched tracking sequences.

        Args:
            tracking_sequences: The parsed tracking_sequences
            participant_sequences: The parsed participant_sequences
            report: the report with check results.
        """
        persons = []
        for identity in participant_sequences:
            appearance_requirement = participant_sequences[identity]["requirement"]
            if identity not in self.identity_mapper and appearance_requirement == "01":
                report["status"] = 1
                report["reasons"].append("A required participant did not appear")
                report_person = ReportPerson(identity=identity, times=[])
                report["result"]["ratio_participants"].append(report_person)

        for identity, t_messages in self.identity_mapper.items():
            if t_messages is None:
                continue
            t_identity = t_messages["t_identity"]
            tracking_sequence = tracking_sequences[t_identity]
            lost_time_patchs = tracking_sequence["lost_time_patchs"]
            face_frame = tracking_sequence["face_frame"]
            appearance_requirement = tracking_sequence["requirement"]
            if identity in participant_sequences:
                appearance_requirement = participant_sequences[identity]["requirement"]
            identity_type = 0 if identity and identity[0] == "v" else 1
            stored_time_patchs = []
            if lost_time_patchs:
                time_patchs = self._get_reversed_time_patchs(lost_time_patchs)
                stored_time_patchs = self._get_format_time_patchs(time_patchs)
            elif isinstance(lost_time_patchs, list):
                stored_time_patch = {
                    "start_time": time_transport(0),
                    "end_time": time_transport(self.video_duration),
                }
                stored_time_patchs.append(stored_time_patch)
            url = ""
            if face_frame.data is not None and len(stored_time_patchs) > 0:
                url = get_storage_url(self.task_uuid, face_frame.data)
            if len(stored_time_patchs) <= 0:
                continue
            person = {
                "url": url,
                "identity": identity if identity_type else "unknown",
                "identity_type": identity_type,
                "appearance_requirement": appearance_requirement,
                "times": stored_time_patchs,
            }
            persons.append(person)
            if appearance_requirement == "02" and len(stored_time_patchs) > 0:
                report["status"] = 1
                report["reasons"].append("A prohibited person appeared on screen")
        report["result"]["persons"] = persons

    def _get_format_time_patchs(self, time_patchs: list[TimePatch]):
        """Change the time_patchs to human-read format.

        Args:
            time_patchs: The origin time patches.

        Returns:
            The human-read time patches.
        """
        format_time_patchs = []
        for time_patch in time_patchs:
            format_time_patchs.append(
                {
                    "start_time": time_transport(time_patch.start_time),
                    "end_time": time_transport(time_patch.end_time),
                }
            )
        return format_time_patchs

    def _get_ratio_warning(
        self, ratio, tracking_sequences, participant_sequences, report
    ):
        """Perform face co-occurrence duration quality check."""
        ratio_participants = []
        for identity, t_messages in self.identity_mapper.items():
            if t_messages is None:
                continue
            t_identity = t_messages["t_identity"]
            tracking_sequence = tracking_sequences[t_identity]
            lost_time_patchs = tracking_sequence["lost_time_patchs"]
            appearance_requirement = tracking_sequence["requirement"]
            if identity in participant_sequences:
                appearance_requirement = participant_sequences[identity]["requirement"]
            if appearance_requirement != "01":
                continue
            total_duration = 0
            for lost_time_patch in lost_time_patchs:
                total_duration += lost_time_patch.get_duration()
            lost_ratio = total_duration / self.video_duration
            if 1 - lost_ratio < ratio:
                report["status"] = 1
                time_patchs = self._get_reversed_time_patchs(lost_time_patchs)
                report_person = ReportPerson(
                    identity=identity, times=self._get_format_time_patchs(time_patchs)
                )
                ratio_participants.append(report_person)
                report["reasons"].append(f"Participant {identity} on-screen time ratio is insufficient")
        report["result"]["ratio_participants"].extend(ratio_participants)

    def _merge_intervals(self, time_patchs: list[TimePatch]):
        """Merge the adjacent time patches.

        Args:
            time_patchs: The origin time patches.

        Returns:
            the merged time patches.
        """
        time_patchs.sort(key=lambda x: x.start_time)
        merged: list[Any] = []
        for time_patch in time_patchs:
            if not merged or merged[-1].end_time < time_patch.start_time:
                merged.append(time_patch)
            else:
                end_time = max(merged[-1].end_time, time_patch.end_time)
                merged[-1].update_end_time(end_time)
        return merged

    def _get_time_patch_count(self, time_patchs: list[TimePatch], num_of_people: int):
        """Calculate time patches with people number greater than num_of_people.

        Args:
            time_patchs: The origin time patches.
            num_of_people: the specified number of people.
        """
        if num_of_people < 0:
            return []
        time_points = []
        for time_patch in time_patchs:
            time_points.append((time_patch.start_time, "l"))
            time_points.append((time_patch.end_time, "r"))
        time_points.sort(key=lambda x: (x[0], -ord(x[1])))
        cnt = 0
        res_time_patchs = []
        for time_point in time_points:
            last_cnt = cnt
            if time_point[1] == "l":
                cnt += 1
            else:
                cnt -= 1
            if cnt == num_of_people + 1 and cnt > last_cnt:
                res_time_patchs.append(
                    TimePatch(start_time=time_point[0], end_time=time_point[0])
                )
            elif last_cnt == num_of_people + 1 and cnt < last_cnt:
                res_time_patchs[-1].update_end_time(time_point[0])
        return res_time_patchs

    def _get_max_num_warning(self, num_of_people, tracking_sequences, report):
        """Perform maximum co-occurrence number warning check."""
        all_time_patchs = []
        for t_messages in self.identity_mapper.values():
            if t_messages is None:
                continue
            t_identity = t_messages["t_identity"]
            tracking_sequence = tracking_sequences[t_identity]
            lost_time_patchs = tracking_sequence["lost_time_patchs"]
            all_time_patchs.extend(self._get_reversed_time_patchs(lost_time_patchs))
        time_patchs = self._get_time_patch_count(all_time_patchs, num_of_people)
        if len(time_patchs) > 0:
            report["status"] = 1
            report["reasons"].append(f"More than {num_of_people} people on screen")
            report_person = ReportPerson(
                times=self._get_format_time_patchs(time_patchs)
            )
            report["result"]["max_participants"] = [report_person]

    def _get_lost_warning(
        self,
        lost_warning_threshold,
        tracking_sequences,
        participant_sequences,
        report,
    ):
        """Perform disappearance warning threshold check."""
        for identity, t_messages in self.identity_mapper.items():
            if t_messages is None:
                continue
            t_identity = t_messages["t_identity"]
            tracking_sequence = tracking_sequences[t_identity]
            lost_time_patchs = tracking_sequence["lost_time_patchs"]
            appearance_requirement = tracking_sequence["requirement"]
            if identity in participant_sequences:
                appearance_requirement = participant_sequences[identity]["requirement"]
            if appearance_requirement != "01":
                continue
            all_lost_time_patchs = []
            for lost_time_patch in lost_time_patchs:
                duration = lost_time_patch.get_duration()
                if duration > lost_warning_threshold:
                    all_lost_time_patchs.append(lost_time_patch)
            if len(all_lost_time_patchs) > 0:
                report_person = ReportPerson(
                    identity=identity,
                    times=self._get_format_time_patchs(all_lost_time_patchs),
                )
                report["status"] = 1
                report["result"]["lost_participants"].append(report_person)

    def _get_stranger_warning(self, tracking_sequences, report):
        """Stranger warning."""
        stranger_time_patchs = []
        for identity, t_messages in self.identity_mapper.items():
            if t_messages is None:
                continue
            t_identity = t_messages["t_identity"]
            tracking_sequence = tracking_sequences[t_identity]
            lost_time_patchs = tracking_sequence["lost_time_patchs"]
            time_patchs = self._get_reversed_time_patchs(lost_time_patchs)
            if identity and identity[0] == "v":
                stranger_time_patchs.extend(time_patchs)
        stranger_time_patchs = self._merge_intervals(stranger_time_patchs)
        if len(stranger_time_patchs) > 0:
            report["status"] = 1
            report["reasons"].append("Stranger detected on screen")
            report_person = ReportPerson(
                identity="", times=self._get_format_time_patchs(stranger_time_patchs)
            )
            report["result"]["strangers"].append(report_person)

    def _get_cumulative_number(
        self, tracking_sequences, required_cumulative_number, report
    ):
        """Cumulative appearance count warning."""
        cumulative_number = len(tracking_sequences)
        report["result"]["cumulative_number"] = cumulative_number
        if cumulative_number != required_cumulative_number:
            report["status"] = 1
            report["reasons"].append(
                f"Video has {cumulative_number} participant(s), "
                f"expected {required_cumulative_number}"
            )
