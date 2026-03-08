import asyncio
import unittest
import os
import sys
# 兼容protoc
absPath = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, absPath)  # noqa
# 这个是必须的, apis 模块必须在 path 里
sys.path.insert(0, os.path.join(absPath, "apis"))  # noqa
sys.path.insert(0, os.path.join(absPath, "apis", "media"))  # noqa
from engine.models.rule import Scenario
from framework.media.data_source_grpc import DataSourceGRPC
from framework.media.model import StreamMessage



from engine.models.task import Task, Media
from framework.media.stream_factory import MediaStream
class TestMedia(unittest.TestCase):
    def mockTask(self) -> Task:
        url = "http://test"
        md = Media(path=url, media_url=url)
        s = Scenario(id=1, name='test_scenario')
        tk = Task(name="test", id=10, media=md, scenario=s)
        return tk
    def test_run(self) -> None:
        mockTk = self.mockTask()
        print(mockTk)
        media = MediaStream(task=mockTk, dispatch_fps=25, cache_size=1024, **{"data_source_grpc_endpoint": True})
        media.start()

    async def _accept_message(self, frame: StreamMessage) -> bool:
        print(frame.id, frame.is_last)
        if frame.image:
            with open('myimage.jpg', 'wb') as f:
                f.write(frame.image.data)  # TODO 可以直接使用，图片都为jpg格式
            return True
        elif frame.audio:
            pass
        return False

    def test_run2(self) -> None:
        mockTk = self.mockTask()
        r = DataSourceGRPC(task=mockTk, data_source_grpc_endpoint="127.0.0.1:8989")
        r.media_job_id = 1
        # asyncio.run(r.setup())
        asyncio.run(r.stream(streamed_cb=self._accept_message))

