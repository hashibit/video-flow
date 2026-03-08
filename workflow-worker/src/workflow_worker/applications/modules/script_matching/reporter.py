from workflow_worker.domain.entities.tasks.script_matching.report import ScriptMatchingReport
from workflow_worker.domain.entities.tasks.script_matching.result import ScriptMatchingJobResult
from workflow_worker.domain.entities.rule import RulePoint
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.base.reporter import Reporter


class ScriptMatchingReporter(Reporter):
    def __init__(self) -> None:
        super().__init__()
        self.job_name = "script_match"

    def run(
        self,
        rule_point: RulePoint,
        task: Task,
        script_match_job_result: ScriptMatchingJobResult,
        **job_results
    ) -> ScriptMatchingReport:
        """Run reporter to get a report for rule point

        Args:
            rule_point (RulePoint): rule point object
            task (Task): the origin task object
            script_match_result (ScriptMatchingJobResult): script match result

        Returns:
            ScriptMatchingReport: report of the input script match rule point
        """
        for rule_point_result in script_match_job_result.results:
            if rule_point_result.id == rule_point.id:
                status = True
                reasons = []
                if rule_point.script_cfg and rule_point_result.score < rule_point.script_cfg.script_threshold:
                    status &= False
                    reasons.append("Script similarity score below threshold")

#               # Script variable matching not included in MVP scope
                # for key_word in rule_point.script_cfg.key_words:
                #     if not word_in_text(
                #         key_word,
                #         rule_point_result.auc_text,
                #         rule_point.script_cfg.key_word_threshold,
                #     ):
                #         status &= False
#               #         reasons.append("Required keyword not detected")

                return ScriptMatchingReport(
                    reasons=reasons,
                    status="passed" if status else "failed",
                    result=rule_point_result,
                )

        reasons = ["No script detected"]
        return ScriptMatchingReport(reasons=reasons, status="failed", result=None)
