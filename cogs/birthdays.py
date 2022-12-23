import os
import sys
import random
import asyncio
import discord
from utils.date_helpers import get_next_occurance

from datetime import datetime
import dateutil.parser
from discord.ext import commands
from discord.utils import get

from utils.discord_helpers import send_text_list_to_author


class Birthdays(commands.Cog):
    def __init__(self, bot, user_manager):
        self.bot = bot
        self.user_manager = user_manager


    @commands.command(name='add_birthday', help='Set a users birthday')
    async def add_birthday(self, ctx, user: discord.User, birthday):
        if not birthday:
            await ctx.send(f'Input \'{birthday}\' not valid')
            return
               
        try:
            birthday_date = dateutil.parser.parse(birthday, dayfirst=True)
        except Exception as e:
            print(e)
            await ctx.send(f'Input \'{birthday}\' not valid \'{e}\'')
            return   

        if datetime.now() <= birthday_date:
            await ctx.send(f'Date cannot be in the future')
            return

        formatted_date = birthday_date.strftime('%Y-%m-%d')
        
        self.user_manager.add_birthday(user.id, formatted_date)

        ret_text = f'\'{user}\' just added the birthday \'{formatted_date}\''
        print(ret_text)
        await ctx.send(ret_text)


    @commands.command(name='list_birthdays', help='List all user birthdays')
    async def list_birthday(self, ctx):
        print(f'List birthdays request from {ctx.message.author}')

        birthdays = []
        for u in self.user_manager.users:
            birthdays.append(f'{u.user_name}: {u.birthday}')

        await send_text_list_to_author(ctx, birthdays)


    @commands.command(name='birthday', help='Display a user birthday with countdown')
    async def user_birthday(self, ctx, user: discord.User):
        jeff_user = self.user_manager.get_user(user.id)
        if jeff_user is None:
            await ctx.send(f'User {user.id} cannot be found')
            return
        if jeff_user.birthday is None:
            await ctx.send(f'User {user.id} needs to input their birthday')
            return

        birthday_countdown = self._get_date_countdown(jeff_user)
        if birthday_countdown.is_today:
            await ctx.send(f"🥳🎉🎊 It's {jeff_user.user_name}'s Birthday !!!! 🥳🎉🎊")
        else:
            await ctx.send(f"It's {birthday_countdown.days} days, {birthday_countdown.hours} "\
                f"hours & {birthday_countdown.mins} minutes until {jeff_user.user_name}'s birthday !!")


    @commands.command(name='next_birthday', help="Show who's birthday is next")
    async def next_birthday(self, ctx):
        print(f"Display next user's birthday {ctx.message.author}")

        users_with_birthdays = list(filter(lambda x: x.birthday is not None, self.user_manager.users))
        winning_user = users_with_birthdays[0]
        winning_birthday = self._get_date_countdown(winning_user)

        for u in users_with_birthdays[1:]:
            users_birthday = self._get_date_countdown(u)
            if users_birthday.total_seconds > 0 and users_birthday.total_seconds < winning_birthday.total_seconds:
                winning_user = u
                winning_birthday = users_birthday

        if winning_birthday.is_today:
            await ctx.send(f"🥳🎉🎊 It's {winning_user.user_name}'s Birthday !!!! 🥳🎉🎊")
        else:
            await ctx.send(f" It's {winning_user.user_name}'s Birthday next.\n" \
                f"It's in {winning_birthday.days} days, {winning_birthday.hours} "\
                f"hours & {winning_birthday.mins} mins")


    def _get_date_countdown(self, user):
        user_birth_date = dateutil.parser.parse(user.birthday)
        return get_next_occurance(user_birth_date.month, user_birth_date.day)
        
