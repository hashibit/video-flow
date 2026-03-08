import io
from datetime import timedelta

from minio import Minio  # pyright: ignore[reportMissingImports]

from workflow_worker.shared.utils.env import get_env

envs = get_env()


class S3Hook(object):

    def __init__(self):
        self.client = Minio(
            endpoint=envs.get_s3_host(),
            access_key=envs.s3_ak,
            secret_key=envs.s3_sk,
            secure=False
        )

    def put_local_file(self, bucket, key, file_path):
        self.client.fput_object(bucket, key, file_path)

    def get_file_to_local(self, bucket, key, file_path):
        self.client.fget_object(bucket, key, file_path)

    def get_key(self, key, bucket):
        response = None
        try:
            response = self.client.get_object(bucket, key)
            return response.data
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def load_file_obj(self, file_obj, key, bucket, replace=False):
        data = file_obj.read()
        obj = io.BytesIO(data)
        self.client.put_object(bucket, key, obj, len(data))

    def load_bytes(self, data, key, bucket, replace=False):
        obj = io.BytesIO(data)
        self.client.put_object(bucket, key, obj, len(data))

    def generate_presigned_url(self, client_method, params, expires_in=3600):
        bucket = params['Bucket']
        key = params['Key']
        expires = timedelta(seconds=expires_in)
        if client_method == "get_object":
            return self.client.presigned_get_object(bucket, key, expires=expires)
        elif client_method == "put_object":
            return self.client.presigned_put_object(bucket, key, expires=expires)
