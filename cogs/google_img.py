import os
import discord
import sys
import logging
import asyncio
from typing import Optional

from google_images_search import GoogleImagesSearch
from io import BytesIO
from PIL import Image

from discord.ext import commands

logger = logging.getLogger('discord.google_img')

MAX_IMG_COUNT = 5
MAX_IMG_SIZE_MB = 8

class GoogleImages(commands.Cog):
    def __init__(self, bot, api_token, api_cx):
        self.bot = bot
        self.api_token = api_token
        self.api_cx = api_cx
        self.gis = None
        
        # Validate API credentials
        if not api_token or not api_cx:
            logger.error("Google Images API credentials are missing")
            self.api_available = False
        else:
            try:
                self.gis = GoogleImagesSearch(api_token, api_cx)
                self.api_available = True
                logger.info("Google Images API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Google Images API: {e}")
                self.api_available = False

    @commands.command(name='img', help='Search for an image - optionally add a number at the end for count (e.g., !img cute cats 3)')
    async def img_search(self, ctx, *args):
        """Search for images using Google Images API"""
        try:
            # Validate API availability
            if not self.api_available:
                await ctx.send("❌ Google Images search is currently unavailable. API credentials may be missing or invalid.")
                return
            
            # Parse arguments to extract query and optional count
            if not args:
                await ctx.send("❌ Please provide a search term! Example: `!img cute cats` or `!img cute cats 3`")
                return
            
            # Check if the last argument is a number (count)
            count = 1  # default
            query_parts = list(args)
            
            if len(args) > 1:
                try:
                    # Try to parse the last argument as count
                    potential_count = int(args[-1])
                    if 1 <= potential_count <= MAX_IMG_COUNT:
                        count = potential_count
                        query_parts = args[:-1]  # Remove count from query
                    elif potential_count > MAX_IMG_COUNT:
                        count = MAX_IMG_COUNT
                        query_parts = args[:-1]  # Remove count from query
                        await ctx.send(f"⚠️ Maximum {MAX_IMG_COUNT} images allowed. Setting count to {MAX_IMG_COUNT}.")
                    elif potential_count < 1:
                        await ctx.send("❌ Count must be at least 1!")
                        return
                except ValueError:
                    # Last argument is not a number, treat it as part of the query
                    pass
            
            # Join the remaining parts as the query
            query = ' '.join(query_parts).strip()
            
            if not query:
                await ctx.send("❌ Please provide a search term! Example: `!img cute cats` or `!img cute cats 3`")
                return
            
            logger.info(f'Image search request from {ctx.author} for "{query}" (count: {count})')
                        
            # Send typing indicator
            async with ctx.typing():
                await self._search(ctx, query, count)
                
        except Exception as e:
            logger.error(f"Error in img_search command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while searching for images. Please try again.")

    async def _search(self, ctx, query: str, count: int):
        """Perform the actual image search and send results"""
        try:
            if not self.gis:
                logger.error("Google Images API not initialized")
                await ctx.send("❌ Google Images API is not available.")
                return
            
            logger.info(f"Starting image search for: {query}")
            
            # Perform search with error handling
            try:
                # Search for more images than requested to have fallbacks
                search_count = min(count * 2, 10)  # Search for double but cap at 10
                
                self.gis.search({
            'q': query,
                    'num': search_count,
                    'safe': 'active',  # Enable safe search
                    'fileType': 'jpg|png|gif',  # Limit to common image formats
                    'imgType': 'photo',  # Prefer photos over clipart
        })

                results = list(self.gis.results())
                logger.info(f"Found {len(results)} search results for '{query}'")

            except Exception as e:
                logger.error(f"Google Images API search failed: {e}")
                if "quota" in str(e).lower() or "limit" in str(e).lower():
                    await ctx.send("❌ Google Images API quota exceeded. Please try again later.")
                elif "key" in str(e).lower() or "invalid" in str(e).lower():
                    await ctx.send("❌ Google Images API key is invalid or expired.")
                else:
                    await ctx.send("❌ Failed to search for images. Please try again.")
                return
            
            if not results:
                await ctx.send(f"😕 No images found for '{query}'. Try a different search term.")
                return
            
            # Process and send images
            sent_count = 0
            processed_count = 0
            
            for i, img in enumerate(results):
                if sent_count >= count:
                    break
                    
                processed_count += 1
                logger.debug(f"Processing image {processed_count}/{len(results)} for '{query}'")
                
                try:
                    # Download image with timeout
                    image_data = await self._download_image_safely(img)
                    if not image_data:
                        continue
                    
                    # Validate image
                    if not self._validate_image(image_data, query):
                        continue
                    
                    # Send image
                    if await self._send_image(ctx, image_data, query, i):
                        sent_count += 1
                        logger.info(f"Successfully sent image {sent_count}/{count} for '{query}'")
                    
                except Exception as e:
                    logger.warning(f"Error processing image {i} for '{query}': {e}")
                continue

            if sent_count == 0:
                await ctx.send(f"😕 Couldn't find any valid images for '{query}'. Try a different search term.")
            elif sent_count < count:
                await ctx.send(f"⚠️ Only found {sent_count} valid images (requested {count}) for '{query}'.")
                
            logger.info(f"Completed image search for '{query}': sent {sent_count}/{count} images")
            
        except Exception as e:
            logger.error(f"Error in image search for '{query}': {e}", exc_info=True)
            await ctx.send("❌ An error occurred while processing the image search.")

    async def _download_image_safely(self, img) -> Optional[bytes]:
        """Download image data with proper error handling and timeout"""
        try:
            # Set a reasonable timeout for image download
            loop = asyncio.get_event_loop()
            
            def download_image():
                try:
                    return img.get_raw_data()
                except Exception as e:
                    logger.warning(f"Error downloading image: {e}")
                    return None
            
            # Run download in thread pool with timeout
            raw_data = await asyncio.wait_for(
                loop.run_in_executor(None, download_image),
                timeout=10.0  # 10 second timeout
            )
            
            if not raw_data:
                logger.warning("No data received from image download")
                return None
                
            logger.debug(f"Downloaded image data: {len(raw_data)} bytes")
            return raw_data
            
        except asyncio.TimeoutError:
            logger.warning("Image download timed out")
            return None
        except Exception as e:
            logger.warning(f"Error downloading image: {e}")
            return None

    def _validate_image(self, image_data: bytes, query: str) -> bool:
        """Validate that the downloaded data is actually an image"""
        try:
            # Check if data is too small to be a real image
            if len(image_data) < 1024:  # Less than 1KB is suspicious
                logger.debug("Image data too small, likely not a real image")
                return False
            
            # Check if data is too large
            max_size_bytes = MAX_IMG_SIZE_MB * 1024 * 1024  # Convert MB to bytes
            if len(image_data) > max_size_bytes:
                logger.warning(f"Image too large: {len(image_data)} bytes (max: {max_size_bytes})")
                return False
            
            # Try to validate as image using PIL
            try:
                with BytesIO(image_data) as img_io:
                    with Image.open(img_io) as img:
                        # Verify it's a valid image
                        img.verify()
                        logger.debug(f"Image validation successful: {img.format} {img.size}")
                        return True
            except Exception as e:
                logger.debug(f"PIL image validation failed: {e}")
                
            # Fallback: Check for image file signatures
            if self._has_image_signature(image_data):
                logger.debug("Image validated by file signature")
                return True
            
            logger.debug("Image validation failed - not a valid image")
            return False
            
        except Exception as e:
            logger.warning(f"Error validating image: {e}")
            return False

    def _has_image_signature(self, data: bytes) -> bool:
        """Check if data starts with known image file signatures"""
        try:
            if len(data) < 8:
                return False
                
            # Common image file signatures
            signatures = [
                b'\xFF\xD8\xFF',  # JPEG
                b'\x89PNG\r\n\x1a\n',  # PNG
                b'GIF87a',  # GIF87a
                b'GIF89a',  # GIF89a
                b'RIFF',  # WEBP (also checks for WEBP signature later)
                b'\x00\x00\x01\x00',  # ICO
                b'BM',  # BMP
            ]
            
            for sig in signatures:
                if data.startswith(sig):
                    return True
                    
            # Special case for WEBP
            if data.startswith(b'RIFF') and b'WEBP' in data[:12]:
                return True
                
            return False
            
        except Exception as e:
            logger.warning(f"Error checking image signature: {e}")
            return False

    async def _send_image(self, ctx, image_data: bytes, query: str, index: int) -> bool:
        """Send image to Discord channel with error handling"""
        try:
            # Determine file extension from image data
            file_ext = self._get_file_extension(image_data)
            filename = f"{query}_{index}.{file_ext}"
            
            # Create BytesIO object for Discord
            with BytesIO(image_data) as image_io:
                image_io.seek(0)
                
                # Create Discord file
                discord_file = discord.File(image_io, filename=filename)
                
                # Send with error handling
                try:
                    await ctx.send(file=discord_file)
                    return True
                except discord.HTTPException as e:
                    if e.status == 413:  # Payload too large
                        logger.warning(f"Image too large for Discord: {filename}")
                        await ctx.send(f"⚠️ Image '{filename}' is too large for Discord.")
                    else:
                        logger.error(f"Discord error sending image: {e}")
                        await ctx.send(f"❌ Failed to send image '{filename}'.")
                    return False
                except Exception as e:
                    logger.error(f"Unexpected error sending image: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error preparing image for sending: {e}")
            return False

    def _get_file_extension(self, image_data: bytes) -> str:
        """Determine file extension from image data"""
        try:
            if image_data.startswith(b'\xFF\xD8\xFF'):
                return 'jpg'
            elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                return 'png'
            elif image_data.startswith((b'GIF87a', b'GIF89a')):
                return 'gif'
            elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
                return 'webp'
            elif image_data.startswith(b'BM'):
                return 'bmp'
            else:
                return 'jpg'  # Default fallback
        except Exception:
            return 'jpg'  # Fallback on error

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle errors specific to this cog"""
        if ctx.command and ctx.command.name == 'img':
            if isinstance(error, commands.MissingRequiredArgument):
                await ctx.send("❌ Please provide a search term! Example: `!img cute cats` or `!img cute cats 3`")
            elif isinstance(error, commands.BadArgument):
                await ctx.send("❌ Invalid count parameter. Please provide a number between 1 and 5.")
            else:
                logger.error(f"Unhandled error in google_img cog: {error}", exc_info=True)