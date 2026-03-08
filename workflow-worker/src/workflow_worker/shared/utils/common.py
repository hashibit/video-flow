import re

from workflow_worker.domain.entities.task import Task


def time_transport(origin_time: float) -> str:
    """Transport time to string.

    Args:
        origin_time (float): the origin time.

    Returns:
        str: the time string.
    """
    origin_time = int(origin_time)
    time_in_second = int(origin_time // 1000)
    time_in_minite = int(time_in_second // 60)
    time_in_second = int(time_in_second % 60)
    time_in_hour = int(time_in_minite // 60)
    time_in_minite = int(time_in_minite % 60)
    return f"{time_in_hour:02d}:{time_in_minite:02d}:{time_in_second:02d}"


def pascal_case_to_snake_case(origin_obj: object, only_key: bool = False) -> object:
    """Convert the value of origin object from pascal case to snake case.

    Args:
        origin_obj (object): Origin object.
        only_key (bool): Used to indicate whether the value of keys needs to be
            converted when origin object is a dict. Defaults to False.

    Returns:
        dest_obj (object): Destination object.
    """

    def _convert(pascal_str: str):
        """Convert a string from pascal case to snake case.

        Args:
            pascal_str (str): A pascal string.

        Returns:
            (str): A snake string.
        """
        splitted_strs = re.findall(
            r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", pascal_str
        )
        return "_".join(map(str.lower, splitted_strs))

    if isinstance(origin_obj, str) and not only_key:
        return _convert(origin_obj)

    if isinstance(origin_obj, list):
        return [pascal_case_to_snake_case(x, only_key) for x in origin_obj]

    if isinstance(origin_obj, dict):
        dest_str = {}
        for key in origin_obj:
            dest_str[_convert(key)] = pascal_case_to_snake_case(
                origin_obj[key], only_key
            )
        return dest_str

    return origin_obj


def snake_case_to_pascal_case(origin_obj: object, only_key: bool = False) -> object:
    """Convert the value of origin object from snake case to pascal case.

    Args:
        origin_obj (object): Origin object.
        only_key (bool): Used to indicate whether the value of keys needs to be
            converted when origin object is a dict. Defaults to False.

    Returns:
        dest_obj (object): Destination object.
    """

    def _convert(snake_str: str):
        """Convert a string from snake case to pascal case.

        Args:
            snake_str (str): A snake string.

        Returns:
            (str): A pascal string.
        """

        return (
            re.sub(r"(?P<uppercase>[A-Z])", r"_\g<uppercase>", snake_str)
            .title()
            .replace("_", "")
        )

    if isinstance(origin_obj, str) and not only_key:
        return _convert(origin_obj)

    if isinstance(origin_obj, list):
        return [snake_case_to_pascal_case(x, only_key) for x in origin_obj]

    if isinstance(origin_obj, dict):
        dest_obj = {}
        for key in origin_obj:
            dest_obj[_convert(key)] = snake_case_to_pascal_case(
                origin_obj[key], only_key
            )
        return dest_obj

    return origin_obj


def need_speech_recognition(task: Task) -> bool:
    """
    Check if the task needs to call speech_recognition separately
    """
    for rule_section in task.scenario.rule_sections:
        for rule_point in rule_section.rule_points:
            if rule_point and (rule_point.script_cfg or rule_point.banword_cfg):
                return False
    return True
