from workflow_worker.shared.utils.env import get_env


class ModuleBase:
    """Base class for all processing modules."""

    def __init__(self, task):
        """Initialize the module with a task.

        Args:
            task: The task to be processed
        """
        self.task = task
        self.task_uuid = task.id
        self.envs = get_env()

    def open(self):
        """Open the module and prepare resources."""
        pass

    def close(self):
        """Close the module and release resources."""
        pass
