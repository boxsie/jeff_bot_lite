import asyncio
import json
import logging
import time
import jwt
from typing import Dict, Set, Optional, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger('discord.ws_server')

WS_PORT = 8765
JWT_SECRET = "your-secret-key"  # Should be loaded from config in production
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

class WSServer:
    """Modern WebSocket server for triggering bot functionality remotely"""
    
    def __init__(self, bot, sound_files):
        self.bot = bot
        self.sound_files = sound_files
        self.active_connections: Set[websockets.WebSocketServerProtocol] = set()
        self.connection_info: Dict[websockets.WebSocketServerProtocol, Dict[str, Any]] = {}
        self.is_running = False
        logger.info("WebSocket server initialized")

    async def start_server(self):
        """Start the WebSocket server"""
        try:
            self.is_running = True
            logger.info(f"Starting WebSocket server on port {WS_PORT}")
            
            async with websockets.serve(
                self.handle_connection,
                "0.0.0.0", 
                WS_PORT,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ):
                logger.info(f"WebSocket server running on ws://0.0.0.0:{WS_PORT}")
                # Keep the server running
                await asyncio.Future()  # Run forever
                
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}", exc_info=True)
            self.is_running = False
            raise

    async def stop_server(self):
        """Stop the WebSocket server and close all connections"""
        try:
            self.is_running = False
            logger.info("Stopping WebSocket server...")
            
            # Close all active connections
            if self.active_connections:
                await asyncio.gather(
                    *[self._close_connection(ws) for ws in self.active_connections.copy()],
                    return_exceptions=True
                )
            
            logger.info("WebSocket server stopped")
        except Exception as e:
            logger.error(f"Error stopping WebSocket server: {e}", exc_info=True)

    async def handle_connection(self, websocket, path):
        """Handle new WebSocket connections"""
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"New WebSocket connection from {client_info}")
        
        try:
            # Add to active connections
            self.active_connections.add(websocket)
            self.connection_info[websocket] = {
                'connected_at': time.time(),
                'client_info': client_info,
                'authenticated': False,
                'user_id': None
            }
            
            # Send welcome message
            await self._send_message(websocket, {
                'action': 'welcome',
                'message': 'Connected to Jeff Bot WebSocket server',
                'timestamp': time.time()
            })
            
            # Handle messages
            async for message in websocket:
                try:
                    await self._handle_message(websocket, message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from {client_info}: {e}")
                    await self._send_error(websocket, 'invalid_json', 'Invalid JSON format')
                except Exception as e:
                    logger.error(f"Error handling message from {client_info}: {e}", exc_info=True)
                    await self._send_error(websocket, 'internal_error', 'Internal server error')
                    
        except ConnectionClosed:
            logger.info(f"WebSocket connection closed: {client_info}")
        except WebSocketException as e:
            logger.warning(f"WebSocket error for {client_info}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for connection {client_info}: {e}", exc_info=True)
        finally:
            await self._cleanup_connection(websocket)

    async def _handle_message(self, websocket, raw_message: str):
        """Handle incoming WebSocket messages"""
        try:
            message = json.loads(raw_message)
            client_info = self.connection_info[websocket]['client_info']
            
            logger.debug(f"Received message from {client_info}: {message.get('action', 'unknown')}")
            
            # Validate message structure
            if not isinstance(message, dict):
                await self._send_error(websocket, 'invalid_format', 'Message must be a JSON object')
                return
                
            if 'action' not in message:
                await self._send_error(websocket, 'missing_action', 'Message must include an "action" field')
                return

            action = message['action']
            
            # Handle authentication
            if action == 'authenticate':
                await self._handle_auth(websocket, message)
                return
            
            # Check if authenticated for protected actions
            if not self.connection_info[websocket]['authenticated']:
                await self._send_error(websocket, 'not_authenticated', 'Authentication required')
                return
            
            # Handle authenticated actions
            await self._handle_authenticated_action(websocket, action, message)
            
        except Exception as e:
            logger.error(f"Error in _handle_message: {e}", exc_info=True)
            await self._send_error(websocket, 'internal_error', 'Failed to process message')

    async def _handle_auth(self, websocket, message: Dict[str, Any]):
        """Handle authentication requests"""
        try:
            token = message.get('token')
            if not token:
                await self._send_error(websocket, 'auth_failed', 'Token required')
                return
            
            user_id = None
            
            # Try JWT token first (production)
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                user_id = payload.get('user_id')
                
                if not user_id:
                    await self._send_error(websocket, 'auth_failed', 'Invalid token payload')
                    return
                    
                logger.info(f"User {user_id} authenticated via JWT token")
                
            except jwt.ExpiredSignatureError:
                await self._send_error(websocket, 'auth_failed', 'Token expired')
                return
            except jwt.InvalidTokenError:
                # Try fallback authentication (for Discord activity)
                try:
                    import base64
                    import json
                    
                    # Check for fallback token format
                    if token == 'fallback-token':
                        # Allow fallback for testing
                        user_id = 'fallback-user'
                        logger.info("User authenticated with fallback token")
                    else:
                        # Try to decode base64 token from Discord activity
                        decoded = base64.b64decode(token).decode('utf-8')
                        payload = json.loads(decoded)
                        user_id = payload.get('user_id')
                        
                        if not user_id:
                            await self._send_error(websocket, 'auth_failed', 'Invalid token payload')
                            return
                            
                        # Check expiration if present
                        exp = payload.get('exp')
                        if exp and time.time() > exp:
                            await self._send_error(websocket, 'auth_failed', 'Token expired')
                            return
                            
                        logger.info(f"User {user_id} authenticated via Discord activity token")
                        
                except Exception as e:
                    logger.warning(f"Failed to parse token: {e}")
                    await self._send_error(websocket, 'auth_failed', 'Invalid token format')
                    return
            
            # Update connection info
            self.connection_info[websocket]['authenticated'] = True
            self.connection_info[websocket]['user_id'] = user_id
            
            await self._send_message(websocket, {
                'action': 'auth_success',
                'message': 'Authentication successful',
                'user_id': user_id
            })
            
            logger.info(f"User {user_id} authenticated via WebSocket")
            
        except Exception as e:
            logger.error(f"Error in authentication: {e}", exc_info=True)
            await self._send_error(websocket, 'auth_error', 'Authentication error')

    async def _handle_authenticated_action(self, websocket, action: str, message: Dict[str, Any]):
        """Handle authenticated actions"""
        try:
            user_id = self.connection_info[websocket]['user_id']
            
            if action == 'list':
                await self._handle_list_sounds(websocket)
            elif action == 'play':
                await self._handle_play_sound(websocket, message, user_id)
            elif action == 'random':
                await self._handle_random_sound(websocket, user_id)
            elif action == 'stop':
                await self._handle_stop_sound(websocket)
            elif action == 'status':
                await self._handle_status(websocket)
            elif action == 'ping':
                # Handle ping/heartbeat
                await self._send_message(websocket, {'action': 'pong'})
            else:
                await self._send_error(websocket, 'unknown_action', f'Unknown action: {action}')
                
        except Exception as e:
            logger.error(f"Error handling action {action}: {e}", exc_info=True)
            await self._send_error(websocket, 'action_error', f'Failed to execute action: {action}')

    async def _handle_list_sounds(self, websocket):
        """Handle list sounds request"""
        try:
            files = self.sound_files.list_files()
            sound_list = [{'name': f.name, 'path': f.path} for f in files]
            
            await self._send_message(websocket, {
                'action': 'list',
                'sounds': sound_list,
                'count': len(sound_list)
            })
            
            logger.debug(f"Sent sound list with {len(sound_list)} items")
            
        except Exception as e:
            logger.error(f"Error listing sounds: {e}", exc_info=True)
            await self._send_error(websocket, 'list_error', 'Failed to list sounds')

    async def _handle_play_sound(self, websocket, message: Dict[str, Any], user_id: str):
        """Handle play sound request"""
        try:
            filename = message.get('filename')
            if not filename:
                await self._send_error(websocket, 'missing_filename', 'Filename is required')
                return
            
            # Find the sound file
            sound_file = self.sound_files.find(filename)
            if not sound_file:
                await self._send_error(websocket, 'sound_not_found', f'Sound "{filename}" not found')
                return
            
            # Get user's voice channel
            channel = await self._get_user_voice_channel(user_id)
            if not channel:
                await self._send_error(websocket, 'no_voice_channel', 'User must be in a voice channel')
                return
            
            # Play the sound
            await self.bot.voice.play(
                channel=channel,
                source=sound_file.path,
                title=sound_file.name
            )
            
            await self._send_message(websocket, {
                'action': 'playing',
                'filename': filename,
                'title': sound_file.name,
                'channel': channel.name
            })
            
            logger.info(f"Playing sound '{filename}' for user {user_id} in channel {channel.name}")
            
        except Exception as e:
            logger.error(f"Error playing sound: {e}", exc_info=True)
            await self._send_error(websocket, 'play_error', 'Failed to play sound')

    async def _handle_random_sound(self, websocket, user_id: str):
        """Handle random sound request"""
        try:
            # Get a random sound file
            sound_file = self.sound_files.random()
            if not sound_file:
                await self._send_error(websocket, 'no_sounds', 'No sounds available')
                return
            
            # Get user's voice channel
            channel = await self._get_user_voice_channel(user_id)
            if not channel:
                await self._send_error(websocket, 'no_voice_channel', 'User must be in a voice channel')
                return
            
            # Play the random sound
            await self.bot.voice.play(
                channel=channel,
                source=sound_file.path,
                title=sound_file.name
            )
            
            await self._send_message(websocket, {
                'action': 'playing',
                'filename': sound_file.name,
                'title': sound_file.name,
                'channel': channel.name,
                'random': True
            })
            
            logger.info(f"Playing random sound '{sound_file.name}' for user {user_id} in channel {channel.name}")
            
        except Exception as e:
            logger.error(f"Error playing random sound: {e}", exc_info=True)
            await self._send_error(websocket, 'random_error', 'Failed to play random sound')

    async def _handle_stop_sound(self, websocket):
        """Handle stop sound request"""
        try:
            await self.bot.voice.stop()
            
            await self._send_message(websocket, {
                'action': 'stopped',
                'message': 'Audio playback stopped'
            })
            
            logger.info("Audio playback stopped via WebSocket")
            
        except Exception as e:
            logger.error(f"Error stopping sound: {e}", exc_info=True)
            await self._send_error(websocket, 'stop_error', 'Failed to stop sound')

    async def _handle_status(self, websocket):
        """Handle status request"""
        try:
            # Get current playback status
            now_playing = getattr(self.bot.voice, 'now_playing', None)
            is_connected = self.bot.voice.voice and self.bot.voice.voice.is_connected()
            is_playing = self.bot.voice.voice and self.bot.voice.voice.is_playing()
            
            status = {
                'action': 'status',
                'connected': is_connected,
                'playing': is_playing,
                'now_playing': now_playing,
                'sound_count': self.sound_files.get_file_count(),
                'server_time': time.time()
            }
            
            if is_connected and self.bot.voice.voice:
                status['channel'] = self.bot.voice.voice.channel.name
            
            await self._send_message(websocket, status)
            
        except Exception as e:
            logger.error(f"Error getting status: {e}", exc_info=True)
            await self._send_error(websocket, 'status_error', 'Failed to get status')

    async def _get_user_voice_channel(self, user_id: str):
        """Get the voice channel for a user"""
        try:
            user_id_int = int(user_id)
            
            # Find the user in all guilds
            for guild in self.bot.guilds:
                member = guild.get_member(user_id_int)
                if member and member.voice and member.voice.channel:
                    return member.voice.channel
            
            return None
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error getting voice channel for user {user_id}: {e}")
            return None

    async def _send_message(self, websocket, message: Dict[str, Any]):
        """Send a message to a WebSocket client"""
        try:
            await websocket.send(json.dumps(message))
        except ConnectionClosed:
            logger.debug("Attempted to send message to closed connection")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def _send_error(self, websocket, error_code: str, error_message: str):
        """Send an error message to a WebSocket client"""
        try:
            error_response = {
                'action': 'error',
                'error_code': error_code,
                'error_message': error_message,
                'timestamp': time.time()
            }
            await self._send_message(websocket, error_response)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")

    async def _close_connection(self, websocket):
        """Close a WebSocket connection gracefully"""
        try:
            await websocket.close()
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")

    async def _cleanup_connection(self, websocket):
        """Clean up connection resources"""
        try:
            self.active_connections.discard(websocket)
            self.connection_info.pop(websocket, None)
        except Exception as e:
            logger.error(f"Error cleaning up connection: {e}")

    @staticmethod
    def generate_auth_token(user_id: str) -> str:
        """Generate a JWT authentication token for a user"""
        try:
            payload = {
                'user_id': user_id,
                'exp': time.time() + (TOKEN_EXPIRY_HOURS * 3600),  # Expire in 24 hours
                'iat': time.time()
            }
            
            token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
            return token
            
        except Exception as e:
            logger.error(f"Error generating auth token: {e}")
            raise

    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)

    def get_authenticated_count(self) -> int:
        """Get the number of authenticated connections"""
        return sum(1 for conn_info in self.connection_info.values() if conn_info['authenticated'])
