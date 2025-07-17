import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('discord.config')

class Config:
    def __init__(self, config: Dict[str, Any], base_bucket: str):
        try:
            if not isinstance(config, dict):
                logger.error(f"Config must be a dictionary, got {type(config)}")
                raise TypeError("Config must be a dictionary")
                
            if 'paths' not in config:
                logger.error("Config missing required 'paths' section")
                raise KeyError("Config missing required 'paths' section")
                
            if not isinstance(config['paths'], dict):
                logger.error("Config 'paths' section must be a dictionary")
                raise TypeError("Config 'paths' section must be a dictionary")
                
            if not base_bucket or not isinstance(base_bucket, str):
                logger.error(f"Invalid base_bucket: {base_bucket}")
                raise ValueError("base_bucket must be a non-empty string")

            self.paths = config['paths']
            self.base_bucket = base_bucket.rstrip('/')  # Remove trailing slash
            
            # Validate all path configurations
            self._validate_paths()
            
            logger.info(f"Config initialized with {len(self.paths)} path configurations")
            logger.debug(f"Available resources: {list(self.paths.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Config: {e}", exc_info=True)
            raise

    def _validate_paths(self):
        """Validate that all path configurations have required fields"""
        try:
            for resource_name, path_config in self.paths.items():
                if not isinstance(path_config, dict):
                    logger.warning(f"Path config for '{resource_name}' is not a dictionary")
                    continue
                    
                required_fields = ['local', 'bucket']
                missing_fields = [field for field in required_fields if field not in path_config]
                
                if missing_fields:
                    logger.warning(f"Resource '{resource_name}' missing fields: {missing_fields}")
                else:
                    logger.debug(f"Resource '{resource_name}' configuration is valid")
                    
        except Exception as e:
            logger.error(f"Error validating path configurations: {e}")

    def get_local_path(self, resource_name: str) -> str:
        """Get local path for a resource with validation"""
        try:
            if not resource_name:
                logger.error("Resource name cannot be empty")
                raise ValueError("Resource name cannot be empty")
                
            if resource_name not in self.paths:
                logger.error(f"Cannot find the resource path for '{resource_name}'. Available: {list(self.paths.keys())}")
                raise KeyError(f"Cannot find the resource path for '{resource_name}'")

            path_config = self.paths[resource_name]
            
            if not isinstance(path_config, dict):
                logger.error(f"Invalid path configuration for '{resource_name}': not a dictionary")
                raise TypeError(f"Invalid path configuration for '{resource_name}'")
                
            if 'local' not in path_config:
                logger.error(f"Resource '{resource_name}' missing 'local' path configuration")
                raise KeyError(f"Resource '{resource_name}' missing 'local' path configuration")

            local_path = path_config['local']
            
            if not isinstance(local_path, str):
                logger.error(f"Local path for '{resource_name}' must be a string, got {type(local_path)}")
                raise TypeError(f"Local path for '{resource_name}' must be a string")
                
            logger.debug(f"Retrieved local path for '{resource_name}': {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"Error getting local path for '{resource_name}': {e}")
            raise

    def get_bucket_path(self, resource_name: str) -> str:
        """Get bucket path for a resource with validation"""
        try:
            if not resource_name:
                logger.error("Resource name cannot be empty")
                raise ValueError("Resource name cannot be empty")
                
            if resource_name not in self.paths:
                logger.error(f"Cannot find the resource path for '{resource_name}'. Available: {list(self.paths.keys())}")
                raise KeyError(f"Cannot find the resource path for '{resource_name}'")

            path_config = self.paths[resource_name]
            
            if not isinstance(path_config, dict):
                logger.error(f"Invalid path configuration for '{resource_name}': not a dictionary")
                raise TypeError(f"Invalid path configuration for '{resource_name}'")
                
            if 'bucket' not in path_config:
                logger.error(f"Resource '{resource_name}' missing 'bucket' path configuration")
                raise KeyError(f"Resource '{resource_name}' missing 'bucket' path configuration")

            bucket_path = path_config['bucket']
            
            if not isinstance(bucket_path, str):
                logger.error(f"Bucket path for '{resource_name}' must be a string, got {type(bucket_path)}")
                raise TypeError(f"Bucket path for '{resource_name}' must be a string")

            full_bucket_path = f'{self.base_bucket}/{bucket_path.lstrip("/")}'
            logger.debug(f"Retrieved bucket path for '{resource_name}': {full_bucket_path}")
            return full_bucket_path
            
        except Exception as e:
            logger.error(f"Error getting bucket path for '{resource_name}': {e}")
            raise

    def list_resources(self) -> list:
        """Get list of available resource names"""
        try:
            resources = list(self.paths.keys())
            logger.debug(f"Available resources: {resources}")
            return resources
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            return []

    def has_resource(self, resource_name: str) -> bool:
        """Check if a resource exists in configuration"""
        try:
            return resource_name in self.paths
        except Exception as e:
            logger.error(f"Error checking resource '{resource_name}': {e}")
            return False