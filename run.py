#!/usr/bin/env python3

import os
import argparse
import asyncio
import logging
import logging.handlers
import json
import sys

from bot.client import BotClient
from bot.scheduler import Scheduler
from utils.files import FileRepo
from utils.users import UserManager
from utils.config import Config
from utils.birthday_service import BirthdayService
from utils.ollama_client import OllamaClient
from utils.jeff_persona import JeffPersona
from cogs.sound_board import SoundBoard
from cogs.entrances import Entrances
from cogs.google_img import GoogleImages
from cogs.birthdays import Birthdays
from cogs.chat_ollama import ChatOllama
from cogs.conversation_ai import ConversationAI
from cogs.ollama_manager import OllamaManager
from jobs.birthday_checker import BirthdayChecker
from jobs.friday_alert import FridayAlert
from commands.commands import friday, tuesday, xmas, jobs
from discord import Intents


CONFIG_PATH = os.environ.get('CONFIG_PATH')
SECRETS_PATH = os.environ.get('SECRETS_PATH')
GOOGLE_CREDS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

async def main():
    # Setup logging first
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)

    try:
        # File handler for persistent logging
        file_handler = logging.handlers.RotatingFileHandler(
            filename='discord.log',
            encoding='utf-8',
            maxBytes=32 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        
        # Console handler for real-time output
        console_handler = logging.StreamHandler()
        
        # Same formatter for both handlers
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logger.info("Logging system initialized successfully")
    except Exception as e:
        print(f"Failed to setup logging: {e}")
        sys.exit(1)

    # Validate required environment variables
    required_env_vars = {'CONFIG_PATH': CONFIG_PATH, 'SECRETS_PATH': SECRETS_PATH, 'GOOGLE_APPLICATION_CREDENTIALS': GOOGLE_CREDS}
    missing_vars = [var for var, value in required_env_vars.items() if not value]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    # Load secrets
    try:
        logger.info(f"Loading secrets from {SECRETS_PATH}")
        with open(SECRETS_PATH) as secrets_file:
            secrets = json.load(secrets_file)
        logger.info("Secrets loaded successfully")
    except FileNotFoundError:
        logger.error(f"Secrets file not found: {SECRETS_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in secrets file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading secrets: {e}")
        sys.exit(1)

    # Validate required secrets
    required_secrets = ['discord_token', 'openwebui_url', 'bucket_path', 'openwebui_api_key']
    missing_secrets = [secret for secret in required_secrets if not secrets.get(secret)]
    
    if missing_secrets:
        logger.error(f"Missing required secrets: {', '.join(missing_secrets)}")
        sys.exit(1)

    # Check for optional GCS secrets
    gcs_secrets = ['project_id', 'bucket_sub_name']
    missing_gcs = [secret for secret in gcs_secrets if not secrets.get(secret)]
    if missing_gcs:
        logger.warning(f"Missing optional GCS secrets (some features may not work): {', '.join(missing_gcs)}")

    args = {
        'discord_token': secrets.get('discord_token'),
        'gimg_api_cx': secrets.get('gimg_api_cx'),
        'gimg_api_token': secrets.get('gimg_api_token'),
        'project_id': secrets.get('project_id'),
        'bucket_sub_name': secrets.get('bucket_sub_name'),
        'bucket_path': secrets.get('bucket_path'),
        'openwebui_url': secrets.get('openwebui_url'),
        'openwebui_api_key': secrets.get('openwebui_api_key')
    }
    logger.info("Configuration arguments processed successfully")
    
    # Load configuration
    try:
        logger.info(f"Loading configuration from {CONFIG_PATH}")
        with open(CONFIG_PATH) as config_file:
            config = Config(
                config=json.load(config_file),
                base_bucket=secrets.get('bucket_path')
            )
        logger.info("Configuration loaded successfully")
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {CONFIG_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)
    
    # Initialize file repositories
    try:
        logger.info("Initializing file repositories...")
        sound_files = FileRepo(
            base_path=config.get_local_path('sounds'),
            bucket_path=config.get_bucket_path('sounds'),
            service_account_json=GOOGLE_CREDS,
            project_id=args['project_id'],
            bucket_sub_name=args['bucket_sub_name']
        )

        resource_files = FileRepo(
            base_path=config.get_local_path('resources'),
            bucket_path=config.get_bucket_path('resources'),
            service_account_json=GOOGLE_CREDS,
            project_id=args['project_id'],
            bucket_sub_name=args['bucket_sub_name']
        )

        user_manager = UserManager(
            user_repo=FileRepo(
                base_path=config.get_local_path('users'),
                bucket_path=config.get_bucket_path('users'),
                service_account_json=GOOGLE_CREDS,
                project_id=args['project_id'],
                bucket_sub_name=args['bucket_sub_name'],
                overwrite=True
            )
        )
        
        # Create memory repository for conversation AI
        memory_repo = FileRepo(
            base_path=config.get_local_path('memory'),
            bucket_path=config.get_bucket_path('memory'),
            service_account_json=GOOGLE_CREDS,
            project_id=args['project_id'],
            bucket_sub_name=args['bucket_sub_name']
        )
        
        logger.info("File repositories initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize file repositories: {e}", exc_info=True)
        sys.exit(1)
    
    # Initialize bot and services
    try:
        logger.info("Initializing bot and services...")
        intents = Intents.all()

        bot = BotClient(
            user_manager=user_manager,
            intents=intents
        )

        # Initialize Open WebUI client
        ollama_client = OllamaClient(
            base_url=args['openwebui_url'],
            api_key=args['openwebui_api_key'],
            default_model="gpt-4.1"
        )

        # Initialize Jeff's persona
        jeff_persona = JeffPersona(ollama_client)

        birthday_service = BirthdayService(user_manager)
        scheduler = Scheduler(bot)
                
        # Attach scheduler and ws_server to bot for command access
        bot.scheduler = scheduler
        
        logger.info("Bot and services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize bot and services: {e}", exc_info=True)
        sys.exit(1)

    # Start bot
    try:
        async with bot:
            logger.info("Starting bot and loading cogs...")
            
            # Add cogs with individual error handling
            cog_configs = [
                ('SoundBoard', SoundBoard, {'bot': bot, 'sound_files': sound_files}),
                ('Entrances', Entrances, {'bot': bot, 'user_manager': user_manager, 'sound_files': sound_files}),
                ('GoogleImages', GoogleImages, {'bot': bot, 'api_token': args['gimg_api_token'], 'api_cx': args['gimg_api_cx']}),
                ('Birthdays', Birthdays, {'bot': bot, 'birthday_service': birthday_service, 'jeff_persona': jeff_persona}),
                ('ChatOllama', ChatOllama, {'bot': bot, 'ollama_client': ollama_client}),
                ('ConversationAI', ConversationAI, {'bot': bot, 'ollama_client': ollama_client, 'memory_repo': memory_repo}),
                ('OllamaManager', OllamaManager, {'bot': bot, 'ollama_client': ollama_client})
            ]
            
            for cog_name, cog_class, cog_kwargs in cog_configs:
                try:
                    await bot.add_cog(cog_class(**cog_kwargs))
                    logger.info(f"Loaded cog: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog_name}: {e}", exc_info=True)
                    # Continue loading other cogs even if one fails

            # Add commands
            commands_to_add = [friday, tuesday, xmas, jobs]
            for command in commands_to_add:
                try:
                    bot.add_command(command)
                    logger.info(f"Added command: {command.name}")
                except Exception as e:
                    logger.error(f"Failed to add command {command.name}: {e}", exc_info=True)
                   
            # Schedule birthday check job
            birthday_checker = BirthdayChecker(
                bot=bot,
                birthday_service=birthday_service,
                jeff_persona=jeff_persona
            )
            scheduler.jobs.append(birthday_checker)
            logger.info("Birthday checker added to scheduler")
            
            # Schedule friday alert job
            friday_alert = FridayAlert(
                bot=bot,
                jeff_persona=jeff_persona
            )
            scheduler.jobs.append(friday_alert)
            logger.info("Friday alert added to scheduler")

            # Start the scheduler
            try:
                scheduler.start()
                logger.info("Scheduler started successfully")
            except Exception as e:
                logger.error(f"Failed to start scheduler: {e}", exc_info=True)            
            
            logger.info("Starting Discord bot...")
            await bot.start(args['discord_token'])
            
    except Exception as e:
        logger.error(f"Bot startup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger = logging.getLogger('discord')
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger = logging.getLogger('discord')
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
