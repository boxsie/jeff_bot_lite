import os
import discord
import asyncio

from discord.utils import get

FFMPEG_OPTIONS = {'options': '-vn'}

class Voice(object):
    def __init__(self, bot):
        self.bot = bot
        self.voice = None
        self.now_playing = None


    async def join_voice_channel(self, channel):
        if self.voice and self.voice.is_connected():
            await self.voice.move_to(channel)
        else:
            self.voice = await channel.connect()


    async def play(self, channel, source, title, delay=0):
        if source.startswith('http') or source.startswith('https'):
            await self._play_url(channel, source, title, delay)
        else:
            await self._play_file(channel, source, title, delay)

        print(f'Playing {source} in {channel.name}...')


    async def stop(self):
        self.voice.stop()
        await self._set_now_playing()


    async def _set_now_playing(self, source=None, title=None):
        if source and title:
            self.now_playing = {
                'source': source,
                'title': title
            }
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=title))
        else:
            self.now_playing = None
            await self.bot.change_presence(status=discord.Status.idle)


    async def _play_file(self, channel, file_path, title, delay):
        await self.join_voice_channel(channel)
        await self._set_now_playing(file_path, title)
        await asyncio.sleep(delay)
        await self._voice_play(discord.FFmpegPCMAudio(file_path), title)


    async def _play_url(self, channel, url, title, delay):
        await self.join_voice_channel(channel)
        await self._set_now_playing(url, title)
        import requests
        r = requests.get(url, allow_redirects=True)
        open(f'{title}.mp3', 'wb').write(r.content)
        await asyncio.sleep(delay)
        await self._voice_play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), title)


    async def _voice_play(self, source, title):
        if self.voice.is_playing():
            self.voice.stop()

        self.voice.play(source)