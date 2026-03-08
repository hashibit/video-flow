from workflow_worker.domain.entities.tasks.subtitle_matching.report import (
    SubtitleMatchingReport,
    SubtitleMatchingSingleResult,
)
from workflow_worker.domain.entities.tasks.subtitle_matching.result import SubtitleJobResult
from workflow_worker.domain.entities.rule import RulePoint
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.jobs.base.reporter import Reporter
from workflow_worker.shared.logging._logging import get_logger

logger = get_logger(__name__)

class SubtitleMatchingReporter(Reporter):
    def __init__(self) -> None:
        super().__init__()
        self.job_name = "subtitle_match"

    def run(
            self,
            rule_point: RulePoint,
            task: Task,
            subtitle_match_job_result: SubtitleJobResult,
            **job_results,
    ) -> SubtitleMatchingReport:
        """Run reporter to get a report for rule point

        Args:
            rule_point (RulePoint): rule point object
            task (Task): the origin task object
            subtitle_match_job_result (SubtitleJobResult): subtitle match result

        Returns:
            SubtitleMatchingReport: report of the input subtitle match rule point
        """
        results = []
        status = True

        rule_text_map = {}
        if rule_point.subtitle_cfg:
            for subtitle_text in rule_point.subtitle_cfg.texts:
                rule_text_map[subtitle_text.text_index] = subtitle_text

        for recog_result in subtitle_match_job_result.recog_results:
            if rule_point.id != recog_result.rule_id:  # Since this method is called based on rule loop count, need to exclude non-rule items here
                continue
            logger.info(f"subtitle_report1 rule_id={recog_result.rule_id}, {recog_result}")
            reasons = []
            if recog_result.mask is not None:
                recog_text_number = sum(x for x in recog_result.mask if x is not None)
            else:
                recog_text_number = 0
            recog_text_ratio = recog_text_number * 1.0 / len(recog_result.text)
            if recog_result.text_type == 0:

                # Distinguish between continuous duration rules and regular rules, quality check methods are different
                if recog_result.continuous_appearance_times > 0:
                    if recog_result.total_continuous_appearance_frame == 0:
                        reasons.append("No segment in the video meets the required continuous display duration")
                else:
                    if recog_text_ratio < recog_result.recog_threshold:
                        reasons.append("Text not fully displayed")

            elif recog_result.text_type == 1:
                rule_text = rule_text_map[recog_result.id]  # Corresponding rule configuration by id
                if recog_text_ratio < rule_text.cumulative_threshold:  # If current display ratio is below configured ratio
                    reasons.append(
                        f"Cumulative ratio {recog_text_ratio: .2f} "
                        f"is below the configured threshold {rule_text.cumulative_threshold: .2f}"
                    )
                if len(recog_result.miss_frame_times) > 0:  # If there are missing frames
                    reasons.append("Some frames do not meet the subtitle display requirement")
            if recog_result.total_frames_count == 0:
                reasons.append("No valid frames")

            # In non-continuous appearance rules, need to determine if there are miss frames to decide if quality check passes
            if recog_result.continuous_appearance_times == 0:
                if recog_result.emergency_type == 0:
                    if recog_result.miss_frame_times:
                        reasons.append("Text absent in some frames")
                elif recog_result.emergency_type == 1:
                    if (
                            len(recog_result.miss_frame_times)
                            == recog_result.total_frames_count
                    ):
                        reasons.append("Text never appeared in any frame")

            if reasons:
                status = False
            # remove mask for report
            recog_result.mask = []

            # remove similarity_mapper for report
            recog_result.similarity_mapper = {}

            results.append(
                SubtitleMatchingSingleResult(
                    subtitle_result=recog_result,
                    reasons=reasons,
                )
            )
        logger.info(f"subtitle_report2= {results}")

        return SubtitleMatchingReport(
            result=results,
            status="passed" if status else "failed",
            reasons=[] if status else ["Subtitle matching result does not meet the requirement"],
        )
