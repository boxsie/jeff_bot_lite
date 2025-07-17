import time
import json
import discord
import logging
from discord.ext import commands

from utils.ollama_client import OllamaClient

logger = logging.getLogger('discord.chat_ollama')

class ChatOllama(commands.Cog):
    def __init__(self, bot, ollama_client: OllamaClient):
        self.bot = bot
        self.ollama = ollama_client
        self.msg_context = []
        self.last_request_time = 0
        logger.info(f"ChatOllama initialized with OllamaClient")

    @commands.command(name='jeff', help='Chat to Jeff')
    async def jeff_chat(self, ctx, *, msg):
        if not msg or not msg.strip():
            await ctx.send("🤔 You didn't say anything! What did you want to tell Jeff?")
            return

        logger.info(f"Chat request from {ctx.author}: {msg[:100]}{'...' if len(msg) > 100 else ''}")

        # Reset context if 5 minutes have passed
        if time.time() - self.last_request_time > 300:
            logger.info("Resetting context due to timeout")
            self.msg_context.clear()

        self.msg_context.append({"role": "user", "content": msg})

        # Truncate context if it's too large
        while self.count_context_tokens() > 3000:
            logger.info("Context too large, removing oldest entries")
            self.msg_context.pop(0)

        # System message to shape Jeff's personality
        system_messages = [
            {"role": "system", "content": "You are a talking dog named Jeff. Respond in character with dog themes, occasional barking, be dry and cutting but not cheesy."},
            {"role": "system", "content": "Format responses appropriately for Discord with proper newlines and emojis"},
            {"role": "system", "content": "Keep responses short."},
            {"role": "system", "content": "Reply in British English."}
        ]
        
        messages = system_messages + self.msg_context

        # Show typing indicator while generating response
        async with ctx.typing():
            try:
                # Use OllamaClient for streaming response
                generated_text = await self.ollama.chat_completion(
                    messages=messages,
                    stream=True
                )

            except Exception as e:
                logger.error(f"Error with Ollama request: {e}", exc_info=True)
                await ctx.send("⚠️ Jeff's brain isn't working properly right now. Try again later!")
                return

        # Validate response
        if not generated_text or not generated_text.strip():
            logger.warning("Received empty response from Ollama")
            await ctx.send("🤐 Jeff seems to be speechless... try asking again!")
            return

        logger.info(f"Ollama response length: {len(generated_text)} characters")
        self.msg_context.append({"role": "assistant", "content": generated_text})

        # Split long messages for Discord
        try:
            chunks = self.split_text_into_chunks(generated_text, 2000)
            
            if not chunks:
                await ctx.send("🤐 Jeff had nothing to say...")
                return
                
            for i, chunk in enumerate(chunks):
                if not chunk.strip():  # Skip empty chunks
                    continue
                    
                message_to_send = chunk + '...' if len(chunk) == 2000 and i < len(chunks) - 1 else chunk
                await ctx.send(message_to_send)
                
        except discord.HTTPException as e:
            logger.error(f"Discord send error: {e}")
            await ctx.send("💥 Jeff's message was too weird for Discord to handle!")
        except Exception as e:
            logger.error(f"Error sending response chunks: {e}", exc_info=True)
            await ctx.send("⚠️ Jeff said something but it got lost in translation!")

        self.last_request_time = int(time.time())

    @commands.command(name='jeff_clear', help="Clear Jeff's chat context")
    async def jeff_clear(self, ctx):
        try:
            context_size = len(self.msg_context)
            self.msg_context.clear()
            logger.info(f"Context cleared by {ctx.author}, removed {context_size} messages")
            await ctx.send("Jeff's memory has been wiped!")
        except Exception as e:
            logger.error(f"Error clearing context: {e}")
            await ctx.send("🤯 Jeff's memory is stuck! Try again.")

    def count_context_tokens(self):
        try:
            return sum(len(message["content"].split()) for message in self.msg_context)
        except Exception as e:
            logger.error(f"Error counting context tokens: {e}")
            return 0

    def split_text_into_chunks(self, text, max_length):
        """Splits a long response into multiple Discord messages (max limit: 2000 chars)."""
        if not text:
            return []
            
        try:
            lines = text.split('\n')
            messages = []
            current_message = ''

            for line in lines:
                if len(current_message) + len(line) + 1 <= max_length:  # +1 for newline
                    current_message += line + '\n'
                else:
                    if current_message:
                        messages.append(current_message.rstrip('\n'))
                        current_message = ''
                    
                    if len(line) <= max_length:
                        current_message = line + '\n'
                    else:
                        # Split very long lines
                        while len(line) > max_length:
                            chunk, line = line[:max_length], line[max_length:]
                            messages.append(chunk)
                        if line:
                            current_message = line + '\n'

            if current_message:
                messages.append(current_message.rstrip('\n'))

            return [msg for msg in messages if msg.strip()]  # Filter out empty messages
            
        except Exception as e:
            logger.error(f"Error splitting text into chunks: {e}")
            return [text[:max_length]] if text else []