import logging
from discord.ext.commands import Bot, CommandError, CommandNotFound, MissingRequiredArgument, UserNotFound
from discord.utils import get
from discord.channel import DMChannel
import discord

from bot.voice import Voice
#from bot.ws_server import WSServer
from utils.users import BotUser

logger = logging.getLogger('discord.bot_client')

class BotClient(Bot):
    def __init__(self, user_manager, intents, command_prefix='!'):
        super().__init__(command_prefix=command_prefix, intents=intents)

        self.voice = Voice(self)
        self.user_manager = user_manager
        #self.ws_server = WSServer(self)
        logger.info(f"Bot client initialized with prefix: {command_prefix}")

    async def on_ready(self):
        try:
            logger.info(f"Bot is ready! Logged in as {self.user} (ID: {self.user.id})")
            logger.info(f"Connected to {len(self.guilds)} guilds")
            
            logger.info('Scanning for new users...')
            total_new_users = 0

            for g in self.guilds:
                try:
                    await g.chunk()
                    logger.info(f"Processing guild: {g.name} ({g.id}) with {g.member_count} members")

                    new_users = []
                    for m in g.members:
                        if self.user.id == m.id:
                            continue

                        user = self.user_manager.get_user(m.id)

                        if user:
                            user.user_name = m.name
                        else:
                            new_users.append(BotUser(
                                user_id=m.id,
                                user_name=m.name
                            ))

                    if new_users:
                        self.user_manager.add_users(new_users)
                        total_new_users += len(new_users)
                        logger.info(f"Added {len(new_users)} new users from guild {g.name}")
                        
                except Exception as e:
                    logger.error(f"Error processing guild {g.name}: {e}", exc_info=True)

            logger.info(f"User scan complete. Added {total_new_users} new users total")

            # print('Starting websocket server...')
            # self.ws_server.start(event_loop=self.loop)

            logger.info('Jeff bot is loaded and ready to go!')
            
        except Exception as e:
            logger.error(f"Error in on_ready: {e}", exc_info=True)

    async def on_message(self, message):
        try:
            if message.author == self.user:
                return  
            
            # Log command usage (but not all messages to avoid spam)
            if message.content.startswith(self.command_prefix):
                logger.info(f"Command from {message.author} in #{message.channel}: {message.content}")
            
            await super().process_commands(message)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def on_member_join(self, member):
        try:
            logger.info(f"New member joined {member.guild.name}: {member} (ID: {member.id})")
            self.user_manager.add_user(member.id, member.name, member.nick)
        except Exception as e:
            logger.error(f"Error handling member join for {member}: {e}", exc_info=True)

    async def on_member_remove(self, member):
        try:
            logger.info(f"Member left {member.guild.name}: {member} (ID: {member.id})")
        except Exception as e:
            logger.error(f"Error handling member remove for {member}: {e}", exc_info=True)

    async def on_command_error(self, ctx, error):
        """Global error handler for all commands"""
        try:
            # Ignore command not found errors to avoid spam
            if isinstance(error, CommandNotFound):
                return

            # Handle specific common errors
            if isinstance(error, MissingRequiredArgument):
                await ctx.send(f"❌ Missing required argument: `{error.param.name}`. Use `!help {ctx.command}` for usage info.")
                logger.warning(f"Missing argument in command {ctx.command} from {ctx.author}: {error.param.name}")
                
            elif isinstance(error, UserNotFound):
                await ctx.send("❌ User not found. Please mention a valid user.")
                logger.warning(f"User not found in command {ctx.command} from {ctx.author}")
                
            elif isinstance(error, discord.Forbidden):
                await ctx.send("❌ I don't have permission to do that!")
                logger.warning(f"Permission denied for command {ctx.command} from {ctx.author}")
                
            elif isinstance(error, discord.HTTPException):
                await ctx.send("❌ Something went wrong with Discord. Please try again.")
                logger.error(f"Discord HTTP error in command {ctx.command}: {error}")
                
            else:
                # Log unexpected errors with full traceback
                logger.error(f"Unexpected error in command {ctx.command} from {ctx.author}: {error}", exc_info=True)
                await ctx.send("❌ An unexpected error occurred. The issue has been logged.")
                
        except Exception as e:
            # If even error handling fails, just log it
            logger.error(f"Error in error handler: {e}", exc_info=True)

    async def on_error(self, event, *args, **kwargs):
        """Global error handler for non-command events"""
        try:
            logger.error(f"Error in event {event}: {args}", exc_info=True)
        except Exception as e:
            # Last resort logging
            print(f"Critical error in error handler: {e}")

    async def on_disconnect(self):
        logger.warning("Bot disconnected from Discord")

    async def on_resumed(self):
        logger.info("Bot connection resumed")