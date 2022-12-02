import os
import discord
import sys

from google_images_search import GoogleImagesSearch
from io import BytesIO
from PIL import Image

from discord.ext import commands

MAX_IMG_COUNT = 5
MAX_IMG_SIZE_MB = 8

class GoogleImages(commands.Cog):
    def __init__(self, bot, api_token, api_cx):
        self.bot = bot
        self.api_token = api_token
        self.api_cx = api_cx


    @commands.command(name='img', help='Search for an image')
    async def img_search(self, ctx, query, count:int=1):
        print(f'Image search request from {ctx.message.author} for {query}')
        await self.bot.loop.create_task(self._search(ctx, query, 'MEDIUM', 'png', count))


    # Turns out a lot of images where being downloaded that wern't images,
    # they were just captcha pages or the site stopping the image scrape.
    # In order to prevent this we query for twice the images that you want
    # and try and replace broken images with the spare ones. The test for a
    # broken image is to try and decode it into a UTF-8 string, if it fails
    # the decoding it is an image and not a website. This can't be checked
    # the other way around because the website bytes can be written to an image.

    async def _search(self, ctx, query, size, file_type, count):
        gis = GoogleImagesSearch(self.api_token, self.api_cx)

        if count > MAX_IMG_COUNT:
            count = MAX_IMG_COUNT

        gis.search({
            'q': query,
            'num': MAX_IMG_COUNT
        })

        bytes_io = BytesIO()
        return_count = 0


        for i, img in enumerate(gis.results()):
            try:
                bytes_io.seek(0)
                raw_image_data = img.get_raw_data()
            except Exception as e:
                print('There was an issue getting the image')
                print(e)
                continue

            try:
                print('Testing image...')
                _ = raw_image_data.decode('utf-8')
                print('Image test failed, ignoring image')
            except:
                img.copy_to(bytes_io, raw_image_data)
                img.copy_to(bytes_io)
                bytes_io.seek(0)

                img_size = sys.getsizeof(bytes_io)

                if img_size < MAX_IMG_SIZE_MB * (4**10):
                    print('Image is valid')
                    await ctx.send(file=discord.File(bytes_io, f'{query}_{i}.{file_type}'))

                    return_count += 1
                    if return_count >= count:
                        break
                else:
                    print(f'Image ({img_size}) is larger than {MAX_IMG_SIZE_MB * (4**10)}')