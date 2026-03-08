from workflow_worker.shared.utils.env import get_env


def debug_f(v, *args):
    if is_debug():
        print("[Debug]", v.format(*args))


def is_debug():
    return get_env().is_debug == "true"
