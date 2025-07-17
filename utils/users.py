import os
import random
import json
import logging
from typing import List, Optional

logger = logging.getLogger('discord.users')

CONFIG_NAME = 'users'

class BotUser(object):
    def __init__(self, user_id: int, user_name: str, entrance_filename: str = None, birthday: str = None):
        try:
            # Validate user_id
            if not isinstance(user_id, int):
                try:
                    user_id = int(user_id)
                except (ValueError, TypeError):
                    logger.error(f"Invalid user_id: {user_id}")
                    raise ValueError(f"user_id must be an integer, got {type(user_id)}")
            
            # Validate user_name
            if not user_name or not isinstance(user_name, str):
                logger.error(f"Invalid user_name: {user_name}")
                raise ValueError("user_name must be a non-empty string")
            
            # Validate optional parameters
            if entrance_filename is not None and not isinstance(entrance_filename, str):
                logger.warning(f"Invalid entrance_filename type: {type(entrance_filename)}")
                entrance_filename = str(entrance_filename) if entrance_filename else None
                
            if birthday is not None and not isinstance(birthday, str):
                logger.warning(f"Invalid birthday type: {type(birthday)}")
                birthday = str(birthday) if birthday else None

            self.user_id = user_id
            self.user_name = user_name.strip()
            self.entrance_filename = entrance_filename
            self.birthday = birthday
            
            logger.debug(f"Created BotUser: {user_id} ({user_name})")
            
        except Exception as e:
            logger.error(f"Error creating BotUser: {e}", exc_info=True)
            raise

    def add_entrance(self, entrance_filename: str):
        """Add entrance sound filename with validation"""
        try:
            if not entrance_filename or not isinstance(entrance_filename, str):
                logger.error(f"Invalid entrance_filename: {entrance_filename}")
                raise ValueError("entrance_filename must be a non-empty string")
                
            self.entrance_filename = entrance_filename.strip()
            logger.info(f"Added entrance '{entrance_filename}' for user {self.user_name}")
            
        except Exception as e:
            logger.error(f"Error adding entrance for user {self.user_name}: {e}")
            raise

    def add_birthday(self, birthday: str):
        """Add birthday with validation"""
        try:
            if not birthday or not isinstance(birthday, str):
                logger.error(f"Invalid birthday: {birthday}")
                raise ValueError("birthday must be a non-empty string")
                
            self.birthday = birthday.strip()
            logger.info(f"Added birthday '{birthday}' for user {self.user_name}")
            
        except Exception as e:
            logger.error(f"Error adding birthday for user {self.user_name}: {e}")
            raise

