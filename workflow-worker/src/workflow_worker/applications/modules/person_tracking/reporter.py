from workflow_worker.domain.entities.tasks.person_tracking.report import (
    HumanTackReportResult,
    PersonTrackingReport,
)
from workflow_worker.domain.entities.rule import RulePoint
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.base.reporter import Reporter


class PersonTrackingReporter(Reporter):
    def __init__(self) -> None:
        super().__init__()
        self.job_name = "human_tracking"

    def run(
        self,
        rule_point: RulePoint,
        task: Task,
        human_tracking_job_result: HumanTackReportResult,
        **job_results,
    ) -> PersonTrackingReport:
        """Run reporter to get a report for rule point.

        Args:
            rule_point (RulePoint): rule point object
            task (Task): the origin task object
            tracking_result (PersonTrackingJobResult): human track result

            Returns:
                PersonTrackingReport: report of the input human track rule point
        """
        return PersonTrackingReport(
            reasons=human_tracking_job_result.reasons,
            status="failed" if human_tracking_job_result.status else "passed",
            result=human_tracking_job_result,
        )
