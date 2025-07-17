import os
import random
import logging
from typing import Optional, List

from google.cloud import storage
from google.cloud import pubsub_v1
from google.cloud.exceptions import GoogleCloudError

from utils.gcs_helpers import connect_to_bucket, download_file, download_files, list_files, generate_url, upload_file

logger = logging.getLogger('discord.files')

class FileObject:
    def __init__(self, path: str, bucket: Optional[storage.Bucket] = None):
        try:
            if not path or not isinstance(path, str):
                logger.error(f"Invalid path: {path}")
                raise ValueError("path must be a non-empty string")
                
            if not os.path.exists(path):
                logger.warning(f"File path does not exist: {path}")
                
            self.path = path
            self.name = self._remove_extension(path)
            self.bucket = bucket
            
            logger.debug(f"Created FileObject: {self.name} (path: {path})")
            
        except Exception as e:
            logger.error(f"Error creating FileObject: {e}", exc_info=True)
            raise

    def _remove_extension(self, file_path: str) -> str:
        """Remove file extension from path to get name"""
        try:
            if not file_path:
                return ""
                
            filename = os.path.split(file_path)[-1]
            name_parts = filename.split('.')
            
            # If there's only one part or it's a hidden file, return as-is
            if len(name_parts) <= 1 or filename.startswith('.'):
                return filename
                
            # Join all parts except the last (extension)
            return ".".join(name_parts[:-1])
            
        except Exception as e:
            logger.warning(f"Error removing extension from {file_path}: {e}")
            return file_path or ""

    def get_path(self) -> str:
        """Get file path or generate signed URL if using bucket"""
        try:
            if self.bucket and self.path:
                try:
                    # For bucket files, generate a signed URL
                    signed_url = generate_url(self.bucket, self.path)
                    if signed_url:
                        logger.debug(f"Generated signed URL for {self.name}")
                        return signed_url
                    else:
                        logger.warning(f"Failed to generate signed URL for {self.name}, falling back to local path")
                except Exception as e:
                    logger.warning(f"Error generating signed URL for {self.name}: {e}")

            return self.path
            
        except Exception as e:
            logger.error(f"Error getting path for {self.name}: {e}")
            return self.path or ""

    def exists(self) -> bool:
        """Check if file exists locally"""
        try:
            return os.path.exists(self.path) if self.path else False
        except Exception as e:
            logger.warning(f"Error checking existence of {self.path}: {e}")
            return False

    def get_size(self) -> int:
        """Get file size in bytes"""
        try:
            if self.exists():
                return os.path.getsize(self.path)
            return 0
        except Exception as e:
            logger.warning(f"Error getting size of {self.path}: {e}")
            return 0

