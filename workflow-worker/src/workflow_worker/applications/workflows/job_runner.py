import asyncio
import json
import os
from typing import Any, cast

import logging as pylogging
from workflow_worker.interfaces.api.workflow_common_pb2 import JobInfo, JobReport
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.domain.entities.report import Report
from workflow_worker.domain.entities.task import Task
from workflow_worker.shared.utils.common import pascal_case_to_snake_case
from workflow_worker.applications.modules.factory import (
    create_subtitle_matching_modules,
    create_person_tracking_modules,
    create_speech_recognition_modules,
    create_banned_word_detection_modules,
    create_script_matching_modules
)
from workflow_worker.interfaces.events.event_factory import event_factory
from workflow_worker.infrastructure.media_stream.stream_factory import stream_factory

from workflow_worker.applications.workflows.task_context import TaskContext, task_context_store

global_logger = get_logger("JobRunner")

def get_task(task_json) -> Task:
    task_dict = cast(dict[str, Any], pascal_case_to_snake_case(task_json, only_key=True))
    task = Task(**task_dict)
    return task


def mock_job_report() -> JobReport:
    mock_file = os.path.join(os.path.dirname(__file__), "..", "test", "mock_job_report.json")
    with open(mock_file) as f:
        return JobReport(valueJson=f.read())


def mock_get_job(task_id) -> Task:
    mock_file = os.path.join(os.path.dirname(__file__), "..", "test", "mock_get_task_subtitle.json")
    with open(mock_file) as f:
        resp = json.load(f)
        task_dict = cast(dict[str, Any], pascal_case_to_snake_case(resp["Result"], only_key=True))
        task = Task(**task_dict)
        return task


async def wait_for_threads_complete(task_context, modules: dict[str, Any]) -> dict[str, Any]:
    # Execute in other threads
    # Pass task_context to every algo module
    running_threads: set[asyncio.Task[Any]] = set()
    for module_name, algo_func in modules.items():
        coro = asyncio.to_thread(algo_func, task_context=task_context)
        t = asyncio.create_task(coro, name=module_name)
        running_threads.add(t)

    results = {}

    logger = task_context.get_task_logger()
    logger.info(f"Start {len(running_threads)} coroutines:  {list(modules.keys())} ")

    while running_threads:
        done, running_threads = await asyncio.wait(running_threads, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            name = t.get_name()
            try:
                results[name] = await t
                # logger.debug(f"get algo result for {name}: {algo_result}")
            except Exception:
                import traceback
                logger.error(f"Error executing {name}! traceback:")
                logger.error(traceback.format_exc())
                results[name] = None
            finally:
                # cleanup task_context.frame_channels
                frame_ch = task_context.frame_channels[name]
                if frame_ch:
                    if type(frame_ch) is not list:
                        frame_ch = [frame_ch]
                    # okay. double loops, for code conciseness
                    logger.info(f"Clean frame_channels for {name}: {[c.get_name() for c in frame_ch]}")
                    for c in frame_ch:
                        c.mark_close()

                event_ch = task_context.event_channels[name]
                if event_ch:
                    if type(event_ch) is not list:
                        event_ch = [event_ch]
                    logger.info(f"Clean event_channels for {name}: {[c.get_name() for c in event_ch]}")
                    for c in event_ch:
                        c.stop()

    logger.info(f"Finished running algo modules: {list(results.keys())}. check their results for correctness...")

    errors = [f"{name} result is None" for name, result in results.items() if result is None]
    if errors:
        logger.error(f"!!! some algo module result are incorrect: {errors}")
        raise Exception(f"Algo module running failed: {errors}")
    else:
        logger.info("all algo modules result are correct!")

    return results


def create_task_logger(job_info: JobInfo):
    task_logger = global_logger.getChild(f"Task-{job_info.task_id}")
    filename = f"/tmp/workflow/task_{job_info.task_id}.log"
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)

    # file handler already exists
    if task_logger.hasHandlers():
        for h in task_logger.handlers:
            if h.get_name() == filename:
                return task_logger

    fh = pylogging.FileHandler(filename)
    fh.setLevel(pylogging.DEBUG)
    formatter = pylogging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    # add formatter to ch
    fh.setFormatter(formatter)
    fh.set_name(filename)
    task_logger.addHandler(fh)
    return task_logger


