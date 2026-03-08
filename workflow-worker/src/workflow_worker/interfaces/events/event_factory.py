import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

from workflow_worker.infrastructure.circular_queue import CircularQueue
from workflow_worker.domain.entities.task import Task


class JobEvent(BaseModel):
    id: int
    task_id: int
    name: str
    algo: str
    created_at: datetime


# Threading-safe, CAUTION: put & consume operations will block current threading!
# FIXME: do we have to use lock? events are not that important anyway.
class EventCollector(object):
    def __init__(self, task: Task, cache_size: int = 100):
        self.id = f"EventCache-{uuid.uuid4().hex[0:4]}"

        # local import. lazy import.
        from workflow_worker.applications.workflows.task_context import task_context_store
        self.logger = task_context_store.get_task_logger(task.id).getChild(self.id)

        self.lock = threading.Lock()
        self.cache_events: CircularQueue = CircularQueue(cache_size)

    def get_name(self):
        return self.id

    # Sync put, because it's called from algo module
    def put(self, evt: JobEvent):
        with self.lock:
            if self.cache_events.is_full():
                self.logger.warning("event local cache is full, discard the oldest event.")
                self.cache_events.dequeue()
            self.logger.info(f"save event {evt.id} to local cache.")
            self.cache_events.enqueue(evt)

    def start(self):
        pass

    def stop(self):
        pass

    def consume_some_events(self, limit=10) -> list[JobEvent]:
        with self.lock:
            ret = []
            for i in range(limit):
                evt = self.cache_events.dequeue()
                if evt is None:
                    break
                ret.append(evt)
            return ret


class EventFactory:
    def __init__(self):
        self.managed_collector: dict[str, EventCollector] = {}

    def build_event_collector_for_algo(self, task: Task, algo_name: str) -> EventCollector:
        key = f"task_{task.id}_algo_{algo_name}"
        self.managed_collector[key] = EventCollector(task)
        return self.managed_collector[key]

    def start_event_queues(self, task: Task, algo_name: str = ""):
        prefix = f"task_{task.id}_algo_{algo_name}"
        for key in list(self.managed_collector.keys()):
            if key.startswith(prefix):
                self.managed_collector[key].start()

    def clear_event_queues(self, task: Task, algo_name: str = ""):
        prefix = f"task_{task.id}_algo_{algo_name}"
        for key in list(self.managed_collector.keys()):
            if key.startswith(prefix):
                self.managed_collector[key].stop()
                self.managed_collector.pop(key)

    def consume_some_events(self, task: Task, algo_name: str = ""):
        prefix = f"task_{task.id}_algo_{algo_name}"
        sampled_events = []
        for key, collector in self.managed_collector.items():
            if key.startswith(prefix):
                sampled_events += collector.consume_some_events()
        return sampled_events


# singleton
event_factory = EventFactory()
