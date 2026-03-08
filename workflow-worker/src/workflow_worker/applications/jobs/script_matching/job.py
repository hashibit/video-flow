import logging
import re
from typing import Any

from workflow_worker.domain.entities.dialogue import Dialogue
from workflow_worker.domain.entities.tasks.script_matching.config import (
    ScriptMatchingJobCfg,
    SingleScriptMatchingJobCfg,
)
from workflow_worker.domain.entities.tasks.script_matching.result import (
    ScriptMatchingJobResult,
    ScriptMatchingReply,
    ScriptMatchingResult,
)
from workflow_worker.domain.entities.task import Task
from workflow_worker.services.ai.auc.service import AUCService
from workflow_worker.shared.utils.text import calc_text_similarity, lcs
from difflib import Differ

from workflow_worker.applications.jobs.module import ModuleBase
from workflow_worker.applications.jobs.model import JobName
from workflow_worker.applications.workflows.task_context import TaskContext


class ScriptMatchingJob(ModuleBase):
    def __init__(self, task) -> None:
        super().__init__(task)
        self.required_jobs: list[str] = []

        # TODO: move to config file
        self.num_match_loop = 3
        # Chinese confirmation/affirmation phrases used as customer reply signals in script matching.
        # These must remain in Chinese as they are matched against ASR-transcribed speech.
        # Approximate English equivalents: "correct", "mm-hm", "uh-huh", "yes", "ok", "agree",
        # "I agree", "understood", "no problem", "got it", "clear", "confirmed", "acknowledge", etc.
        self._reply_words = [
            "对",
            "嗯",
            "呃",
            "是的",
            "嗯啊",
            "好的",
            "同意",
            "我同意",
            "明白",
            "没问题",
            "知道了",
            "了解了",
            "可以确认",
            "可以",
            "准确",
            "清楚",
            "是",
            "说清楚了",
            "说清楚",
            "清楚了",
            "清楚了啊",
            "确认",
            "了解",
            "知晓",
            "接受",
            "确定",
        ]
        self._start_len = 40
        self._quick_filter_threshold = 0.3
        self._prouncs = ['，', '。', '！', '？', '、']

    def parse_task(self, task: Task) -> ScriptMatchingJobCfg:
        """Parse task to dict.

        Args:
            task (Task): task config.

        Returns:
            ScriptMatchingJobCfg: script match job config.
        """
        configs = []
        for rule_section in task.scenario.rule_sections:
            for rule_point in rule_section.rule_points:
                if rule_point and rule_point.script_cfg:
                    config = SingleScriptMatchingJobCfg(
                        id=rule_point.id,
                        script=rule_point.script_cfg.script,
                        script_threshold=rule_point.script_cfg.script_threshold,
                        key_words=rule_point.script_cfg.key_words,
                        key_word_threshold=rule_point.script_cfg.key_word_threshold,
                        answer_flag=rule_point.script_cfg.answer_flag,
                    )
                    configs.append(config)

        return ScriptMatchingJobCfg(id=task.id, audio=None, configs=configs)

    def _get_start_ids(
            self, diaglogue: Dialogue, script_match_job_cfg: ScriptMatchingJobCfg
    ) -> list[list[Any]]:
        """Get start ids.
        Traverse the entire dialog content by a K-length window, and compare it with
        the script content in the rule point. Find out the candidate start index in
        dialogue for each rule point.

        Args:
            diaglogue (Dialogue): origin dialogue.
            script_match_job_cfg (ScriptMatchingJobCfg): script match job config.

        Returns:
            list[Tuple]: start ids. Format: (point id, candidate start ids).
        """

        start_ids = []

        for i, script_match_cfg in enumerate(script_match_job_cfg.configs):

            max_idx = -1
            max_score = 0

            script_text = script_match_cfg.script
            # get start text of script text
            start_text = script_text[: self._start_len]

            # candidate start ids
            candidate_start_ids = []
            candidate_scores = []
