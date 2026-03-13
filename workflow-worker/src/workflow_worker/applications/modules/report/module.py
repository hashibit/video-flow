
from workflow_worker.domain.entities.report import (
    AiResult,
    Report,
    RulePointReport,
    RuleSectionReport,
)
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.base.reporter import Reporter
from workflow_worker.applications.modules.banned_word_detection.reporter import BannedWordDetectionReporter
from workflow_worker.applications.modules.person_tracking.reporter import PersonTrackingReporter
from workflow_worker.applications.modules.model import JobName
from workflow_worker.applications.modules.subtitle_matching.reporter import SubtitleMatchingReporter
from workflow_worker.applications.modules.script_matching.reporter import ScriptMatchingReporter


class ReportModule:
    def parse_task(self, task: Task) -> dict[str, Reporter]:
        """Parse task and create reporters.

        Args:
            task (Task): task config.

        Returns:
            dict[str, Reporter]: all reporter objects.
        """
        reporters: dict[str, Reporter] = {}
        for rule_section in task.scenario.rule_sections:
            rule_point = rule_section.rule_points[0]
            if not rule_point:
                continue
            # TODO: how to make it automated.
            if rule_point.script_cfg:
                reporters[JobName.ScriptMatching] = ScriptMatchingReporter()
            if rule_point.banword_cfg:
                reporters[JobName.BannedWordDetection] = BannedWordDetectionReporter()
            if rule_point.same_frame_cfg:
                reporters[JobName.PersonTracking] = PersonTrackingReporter()
            if rule_point.subtitle_cfg:
                reporters[JobName.SubtitleMatching] = SubtitleMatchingReporter()
        return reporters

    def run(self, task: Task, reporters: dict[str, Reporter], **job_results) -> Report:
        """Run all reporters to generate each report for jobs.

        Args:
            task (Task): task entity.
            reporters (dict[str, Reporter]): all reporter objects.

        Returns:
            Report: a report object.
        """

        rule_section_reports = []
        task_status = True
        task_reasons = []
        ai_result = {}
        for job_name in job_results:
            if getattr(job_results[job_name], "ai_result", None):
                ai_result.update(job_results[job_name].ai_result)
        for rule_section in task.scenario.rule_sections:  # Use scenario
            rule_point = rule_section.rule_points[0]
            if not rule_point:
                continue

            job_reports = {}
            job_cfgs = {}
            reasons = []

            for key in rule_point.__dict__:
                if key.endswith("_cfg"):
                    cfg = getattr(rule_point, key, None)
                    if not cfg:
                        continue
                    for job_name in cfg.require_jobs:
                        job_report = reporters[job_name].run(rule_point, task, **job_results)
                        job_reports[job_name + "_report"] = job_report
                        reasons += job_report.reasons
                        job_cfgs[key] = cfg
            rule_point_report = RulePointReport(
                id=rule_point.id,
                name=rule_point.name,
                biz_category=rule_point.biz_category,
                temporal_scope_category=rule_point.temporal_scope_category,
                category=rule_point.category,
                reasons=reasons,
                **job_reports,
                **job_cfgs
            )

            rule_section_report = RuleSectionReport(
                id=rule_section.id,
                name=rule_section.name,
                rule_point_reports=[rule_point_report],
                status="failed" if reasons else "passed",
                checked_status="failed" if reasons else "passed",
                reasons=rule_point_report.reasons,
            )
            rule_section_reports.append(rule_section_report)
            task_reasons.append(reasons)
            task_status = task_status and not reasons

        if "auc" in ai_result:
            auc = ai_result["auc"]
            # no need for saving word-level info
            for u in auc.dialogue.utterances:
                u.words = []

        return Report(
            name=task.name,
            id=task.id,
            rule_section_reports=rule_section_reports,
            status="passed" if task_status else "failed",
            checked_status="passed" if task_status else "failed",
            reasons=task_reasons,
            ai_result=AiResult(**ai_result),
            media=task.media,
        )
