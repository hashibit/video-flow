"""RetryPolicy: configurable retry strategy with jitter sleep."""

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryExhausted(RuntimeError):
    def __init__(self, attempts: int, last_error: Exception | None = None):
        super().__init__(f"Retry exhausted after {attempts} attempt(s)")
        self.attempts = attempts
        self.last_error = last_error


@dataclass(frozen=True)
class RetryPolicy:
    """Configurable retry strategy with uniform-random jitter sleep.

    Args:
        max_attempts: Maximum number of attempts (0 = unlimited).
        sleep_min:    Lower bound of per-retry sleep interval (seconds).
        sleep_max:    Upper bound of per-retry sleep interval (seconds).
    """

    max_attempts: int = 0
    sleep_min: float = 1.0
    sleep_max: float = 3.0

    def execute(self, func: Callable[[], T]) -> T:
        """Call *func* until it succeeds, sleeping between failures.

        Raises:
            RetryExhausted: when max_attempts > 0 and all attempts failed.
        """
        attempt = 0
        last_err: Exception | None = None
        while True:
            attempt += 1
            try:
                return func()
            except Exception as exc:
                last_err = exc
                if self.max_attempts and attempt >= self.max_attempts:
                    raise RetryExhausted(attempt, last_err) from last_err
                time.sleep(random.uniform(self.sleep_min, self.sleep_max))


RETRY_UNLIMITED = RetryPolicy(max_attempts=0, sleep_min=1.0, sleep_max=3.0)
RETRY_3_TIMES = RetryPolicy(max_attempts=3, sleep_min=1.0, sleep_max=3.0)
