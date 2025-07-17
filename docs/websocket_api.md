# Jeff Bot WebSocket API

The Jeff Bot WebSocket server provides a real-time API for triggering sound effects and managing bot functionality remotely. The server runs on port 8765 and requires JWT authentication.

## Features

- **JWT-based Authentication**: Secure token-based authentication
- **Sound Effect Triggering**: Play specific sounds or random sounds
- **Sound Listing**: Get a list of all available sound effects
- **Real-time Status**: Check bot and playback status
- **Connection Management**: Automatic connection cleanup and error handling
- **Comprehensive Logging**: Full request/response logging for debugging

## Authentication

All API calls (except `authenticate`) require a valid JWT token.

### Generating Tokens

Use the utility script to generate authentication tokens:

```bash
cd jeff_bot_lite
python utils/ws_auth.py <discord_user_id>
```

Example:

```bash
python utils/ws_auth.py 123456789012345678
```

This will output a JWT token that expires in 24 hours.

### Authentication Flow

1. Connect to `ws://localhost:8765`
2. Receive welcome message
3. Send authentication message with your token
4. Receive authentication confirmation
5. Use authenticated API calls

## API Reference

### Connection

Connect to: `ws://localhost:8765`

### Message Format

All messages are JSON objects with an `action` field:

```json
{
  "action": "action_name",
  "additional_field": "value"
}
```

### Authentication

**Request:**

```json
{
  "action": "authenticate",
  "token": "your_jwt_token_here"
}
```

**Success Response:**

```json
{
  "action": "auth_success",
  "message": "Authentication successful",
  "user_id": "123456789012345678"
}
```

**Error Response:**

```json
{
  "action": "error",
  "error_code": "auth_failed",
  "error_message": "Token expired",
  "timestamp": 1640995200.0
}
```

### List Sounds

Get a list of all available sound effects.

**Request:**

```json
{
  "action": "list"
}
```

**Response:**

```json
{
  "action": "list",
  "sounds": [
    {
      "name": "airhorn.mp3",
      "path": "/path/to/sounds/airhorn.mp3"
    },
    {
      "name": "sad_trombone.mp3",
      "path": "/path/to/sounds/sad_trombone.mp3"
    }
  ],
  "count": 247
}
```

### Play Sound

Play a specific sound effect. The user must be in a Discord voice channel.

**Request:**

```json
{
  "action": "play",
  "filename": "airhorn.mp3"
}
```

**Success Response:**

```json
{
  "action": "playing",
  "filename": "airhorn.mp3",
  "title": "airhorn.mp3",
  "channel": "General"
}
```

**Error Responses:**

```json
{
  "action": "error",
  "error_code": "sound_not_found",
  "error_message": "Sound \"invalid.mp3\" not found",
  "timestamp": 1640995200.0
}
```

```json
{
  "action": "error",
  "error_code": "no_voice_channel",
  "error_message": "User must be in a voice channel",
  "timestamp": 1640995200.0
}
```

### Play Random Sound

Play a random sound effect. The user must be in a Discord voice channel.

**Request:**

```json
{
  "action": "random"
}
```

**Response:**

```json
{
  "action": "playing",
  "filename": "random_sound.mp3",
  "title": "random_sound.mp3",
  "channel": "General",
  "random": true
}
```

### Stop Playback

Stop current audio playback.

**Request:**

```json
{
  "action": "stop"
}
```

**Response:**

```json
{
  "action": "stopped",
  "message": "Audio playback stopped"
}
```

### Get Status

Get current server and bot status.

**Request:**

```json
{
  "action": "status"
}
```

**Response:**

```json
{
  "action": "status",
  "connected": true,
  "playing": false,
  "now_playing": null,
  "sound_count": 247,
  "server_time": 1640995200.0,
  "channel": "General"
}
```

## Error Codes