# Compare in two steps for performance reasons
            win_size = max(len(diaglogue) - len(start_text) + 1, 0)
            for k in range(win_size):
                candidate_text = diaglogue[k : k + len(start_text)]
                score = calc_text_similarity(start_text, str(candidate_text)) # Calculate jaccard similarity, O(n+m)
                # select the similary texts
                if score > self._quick_filter_threshold:
                    candidate_start_ids.append(k)

# Calculate overall similarity
            for k, idx in enumerate(candidate_start_ids):
                candidate_text = diaglogue[idx : idx + len(script_text)]
                score = calc_text_similarity(
                    script_text, str(candidate_text), "nlevenshtein" # Calculate edit distance, O(mn)
                )
                # candidate strategy: if score >= 0.2:
                candidate_scores.append(score)
                if score > max_score:
                    max_score = score
                    max_idx = idx

            if max_idx == -1 or max_score < 0.1:
                # No similar start found
                continue

            candidates_zip = zip(
                candidate_start_ids,
                candidate_scores,
                range(len(candidate_start_ids)),
            )
            candidates = sorted(candidates_zip, key=lambda x: (-x[1], x[2]))
            candidate_ids = [c[0] for c in candidates]
            start_ids.append([i, candidate_ids])
        return start_ids

    def _match_scripts(
        self,
        diaglogue: Dialogue,
        start_ids: list[list[Any]],
        script_match_job_cfg: ScriptMatchingJobCfg,
        logger: logging.Logger,
    ) -> list[ScriptMatchingResult]:
        """Match scripts.
        Match the whole script in dialogue. _get_start_ids only compare the first K
        characters with dialogue and it will get multi candidates. This function will
        check all candidate start ids and find out which one is right.

        Args:
            diaglogue (Dialogue): origin dialogue.
            start_ids (List): each section start ids.
            script_match_job_cfg (ScriptMatchingJobCfg): script match job config.

        Returns:
            list[ScriptMatchingJobResult]: script match job results.
        """

        script_results = {}
        # This will modify start and end positions. After modification, match config text against content in [start: end].
        # After adjusting positions, re-match and then re-evaluate the validity of start and end.
        for _ in range(self.num_match_loop):

            # sort by start id
            start_ids = sorted(start_ids, key=lambda x: x[-1][0])

            configs = script_match_job_cfg.configs

            for i, (config_idx, candidate_ids) in enumerate(start_ids):
                config = configs[config_idx]
                script_text = config.script.strip()
                # Avoid detecting punctuation characters in common strings
                if script_text[-1] in self._prouncs:
                    script_text = script_text[:-1]
                # end_idx is the start of the next segment. If current end - start is much smaller than config script,
                # it's likely a segmentation error, so adjust end_idx to the start of the next next segment.
                # In this step, compare these two segments with the config together.
                start_idx = candidate_ids[0]
                if i + 1 != len(start_ids):
                    if start_ids[i + 1][-1][0] < start_idx:
                        continue
                    end_idx = start_ids[i + 1][-1][0]
                    if (end_idx - start_idx) < len(script_text) * 0.75:
                        if i + 2 != len(start_ids):
                            end_idx = start_ids[i + 2][-1][0]
                        else:
                            end_idx = len(diaglogue)
                else:
                    end_idx = len(diaglogue)

                end_idx = min(int(start_idx + len(script_text) * 1.2), end_idx)
                auc_text = diaglogue[start_idx:end_idx]
                logger.info("BEFORE: " + str(auc_text))
                # Longest common subsequence algorithm
                detected_ids = lcs(script_text, str(auc_text))
                if not detected_ids:
                    continue
                # If the distance between the first few characters is too large, consider the start point as incorrect
                # if len(detected_ids) > 2:
                #     if detected_ids[1] - detected_ids[0] >= 4:
                #         # Prevent isolated starting point
                #         detected_ids = detected_ids[1:]
                #     elif detected_ids[2] - detected_ids[1] >= 4:
                #         detected_ids = detected_ids[2:]

                detect_start = start_idx + detected_ids[0]
                detect_end = start_idx + detected_ids[-1] + 1
                auc_text = diaglogue[detect_start:detect_end]

                if len(auc_text) >= 3:
                    if auc_text[1] in self._prouncs:
                        auc_text = auc_text[2:]
                        detect_start += 2

                logger.info(f"EVENT: {script_text}")
                logger.info(f"AUC: {auc_text}")
                logger.info(f"IDS: {detected_ids}")
                # Update start idx
                start_ids[i][1][0] = detect_start
                # TODO: fix strange issue: punctuation may appear at the beginning of a sentence
                if auc_text[0] in self._prouncs:
                    if len(auc_text) == 1:
                        continue
                    auc_text = auc_text[1:]
                    start_ids[i][1][0] += 1
                # If it starts with some response words, consider it meaningless
                for word in self._reply_words:
                    if auc_text[: len(word)] == word:
                        auc_text = auc_text[len(word):]
                        start_ids[i][1][0] += len(word)
                        break

                auc_len = 0
                for idx in detected_ids:
                    auc_len += len(str(diaglogue[start_idx + idx]))

                script_results[config.id] = ScriptMatchingResult(
                    id=config.id,
                    start_time=auc_text.start_time,
                    end_time=auc_text.end_time,
                    auc_text=str(auc_text),
                    start_idx=detect_start,
                    end_idx=detect_end,
                    score=auc_len / len(script_text),
                    diff_text=[],
                )
        return list(script_results.values())

    def _detect_reply(
        self, diaglogue: Dialogue, script_results: list[ScriptMatchingResult]
    ) -> list[ScriptMatchingResult]:
        """Detect reply word from script results

        Args:
            diaglogue (Dialogue): origin dialogue.
            script_results (list[ScriptMatchingJobResult]): matched script results.

        Returns:
            list[ScriptMatchingJobResult]: matched script results with detected replies.
        """
        script_results = sorted(script_results, key=lambda x: x.start_idx)

        # rule_section_infos = self._rule_info.rule_section_infos
        for i, script_result in enumerate(script_results):
