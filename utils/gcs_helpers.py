import os
import logging
from typing import Optional, List

from tqdm import tqdm
from google.cloud import storage
from google.cloud.exceptions import NotFound, Forbidden, GoogleCloudError
from datetime import timezone, datetime

logger = logging.getLogger('discord.gcs_helpers')

def connect_to_bucket(bucket_name: str, service_account_json: str) -> Optional[storage.Bucket]:
    """Connect to Google Cloud Storage bucket with error handling"""
    try:
        if not bucket_name or not isinstance(bucket_name, str):
            logger.error(f"Invalid bucket_name: {bucket_name}")
            return None
            
        if not service_account_json or not isinstance(service_account_json, str):
            logger.error(f"Invalid service_account_json path: {service_account_json}")
            return None
            
        if not os.path.exists(service_account_json):
            logger.error(f"Service account file not found: {service_account_json}")
            return None
            
        logger.info(f"Connecting to GCS bucket: {bucket_name}")
        
        try:
            storage_client = storage.Client.from_service_account_json(service_account_json)
            bucket = storage_client.get_bucket(bucket_name)
            
            # Test bucket access by trying to list blobs (limit to 1 for efficiency)
            try:
                list(bucket.list_blobs(max_results=1))
                logger.info(f"Successfully connected to bucket: {bucket_name}")
                return bucket
            except Exception as e:
                logger.error(f"Cannot access bucket {bucket_name}: {e}")
                return None
                
        except NotFound:
            logger.error(f"Bucket not found: {bucket_name}")
            return None
        except Forbidden:
            logger.error(f"Access denied to bucket: {bucket_name}")
            return None
        except Exception as e:
            logger.error(f"Error connecting to bucket {bucket_name}: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Unexpected error in connect_to_bucket: {e}", exc_info=True)
        return None

def download_file(bucket: storage.Bucket, bucket_path: str, filename: str, 
                 output_path: str, overwrite: bool = False) -> bool:
    """Download a single file from GCS bucket with error handling"""
    try:
        if not bucket:
            logger.error("Bucket is required")
            return False
            
        if not bucket_path or not filename or not output_path:
            logger.error("bucket_path, filename, and output_path are required")
            return False
            
        bucket_path_full = os.path.join(bucket_path, filename).replace('\\', '/')
        logger.debug(f"Downloading file: {bucket_path_full}")
        
        try:
            blob = bucket.blob(bucket_path_full)
            
            if not blob.exists():
                logger.warning(f'File {bucket_path_full} does not exist in the bucket')
                return False
                
        except Exception as e:
            logger.error(f"Error checking blob existence for {bucket_path_full}: {e}")
            return False

        # Ensure output directory exists
        try:
            if not os.path.exists(output_path):
                os.makedirs(output_path)
                logger.debug(f"Created output directory: {output_path}")
        except Exception as e:
            logger.error(f"Failed to create output directory {output_path}: {e}")
            return False

        full_path = os.path.join(output_path, filename)
        logger.info(f'Downloading {blob.name} to {full_path}')

        # Check if file exists and overwrite setting
        if os.path.isfile(full_path) and not overwrite:
            logger.info(f'File download skipped - File {full_path} exists and overwrite is False')
            return True

        try:
            # Download with progress tracking for large files
            file_size = blob.size
            if file_size and file_size > 10 * 1024 * 1024:  # > 10MB
                logger.info(f"Downloading large file ({file_size / 1024 / 1024:.1f}MB): {filename}")
                
            blob.download_to_filename(full_path)
            
            # Verify download
            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                logger.info(f"Successfully downloaded: {filename}")
                return True
            else:
                logger.error(f"Download verification failed for: {filename}")
                return False
                
        except Exception as e:
            logger.error(f"Error downloading file {bucket_path_full}: {e}")
            # Clean up partial download
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except:
                    pass
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in download_file: {e}", exc_info=True)
        return False

def download_files(bucket: storage.Bucket, bucket_path: str, output_path: str, 
                  overwrite: bool = False) -> bool:
    """Download all files from a GCS bucket path with error handling"""
    try:
        if not bucket or not bucket_path or not output_path:
            logger.error("bucket, bucket_path, and output_path are required")
            return False
            
        logger.info(f'Starting download from {bucket_path} to {output_path}')
        
        try:
            blobs = list(bucket.list_blobs(prefix=bucket_path))
            logger.info(f"Found {len(blobs)} objects with prefix {bucket_path}")
        except Exception as e:
            logger.error(f"Error listing blobs with prefix {bucket_path}: {e}")
            return False

        # Ensure output directory exists
        try:
            if not os.path.exists(output_path):
                os.makedirs(output_path)
                logger.debug(f"Created output directory: {output_path}")
        except Exception as e:
            logger.error(f"Failed to create output directory {output_path}: {e}")
            return False

        # Get current files if not overwriting
        current_files = []
        if not overwrite:
            try:
                current_files = os.listdir(output_path)
            except Exception as e:
                logger.warning(f"Error listing current files: {e}")
                current_files = []

        # Prepare download list
        files_to_download = []
        for blob in blobs:
            try:
                # Skip directories (blobs ending with '/')
                if blob.name.endswith('/'):
                    continue
                    
                _, tail = os.path.split(blob.name)
                
                if not tail:  # Skip if no filename
                    continue

                if not overwrite and tail in current_files:
                    logger.debug(f"Skipping existing file: {tail}")
                    continue

                full_path = os.path.join(output_path, tail)
                files_to_download.append((blob, full_path, tail))
                
            except Exception as e:
                logger.warning(f"Error processing blob {blob.name}: {e}")
                continue

        if not files_to_download:
            logger.info(f'{bucket_path} had no files to download!')
            return True

        # Download files with progress bar
        logger.info(f'Downloading {len(files_to_download)} files...')
        successful_downloads = 0
        
        try:
            for blob, full_path, filename in tqdm(files_to_download, desc="Downloading"):
                try:
                    blob.download_to_filename(full_path)
                    
                    # Verify download
                    if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                        successful_downloads += 1
                        logger.debug(f"Downloaded: {filename}")
                    else:
                        logger.warning(f"Download verification failed: {filename}")
                        
                except Exception as e:
                    logger.warning(f"Failed to download {filename}: {e}")
                    # Clean up partial download
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                        except:
                            pass
                    continue

            logger.info(f'{bucket_path} download complete: {successful_downloads}/{len(files_to_download)} files')
            return successful_downloads > 0
            
        except Exception as e:
            logger.error(f"Error during bulk download: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in download_files: {e}", exc_info=True)
        return False