class FileRepo:
    def __init__(self, base_path: str, bucket_path: Optional[str] = None, 
                 service_account_json: Optional[str] = None, project_id: Optional[str] = None, 
                 bucket_sub_name: Optional[str] = None, overwrite: bool = False):
        try:
            if not base_path or not isinstance(base_path, str):
                logger.error(f"Invalid base_path: {base_path}")
                raise ValueError("base_path must be a non-empty string")
                
            self.base_path = os.path.abspath(base_path)
            self.bucket_path = bucket_path
            self.bucket = None
            self.bucket_dir = None
            self.files = []
            self.subscriber = None
            
            logger.info(f"Initializing FileRepo with base_path: {self.base_path}")

            # Create local directory if it doesn't exist
            try:
                if not os.path.exists(self.base_path):
                    os.makedirs(self.base_path, exist_ok=True)
                    logger.info(f"Created directory: {self.base_path}")
            except Exception as e:
                logger.error(f"Failed to create directory {self.base_path}: {e}")
                raise

            # Setup bucket connection if specified
            if self.bucket_path:
                try:
                    self._setup_bucket_connection(service_account_json, project_id, bucket_sub_name, overwrite)
                except Exception as e:
                    logger.error(f"Failed to setup bucket connection: {e}")
                    raise

            # Load files from local directory
            self._load_files()
            
            logger.info(f"FileRepo initialized with {len(self.files)} files")
            
        except Exception as e:
            logger.error(f"Failed to initialize FileRepo: {e}", exc_info=True)
            raise

    def _setup_bucket_connection(self, service_account_json: Optional[str], 
                               project_id: Optional[str], bucket_sub_name: Optional[str], 
                               overwrite: bool):
        """Setup Google Cloud Storage bucket connection"""
        try:
            if not service_account_json:
                logger.warning("No service account JSON provided, skipping bucket setup")
                return
                
            path_split = self.bucket_path.split('/')
            bucket_name = path_split[0]
            bucket_dir = '/'.join(path_split[1:]) if len(path_split) > 1 else ''
            
            logger.info(f"Connecting to bucket: {bucket_name}, directory: {bucket_dir}")
            
            self.bucket = connect_to_bucket(bucket_name, service_account_json)
            self.bucket_dir = bucket_dir

            if not self.bucket:
                logger.error('Unable to connect to GCS bucket')
                raise Exception('Unable to connect to GCS bucket')

            # Download files from bucket
            if self.base_path:
                logger.info(f'Downloading files from {self.bucket_path}')
                success = download_files(
                    bucket=self.bucket,
                    bucket_path=self.bucket_dir,
                    output_path=self.base_path,
                    overwrite=overwrite
                )
                
                if success:
                    logger.info("Files downloaded successfully")
                else:
                    logger.warning("Some files failed to download")

                # Setup pub/sub subscription if requested
                if project_id and bucket_sub_name:
                    try:
                        self.subscribe_to_bucket(project_id=project_id, bucket_sub_name=bucket_sub_name)
                    except Exception as e:
                        logger.warning(f"Failed to setup bucket subscription: {e}")
                        
        except Exception as e:
            logger.error(f"Error in _setup_bucket_connection: {e}")
            raise

    def _load_files(self):
        """Load files from the local directory"""
        try:
            if not os.path.exists(self.base_path):
                logger.warning(f"Base path does not exist: {self.base_path}")
                self.files = []
                return
                
            logger.debug(f"Loading files from: {self.base_path}")
            
            try:
                file_names = os.listdir(self.base_path)
            except Exception as e:
                logger.error(f"Error listing directory {self.base_path}: {e}")
                self.files = []
                return
                
            loaded_files = []
            for filename in file_names:
                try:
                    file_path = os.path.join(self.base_path, filename)
                    
                    # Skip directories and hidden files
                    if os.path.isdir(file_path) or filename.startswith('.'):
                        continue
                        
                    file_obj = FileObject(file_path, self.bucket)
                    loaded_files.append(file_obj)
                    
                except Exception as e:
                    logger.warning(f"Error creating FileObject for {filename}: {e}")
                    continue
                    
            self.files = loaded_files
            logger.info(f"Loaded {len(self.files)} files from {self.base_path}")
            
        except Exception as e:
            logger.error(f"Error in _load_files: {e}", exc_info=True)
            self.files = []

    def create_file_path(self, filename: str) -> str:
        """Create full file path for a filename"""
        try:
            if not filename or not isinstance(filename, str):
                logger.error(f"Invalid filename: {filename}")
                raise ValueError("filename must be a non-empty string")
                
            # Sanitize filename
            filename = filename.strip()
            if not filename:
                raise ValueError("filename cannot be empty after stripping")
                
            file_path = os.path.join(self.base_path, filename)
            logger.debug(f"Created file path: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error creating file path for {filename}: {e}")
            raise

    def add_file(self, filename: str) -> Optional[FileObject]:
        """Add a new file to the repository"""
        try:
            if not filename:
                logger.error("filename is required")
                return None
                
            file_path = self.create_file_path(filename=filename)
            
            # Check if file already exists in repository
            existing_file = self.find(filename.split('.')[0])  # Name without extension
            if existing_file:
                logger.info(f"File already exists in repository: {filename}")
                return existing_file
                
            fo = FileObject(file_path, self.bucket)
            self.files.append(fo)
            
            logger.info(f"Added file to repository: {filename}")
            return fo
            
        except Exception as e:
            logger.error(f"Error adding file {filename}: {e}", exc_info=True)
            return None

    def update_file(self, file_obj: FileObject) -> bool:
        """Update file in bucket storage"""
        try:
            if not file_obj:
                logger.error("file_obj is required")
                return False
                
            if not self.bucket:
                logger.debug("No bucket configured, skipping upload")
                return True
                
            if not file_obj.exists():
                logger.error(f"File does not exist locally: {file_obj.path}")
                return False
                
            # Upload to bucket
            bucket_file_path = os.path.join(self.bucket_dir, os.path.basename(file_obj.path)).replace('\\', '/')
            success = upload_file(bucket=self.bucket, source_path=file_obj.path, bucket_path=bucket_file_path)
            
            if success:
                logger.info(f"Successfully uploaded file: {file_obj.name}")
            else:
                logger.error(f"Failed to upload file: {file_obj.name}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error updating file {getattr(file_obj, 'name', 'unknown')}: {e}", exc_info=True)
            return False

    def delete_file(self, filename: str) -> bool:
        """Delete a file from the repository"""
        try:
            if not filename:
                logger.error("filename is required")
                return False
                
            file_path = self.create_file_path(filename=filename)

            if not os.path.exists(file_path):
                logger.warning(f'Unable to delete file - {filename} not found')
                return False

            # Remove from files list
            self.files = [f for f in self.files if f.path != file_path]
            
            # Delete local file
            try:
                os.remove(file_path)
                logger.info(f"Deleted local file: {filename}")
            except Exception as e:
                logger.error(f"Error deleting local file {filename}: {e}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {filename}: {e}", exc_info=True)
            return False

    def find(self, name: str) -> Optional[FileObject]:
        """Find a file by name"""
        try:
            if not name:
                return None
                
            found_file = next((f for f in self.files if f.name == name), None)
            
            if found_file:
                logger.debug(f"Found file: {name}")
            else:
                logger.debug(f"File not found: {name}")
                
            return found_file
            
        except Exception as e:
            logger.error(f"Error finding file {name}: {e}")
            return None

    def random(self) -> Optional[FileObject]:
        """Get a random file from the repository"""
        try:
            if not self.files:
                logger.warning("No files available for random selection")
                return None
                
            selected_file = random.choice(self.files)
            logger.debug(f"Selected random file: {selected_file.name}")
            return selected_file
            
        except Exception as e:
            logger.error(f"Error selecting random file: {e}")
            return None

    def list_files(self) -> List[FileObject]:
        """Get list of all files"""
        try:
            return self.files.copy()
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []

    def get_file_count(self) -> int:
        """Get total number of files"""
        try:
            return len(self.files)
        except Exception as e:
            logger.error(f"Error getting file count: {e}")
            return 0

    def subscribe_to_bucket(self, project_id: str, bucket_sub_name: str):
        """Subscribe to bucket change notifications"""
        try:
            if not self.bucket:
                logger.error('Unable to subscribe - no bucket connection')
                return

            if not project_id or not bucket_sub_name:
                logger.error("project_id and bucket_sub_name are required")
                return
                
            logger.info(f"Setting up bucket subscription: {bucket_sub_name}")
            
            try:
                subscriber = pubsub_v1.SubscriberClient()
                subscription_path = subscriber.subscription_path(project_id, bucket_sub_name)

                def callback(message):
                    try:
                        logger.debug(f"Received bucket notification: {message.attributes.get('eventType', 'unknown')}")
                        message.ack()

                        event_type = message.attributes.get('eventType')
                        if not event_type:
                            logger.warning("No event type in bucket notification")
                            return

                        obj_id = message.attributes.get('objectId')
                        if not obj_id:
                            logger.warning("No object ID in bucket notification")
                            return
                            
                        bucket_dir, filename = os.path.split(obj_id)

                        if bucket_dir != self.bucket_dir:
                            logger.debug(f"Ignoring notification for different directory: {bucket_dir}")
                            return

                        if event_type == 'OBJECT_DELETE':
                            self._handle_bucket_delete(filename)
                        elif event_type == 'OBJECT_FINALIZE':
                            self._handle_bucket_create(filename)
                        else:
                            logger.debug(f"Unhandled event type: {event_type}")
                            
                    except Exception as e:
                        logger.error(f"Error in bucket notification callback: {e}", exc_info=True)

                self.subscriber = subscriber
                subscriber.subscribe(subscription_path, callback=callback)
                logger.info(f"Successfully subscribed to bucket notifications: {bucket_sub_name}")
                
            except Exception as e:
                logger.error(f"Error setting up bucket subscription: {e}")
                
        except Exception as e:
            logger.error(f"Error in subscribe_to_bucket: {e}", exc_info=True)

    def _handle_bucket_delete(self, filename: str):
        """Handle bucket file deletion notification"""
        try:
            logger.info(f'Bucket delete notification: {filename}')
            
            if self.delete_file(filename):
                logger.info(f'{filename} deleted successfully')
            else:
                logger.warning(f'Failed to delete {filename}')
                
        except Exception as e:
            logger.error(f"Error handling bucket delete for {filename}: {e}")

    def _handle_bucket_create(self, filename: str):
        """Handle bucket file creation notification"""
        try:
            logger.info(f'Bucket create notification: {filename}')
            
            # Download the new file
            success = download_file(
                bucket=self.bucket,
                bucket_path=self.bucket_dir,
                filename=filename,
                output_path=self.base_path,
                overwrite=True
            )
            
            if success:
                # Add to file list
                new_file = self.add_file(filename)
                if new_file:
                    logger.info(f'{filename} added successfully')
                else:
                    logger.warning(f'Failed to add {filename} to repository')
            else:
                logger.warning(f'Failed to download {filename}')
                
        except Exception as e:
            logger.error(f"Error handling bucket create for {filename}: {e}")

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.subscriber:
                try:
                    # Note: Subscriber cleanup is complex in pub/sub, usually handled by context managers
                    logger.info("Cleaning up bucket subscriber")
                    self.subscriber = None
                except Exception as e:
                    logger.warning(f"Error cleaning up subscriber: {e}")
                    
            logger.info("FileRepo cleanup completed")
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")