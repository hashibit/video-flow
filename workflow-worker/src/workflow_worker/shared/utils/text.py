import re
from typing import Any

import distance  # pyright: ignore[reportMissingImports]

from workflow_worker.domain.entities.dialogue import Dialogue


def calc_text_similarity(s1: str, s2: str, method: str = "jaccard") -> float:
    """Calculates two sentence similarity, all score will be scaled to 0~1.

    Args:
        s1 (str): Fisrt sentence.
        s2 (str): Second sentence.
        method (str, optional): The compute method. Defaults to "jaccard".

    Raises:
        KeyError: Wrong method name.

    Returns:
        float: The similarity score. To keep the score uniformity, the score
            will be scaled to 0~1 and 1 means the two sentence are the same.
    """
    if method == "jaccard":
        similarity = 1 - distance.jaccard(s1, s2)
    elif method == "nlevenshtein":
        similarity = 1 - distance.nlevenshtein(s1, s2)
    else:
        # TODO: add more methods
        raise KeyError("No this method")
    return similarity


def lcs(source: str | Dialogue, target: str | Dialogue) -> list[Any]:
    """A function to find the longest common subsequence between two strings.

    Args:
        source (str | Dialogue): source string.
        target (str | Dialogue): target string.

    Returns:
        list: longest common subsequence.
    """

    m = len(source)
    n = len(target)

    dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if source[i - 1] == target[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    i = m
    j = n

    path = []
    while i > 0 and j > 0:
        # For the second half, prefer earlier positions; for the first half, prefer later positions
        if i >= m // 2 and j >= n // 2:
            if dp[i][j - 1] == dp[i][j]:
                j -= 1
            elif dp[i - 1][j] == dp[i][j]:
                i -= 1
            else:
                path.append(j - 1)
                i -= 1
                j -= 1
        else:
            if dp[i - 1][j] == dp[i][j]:
                i -= 1
            elif dp[i][j - 1] == dp[i][j]:
                j -= 1
            else:
                path.append(j - 1)
                i -= 1
                j -= 1
    path = path[::-1]
    if not path:
        return []
    new_path = [path[0]]
    for idx in path[1:]:
        if idx - new_path[-1] > 20:  # TODO: Is 20 a reasonable value?
            break
        new_path.append(idx)
    return new_path


def word_in_text(text, auc_text, threshold=None):
    def compute_thresholds(length):
        if length <= 4:
            return 0.8
        if length <= 8:
            return 0.7
        return 0.6

    # remove
    auc_text = "".join(re.split(r",|。|，|！|？|\?", auc_text))
    # Chinese ASR filler/interjection stop words — must remain in Chinese to clean ASR output
    stop_words = ["嗯", "啊", "耶", "呃"]  # "mm", "ah", "yeah", "uh"
    for word in stop_words:
        auc_text = auc_text.replace(word, "")
    text = "".join(re.split(r",|。|，|！|？|\?", text))
    if not threshold:
        threshold = compute_thresholds(len(text))

# If the input is a number, require complete matching
    if text.isdigit():
        threshold = 1.0

    if len(text) > len(auc_text):
        score = calc_text_similarity(text, auc_text, "nlevenshtein")
        if score >= threshold:
            return True
    else:
        for i in range(len(auc_text) - len(text) + 1):
            score = calc_text_similarity(
                text, auc_text[i : i + len(text)], "nlevenshtein"
            )
            if score >= threshold:
                print(score, threshold, auc_text, auc_text[i : i + len(text)])
                return True
        return False
