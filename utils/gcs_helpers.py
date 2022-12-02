import os

from tqdm import tqdm
from google.cloud import storage
from datetime import timezone, datetime

def connect_to_bucket(bucket_name):
    storage_client = storage.Client.from_service_account_json(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
    bucket = storage_client.get_bucket(bucket_name)
    return bucket


def download_file(bucket, bucket_path, filename, output_path, overwrite=False):
    bucket_path_full = os.path.join(bucket_path, filename)
    blob = bucket.blob(bucket_path_full)

    if not blob.exists():
        print(f'File {bucket_path_full} does not exist in the bucket')
        return

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    full_path = os.path.join(output_path, filename)
    print(f'Downloading {blob.name} to {full_path}')

    if not overwrite and os.path.isfile(full_path):
       print(f'File download failed - File {full_path} exists and overwrite is set to False')
       return

    blob.download_to_filename(full_path)


def download_files(bucket, bucket_path, output_path, overwrite=False):
    blobs = bucket.list_blobs(prefix=bucket_path)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    current_files = [] if overwrite else os.listdir(output_path)

    print(f'Downloading all files from {bucket_path} to {output_path}')
    files_to_download = []
    for blob in blobs:
        if blob.name[-1] != '/':
            _, tail = os.path.split(blob.name)

            if not overwrite and any(tail == fn for fn in current_files):
                continue

            full_path = os.path.join(output_path, tail)
            files_to_download.append((blob, full_path))

    if len(files_to_download):
        for f in tqdm(files_to_download):
            blob, full_path = f
            blob.download_to_filename(full_path)

        print(f'{bucket_path} download complete')
    else:
        print(f'{bucket_path} had no files to download!')


def upload_file(bucket, source_path, bucket_path):
    print(f'Uploading {source_path} to {bucket_path}')
    blob = bucket.blob(bucket_path)
    blob.upload_from_filename(source_path)


def list_files(bucket, bucket_path):
    blobs = bucket.list_blobs(prefix=bucket_path)
    return [b.name for b in filter(lambda x: x.name[-1] != '/', blobs)]


def generate_url(bucket, bucket_path):
    blob = bucket.blob(bucket_path)
    url_lifetime = int(datetime.now(tz=timezone.utc).timestamp()) + 3600
    return blob.generate_signed_url(url_lifetime)