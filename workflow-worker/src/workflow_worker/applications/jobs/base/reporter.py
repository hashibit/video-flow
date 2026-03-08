from typing import Any


class Reporter:
    def __init__(self) -> None:
        pass

    def run(self, *args, **job_results) -> Any:
        raise NotImplementedError