# The text between the end of the current matched text and the start of the next text is the candidate for reply
            start_idx = script_result.end_idx
            if i + 1 != len(script_results):
                next_result = script_results[i + 1]
                next_start_idx = next_result.start_idx

                if start_idx >= next_start_idx:
                    continue
                candidate_text = diaglogue[start_idx:next_start_idx]
            else:
                if start_idx >= len(diaglogue):
                    continue
                candidate_text = diaglogue[start_idx:]
            if len(candidate_text) > 1:
                # A standalone bad case
                for j, _ in enumerate(candidate_text[:-1]):
                    if candidate_text[j: j + 2] == "4的":
                        candidate_text[j] = "是"

            replys = []

            for reply_word in self._reply_words:
                detect_range = min(len(candidate_text) - len(reply_word) + 1, 5)
                for j in range(detect_range):
                    word_len = len(reply_word)
                    if j > 0 and candidate_text[j - 1: j] == "不":
                        break
                    if candidate_text[j: j + word_len] == reply_word:
                        replys.append(
                            ScriptMatchingReply(
                                text=reply_word,
                                start_time=candidate_text[j].start_time,
                                end_time=candidate_text[j + word_len - 1].end_time,
                            )
                        )
                        # break # Effect needs investigation

            script_results[i].replys = replys
        return script_results

    def _short_match(
            self, dialogue: Dialogue, script_match_job_cfg: ScriptMatchingJobCfg
    ) -> list[ScriptMatchingResult]:
        """short sentence level script match

        Args:
            dialogue (Dialogue): the whole dialogue
            script_match_job_cfg (ScriptMatchingJobCfg): script match job config

        Returns:
            list[ScriptMatchingResult]: list of script match result
        """
        script_results = []
        sub_utterances = []
        for utterance in dialogue.utterances:
            cursor_index = 0
            last_comma = 0
            # split utterence into sub_utterence by "，"
            for i in range(len(utterance)):
                if utterance[i] == "，":
                    last_word_size = i - last_comma
                    last_comma = i
                    if last_word_size <= 4:
                        continue
                    sub_utterances.append(utterance[cursor_index: i + 1])
                    cursor_index = i + 1
            if cursor_index < len(utterance) and str(utterance[cursor_index:]) != "":
                sub_utterances.append(utterance[cursor_index:])

        masks = [False] * len(sub_utterances)
        for i, config in enumerate(script_match_job_cfg.configs):
            hit_ids = []
            for short_script in re.split("。|！|？|，", config.script):
                for i in range(len(masks)):
                    if masks[i]:
                        # sub utterence has already used
                        continue
                    if calc_text_similarity(short_script, str(sub_utterances[i])) > 0.3:
                        masks[i] = True
                        hit_ids.append(i)
                        # break loop if find out one sentence
                        break
            auc_text = "".join(
                [str(sub_utterances[i]) if masks[i] else "" for i in hit_ids]
            )
            if hit_ids:
                script_results.append(
                    ScriptMatchingResult(
                        id=config.id,
                        start_time=sub_utterances[hit_ids[0]].start_time,
                        end_time=sub_utterances[hit_ids[-1]].end_time,
                        # auc_text=auc_text,
                        auc_text=str(dialogue.text),
                        start_idx=-1,
                        end_idx=-1,
                        score=calc_text_similarity(auc_text, dialogue.text),
                        diff_text=[],
                    )
                )
        return script_results

    def run(self, script_match_job_cfg: ScriptMatchingJobCfg, task_context: TaskContext) -> ScriptMatchingJobResult | None:
        """Run script match job.

        Args:
            script_match_job_cfg (ScriptMatchingJobCfg): script match job config.
            task_context (TaskContext): The global task context.

        Returns:
            ScriptMatchingJobResult: script match job results.
        """

        _event_ch = task_context.event_channels[JobName.ScriptMatching]
        logger = task_context.get_task_logger().getChild("Module.ScriptMatching")

