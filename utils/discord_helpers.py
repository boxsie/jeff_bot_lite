import sys
import logging
from typing import List, Optional
import discord

from io import BytesIO
from PIL import Image

logger = logging.getLogger('discord.discord_helpers')

MSG_CHAR_LIMIT = 2000
MAX_IMG_SIZE_MB = 8


async def send_text_list_to_author(ctx, strings: List[str]):
    """Send a list of strings to the command author via DM with proper chunking"""
    try:
        if not strings:
            logger.warning("Empty strings list provided to send_text_list_to_author")
            await ctx.author.send("```\nNo data to display\n```")
            return
            
        if not isinstance(strings, (list, tuple)):
            logger.error(f"strings must be a list or tuple, got {type(strings)}")
            raise TypeError("strings must be a list or tuple")

        logger.info(f"Sending {len(strings)} strings to {ctx.author} via DM")
        
        ret = '```'
        sent_messages = 0

        for s in sorted(strings):
            try:
                # Convert to string and sanitize
                s = str(s).strip()
                if not s:
                    continue
                    
                # Check if adding this string would exceed limit
                if (len(ret) + len(s) >= MSG_CHAR_LIMIT - 6):  # -6 for closing ```
                    r = ret
                    r = f'{r}```'
                    
                    try:
                        await ctx.author.send(r)
                        sent_messages += 1
                        logger.debug(f"Sent message chunk {sent_messages}")
                    except discord.HTTPException as e:
                        logger.error(f"Failed to send DM to {ctx.author}: {e}")
                        # Fallback to channel if DM fails
                        await ctx.send(f"⚠️ Couldn't send DM. Here's the data:\n{r}")
                        
                    ret = '```'
                    
                ret = f'{ret}\n{s}'
                
            except Exception as e:
                logger.warning(f"Error processing string in list: {e}")
                continue

        # Send the final chunk
        try:
            ret = f'{ret}```'
            await ctx.author.send(ret)
            sent_messages += 1
            logger.info(f"Successfully sent {sent_messages} message chunks to {ctx.author}")
            
        except discord.HTTPException as e:
            logger.error(f"Failed to send final DM to {ctx.author}: {e}")
            await ctx.send(f"⚠️ Couldn't send DM. Here's the final data:\n{ret}")
            
    except Exception as e:
        logger.error(f"Error in send_text_list_to_author: {e}", exc_info=True)
        try:
            await ctx.send("❌ An error occurred while sending the data.")
        except:
            pass  # If we can't even send an error message, give up


def create_img_bytes(img) -> Optional[BytesIO]:
    """Create BytesIO from image with proper validation (legacy function - deprecated)"""
    logger.warning("create_img_bytes is deprecated and should be replaced with proper image validation")
    
    try:
        if not img:
            logger.error("No image provided to create_img_bytes")
            return None
            
        bytes_io = BytesIO()

        try:
            bytes_io.seek(0)
            raw_image_data = img.get_raw_data()
            
            if not raw_image_data:
                logger.warning("No raw image data received")
                return None
                
        except Exception as e:
            logger.error(f"Error getting raw image data: {e}")
            return None

        # This validation method is flawed but keeping for compatibility
        try:
            logger.debug('Testing image with UTF-8 decode method...')
            _ = raw_image_data.decode('utf-8')
            logger.warning('Image test failed using UTF-8 decode - likely not an image')
            return None
        except UnicodeDecodeError:
            # This is expected for binary image data
            logger.debug('Image passed UTF-8 decode test (failed to decode = good)')
            
            try:
                img.copy_to(bytes_io, raw_image_data)
                img.copy_to(bytes_io)
                bytes_io.seek(0)

                img_size = sys.getsizeof(bytes_io)
                max_size = MAX_IMG_SIZE_MB * (1024 ** 2)  # Convert to proper MB

                if img_size < max_size:
                    logger.info(f'Image validation successful: {img_size} bytes')
                    return bytes_io
                else:
                    logger.warning(f'Image too large: {img_size} bytes (max: {max_size})')
                    return None
                    
            except Exception as e:
                logger.error(f"Error processing image data: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error in image validation: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error in create_img_bytes: {e}", exc_info=True)
        return None


