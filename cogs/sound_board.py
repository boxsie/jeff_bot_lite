import os
import sys
import random
import asyncio
import discord

from discord.ext import commands
from discord.utils import get

from utils.discord_helpers import send_text_list_to_author
from utils.discord_helpers import get_channel_from_ctx


class SoundBoard(commands.Cog):
    def __init__(self, bot, sound_files):
        self.bot = bot
        self.sound_files = sound_files


    @commands.command(name='play', help='Play a sound')
    async def play(self, ctx, sound_name):
        try:
            print(f'Play audio request from {ctx.message.author} for {sound_name}')
            channel = get_channel_from_ctx(bot=self.bot, ctx=ctx)
            sound_file = self.sound_files.find(sound_name)

            if sound_file:
                await self.bot.voice.play(channel=channel, source=sound_file.path, title=sound_file.name)
            else:
                await ctx.message.author.send(f'Could not find sound `{sound_name}`')
        except Exception as e:
            print(e)
            await ctx.message.author.send(f'Failed to play `{sound_name}`')


    @commands.command(name='stop', help='Stops all sounds')
    async def stop(self, ctx):
        print(f'Stop audio request from {ctx.message.author}')
        await self.bot.voice.stop()


    @commands.command(help='Random sound')
    async def random(self, ctx):
        try:
            print(f'Random audio request from {ctx.message.author}')
            channel = get_channel_from_ctx(bot=self.bot, ctx=ctx)
            sound_file = self.sound_files.random()
            await self.bot.voice.play(channel=channel, source=sound_file.path, title=sound_file.name)
        except Exception as e:
            print(e)
            await ctx.message.author.send(f'Failed to play random sound')


    @commands.command(name='list', help='List all sounds')
    async def list_sounds(self, ctx):
        print(f'List sounds request from {ctx.message.author}')

        filenames = self.sound_files.list_files()

        if not filenames or len(filenames) == 0:
            await ctx.message.author.send('There are no audio files')
            return

        await send_text_list_to_author(ctx, [f.name for f in filenames])