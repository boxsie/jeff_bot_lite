import os
import random

from google.cloud import storage
from google.cloud import pubsub_v1

from utils.gcs_helpers import connect_to_bucket, download_file, download_files, list_files, generate_url, upload_file

class FileObject:
    def __init__(self, path, bucket=None):
        self.path = path
        self.name = self._remove_extension(path)
        self.bucket = bucket

    def _remove_extension(self, file_path):
        filename = os.path.split(file_path)[-1]
        return "".join(filename.split('.')[:-1])

    def get_path(self):
        if self.bucket:
            return generate_url(self.bucket, self.path)

        return self.path


class FileRepo:
    def __init__(self, base_path=None, bucket_path=None, project_id=None, bucket_sub_name=None, overwrite=False):
        if not base_path and not bucket_path:
            raise Exception('Local base path and/or remote bucket path must be set')

        self.base_path = base_path
        self.bucket_path = bucket_path

        if self.base_path and not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

        if self.bucket_path:
            path_split = self.bucket_path.split('/')
            bucket_name = path_split[0]
            bucket_dir = '/'.join(path_split[1:])
            self.bucket = connect_to_bucket(bucket_name)
            self.bucket_dir = bucket_dir

            if not self.bucket:
                raise Exception('Unable to connect to GCS bucket')

            if self.base_path:
                print(f'Downloading the latest files from {self.bucket_path}')
                download_files(
                    bucket=self.bucket,
                    bucket_path=self.bucket_dir,
                    output_path=self.base_path,
                    overwrite=overwrite
                )

                if project_id and bucket_sub_name:
                    self.subscribe_to_bucket(
                        project_id=project_id,
                        bucket_sub_name=bucket_sub_name
                    )

        self.files = [FileObject(os.path.join(self.base_path, f), self.bucket) for f in os.listdir(self.base_path)]


    def create_file_path(self, filename):
        return os.path.join(self.base_path, filename)


    def add_file(self, filename):
        file_path = self.create_file_path(filename=filename)
        fo = FileObject(file_path, self.bucket)
        self.files.append(fo)

        return fo


    def update_file(self, file_obj):
        if self.bucket:
            upload_file(bucket=self.bucket, source_path=file_obj.path, bucket_path=file_obj.path)


    def delete_file(self, filename):
        file_path = self.create_file_path(filename=filename)

        if not os.path.exists(file_path):
            print(f'Unable to delete file - {filename} not found')
            return

        self.files = [f for f in self.files if f.path != file_path]


    def find(self, name) -> object:
        return next((f for f in self.files if f.name == name), None)


    def random(self) -> object:
        return random.choice(self.files)


    def list_files(self) -> list:
        return self.files


    def subscribe_to_bucket(self, project_id, bucket_sub_name):
        if not self.bucket:
            print('Unable to connect to bucket')
            return

        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(project_id, bucket_sub_name)

        def callback(message):
            print(f"Received {message.attributes['eventType']} message")
            message.ack()

            evnt_type = message.attributes['eventType']

            if not evnt_type:
                return

            obj_id = message.attributes['objectId']
            bucket_dir, filename = os.path.split(obj_id)

            if bucket_dir != self.bucket_dir:
                return

            if evnt_type == 'OBJECT_DELETE':
                print(f'Deleting {filename}...')
                self.delete_file(filename)
                os.remove(os.path.join(self.base_path, filename))
                print(f'{filename} deleted')

            elif evnt_type == 'OBJECT_FINALIZE':
                print(f'Downloading {filename}...')
                download_file(
                    bucket=self.bucket,
                    bucket_path=self.bucket_dir,
                    filename=filename,
                    output_path=self.base_path,
                    overwrite=True
                )
                self.add_file(filename)
                print(f'{filename} added')

        subscriber.subscribe(subscription_path, callback=callback)