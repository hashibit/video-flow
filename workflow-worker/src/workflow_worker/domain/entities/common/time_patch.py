# pylint: disable=no-name-in-module,no-self-argument


from pydantic import BaseModel

from workflow_worker.shared.logging._logging import get_logger

logger = get_logger(__name__)


class TimePatch(BaseModel):
    """TimePatch is designed to represent time's patch with time_unit.

    Attributes:
        start_time (float): the start point on time line in ms.
        end_time (float): the end point on time line in ms.
        min_time_interval (float): the minimum time interval. TimePatch will be invalid
            when the duration of time_patch is less than min_time_interval.
        time_unit (str): the unit for start_time & end_time to represent time patch.
            Only support ms, s, m(min), h(our).
    """

    start_time: float
    end_time: float
    min_time_interval: float | None = 3000
    time_unit: str | None = "ms"

    def _calc_time_scale(self, time_unit="ms"):
        """calculate the scale for time_unit.

        Args:
            time_unit (str, optional): The time_unit needs to be calculate.
                Defaults to "ms".

        Returns:
            time_scale (int): millisecond-based timescales.
        """
        time_scale = 1
        if time_unit == "ms":
            time_scale = 1
        elif time_unit == "s":
            time_scale = 1000
        elif time_unit in ["min", "m"]:
            time_scale = 60 * 1000
        elif time_unit in ["h", "hour"]:
            time_scale = 60 * 1000 * 1000
        else:
            logger.error("unsupport time_unit with {}, treat as ms".format(time_unit))
        return time_scale

    def _calc_time_ratio(self, time_unit="ms"):
        """calculate the ratio from source time_unit to target time_unit.

        Args:
            time_unit (str, optional): The target time_unit. Defaults to "ms".

        Returns:
            ratio (float): the ratio between two time_units.
        """
        target_time_scale = self._calc_time_scale(time_unit)
        source_time_scale = self._calc_time_scale(self.time_unit or "ms")

        ratio = target_time_scale * 1.0 / source_time_scale

        return ratio

    def update_end_time(self, frame_time, time_unit="ms"):
        """Update the end time using frame_time in 'time_unit'.

        Args:
            frame_time (float): the new end_time.
            time_unit (str, optional): the unit of frame_time. Defaults to "ms".
        """
        ratio = self._calc_time_ratio(time_unit)

        self.end_time = frame_time * ratio

    def is_burr(self):
        """Check if the time_patch is valid.

        Returns:
            bool: True if duration is less than min_time_interval.
        """
        return self.end_time - self.start_time < (self.min_time_interval or 0)

    def get_duration(self, time_unit="ms"):
        """Get the time duration based on the special time_unit.

        Args:
            time_unit (str, optional): the expected time unit. Defaults to "ms".

        Returns:
            float: the duration for this time_patch in 'time_unit'.
        """
        ratio = self._calc_time_ratio(time_unit)
        return (self.end_time - self.start_time) * 1.0 / ratio

    def is_overlap(self, start_time: float, end_time: float):
        """Check if there is overlap with the given start and end times.

        Args:
            start_time (float): the start time stamp.
            end_time (float): the end time stamp.

        Returns:
            bool: the checking result.
        """
        if self.start_time <= start_time:
            return self.end_time >= start_time
        return self.start_time <= end_time

    def is_in(self, time_stamp: float, time_unit: str = "ms"):
        ratio = self._calc_time_ratio(time_unit)
        if self.start_time <= time_stamp * ratio <= self.end_time:
            return True
        return False