| Error Code          | Description                                   |
| ------------------- | --------------------------------------------- |
| `invalid_json`      | Message is not valid JSON                     |
| `invalid_format`    | Message is not a JSON object                  |
| `missing_action`    | Message missing required "action" field       |
| `not_authenticated` | Authentication required for this action       |
| `auth_failed`       | Authentication failed (invalid/expired token) |
| `auth_error`        | Internal authentication error                 |
| `unknown_action`    | Unknown/unsupported action                    |
| `action_error`      | Error executing the requested action          |
| `missing_filename`  | Filename required for play action             |
| `sound_not_found`   | Specified sound file not found                |
| `no_voice_channel`  | User must be in a Discord voice channel       |
| `no_sounds`         | No sound files available                      |
| `list_error`        | Error retrieving sound list                   |
| `play_error`        | Error playing sound                           |
| `random_error`      | Error playing random sound                    |
| `stop_error`        | Error stopping playback                       |
| `status_error`      | Error retrieving status                       |
| `internal_error`    | Internal server error                         |

## Example Client

See `examples/ws_client_example.py` for a complete example client implementation.

**Usage:**

```bash
cd jeff_bot_lite
python examples/ws_client_example.py <your_discord_user_id>
```

**Interactive Commands:**

- `list` - List available sounds
- `play <filename>` - Play a specific sound
- `random` - Play a random sound
- `stop` - Stop current playback
- `status` - Get server status
- `quit` - Exit

## Security Considerations

1. **JWT Secret**: Change the default JWT secret in production
2. **Token Expiry**: Tokens expire after 24 hours by default
3. **Network Access**: Server binds to `0.0.0.0` - restrict network access in production
4. **User Validation**: Tokens contain user IDs but don't validate Discord user existence
5. **Rate Limiting**: No built-in rate limiting - implement if needed

## Integration Examples

### Python Client

```python
import asyncio
import json
import websockets
from utils.ws_auth import generate_token

async def play_sound(user_id, filename):
    token = generate_token(user_id)

    async with websockets.connect("ws://localhost:8765") as websocket:
        # Wait for welcome
        await websocket.recv()

        # Authenticate
        auth_msg = {"action": "authenticate", "token": token}
        await websocket.send(json.dumps(auth_msg))
        await websocket.recv()  # Auth response

        # Play sound
        play_msg = {"action": "play", "filename": filename}
        await websocket.send(json.dumps(play_msg))
        response = await websocket.recv()

        return json.loads(response)

# Usage
result = asyncio.run(play_sound("123456789", "airhorn.mp3"))
```

### JavaScript/Node.js Client

```javascript
const WebSocket = require("ws");

async function playSoundJS(userId, filename, token) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket("ws://localhost:8765");

    ws.on("open", () => {
      // Wait for welcome message, then authenticate
      ws.on("message", (data) => {
        const msg = JSON.parse(data);

        if (msg.action === "welcome") {
          // Send authentication
          ws.send(
            JSON.stringify({
              action: "authenticate",
              token: token,
            })
          );
        } else if (msg.action === "auth_success") {
          // Send play command
          ws.send(
            JSON.stringify({
              action: "play",
              filename: filename,
            })
          );
        } else if (msg.action === "playing") {
          ws.close();
          resolve(msg);
        } else if (msg.action === "error") {
          ws.close();
          reject(new Error(msg.error_message));
        }
      });
    });

    ws.on("error", reject);
  });
}
```

## Troubleshooting

### Common Issues

1. **Connection Refused**: Make sure the bot is running and the WebSocket server is started
2. **Authentication Failed**: Check that your token is valid and not expired
3. **No Voice Channel Error**: Ensure the user is in a Discord voice channel
4. **Sound Not Found**: Verify the filename exists in the sound list
5. **Permission Errors**: Bot needs voice channel permissions

### Debugging

Enable debug logging by setting the log level:

```python
import logging
logging.getLogger('discord.ws_server').setLevel(logging.DEBUG)
```

Check the server logs for detailed request/response information and error traces.
