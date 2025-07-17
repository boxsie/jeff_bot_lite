import asyncio
import logging
import json
import random
from bot.scheduler import ScheduledJob
from utils.jeff_persona import JeffPersona

logger = logging.getLogger('discord.birthday_checker')

class BirthdayChecker(ScheduledJob):
    def __init__(self, bot, birthday_service, jeff_persona: JeffPersona, general_channel_name="general"):
        # Initialize as a scheduled job that runs every morning at 9 AM
        super().__init__(
            cron_expression="0 9 * * *",  # 9 AM every day
            callback=None,  # We override execute instead
            name="daily_birthday_check"
        )
        
        self.bot = bot
        self.birthday_service = birthday_service
        self.jeff_persona = jeff_persona
        self.general_channel_name = general_channel_name

    async def execute(self):
        """Override ScheduledJob execute to run the birthday check"""
        try:
            logger.info("Executing daily birthday check...")
            await self.check_birthdays()
            logger.info("Daily birthday check completed successfully")
        except Exception as e:
            logger.error(f"Error in daily birthday check: {str(e)}", exc_info=True)
        finally:
            self._calculate_next_run()

    async def check_birthdays(self):
        """Main birthday checking function"""
        logger.info("Running birthday check...")
        
        # Find the general channel
        general_channel = None
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.name.lower() == self.general_channel_name.lower():
                    general_channel = channel
                    break
            if general_channel:
                break
        
        if not general_channel:
            logger.error(f"Could not find channel named '{self.general_channel_name}'")
            return

        # Get users with birthdays today and in 1 week
        today_birthdays = self.birthday_service.get_users_with_birthday_today()
        week_reminder_birthdays = self.birthday_service.get_users_with_birthday_in_days(7)

        # Log all users and their countdown for debugging
        for user in self.birthday_service.get_users_with_birthdays():
            try:
                birthday_countdown = self.birthday_service.get_date_countdown(user)
                logger.info(f"User {user.user_name}: {birthday_countdown.days} days until birthday")
            except Exception as e:
                logger.error(f"Error processing birthday for user {user.user_name}: {e}")

        # Send birthday celebrations
        for user in today_birthdays:
            await self._celebrate_birthday(user, general_channel)

        # Send weekly reminders
        for user in week_reminder_birthdays:
            await self._send_weekly_reminder(user, general_channel)

        if today_birthdays:
            logger.info(f"Celebrated {len(today_birthdays)} birthdays")
        if week_reminder_birthdays:
            logger.info(f"Sent {len(week_reminder_birthdays)} weekly reminders")
        
        if not today_birthdays and not week_reminder_birthdays:
            logger.info("No birthdays or reminders to send today")

    async def _celebrate_birthday(self, user, channel):
        """Generate and send a unique birthday celebration message using Jeff's personality"""
        try:
            # Generate unique birthday message using Jeff's persona
            birthday_topic = f"{user.user_name}'s birthday celebration"
            birthday_context = f"It's {user.user_name}'s birthday today! This is a special day that deserves a proper celebration. Generate a birthday message that's enthusiastic but in Jeff's casual style."
            
            celebration_message = await self.jeff_persona.generate_casual_comment(
                topic=birthday_topic,
                context=birthday_context
            )
            
            if celebration_message and celebration_message != "Can't be bothered to comment on that":
                await channel.send(f"🎉🎂 **BIRTHDAY ALERT!** 🎂🎉\n\n{celebration_message}")
            else:
                # Fallback to existing birthday cog message style
                await channel.send(f"🥳🎉🎊 It's {user.user_name}'s Birthday !!!! 🥳🎉🎊")
                
        except Exception as e:
            logger.error(f"Error celebrating birthday for {user.user_name}: {e}")

    async def _send_weekly_reminder(self, user, channel):
        """Send a 1-week birthday reminder with Jeff's personality"""
        try:
            # Generate Jeff-style reminder message
            reminder_topic = f"{user.user_name}'s upcoming birthday reminder"
            reminder_context = f"{user.user_name} has a birthday coming up in exactly one week. Generate a casual reminder that people should remember to wish them well or prepare something nice."
            
            reminder_message = await self.jeff_persona.generate_casual_comment(
                topic=reminder_topic,
                context=reminder_context
            )
            
            if reminder_message and reminder_message != "Can't be bothered to comment on that":
                await channel.send(f"📅 **BIRTHDAY REMINDER** 📅\n\n{reminder_message}")
            else:
                # Fallback to random pre-written messages
                fallback_messages = [
                    f"📅 Just a heads up - {user.user_name}'s birthday is coming up in exactly one week! 🎂",
                    f"⏰ Mark your calendars! {user.user_name} will be celebrating their birthday in 7 days! 🎉",
                    f"🗓️ Friendly reminder: {user.user_name}'s big day is just one week away! 🎈",
                    f"📢 T-minus 7 days until {user.user_name}'s birthday celebration! 🥳"
                ]
                await channel.send(random.choice(fallback_messages))
            
        except Exception as e:
            logger.error(f"Error sending weekly reminder for {user.user_name}: {e}")

