import logging
from bot.scheduler import ScheduledJob
from utils.jeff_persona import JeffPersona

logger = logging.getLogger('discord.friday_alert')

class FridayAlert(ScheduledJob):
    def __init__(self, bot, jeff_persona: JeffPersona, general_channel_name="general"):
        # Initialize as a scheduled job that runs only on Fridays at 8 AM
        super().__init__(
            cron_expression="0 8 * * 5",  # 8 AM on Fridays only (5 = Friday)
            callback=None,  # We override execute instead
            name="friday_alert"
        )
        
        self.bot = bot
        self.general_channel_name = general_channel_name
        self.jeff_persona = jeff_persona

    async def execute(self):
        """Override ScheduledJob execute to run the friday alert"""
        try:
            logger.info("Executing Friday alert...")
            # Find the general channel by name (same way birthday job does it)
            general_channel = None
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if channel.name.lower() == self.general_channel_name.lower():
                        general_channel = channel
                        break
                if general_channel:
                    break
            
            if general_channel:
                # Generate Jeff's Friday morning comment
                friday_message = await self.jeff_persona.generate_casual_comment(
                    topic="Friday morning",
                    context="It's Friday morning! Generate a casual comment to start some conversation in the chat. Keep it natural and conversational."
                )
                
                if friday_message and friday_message != "Can't be bothered to comment on that":
                    await general_channel.send(friday_message)
                else:
                    # Fallback to simple Friday message
                    await general_channel.send(f"🎉 It's Friday! Weekend's here! 🎉")
                
                logger.info(f"Sent Friday alert to #{general_channel.name}")
            else:
                logger.error(f"Could not find channel named '{self.general_channel_name}'")
        except Exception as e:
            logger.error(f"Error in Friday alert: {str(e)}", exc_info=True)
        finally:
            self._calculate_next_run()