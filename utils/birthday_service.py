import dateutil.parser
import logging
from utils.date_helpers import get_next_occurance
from typing import List, Optional

logger = logging.getLogger('discord.birthday_service')

class BirthdayService:
    def __init__(self, user_manager):
        self.user_manager = user_manager
        logger.info("Birthday service initialized")

    def get_date_countdown(self, user):
        """Get countdown to a user's next birthday"""
        try:
            if not user or not user.birthday:
                logger.warning(f"User {getattr(user, 'user_name', 'unknown')} has no birthday set")
                return None
                
            user_birth_date = dateutil.parser.parse(user.birthday)
            countdown = get_next_occurance(user_birth_date.month, user_birth_date.day)
            
            logger.debug(f"Birthday countdown for {user.user_name}: {countdown.days} days")
            return countdown
            
        except (ValueError, dateutil.parser.ParserError) as e:
            logger.error(f"Invalid birthday format for user {getattr(user, 'user_name', 'unknown')}: {user.birthday if user else 'None'}")
            return None
        except Exception as e:
            logger.error(f"Error calculating birthday countdown for user {getattr(user, 'user_name', 'unknown')}: {e}")
            return None

    def get_users_with_birthdays(self):
        """Get all users who have birthdays set"""
        try:
            users = [u for u in self.user_manager.users if u.birthday is not None]
            logger.debug(f"Found {len(users)} users with birthdays")
            return users
        except Exception as e:
            logger.error(f"Error getting users with birthdays: {e}")
            return []

    def get_users_with_birthday_today(self):
        """Get users whose birthday is today"""
        try:
            users_with_birthdays = self.get_users_with_birthdays()
            today_birthdays = []
            
            for user in users_with_birthdays:
                try:
                    birthday_countdown = self.get_date_countdown(user)
                    if birthday_countdown and birthday_countdown.is_today:
                        today_birthdays.append(user)
                        logger.info(f"Today is {user.user_name}'s birthday!")
                except Exception as e:
                    logger.warning(f"Error checking birthday for user {user.user_name}: {e}")
                    continue
            
            logger.info(f"Found {len(today_birthdays)} birthdays today")
            return today_birthdays
            
        except Exception as e:
            logger.error(f"Error getting today's birthdays: {e}")
            return []

    def get_users_with_birthday_in_days(self, days: int):
        """Get users whose birthday is in exactly X days"""
        try:
            if days < 0:
                logger.warning(f"Invalid days parameter: {days}")
                return []
                
            users_with_birthdays = self.get_users_with_birthdays()
            future_birthdays = []
            
            for user in users_with_birthdays:
                try:
                    birthday_countdown = self.get_date_countdown(user)
                    if birthday_countdown and birthday_countdown.days == days:
                        future_birthdays.append(user)
                        logger.info(f"{user.user_name}'s birthday is in {days} days")
                except Exception as e:
                    logger.warning(f"Error checking birthday countdown for user {user.user_name}: {e}")
                    continue
            
            logger.info(f"Found {len(future_birthdays)} birthdays in {days} days")
            return future_birthdays
            
        except Exception as e:
            logger.error(f"Error getting birthdays in {days} days: {e}")
            return []

    def get_next_birthday_user(self):
        """Get the user whose birthday is next"""
        try:
            users_with_birthdays = self.get_users_with_birthdays()
            
            if not users_with_birthdays:
                logger.info("No users with birthdays found")
                return None, None

            winning_user = None
            winning_birthday = None
            
            for user in users_with_birthdays:
                try:
                    user_birthday = self.get_date_countdown(user)
                    if not user_birthday:
                        continue
                        
                    if winning_user is None or (
                        user_birthday.total_seconds > 0 and 
                        user_birthday.total_seconds < winning_birthday.total_seconds
                    ):
                        winning_user = user
                        winning_birthday = user_birthday
                        
                except Exception as e:
                    logger.warning(f"Error processing birthday for user {user.user_name}: {e}")
                    continue

            if winning_user:
                logger.info(f"Next birthday: {winning_user.user_name} in {winning_birthday.days} days")
            else:
                logger.info("No valid next birthday found")
                
            return winning_user, winning_birthday
            
        except Exception as e:
            logger.error(f"Error finding next birthday user: {e}")
            return None, None

    def add_birthday(self, user_id: int, birthday_date: str):
        """Add a birthday for a user"""
        try:
            if not user_id or not birthday_date:
                logger.warning(f"Invalid parameters for add_birthday: user_id={user_id}, birthday_date={birthday_date}")
                return False
                
            # Validate date format
            try:
                dateutil.parser.parse(birthday_date)
            except (ValueError, dateutil.parser.ParserError) as e:
                logger.error(f"Invalid birthday date format: {birthday_date}")
                return False
                
            result = self.user_manager.add_birthday(user_id, birthday_date)
            logger.info(f"Birthday added for user {user_id}: {birthday_date}")
            return result
            
        except Exception as e:
            logger.error(f"Error adding birthday for user {user_id}: {e}", exc_info=True)
            return False 