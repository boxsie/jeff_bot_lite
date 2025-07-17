import os
import discord
import asyncio
import logging
import aiohttp
import tempfile
from pathlib import Path

from discord.utils import get

logger = logging.getLogger('discord.voice')

FFMPEG_OPTIONS = {'options': '-vn'}

class Voice(object):
    def __init__(self, bot):
        self.bot = bot
        self.voice = None
        self.now_playing = None
        self._temp_files = []  # Track temporary files for cleanup
        logger.info("Voice system initialized")

    async def join_voice_channel(self, channel):
        """Join or move to a voice channel with error handling"""
        try:
            if not channel:
                logger.error("Cannot join voice channel: channel is None")
                raise ValueError("Voice channel is required")
                
            logger.info(f"Attempting to join voice channel: {channel.name} in {channel.guild.name}")
            
            if self.voice and self.voice.is_connected():
                if self.voice.channel.id == channel.id:
                    logger.info(f"Already in target channel: {channel.name}")
                    return
                logger.info(f"Moving from {self.voice.channel.name} to {channel.name}")
                await self.voice.move_to(channel)
            else:
                # Clean up any existing voice connection
                if self.voice:
                    try:
                        await self.voice.disconnect()
                    except Exception as e:
                        logger.warning(f"Error disconnecting old voice connection: {e}")
                        
                self.voice = await channel.connect()
                logger.info(f"Successfully connected to voice channel: {channel.name}")
                
        except discord.ClientException as e:
            logger.error(f"Discord client error joining voice channel {channel.name}: {e}")
            raise
        except discord.Forbidden:
            logger.error(f"No permission to join voice channel: {channel.name}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error joining voice channel {channel.name}: {e}", exc_info=True)
            raise

    async def play(self, channel, source, title, delay=0):
        """Play audio from a source with error handling"""
        try:
            if not source:
                logger.error("Cannot play: source is empty")
                raise ValueError("Audio source is required")
                
            if not title:
                title = "Unknown"
                
            logger.info(f"Play request: {title} from {source[:100]}{'...' if len(source) > 100 else ''}")
            
            # Validate delay parameter
            if delay < 0:
                logger.warning(f"Invalid delay {delay}, setting to 0")
                delay = 0
            elif delay > 60:  # Sanity check for very long delays
                logger.warning(f"Very long delay {delay} seconds for {title}")

            if source.startswith(('http://', 'https://')):
                await self._play_url(channel, source, title, delay)
            else:
                await self._play_file(channel, source, title, delay)

            logger.info(f'Successfully started playing {title} in {channel.name}')
            
        except Exception as e:
            logger.error(f"Error playing {title}: {e}", exc_info=True)
            await self._set_now_playing()  # Clear now playing on error
            raise

    async def stop(self):
        """Stop audio playback with error handling"""
        try:
            if not self.voice:
                logger.warning("Stop called but no voice connection exists")
                return
                
            if self.voice.is_playing():
                logger.info("Stopping audio playback")
                self.voice.stop()
            else:
                logger.info("Stop called but nothing is playing")
                
            await self._set_now_playing()
            
        except Exception as e:
            logger.error(f"Error stopping playback: {e}", exc_info=True)
            await self._set_now_playing()  # Ensure status is cleared

    async def disconnect(self):
        """Disconnect from voice channel and cleanup"""
        try:
            if self.voice and self.voice.is_connected():
                logger.info(f"Disconnecting from voice channel: {self.voice.channel.name}")
                await self.voice.disconnect()
            
            await self._set_now_playing()
            await self._cleanup_temp_files()
            self.voice = None
            
        except Exception as e:
            logger.error(f"Error disconnecting from voice: {e}", exc_info=True)

    async def _set_now_playing(self, source=None, title=None):
        """Set bot activity status with error handling"""
        try:
            if source and title:
                self.now_playing = {
                    'source': source,
                    'title': title
                }
                activity = discord.Activity(type=discord.ActivityType.listening, name=title)
                await self.bot.change_presence(activity=activity)
                logger.debug(f"Set now playing: {title}")
            else:
                self.now_playing = None
                await self.bot.change_presence(status=discord.Status.online)
                logger.debug("Cleared now playing status")
                
        except discord.HTTPException as e:
            logger.warning(f"Error updating bot presence: {e}")
        except Exception as e:
            logger.error(f"Unexpected error setting now playing status: {e}", exc_info=True)

    async def _play_file(self, channel, file_path, title, delay):
        """Play audio from a local file with error handling"""
        try:
            # Validate file exists and is readable
            if not os.path.exists(file_path):
                logger.error(f"Audio file not found: {file_path}")
                raise FileNotFoundError(f"Audio file not found: {file_path}")
                
            if not os.path.isfile(file_path):
                logger.error(f"Path is not a file: {file_path}")
                raise ValueError(f"Path is not a file: {file_path}")
                
            # Check file size (reasonable limit)
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                logger.warning(f"Large audio file: {file_size / 1024 / 1024:.1f}MB for {title}")
                
            await self.join_voice_channel(channel)
            await self._set_now_playing(file_path, title)
            
            if delay > 0:
                logger.debug(f"Waiting {delay} seconds before playing {title}")
                await asyncio.sleep(delay)
                
            audio_source = discord.FFmpegPCMAudio(file_path)
            await self._voice_play(audio_source, title)
            
        except Exception as e:
            logger.error(f"Error playing file {file_path}: {e}", exc_info=True)
            raise

    async def _play_url(self, channel, url, title, delay):
        """Play audio from a URL with error handling"""
        temp_file = None
        try:
            logger.info(f"Downloading audio from URL: {url[:100]}{'...' if len(url) > 100 else ''}")
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            temp_file_path = temp_file.name
            temp_file.close()
            self._temp_files.append(temp_file_path)
            
            # Download with timeout and size limit
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"HTTP error downloading {url}: {response.status}")
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
                    
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > 50 * 1024 * 1024:  # 50MB limit
                        logger.error(f"File too large: {content_length} bytes from {url}")
                        raise ValueError(f"File too large: {content_length} bytes")
                    
                    # Download in chunks
                    downloaded = 0
                    max_size = 50 * 1024 * 1024  # 50MB limit
                    
                    with open(temp_file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            downloaded += len(chunk)
                            if downloaded > max_size:
                                logger.error(f"Download size exceeded limit: {downloaded} bytes")
                                raise ValueError("Download size exceeded limit")
                            f.write(chunk)
            
            logger.info(f"Successfully downloaded {downloaded} bytes for {title}")
            
            await self.join_voice_channel(channel)
            await self._set_now_playing(url, title)
            
            if delay > 0:
                logger.debug(f"Waiting {delay} seconds before playing {title}")
                await asyncio.sleep(delay)
                
            # Use the downloaded file instead of streaming
            audio_source = discord.FFmpegPCMAudio(temp_file_path, **FFMPEG_OPTIONS)
            await self._voice_play(audio_source, title)
            
        except aiohttp.ClientError as e:
            logger.error(f"Network error downloading {url}: {e}")
            raise
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading {url}")
            raise
        except Exception as e:
            logger.error(f"Error playing URL {url}: {e}", exc_info=True)
            raise

    async def _voice_play(self, source, title):
        """Play audio source with error handling"""
        try:
            if not self.voice:
                logger.error("Cannot play: no voice connection")
                raise RuntimeError("No voice connection")
                
            if not self.voice.is_connected():
                logger.error("Cannot play: voice connection lost")
                raise RuntimeError("Voice connection lost")
                
            # Stop any currently playing audio
            if self.voice.is_playing():
                logger.info("Stopping current audio before playing new track")
                self.voice.stop()
                # Give it a moment to stop
                await asyncio.sleep(0.1)
                
            logger.info(f"Starting playback of {title}")
            self.voice.play(source, after=lambda e: self._playback_finished(title, e))
            
        except Exception as e:
            logger.error(f"Error starting playback of {title}: {e}", exc_info=True)
            raise

    def _playback_finished(self, title, error):
        """Callback for when playback finishes"""
        if error:
            logger.error(f"Playback error for {title}: {error}")
        else:
            logger.info(f"Playback finished: {title}")
            
        # Schedule cleanup on the bot's event loop
        try:
            loop = self.bot.loop
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self._on_playback_finished(), loop)
        except Exception as e:
            logger.error(f"Error scheduling playback finished handler: {e}", exc_info=True)

    async def _on_playback_finished(self):
        """Handle post-playback cleanup"""
        try:
            await self._set_now_playing()
            # Clean up old temp files
            await self._cleanup_temp_files()
        except Exception as e:
            logger.error(f"Error in playback finished handler: {e}", exc_info=True)

    async def _cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            cleaned = 0
            for temp_file in self._temp_files[:]:  # Copy list to avoid modification during iteration
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        cleaned += 1
                    self._temp_files.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Error removing temp file {temp_file}: {e}")
                    
            if cleaned > 0:
                logger.debug(f"Cleaned up {cleaned} temporary files")
                
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}", exc_info=True)