def upload_file(bucket: storage.Bucket, source_path: str, bucket_path: str) -> bool:
    """Upload a file to GCS bucket with error handling"""
    try:
        if not bucket or not source_path or not bucket_path:
            logger.error("bucket, source_path, and bucket_path are required")
            return False
            
        if not os.path.exists(source_path):
            logger.error(f"Source file not found: {source_path}")
            return False
            
        if not os.path.isfile(source_path):
            logger.error(f"Source path is not a file: {source_path}")
            return False
            
        file_size = os.path.getsize(source_path)
        logger.info(f'Uploading {source_path} ({file_size / 1024 / 1024:.1f}MB) to {bucket_path}')
        
        try:
            blob = bucket.blob(bucket_path)
            
            # Set content type based on file extension
            content_type = None
            _, ext = os.path.splitext(source_path)
            if ext.lower() in ['.mp3', '.wav', '.ogg']:
                content_type = f'audio/{ext[1:]}'
            elif ext.lower() in ['.json']:
                content_type = 'application/json'
            
            if content_type:
                blob.content_type = content_type
                
            blob.upload_from_filename(source_path)
            
            # Verify upload
            if blob.exists():
                logger.info(f"Successfully uploaded: {source_path}")
                return True
            else:
                logger.error(f"Upload verification failed: {source_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error uploading file {source_path}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {e}", exc_info=True)
        return False

def list_files(bucket: storage.Bucket, bucket_path: str) -> List[str]:
    """List files in GCS bucket path with error handling"""
    try:
        if not bucket or not bucket_path:
            logger.error("bucket and bucket_path are required")
            return []
            
        logger.debug(f"Listing files in bucket path: {bucket_path}")
        
        try:
            blobs = bucket.list_blobs(prefix=bucket_path)
            file_list = []
            
            for blob in blobs:
                try:
                    # Skip directories
                    if not blob.name.endswith('/'):
                        file_list.append(blob.name)
                except Exception as e:
                    logger.warning(f"Error processing blob: {e}")
                    continue
                    
            logger.debug(f"Found {len(file_list)} files in {bucket_path}")
            return file_list
            
        except Exception as e:
            logger.error(f"Error listing files in {bucket_path}: {e}")
            return []
            
    except Exception as e:
        logger.error(f"Unexpected error in list_files: {e}", exc_info=True)
        return []

def generate_url(bucket: storage.Bucket, bucket_path: str) -> Optional[str]:
    """Generate signed URL for GCS object with error handling"""
    try:
        if not bucket or not bucket_path:
            logger.error("bucket and bucket_path are required")
            return None
            
        logger.debug(f"Generating signed URL for: {bucket_path}")
        
        try:
            blob = bucket.blob(bucket_path)
            
            if not blob.exists():
                logger.warning(f"Blob does not exist: {bucket_path}")
                return None
                
            # Generate URL valid for 1 hour
            url_lifetime = int(datetime.now(tz=timezone.utc).timestamp()) + 3600
            
            signed_url = blob.generate_signed_url(url_lifetime)
            logger.debug(f"Generated signed URL for {bucket_path}")
            return signed_url
            
        except Exception as e:
            logger.error(f"Error generating signed URL for {bucket_path}: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Unexpected error in generate_url: {e}", exc_info=True)
        return None

def delete_file(bucket: storage.Bucket, bucket_path: str) -> bool:
    """Delete file from GCS bucket with error handling"""
    try:
        if not bucket or not bucket_path:
            logger.error("bucket and bucket_path are required")
            return False
            
        logger.info(f"Deleting file from bucket: {bucket_path}")
        
        try:
            blob = bucket.blob(bucket_path)
            
            if not blob.exists():
                logger.warning(f"File does not exist (already deleted?): {bucket_path}")
                return True  # Consider this success
                
            blob.delete()
            logger.info(f"Successfully deleted: {bucket_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {bucket_path}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in delete_file: {e}", exc_info=True)
        return False