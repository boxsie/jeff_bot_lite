from discord.ext.commands import Bot
from discord.utils import get
from discord.channel import DMChannel

from bot.voice import Voice
#from bot.ws_server import WSServer
from utils.users import BotUser


class BotClient(Bot):
    def __init__(self, user_manager, intents, command_prefix='!'):
        super().__init__(command_prefix=command_prefix, intents=intents)

        self.voice = Voice(self)
        self.user_manager = user_manager
        #self.ws_server = WSServer(self)
        

    async def on_ready(self):
        print('Looking for new users...')

        for g in self.guilds:
            await g.chunk()

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

            self.user_manager.add_users(new_users)

        # print('Starting websocket server...')
        # self.ws_server.start(event_loop=self.loop)

        print('Jeff bot is loaded and ready to go!')


    async def on_message(self, message):
        if message.author == self.user:
            return  
        
        await super().process_commands(message) 


    async def on_member_join(self, member):
        self.user_manager.add_user(member.id, member.name, member.nick)