class UserManager():
    def __init__(self, user_repo):
        try:
            if not user_repo:
                logger.error("user_repo is required")
                raise ValueError("user_repo is required")
                
            self.users = []
            self.user_repo = user_repo
            self.users_json_file = None
            
            logger.info("Initializing UserManager...")
            
            # Find or create users config file
            self.users_json_file = self.user_repo.find(CONFIG_NAME)

            if self.users_json_file is None:
                logger.info(f"Users config file not found, creating new one: {CONFIG_NAME}.json")
                try:
                    self.users_json_file = self.user_repo.add_file(filename=f'{CONFIG_NAME}.json')
                    # Initialize with empty users list
                    self._save_user_json()
                    logger.info("Created new users config file")
                except Exception as e:
                    logger.error(f"Failed to create users config file: {e}")
                    raise
            else:
                logger.info(f"Found existing users config file: {self.users_json_file.path}")
                self._load_users()
                
            logger.info(f"UserManager initialized with {len(self.users)} users")
            
        except Exception as e:
            logger.error(f"Failed to initialize UserManager: {e}", exc_info=True)
            raise

    def _load_users(self):
        """Load users from JSON file with error handling"""
        try:
            if not self.users_json_file or not os.path.exists(self.users_json_file.path):
                logger.warning("Users JSON file not found, starting with empty user list")
                self.users = []
                return
                
            logger.info(f'Loading user json from {self.users_json_file.path}')

            try:
                with open(self.users_json_file.path, 'r', encoding='utf-8') as json_file:
                    content = json_file.read().strip()
                    
                    if not content:
                        logger.info("Users file is empty, starting with empty user list")
                        self.users = []
                        return
                        
                    users_json = json.loads(content)
                    
                    if not isinstance(users_json, list):
                        logger.error(f"Users JSON should be a list, got {type(users_json)}")
                        self.users = []
                        return
                        
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in users file: {e}")
                # Backup corrupted file
                backup_path = f"{self.users_json_file.path}.backup"
                try:
                    import shutil
                    shutil.copy2(self.users_json_file.path, backup_path)
                    logger.info(f"Backed up corrupted file to {backup_path}")
                except Exception as backup_error:
                    logger.warning(f"Failed to backup corrupted file: {backup_error}")
                self.users = []
                return
                
            except Exception as e:
                logger.error(f"Error reading users file: {e}")
                self.users = []
                return

            # Parse users with individual error handling
            loaded_users = []
            for i, user_data in enumerate(users_json):
                try:
                    if not isinstance(user_data, dict):
                        logger.warning(f"Skipping invalid user data at index {i}: not a dict")
                        continue
                        
                    required_fields = ['user_id', 'user_name']
                    missing_fields = [field for field in required_fields if field not in user_data]
                    
                    if missing_fields:
                        logger.warning(f"Skipping user at index {i}, missing fields: {missing_fields}")
                        continue
                        
                    user = BotUser(
                        user_id=user_data['user_id'], 
                        user_name=user_data['user_name'], 
                        entrance_filename=user_data.get('entrance_filename'),
                        birthday=user_data.get('birthday')
                    )
                    loaded_users.append(user)
                    
                except Exception as e:
                    logger.warning(f"Error loading user at index {i}: {e}")
                    continue

            self.users = loaded_users
            logger.info(f'Successfully loaded {len(self.users)} users')

        except Exception as e:
            logger.error(f"Error in _load_users: {e}", exc_info=True)
            self.users = []

    def _save_user_json(self):
        """Save users to JSON file with error handling"""
        try:
            if not self.users_json_file:
                logger.error("No users JSON file configured")
                return False
                
            logger.info(f'Saving {len(self.users)} users to {self.users_json_file.path}')

            # Convert users to dictionaries
            users_data = []
            for user in self.users:
                try:
                    user_dict = {
                        'user_id': user.user_id,
                        'user_name': user.user_name,
                        'entrance_filename': user.entrance_filename,
                        'birthday': user.birthday
                    }
                    users_data.append(user_dict)
                except Exception as e:
                    logger.warning(f"Error serializing user {getattr(user, 'user_name', 'unknown')}: {e}")
                    continue

            # Create backup of existing file
            if os.path.exists(self.users_json_file.path):
                try:
                    backup_path = f"{self.users_json_file.path}.bak"
                    import shutil
                    shutil.copy2(self.users_json_file.path, backup_path)
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")

            # Write to file
            try:
                with open(self.users_json_file.path, 'w', encoding='utf-8') as f:
                    json.dump(users_data, f, indent=4, ensure_ascii=False)
                logger.info('Users save completed successfully')
            except Exception as e:
                logger.error(f"Error writing users file: {e}")
                return False

            # Update file repository
            try:
                self.user_repo.update_file(file_obj=self.users_json_file)
                logger.debug("Updated file in repository")
            except Exception as e:
                logger.warning(f"Failed to update file in repository: {e}")
                
            return True

        except Exception as e:
            logger.error(f"Error in _save_user_json: {e}", exc_info=True)
            return False

    def add_user(self, user_id: int, user_name: str, save: bool = True) -> bool:
        """Add a single user with validation"""
        try:
            if not user_id or not user_name:
                logger.error("user_id and user_name are required")
                return False
                
            # Check if user already exists
            existing_user = self.get_user(user_id)
            if existing_user:
                # Update name if different
                if existing_user.user_name != user_name:
                    logger.info(f"Updating user name: {existing_user.user_name} -> {user_name}")
                    existing_user.user_name = user_name
                    if save:
                        return self._save_user_json()
                else:
                    logger.debug(f"User {user_id} already exists with same name")
                return True
                
            logger.info(f"Adding new user: {user_id} ({user_name})")
            new_user = BotUser(user_id=user_id, user_name=user_name)
            self.users.append(new_user)
            
            if save:
                return self._save_user_json()
            return True
        
        except Exception as e:
            logger.error(f"Error adding user {user_id} ({user_name}): {e}", exc_info=True)
            return False

    def add_users(self, bot_users: List[BotUser]) -> bool:
        """Add multiple users with validation"""
        try:
            if not bot_users:
                logger.info("No users to add")
                return True
                
            if not isinstance(bot_users, (list, tuple)):
                logger.error("bot_users must be a list or tuple")
                return False
                
            logger.info(f"Adding {len(bot_users)} users")
            
            added_count = 0
            for user in bot_users:
                try:
                    if not isinstance(user, BotUser):
                        logger.warning(f"Skipping invalid user object: {type(user)}")
                        continue
                        
                    if self.add_user(user_id=user.user_id, user_name=user.user_name, save=False):
                        added_count += 1
                        
                except Exception as e:
                    logger.warning(f"Error adding user {getattr(user, 'user_name', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Successfully added {added_count} users")
            return self._save_user_json()
            
        except Exception as e:
            logger.error(f"Error in add_users: {e}", exc_info=True)
            return False

    def add_entrance(self, user_id: int, entrance_sound: str) -> bool:
        """Add entrance sound for a user"""
        try:
            if not user_id or not entrance_sound:
                logger.error("user_id and entrance_sound are required")
                return False
                
            user = self.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False

            user.add_entrance(entrance_sound)
            return self._save_user_json()
            
        except Exception as e:
            logger.error(f"Error adding entrance for user {user_id}: {e}", exc_info=True)
            return False

    def add_birthday(self, user_id: int, birthday: str) -> bool:
        """Add birthday for a user"""
        try:
            if not user_id or not birthday:
                logger.error("user_id and birthday are required")
                return False
                
            user = self.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False

            user.add_birthday(birthday)
            return self._save_user_json()
            
        except Exception as e:
            logger.error(f"Error adding birthday for user {user_id}: {e}", exc_info=True)
            return False

    def get_user(self, user_id: int) -> Optional[BotUser]:
        """Get user by ID with validation"""
        try:
            if not user_id:
                return None
                
            if not isinstance(user_id, int):
                try:
                    user_id = int(user_id)
                except (ValueError, TypeError):
                    logger.error(f"Invalid user_id: {user_id}")
                    return None
                    
            user = next((u for u in self.users if u.user_id == user_id), None)
            
            if user:
                logger.debug(f"Found user: {user.user_name} ({user_id})")
            else:
                logger.debug(f"User {user_id} not found")
                
            return user
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}", exc_info=True)
            return None

    def get_user_count(self) -> int:
        """Get total number of users"""
        try:
            return len(self.users)
        except Exception as e:
            logger.error(f"Error getting user count: {e}")
            return 0

    def list_users(self) -> List[BotUser]:
        """Get list of all users"""
        try:
            return self.users.copy()
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []        