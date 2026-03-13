
import requests  # type: ignore[import-untyped]

from workflow_worker.domain.entities.task import MediaMeta
from workflow_worker.shared.logging._logging import get_logger

logger = get_logger(__name__)


def create_media(endpoint, task_id, fps, medias=('video', 'audio')) -> tuple[int, str]:
    url = f'http://{endpoint}/manager/v1/create'
    # url = 'http://127.0.0.1:6889/manager/v1/create'  # for local test
    data = {
        'task_id': task_id,
        'medias': medias,
        'fps': fps,
    }

    headers = {'Content-Type': 'application/json'}
    resp = requests.post(url, json=data, headers=headers)
    if resp.status_code != 200:
        raise Exception(f'create media task failed, http code: {resp.status_code}, resp text: {resp.text}')
    result = resp.json()
    logger.info(f"create_media -> HTTP response: {result}")
    return result['data']['media_id'], result['data']['grpc_host']


def is_data_ready(endpoint, media_id) -> bool:
    url = f'http://{endpoint}/manager/v1/ready?media_id={media_id}'
    # url = f'http://127.0.0.1:6889/manager/v1/ready?media_id={media_id}'  # for local test

    logger.info(f"is_data_ready -> HTTP request: media_id={media_id}")
    resp = requests.get(url)
    if resp.status_code != 200:
        raise Exception(f'is_data_ready failed, http code: {resp.status_code}, resp text: {resp.text}')
    result = resp.json()
    logger.info(f"is_data_ready -> HTTP response: {result}")
    return True


def get_media_metadata(endpoint, task_id) -> MediaMeta:
    url = f'http://{endpoint}/manager/v1/media_metadata?task_id={task_id}'
    # url = f'http://127.0.0.1:6889/manager/v1/media_metadata?task_id={task_id}'  # for local test

    logger.info(f"get_media_metadata -> HTTP request: task_id={task_id}")
    resp = requests.get(url)
    if resp.status_code != 200:
        raise Exception(f'get_media_metadata failed, http code: {resp.status_code}, resp text: {resp.text}')
    result = resp.json()
    logger.info(f"get_media_metadata -> HTTP response: {result}")
    data = result['data']
    meta = MediaMeta(duration=data['video_duration'],
                     resolution=data['video_resolution'],
                     size=data['video_size'],
                     bitrate=data['video_bitrate'],
                     fps=data['video_fps'],
                     width=data['video_width'],
                     height=data['video_height'],
                     format_name=data['video_format_name'],
                     )
    return meta
