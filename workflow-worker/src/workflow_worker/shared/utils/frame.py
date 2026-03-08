import hashlib
import os
import cv2  # pyright: ignore[reportMissingImports]
import numpy as np
import requests
from six.moves import urllib_parse  # pyright: ignore[reportMissingImports,reportMissingModuleSource]
from workflow_worker.domain.entities.frame import BatchFrame, Frame
def get_image_bytes(frame: Frame):
    """Get frame bytes from Frame.
    Args:
        frame (Frame): the frame object stored frame's url or bytes.
    Returns:
        image_bytes: the encoding bytes of one frame.
    """
    image_bytes = frame.data
    if image_bytes:
        return image_bytes
    url = frame.url
    # TODO: fix the function.
    image_bytes = get_data_from_url(url or "")
    if image_bytes:
        return image_bytes
    return None
def get_batch_image_bytes(frames: BatchFrame):
    """Get batch frame bytes from BatchFrame.
    Args:
        frames (BatchFrame): the batch frame object stored frames with batch_size count.
    Returns:
        images_index: the index for frame witch get bytes successful.
        images_bytes: the bytes for frames.
    """
    images_bytes = []
    images_index = []
    for index in range(frames.batch_size):
        # Get valid current frame image byte data
        image_bytes = get_image_bytes(frames.frames[index])
        if image_bytes:
            images_bytes.append(image_bytes)
            images_index.append(index)
    return images_index, images_bytes
def get_data_from_url(url: str):
    """Get image bytes from url.
    Args:
        url (str): the path for stored data.
    Returns:
        image_bytes: the images bytes.
    """
    image_bytes = None
    if not url:
        return image_bytes
    file_url = urllib_parse.urlparse(url)
    if file_url.scheme == "file":
        path = file_url.netloc + file_url.path
        with open(path, "rb") as fp:
            image_bytes = fp.read()
    elif file_url.scheme == "http":
        req = requests.get(url)
        image_bytes = req.content
    return image_bytes
def encode_image(cv_img: np.ndarray, ext: str = "jpg"):
    """Encode the img with np.ndarray format to bytes.
    Args:
        cv_img (np.ndarray): The raw img with np.ndarray.
        ext (str, optional): The encoding format. Defaults to "jpg".
    Returns:
        bytes: the bytes of image.
    """
    _, img_encode = cv2.imencode(f".{ext}", cv_img)
    return np.array(img_encode).tobytes()
def decode_image(img_bytes: bytes):
    """Decode image in bytes to cv2 format.
    Args:
        img_bytes (bytes): the image bytes.
    Returns:
        np.ndarray: the decoded img in np.ndarray format.
    """
    cv_img = cv2.imdecode(np.frombuffer(img_bytes, dtype=np.uint8), 1)
    return cv_img
def calc_etag(obj_data, chunk_size=5 * 1024 * 1024):
    """Calculate etag for obj_data.
    Args:
        obj_data (bytes): the data in bytes.
        chunk_size (int, optional): the chunk size in one calculate.
            Defaults to 5*1024*1024.
    Returns:
        str: the etag of obj.
    """
    md5s = []
    index = 0
    length = len(obj_data)
    while True:
        start_index = index * chunk_size
        end_index = (index + 1) * chunk_size
        end_index = length if end_index > length else end_index
        clip_data = obj_data[start_index:end_index]
        md5s.append(hashlib.md5(clip_data))
        index += 1
        if end_index == length:
            break
    if len(md5s) < 1:
        return "{}".format(hashlib.md5().hexdigest())
    if len(md5s) == 1:
        return "{}".format(md5s[0].hexdigest())
    digests = b"".join(m.digest() for m in md5s)
    digests_md5 = hashlib.md5(digests).hexdigest()
    return f"{digests_md5}-{len(md5s)}"
def get_storage_url(task_uuid, image_bytes):
    """Save the image to local and return the local path.
    Args:
        task_uuid (str): the uuid of task
        image_bytes (bytes): image bytes.
    Returns:
        str: the local path of image.
    """
    url = ""
    if image_bytes:
        etag = calc_etag(image_bytes)
        folder = "temp/{}/pics".format(task_uuid)
        if not os.path.exists(folder):
            os.makedirs(folder)
        storage_path = "{}/{}.jpg".format(folder, etag)
        with open(storage_path, "wb") as f:
            f.write(image_bytes)
        url = "file://" + storage_path
    return url