#       # GetAudioResult
        auc_service_result = task_context.get_auc_service_result()
        if auc_service_result is None:
            logger.error("no auc service result in task_context?? fallback: use audio to extract one.")
            audio = task_context.get_audio_object()
            if not audio:
                logger.error("no audio in task_context?? return None result")
                return None
            service = AUCService()
            auc_service_result = service.run(audio)
            task_context.set_auc_service_result(auc_service_result)

# Get audio result object, including parsed text
        dialogue = auc_service_result.dialogue

        # Find all possible matching start positions
        # start_ids = self._get_start_ids(dialogue, script_match_job_cfg)
        # script_results = self._match_scripts(dialogue, start_ids, script_match_job_cfg, logger=logger)
        # script_results = self._detect_reply(dialogue, script_results)

        script_results = self._short_match(dialogue, script_match_job_cfg)
        script_results = self._diff(script_match_job_cfg.configs, script_results)

        logger.debug(f"script_results: {script_results}")

        return ScriptMatchingJobResult(
            results=script_results, ai_result={"auc": auc_service_result}
        )

    def _diff(self, script_match_configs: list[SingleScriptMatchingJobCfg], script_results: list[ScriptMatchingResult]) -> list[ScriptMatchingResult]:
        differ = Differ()
        # Sort by rule ID in ascending order to reduce complexity of subsequent matching
        script_match_configs = sorted(script_match_configs, key=lambda x: x.id)
        script_results = sorted(script_results, key=lambda x: x.id)

        for j, script_result in enumerate(script_results):
            for i, script_match_config in enumerate(script_match_configs):
                if script_result.id != script_match_config.id:
                    continue

                # diflib text comparison
                diff_result = differ.compare(script_match_config.script, script_result.auc_text)

                # Merge adjacent words with the same status
                pre_item = ''
                for item in diff_result:
                    if pre_item == '':
                        pre_item = item
                        continue
                    if item[0] == pre_item[0]:
                        pre_item += item[2]
                    else:
                        script_results[j].diff_text.append(pre_item)
                        pre_item = item
                script_results[j].diff_text.append(pre_item)
                break
        return script_results