def get_channel_from_user(bot, user) -> Optional[discord.VoiceChannel]:
    """Find the voice channel a user is currently in"""
    try:
        if not bot or not user:
            logger.error("Bot and user are required parameters")
            return None
            
        logger.debug(f"Looking for voice channel for user {user}")
        
        for guild in bot.guilds:
            try:
                for channel in guild.voice_channels:
                    for member in channel.members:
                        if member.id == user.id:
                            logger.info(f"Found user {user} in voice channel {channel.name} ({guild.name})")
                            return channel
            except Exception as e:
                logger.warning(f"Error checking guild {guild.name}: {e}")
                continue

        logger.info(f"User {user} not found in any voice channel")
        return None
        
    except Exception as e:
        logger.error(f"Error finding voice channel for user {user}: {e}", exc_info=True)
        return None


def get_channel_from_ctx(bot, ctx) -> Optional[discord.VoiceChannel]:
    """Get voice channel from command context"""
    try:
        if not bot or not ctx:
            logger.error("Bot and ctx are required parameters")
            return None
            
        logger.debug(f"Getting voice channel from context for {ctx.author}")
        
        # First try to get from voice state
        if (hasattr(ctx.author, 'voice') and 
            hasattr(ctx.author.voice, 'channel') and 
            ctx.author.voice.channel):
            channel = ctx.author.voice.channel
            logger.info(f"Found channel from voice state: {channel.name}")
            return channel

        # Fallback to searching all channels
        channel = get_channel_from_user(bot=bot, user=ctx.author)
        
        if channel:
            logger.info(f"Found channel via search: {channel.name}")
            return channel

        logger.warning(f"Unable to find voice channel for {ctx.author}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting voice channel from context: {e}", exc_info=True)
        return None


def get_channel_from_user_id(bot, user_id: int) -> Optional[discord.VoiceChannel]:
    """Find voice channel by user ID"""
    try:
        if not bot or not user_id:
            logger.error("Bot and user_id are required parameters")
            return None
            
        if not isinstance(user_id, int):
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid user_id: {user_id}")
                return None
                
        logger.debug(f"Looking for voice channel for user ID {user_id}")
        
        for guild in bot.guilds:
            try:
                for channel in guild.voice_channels:
                    for member in channel.members:
                        if member.id == user_id:
                            logger.info(f"Found user {user_id} in voice channel {channel.name} ({guild.name})")
                            return channel
            except Exception as e:
                logger.warning(f"Error checking guild {guild.name}: {e}")
                continue

        logger.info(f"User {user_id} not found in any voice channel")
        return None
        
    except Exception as e:
        logger.error(f"Error finding voice channel for user ID {user_id}: {e}", exc_info=True)
        return None

def split_text_into_chunks(text: str, size: int = 2000) -> List[str]:
    """Split text into chunks that fit Discord message limits"""
    try:
        if not text:
            logger.debug("Empty text provided to split_text_into_chunks")
            return []
            
        if not isinstance(text, str):
            logger.warning(f"Converting non-string input to string: {type(text)}")
            text = str(text)
            
        if size <= 0:
            logger.error(f"Invalid chunk size: {size}")
            size = 2000
        elif size > MSG_CHAR_LIMIT:
            logger.warning(f"Chunk size {size} exceeds Discord limit, using {MSG_CHAR_LIMIT}")
            size = MSG_CHAR_LIMIT

        logger.debug(f"Splitting text of {len(text)} chars into chunks of max {size} chars")
        
        words = text.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            # Check if adding this word would exceed the limit
            test_chunk = current_chunk + (" " if current_chunk else "") + word
            
            if len(test_chunk) > size:
                # If current chunk is not empty, save it
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # If single word is too long, split it
                if len(word) > size:
                    logger.warning(f"Word too long ({len(word)} chars), splitting: {word[:50]}...")
                    # Split long word into chunks
                    for i in range(0, len(word), size):
                        word_chunk = word[i:i+size]
                        chunks.append(word_chunk)
                else:
                    current_chunk = word
            else:
                current_chunk = test_chunk
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Filter out empty chunks
        chunks = [chunk for chunk in chunks if chunk.strip()]
        
        logger.debug(f"Split text into {len(chunks)} chunks")
        return chunks
        
    except Exception as e:
        logger.error(f"Error splitting text into chunks: {e}", exc_info=True)
        # Return original text as single chunk as fallback
        return [text[:size]] if text else []