class JobRunner:
    def __init__(self):
        self.running_jobs: dict[int, JobInfo] = {}

    async def run_job(self, job_info: JobInfo) -> Report | str:
        task_logger = create_task_logger(job_info)
        try:
            self.running_jobs[job_info.id] = job_info
            # download task
            # task = mock_get_job(job_info.task_id)
            task = get_task(json.loads(job_info.task_json))

            task_logger.info("")
            task_logger.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            task_logger.info("")
            task_logger.info(f"Process {len(task.scenario.rule_sections)} rules for task: {task.id}")
            task_logger.info("")
            task_logger.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n")
            task_logger.info("")
            task_logger.debug(f"get_task: {task}")

            task_context = TaskContext(task, task_logger)
            task_context_store.store(task.id, task_context)

            report = await self._process_modules(task, task_context)
            task_logger.info("")
            task_logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            task_logger.info("")
            task_logger.info(f"Successfully processed all rules. "
                             f"report status: {report.status}, report reasons: {report.reasons}")
            task_logger.info("")
            task_logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            task_logger.info("")
            return report

        except Exception:
            import traceback
            backtrack = traceback.format_exc()
            error_msg = (f"Failed to process job[task_id: {job_info.task_id}, job_id: {job_info.id}], "
                         f"exception traceback: {backtrack}")
            task_logger.info("")
            task_logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            task_logger.info("")
            task_logger.error(error_msg)
            task_logger.info("")
            task_logger.info("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
            task_logger.info("")
            return error_msg
        finally:
            self.running_jobs.pop(job_info.id)
            event_factory.clear_event_queues(job_info)  # pyright: ignore[reportArgumentType]
            stream_factory.stop_media_stream(job_info)  # pyright: ignore[reportArgumentType]
            task_context_store.clear(job_info.task_id)

    async def _process_modules(self, task: Task, task_context: TaskContext) -> Report:
        ################################################################
        # Process the video inspect task
        ################################################################

        # All quality inspection sub-modules. Each inspection type corresponds to an algorithm sub-module.
        # FIXME: The `modules` here is a dictionary with only one element. This can be refactored
        # into a proper structure instead of using this Dict format.
        subtitle_modules = create_subtitle_matching_modules(task, task_context)
        person_tracking_modules = create_person_tracking_modules(task, task_context)
        speech_recognition_modules = create_speech_recognition_modules(task, task_context)
        banned_word_detection_modules = create_banned_word_detection_modules(task, task_context)
        script_matching_modules = create_script_matching_modules(task, task_context)

        # prepare media queue
        stream_factory.start_media_stream(task)
        # start running these threads and wait for them to finish, or raise exception
        event_factory.start_event_queues(task)


        ################################################################
        # Phase 1: Execute first-layer algorithm modules, i.e., all modules that directly require image & audio
        # Notice: This phase will consume all media in the media_stream. Subsequent phases will have no
        # media available and should not depend on media.
        ################################################################

        module_results = await wait_for_threads_complete(
            task_context,
            {
                **subtitle_modules,
                **person_tracking_modules,
                **speech_recognition_modules
            }
        )

        global_logger.info(f'[first result] -> {module_results}')
        task_context.update_module_results(module_results)

        ################################################################
        # Phase 2: Execute second-layer algorithm modules that may depend on Phase 1 results.
        # These modules must not depend on media as media processing is already complete.
        ################################################################
        module_results = await wait_for_threads_complete(
            task_context,
            {
                **banned_word_detection_modules,
                **script_matching_modules
            }
        )

        global_logger.info(f'[second result] -> {module_results}')
        task_context.update_module_results(module_results)

        report = task_context.create_job_report()
        return report


# singleton
job_runner = JobRunner()
