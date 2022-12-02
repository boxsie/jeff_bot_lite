import sys

from io import BytesIO
from PIL import Image

MSG_CHAR_LIMIT = 2000
MAX_IMG_SIZE_MB = 8


async def send_text_list_to_author(ctx, strings):
    ret = '```'

    for s in sorted(strings):
        if (len(ret) + len(s) >= MSG_CHAR_LIMIT - 6):
            r = ret
            r = f'{r}```'
            await ctx.author.send(r)
            ret = '```'
        else:
            ret = f'{ret}\n{s}'

    ret = f'{ret}```'
    await ctx.author.send(ret)


def create_img_bytes(img):
    bytes_io = BytesIO()

    try:
        bytes_io.seek(0)
        raw_image_data = img.get_raw_data()
    except:
        print('There was an issue getting the image')
        return None

    try:
        print('Testing image...')
        _ = raw_image_data.decode('utf-8')
        print('Image test failed, this is not an image')
        return None
    except:
        img.copy_to(bytes_io, raw_image_data)
        img.copy_to(bytes_io)
        bytes_io.seek(0)

        img_size = sys.getsizeof(bytes_io)

        if img_size < MAX_IMG_SIZE_MB * (4**10):
            print('Image is valid')
            return bytes_io
        else:
            print(f'Image ({img_size}) is larger than {MAX_IMG_SIZE_MB * (4**10)}')
            return None


def get_channel_from_user(bot, user):
    for g in bot.guilds:
        for c in g.voice_channels:
            for m in c.members:
                if m.id == user.id:
                    return c

    raise Exception(f'User {user.name} is not in a voice channel')


def get_channel_from_ctx(bot, ctx):
    if hasattr(ctx.message.author, 'voice') and hasattr(ctx.message.author.voice, 'channel'):
        return ctx.message.author.voice.channel

    channel = get_channel_from_user(bot=bot, user=ctx.message.author)

    if channel:
        return channel

    raise Exception(f'Unable to get voice channel from ctx {ctx.message}')


def get_channel_from_user_id(bot, user_id):
    for g in bot.guilds:
        for c in g.voice_channels:
            for m in c.members:
                if m.id == int(user_id):
                    return c

    raise Exception(f'User {user_id} is not in a voice channel')