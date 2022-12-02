import websockets
import json
import nest_asyncio

WS_PORT = 8765

class WSServer(object):
    def __init__(self, bot):
        self.bot = bot
        nest_asyncio.apply()


    def start(self, event_loop):
        start_server = websockets.serve(self.serve, "0.0.0.0", WS_PORT)
        event_loop.run_until_complete(start_server)
        print(f'Websocket server running on port {WS_PORT}')


    async def serve(self, websocket, path):
        while True:
            req = await websocket.recv()
            print(f"Websocket request {req}")
            req_json = json.loads(req)

            if 'action' not in req_json:
                await self.return_err(websocket, None, "The 'action' property is required")
                return

            action = req_json['action']

            if action == 'play' or  action == 'random':
                channel = self.bot.voice_control.get_channel_from_user_id(req_json['user_id'])

                now_playing = await self.bot.voice_control.play(channel, req_json['filename']) \
                    if action == 'play' else \
                        await self.bot.voice_control.play_random(channel)

                await self.return_msg(websocket, 'playing', now_playing)
            elif action == 'stop':
                self.bot.voice_control.stop()
            elif action == 'list':
                await self.return_msg(websocket, action, self.bot.file_manager.list_filenames())


    async def return_msg(self, websocket, action, msg):
        msg = {
            'action': action,
            'msg': msg
        }
        print(msg)
        await websocket.send(json.dumps(msg))


    async def return_err(self, websocket, action, msg):
        err = {
            'action': action,
            'err': str(msg)
        }
        print(err)
        await websocket.send(json.dumps(err))
