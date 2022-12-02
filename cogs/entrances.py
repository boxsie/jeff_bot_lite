import os
import sys
import random
import asyncio
import discord

from discord.ext import commands
from discord.utils import get

from utils.discord_helpers import send_text_list_to_author


class Entrances(commands.Cog):
    def __init__(self, bot, user_manager, sound_files):
        self.bot = bot
        self.user_manager = user_manager
        self.sound_files = sound_files


    @commands.command(name='entrance', help='Set a users entrance audio')
    async def add_entrance(self, ctx, user: discord.User, filename):
        print(f'Add entrance audio request from {ctx.message.author}')

        file_obj = self.sound_files.find(filename)
        if not file_obj:
            await ctx.send(f'Could not find audio file \'{filename}\'')
            return

        self.user_manager.add_entrance(user.id, filename)

        msg = f'User {user} entrance audio has been set to \'{filename}\''
        print(msg)
        await ctx.send(msg)


    @commands.command(name='list_entrances', help='List all entrance sounds')
    async def list_entrances(self, ctx):
        print(f'List entrance sounds request from {ctx.message.author}')

        entrances = []
        for u in self.user_manager.users:
            entrances.append(f'{u.user_name}: {u.entrance_filename}')

        await send_text_list_to_author(ctx, entrances)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user:
            return

        if after.channel and before.channel != after.channel:
            user = self.user_manager.get_user(member.id)

            if user and user.entrance_filename:
                print(f'{member.name} has arrived in {after.channel.name} playing entrance audio \'{user.entrance_filename}\'')
                try:
                    sound_file = self.sound_files.find(user.entrance_filename)
                    await self.bot.voice.play(channel=after.channel, source=sound_file.path, title=sound_file.name, delay=1)
                except Exception as e:
                    print(e)
                    print(f'Failed to play {member.name} entrance audio \'{user.entrance_filename}\'')