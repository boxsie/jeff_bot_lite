#!/usr/bin/env python3

import os
import argparse
import asyncio
import logging
import logging.handlers
import json

from bot.client import BotClient
from utils.files import FileRepo
from utils.users import UserManager
from utils.config import Config
from cogs.sound_board import SoundBoard
from cogs.entrances import Entrances
from cogs.google_img import GoogleImages
from commands.fun import friday, xmas
from discord import Intents

CONFIG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')

def _load_json_config(bucket_path):
    with open(CONFIG_FILE) as json_file:
        return Config(
            cfg_json=json.load(json_file),
            base_bucket=bucket_path
        )


async def main():
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        filename='discord.log',
        encoding='utf-8',
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    args = {
        'discord_token': os.environ.get('discord_token'),
        'gimg_api_cx': os.environ.get('gimg_api_cx'),
        'gimg_api_token': os.environ.get('gimg_api_token'),
        'project_id': os.environ.get('project_id'),
        'bucket_sub_name': os.environ.get('bucket_sub_name'),
        'bucket_path': os.environ.get('bucket_path')
    }
    print(f'Arguments processed: {args}')
    
    config = _load_json_config(
        bucket_path=args['bucket_path']
    )
    
    sound_files = FileRepo(
        base_path=config.paths['sounds'],
        bucket_path=config.get_bucket_path('sounds'),
        project_id=args['project_id'],
        bucket_sub_name=args['bucket_sub_name']
    )

    resource_files = FileRepo(
        base_path=config.paths['resources'],
        bucket_path=config.get_bucket_path('resources'),
        project_id=args['project_id'],
        bucket_sub_name=args['bucket_sub_name']
    )

    user_manager = UserManager(
        user_repo=FileRepo(
            base_path=config.paths['users'],
            bucket_path=config.get_bucket_path('users'),
            project_id=args['project_id'],
            bucket_sub_name=args['bucket_sub_name'],
            overwrite=True
        )
    )
    
    intents = Intents.all()

    bot = BotClient(
        user_manager=user_manager,
        intents=intents
    )

    async with bot:
        await bot.add_cog(SoundBoard(
            bot=bot,
            sound_files=sound_files
        ))

        await bot.add_cog(Entrances(
            bot=bot,
            user_manager=user_manager,
            sound_files=sound_files
        ))

        await bot.add_cog(GoogleImages(
            bot=bot,
            api_token=args['gimg_api_token'],
            api_cx=args['gimg_api_cx']
        ))

        bot.add_command(friday)
        bot.add_command(xmas)
        
        await bot.start(args['discord_token'])


asyncio.run(main())