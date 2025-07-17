import os
import sys
import random
import asyncio
import discord
import logging

from datetime import datetime
import dateutil.parser
from discord.ext import commands
from discord.utils import get
from typing import Optional

from utils.discord_helpers import send_text_list_to_author
from utils.jeff_persona import JeffPersona

logger = logging.getLogger('discord.birthdays')

class Birthdays(commands.Cog):
    def __init__(self, bot, birthday_service, jeff_persona: JeffPersona = None):
        self.bot = bot
        self.birthday_service = birthday_service
        self.jeff_persona = jeff_persona
        logger.info("Birthdays cog initialized")

    @commands.command(name='add_birthday', help='Set a users birthday')
    async def add_birthday(self, ctx, user: discord.User, birthday):
        try:
            if not birthday:
                await ctx.send(f'❌ Birthday input is required')
                return
                
            logger.info(f"Birthday add request from {ctx.author} for user {user} with date '{birthday}'")
               
            try:
                birthday_date = dateutil.parser.parse(birthday, dayfirst=True)
            except (ValueError, dateutil.parser.ParserError) as e:
                logger.warning(f"Invalid birthday format '{birthday}' provided by {ctx.author}")
                await ctx.send(f'❌ Invalid birthday format: \'{birthday}\'. Please use a format like "DD/MM/YYYY" or "1 Jan 1990"')
                return   

            if datetime.now() <= birthday_date:
                logger.warning(f"Future date provided by {ctx.author}: {birthday}")
                await ctx.send(f'❌ Birthday cannot be in the future')
                return

            formatted_date = birthday_date.strftime('%Y-%m-%d')
            
            success = self.birthday_service.add_birthday(user.id, formatted_date)
            
            if success:
                ret_text = f'✅ {user.display_name}\'s birthday has been set to {formatted_date}'
                logger.info(f"Birthday successfully added for user {user.id} by {ctx.author}")
                await ctx.send(ret_text)
            else:
                logger.error(f"Failed to add birthday for user {user.id}")
                await ctx.send(f'❌ Failed to save birthday. Please try again.')
                
        except Exception as e:
            logger.error(f"Error in add_birthday command: {e}", exc_info=True)
            await ctx.send('❌ An unexpected error occurred while adding the birthday.')

    @commands.command(name='list_birthdays', help='List all user birthdays')
    async def list_birthday(self, ctx):
        try:
            logger.info(f"List birthdays request from {ctx.author}")

            users_with_birthdays = self.birthday_service.get_users_with_birthdays()
            
            if not users_with_birthdays:
                await ctx.send("📅 No birthdays have been added yet!")
                return

            birthdays = []
            for u in users_with_birthdays:
                try:
                    # Format the birthday nicely
                    date_obj = dateutil.parser.parse(u.birthday)
                    formatted_date = date_obj.strftime('%d %B %Y')
                    birthdays.append(f'{u.user_name}: {formatted_date}')
                except Exception as e:
                    logger.warning(f"Error formatting birthday for user {u.user_name}: {e}")
                    birthdays.append(f'{u.user_name}: {u.birthday} (invalid format)')

            await send_text_list_to_author(ctx, birthdays)
            logger.info(f"Sent birthday list to {ctx.author} with {len(birthdays)} entries")
            
        except Exception as e:
            logger.error(f"Error in list_birthday command: {e}", exc_info=True)
            await ctx.send('❌ An error occurred while retrieving birthdays.')

    @commands.command(name='birthday', help='Display a user birthday with countdown, or show next birthday if no user specified')
    async def user_birthday(self, ctx, user: Optional[discord.User] = None):
        try:
            # Determine which user to show
            if user is None:
                # Show next birthday if no user specified
                logger.info(f"Next birthday request from {ctx.author}")
                target_user, birthday_countdown = self.birthday_service.get_next_birthday_user()
                
                if target_user is None:
                    await ctx.send("📅 No birthdays found! Use `!add_birthday @user DD/MM/YYYY` to add some.")
                    return
                
                # Handle next birthday display
                if birthday_countdown.is_today:
                    # Use Jeff's persona for birthday celebration if available
                    if self.jeff_persona:
                        birthday_topic = f"{target_user.user_name}'s birthday celebration"
                        birthday_context = f"It's {target_user.user_name}'s birthday today! Generate a casual but celebratory message."
                        
                        try:
                            jeff_message = await self.jeff_persona.generate_casual_comment(
                                topic=birthday_topic,
                                context=birthday_context
                            )
                            if jeff_message and jeff_message != "Can't be bothered to comment on that":
                                await ctx.send(f"🥳🎉🎊 {jeff_message} 🥳🎉🎊")
                            else:
                                await ctx.send(f"🥳🎉🎊 It's {target_user.user_name}'s Birthday !!!! 🥳🎉🎊")
                        except Exception as e:
                            logger.error(f"Error generating Jeff birthday message: {e}")
                            await ctx.send(f"🥳🎉🎊 It's {target_user.user_name}'s Birthday !!!! 🥳🎉🎊")
                    else:
                        await ctx.send(f"🥳🎉🎊 It's {target_user.user_name}'s Birthday !!!! 🥳🎉🎊")
                else:
                    await ctx.send(f"🎂 {target_user.user_name}'s Birthday is next.\n" \
                        f"It's in {birthday_countdown.days} days, {birthday_countdown.hours} " \
                        f"hours & {birthday_countdown.mins} mins")
            else:
                # Show specific user's birthday
                logger.info(f"Specific birthday request from {ctx.author} for user {user}")
                jeff_user = self.birthday_service.user_manager.get_user(user.id)
                
                if jeff_user is None:
                    logger.warning(f"User {user.id} not found in system")
                    await ctx.send(f'❌ User {user.display_name} not found in the system')
                    return
                    
                if jeff_user.birthday is None:
                    await ctx.send(f'📅 {user.display_name} hasn\'t set their birthday yet! They can use `!add_birthday @{user.display_name} DD/MM/YYYY`')
                    return
                
                birthday_countdown = self.birthday_service.get_date_countdown(jeff_user)
                
                if birthday_countdown is None:
                    logger.error(f"Failed to calculate birthday countdown for user {user.id}")
                    await ctx.send(f'❌ Error calculating birthday countdown for {user.display_name}')
                    return
                
                # Handle specific user birthday display
                if birthday_countdown.is_today:
                    # Use Jeff's persona for birthday celebration if available
                    if self.jeff_persona:
                        birthday_topic = f"{jeff_user.user_name}'s birthday celebration"
                        birthday_context = f"It's {jeff_user.user_name}'s birthday today! Generate a casual but celebratory message."
                        
                        try:
                            jeff_message = await self.jeff_persona.generate_casual_comment(
                                topic=birthday_topic,
                                context=birthday_context
                            )
                            if jeff_message and jeff_message != "Can't be bothered to comment on that":
                                await ctx.send(f"🥳🎉🎊 {jeff_message} 🥳🎉🎊")
                            else:
                                await ctx.send(f"🥳🎉🎊 It's {jeff_user.user_name}'s Birthday !!!! 🥳🎉🎊")
                        except Exception as e:
                            logger.error(f"Error generating Jeff birthday message: {e}")
                            await ctx.send(f"🥳🎉🎊 It's {jeff_user.user_name}'s Birthday !!!! 🥳🎉🎊")
                    else:
                        await ctx.send(f"🥳🎉🎊 It's {jeff_user.user_name}'s Birthday !!!! 🥳🎉🎊")
                else:
                    await ctx.send(f"🎂 It's {birthday_countdown.days} days, {birthday_countdown.hours} " \
                        f"hours & {birthday_countdown.mins} minutes until {jeff_user.user_name}'s birthday !!")
                        
        except Exception as e:
            logger.error(f"Error in user_birthday command: {e}", exc_info=True)
            await ctx.send('❌ An error occurred while checking the birthday.')
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle errors specific to this cog's commands only"""
        # Only handle errors from this cog's commands
        if ctx.command and ctx.command.name in ['add_birthday', 'list_birthdays', 'birthday']:
            if isinstance(error, commands.UserNotFound):
                await ctx.send("❌ User not found. Please mention a valid user.")
            elif isinstance(error, commands.MissingRequiredArgument):
                if ctx.command.name == 'add_birthday':
                    await ctx.send("❌ Please provide both a user and their birthday: `!add_birthday @user DD/MM/YYYY`")
            else:
                # Let the global error handler deal with it
                logger.error(f"Unhandled error in birthdays cog: {error}", exc_info=True)
        
