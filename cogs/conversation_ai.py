import asyncio
import logging
import json
from datetime import datetime
from typing import Dict
from collections import deque

import discord
from discord.ext import commands

from utils.files import FileRepo
from utils.ollama_client import OllamaClient
from utils.jeff_persona import JeffPersona

logger = logging.getLogger('discord.conversation_ai')

def is_admin_or_owner():
    """Custom check: bot owner in DMs, administrator in guilds"""
    async def predicate(ctx):
        if not ctx.guild:
            return await ctx.bot.is_owner(ctx.author)
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

class ConversationAI(commands.Cog):
    def __init__(self, bot, ollama_client: OllamaClient, memory_repo: FileRepo = None):
        self.bot = bot
        self.ollama = ollama_client
        self.memory_repo = memory_repo
        self.jeff_persona = JeffPersona(ollama_client)
        
        # Memory tracking only
        self.user_memories: Dict[int, Dict] = {}
        self.general_insights: Dict = {}
        
        # Processing queue to avoid overwhelming the LLM
        self.processing_queue = asyncio.Queue()
        self.processor_task = None
        
        # Auto-save system
        self.memory_modified = False
        self.auto_save_task = None
        
        # Recent message history (memory only, not saved to disk)
        self.recent_messages: Dict[int, deque] = {}  # channel_id -> last 50 messages
        
        # Channels to ignore
        self.ignored_channels = set()
        
        # Load existing memories
        if self.memory_repo:
            self._load_memories()
            # Start auto-save task
            self._start_auto_save()
            
        # Backfill message history flag
        self.history_backfilled = False
        
        # Bot mention tracking
        self.bot_mentions_detected = 0
        self.responses_sent = 0

    def _load_memories(self):
        """Load conversation memories from persistent storage"""
        try:
            if not self.memory_repo:
                return
                
            # Load general insights
            insights_file = self.memory_repo.find("general_insights")
            if insights_file and insights_file.exists():
                with open(insights_file.path, 'r', encoding='utf-8') as f:
                    self.general_insights = json.load(f)
                logger.info(f"Loaded {len(self.general_insights)} general insights")
            
            # Load user memories
            user_files = [f for f in self.memory_repo.list_files() if f.name.startswith("user_")]
            for user_file in user_files:
                try:
                    user_id = int(user_file.name.replace("user_", "").replace(".json", ""))
                    with open(user_file.path, 'r', encoding='utf-8') as f:
                        self.user_memories[user_id] = json.load(f)
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(f"Error loading memory for {user_file.name}: {e}")
                    
            logger.info(f"Loaded memories for {len(self.user_memories)} users")
            
        except Exception as e:
            logger.error(f"Error loading memories: {e}", exc_info=True)

    def _save_general_insights(self):
        """Save general conversation insights"""
        try:
            if not self.memory_repo or not self.general_insights:
                return
                
            insights_file = self.memory_repo.find("general_insights")
            if not insights_file:
                insights_file = self.memory_repo.add_file("general_insights.json")
                
            if insights_file:
                with open(insights_file.path, 'w', encoding='utf-8') as f:
                    json.dump(self.general_insights, f, indent=2, ensure_ascii=False)
                self.memory_repo.update_file(insights_file)
                
        except Exception as e:
            logger.error(f"Error saving general insights: {e}", exc_info=True)

    def _save_user_memory(self, user_id: int):
        """Save user-specific memory"""
        try:
            if not self.memory_repo or user_id not in self.user_memories:
                return
                
            filename = f"user_{user_id}.json"
            user_file = self.memory_repo.find(f"user_{user_id}")
            if not user_file:
                user_file = self.memory_repo.add_file(filename)
                
            if user_file:
                with open(user_file.path, 'w', encoding='utf-8') as f:
                    json.dump(self.user_memories[user_id], f, indent=2, ensure_ascii=False)
                self.memory_repo.update_file(user_file)
                logger.info(f"💾 Saved memory for user {user_id} - {self.user_memories[user_id]['interaction_count']} interactions")
                
        except Exception as e:
            logger.error(f"Error saving memory for user {user_id}: {e}", exc_info=True)

    async def _process_message_for_memory(self, message: discord.Message):
        """Process message with LLM for memory extraction"""
        try:
            user = message.author
            user_id = user.id
            logger.debug(f"🎯 Processing message from {user.display_name}: '{message.content[:50]}...'")  
            
            # Initialize user memory if needed
            if user_id not in self.user_memories:
                self.user_memories[user_id] = {
                    'user_name': user.display_name,
                    'first_seen': datetime.now().isoformat(),
                    'last_interaction': datetime.now().isoformat(),
                    'interaction_count': 0,
                    'topics_discussed': [],
                    'notable_interactions': [],
                    'personality_notes': [],
                    'preferences': {},
                    'sentiment_history': []
                }

            # Build context for LLM with conversation history
            is_dm = not message.guild
            
            # Get recent messages for context (last 5 messages)
            recent_messages = self.get_recent_messages(message.channel.id, limit=5)
            
            # Build conversation context
            context_lines = []
            if recent_messages:
                context_lines.append("=== RECENT CONVERSATION CONTEXT ===")
                for msg in recent_messages:
                    timestamp = msg['timestamp'][:16].replace('T', ' ')  # Format: YYYY-MM-DD HH:MM
                    context_lines.append(f"[{timestamp}] {msg['author_name']}: {msg['content']}")
                context_lines.append("=== END CONTEXT ===\n")
            
            # Current message to analyze
            context_lines.append("=== MESSAGE TO ANALYZE ===")
            context_lines.append(f"User: {user.display_name}")
            context_lines.append(f"Message: {message.content}")
            
            if message.guild:
                context_lines.append(f"Channel: #{message.channel.name}")
                context_lines.append(f"Server: {message.guild.name}")
            else:
                context_lines.append(f"Context: Direct Message (DM) with bot")
                
            context = "\n".join(context_lines)

            # Build bot direction detection rules based on context
            if is_dm:
                bot_direction_rules = "- DIRECT MESSAGE: Always set to 1.0 (DMs are always directed at the bot)"
            else:
                bot_direction_rules = """- 1.0: Direct mention, "@jeff", "@Jeff", "hey jeff", "jeff", questions clearly TO jeff, direct address
                                         - 0.8-0.9: Asking questions that seem directed at jeff, using "you" when jeff context is clear
                                         - 0.6-0.7: General questions that could be for anyone but jeff might answer
                                         - 0.3-0.5: Discussing topics related to jeff's capabilities or AI in general
                                         - 0.1-0.2: Casual conversation that might include jeff tangentially
                                         - 0.0: Clearly not directed at jeff, private conversation between users
                                         
                                         IMPORTANT: Look specifically for "jeff" (case insensitive) in the message as a strong indicator! When jeff has recently replied to a message, it's more likely that the message is directed at jeff."""

            # LLM prompt for memory extraction and bot detection
            system_prompt = {
                "role": "system",
                "content": f"""
                            You are analyzing Discord messages to extract structured data for user memory and detect if the bot is being addressed.
                            The bot's name is "{self.bot.user.display_name}" and its username is "{self.bot.user.name}".
                            
                            You will be provided with recent conversation context and a specific message to analyze.
                            Use the conversation context to better understand the topics, sentiment, and whether the message is directed at the bot.
                            Only analyze the message marked as "MESSAGE TO ANALYZE" - the context is just for reference.
                            
                            Respond with valid JSON in this exact format:
                            {{
                                "metadata": {{
                                    "topics": ["topic1", "topic2"],
                                    "is_notable": true/false,
                                    "notable_reason": "why this interaction is notable (if applicable)",
                                    "user_insights": ["insight1", "insight2"],
                                    "sentiment": "positive/neutral/negative",
                                    "contains_personal_info": true/false,
                                    "directed_at_bot_probability": 0.0-1.0,
                                    "bot_direction_reason": "explanation for why this might be directed at the bot"
                                }}
                            }}

                            Guidelines:
                            - Topics: 1-3 relevant keywords about what's being discussed
                            - Notable if: sharing personal info, emotional content, asking for help, expressing strong opinions, creative content
                            - User insights: observations about interests, personality, preferences, behavior patterns
                            - Sentiment: overall emotional tone of the message
                            - Personal info: if they share details about themselves, their life, preferences, etc.
                            - directed_at_bot_probability: Float 0.0-1.0 indicating likelihood the message is directed at the bot
                            - bot_direction_reason: Brief explanation of why you think it's directed at the bot (or not)
                            
                            Bot Direction Detection:
                            {bot_direction_rules}

                            Only return the JSON, no other text.
                           """
            }

            messages = [
                system_prompt,
                {"role": "user", "content": context}
            ]

            # Get LLM analysis
            logger.debug(f"🔍 Sending message to LLM for {user.display_name}: {context[:100]}...")
            response_data = await self.ollama.generate_with_metadata(messages)
            logger.debug(f"📥 LLM response received for {user.display_name}: {response_data}")
            
            if not response_data or 'metadata' not in response_data:
                logger.warning(f"❌ No valid metadata from LLM for {user.display_name}. Response: {response_data}")
                return

            metadata = response_data['metadata']
            
            # Check if message is directed at bot
            directed_at_bot_prob = metadata.get('directed_at_bot_probability', 0.0)
            bot_direction_reason = metadata.get('bot_direction_reason', '')
            
            is_directed_at_bot = directed_at_bot_prob >= 0.7  # Threshold for considering it directed at bot
            
            if is_directed_at_bot:
                self.bot_mentions_detected += 1
                logger.info(f"🤖 Bot addressed by {user.display_name} (probability: {directed_at_bot_prob:.2f}): {bot_direction_reason}")
                
                # Generate and send response since Jeff is being addressed
                await self._generate_and_send_response(message, context, user)
            
            # Update user memory with extracted data
            await self._update_user_memory_with_metadata(user, message.content, metadata)
            
            logger.debug(f"🧠 Processed memory for {user.display_name}: {json.dumps(metadata, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"Error processing message for memory: {e}", exc_info=True)

    async def _generate_and_send_response(self, message: discord.Message, context: str, user: discord.User):
        """Generate and send a response when Jeff is being addressed"""
        try:
            logger.info(f"🗣️ Generating response for {user.display_name}: '{message.content[:50]}...'")
            
            # Get user memory for context
            user_memory = self.user_memories.get(user.id, {})
            
            # Build smart personality context based on message relevance
            all_personality_notes = user_memory.get('personality_notes', [])
            all_topics_discussed = user_memory.get('topics_discussed', [])
            interaction_count = user_memory.get('interaction_count', 0)
            
            # Extract relevant insights based on current message content and recent topics
            relevant_insights = self._get_relevant_user_insights(message.content, all_personality_notes, all_topics_discussed)
            
            # Get recent conversation history for response context
            recent_messages = self.get_recent_messages(message.channel.id, limit=10)
            
            # Build conversation history context
            conversation_history = ""
            if recent_messages and len(recent_messages) > 1:  # Only include if there's actual conversation
                conversation_history = "\n=== RECENT CONVERSATION HISTORY ===\n"
                conversation_history += "(This is what was said leading up to the message you're responding to)\n\n"
                
                for msg in recent_messages[:-1]:  # Exclude the current message being responded to
                    timestamp = msg['timestamp'][:16].replace('T', ' ')  # Format: YYYY-MM-DD HH:MM
                    author = msg['author_name']
                    content = msg['content']
                    
                    # Mark if it was Jeff who said it
                    if msg['is_bot'] and msg['author_name'] == self.bot.user.display_name:
                        author = "Jeff (you)"
                    
                    conversation_history += f"[{timestamp}] {author}: {content}\n"
                
                conversation_history += "\n=== END CONVERSATION HISTORY ===\n\n"
            else:
                conversation_history = "\n(No recent conversation history available)\n\n"
            
            # Build user context for JeffPersona
            user_context = {
                'interaction_count': interaction_count,
                'personality': relevant_insights['personality'] if relevant_insights['personality'] else 'Unknown so far',
                'topics': relevant_insights['topics'] if relevant_insights['topics'] else 'Various'
            }
            
            # Determine context type
            context_type = "dm" if not message.guild else "server"
            
            # Use JeffPersona to generate response
            response_text = await self.jeff_persona.generate_response(
                message_content=message.content,
                user_name=user.display_name,
                conversation_history=conversation_history,
                user_context=user_context,
                context_type=context_type
            )
            
            # Send response
            await message.channel.send(response_text)
            self.responses_sent += 1
                
        except Exception as e:
            logger.error(f"Error generating response for {user.display_name}: {e}", exc_info=True)
            # Fallback response
            try:
                await message.channel.send("Sorry mate, brain's not working right now")
            except:
                pass

    def _get_relevant_user_insights(self, message_content: str, personality_notes: list, topics_discussed: list) -> dict:
        """Get user insights relevant to the current message topic"""
        try:
            message_lower = message_content.lower()
            
            # Find relevant personality insights
            relevant_personality = []
            recent_personality = personality_notes[-10:] if personality_notes else []  # Start with most recent
            
            # First, add insights that contain words from the current message
            for insight in recent_personality:
                insight_words = insight.lower().split()
                message_words = message_lower.split()
                
                # Check if any words from the insight appear in the message
                if any(word in message_lower for word in insight_words if len(word) > 3):
                    if insight not in relevant_personality:
                        relevant_personality.append(insight)
            
            # Then add the most recent ones if we don't have enough context
            for insight in reversed(recent_personality):
                if len(relevant_personality) >= 5:
                    break
                if insight not in relevant_personality:
                    relevant_personality.append(insight)
            
            # Find relevant topics
            relevant_topics = []
            recent_topics = topics_discussed[-15:] if topics_discussed else []  # Start with most recent
            
            # First, add topics that relate to the current message
            for topic in recent_topics:
                topic_lower = topic.lower()
                # Check if topic words appear in message or vice versa
                if (topic_lower in message_lower or 
                    any(word in topic_lower for word in message_lower.split() if len(word) > 3)):
                    if topic not in relevant_topics:
                        relevant_topics.append(topic)
            
            # Then add the most recent ones if we need more context
            for topic in reversed(recent_topics):
                if len(relevant_topics) >= 8:
                    break
                if topic not in relevant_topics:
                    relevant_topics.append(topic)
            
            return {
                'personality': ', '.join(relevant_personality) if relevant_personality else '',
                'topics': ', '.join(relevant_topics) if relevant_topics else ''
            }
            
        except Exception as e:
            logger.error(f"Error getting relevant insights: {e}")
            # Fallback to recent items
            return {
                'personality': ', '.join(personality_notes[-5:]) if personality_notes else '',
                'topics': ', '.join(topics_discussed[-5:]) if topics_discussed else ''
            }

    async def _update_user_memory_with_metadata(self, user: discord.User, message_content: str, metadata: dict):
        """Update user memory using LLM-extracted metadata"""
        try:
            user_id = user.id
            memory = self.user_memories[user_id]
            
            # Update basic info
            memory['user_name'] = user.display_name
            memory['last_interaction'] = datetime.now().isoformat()
            memory['interaction_count'] += 1
            
            # Add topics
            topics = metadata.get('topics', [])
            for topic in topics:
                if topic and topic not in memory['topics_discussed']:
                    memory['topics_discussed'].append(topic)
            memory['topics_discussed'] = memory['topics_discussed'][-20:]  # Keep last 20
            
            # Add user insights
            user_insights = metadata.get('user_insights', [])
            for insight in user_insights:
                if insight and insight not in memory['personality_notes']:
                    memory['personality_notes'].append(insight)
            memory['personality_notes'] = memory['personality_notes'][-15:]  # Keep last 15
            
            # Track sentiment
            sentiment = metadata.get('sentiment', 'neutral')
            memory['sentiment_history'].append({
                'timestamp': datetime.now().isoformat(),
                'sentiment': sentiment
            })
            memory['sentiment_history'] = memory['sentiment_history'][-10:]  # Keep last 10
            
            # Save notable interactions
            if metadata.get('is_notable', False):
                notable_reason = metadata.get('notable_reason', 'LLM identified as notable')
                notable_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'content': message_content[:200],
                    'reason': notable_reason,
                    'sentiment': sentiment,
                    'topics': topics
                }
                memory['notable_interactions'].append(notable_entry)
                memory['notable_interactions'] = memory['notable_interactions'][-10:]  # Keep last 10
                
                logger.info(f"Notable interaction saved for {user.display_name}: {notable_reason}")
            
            # Mark memory as modified for auto-save
            self.memory_modified = True
                
        except Exception as e:
            logger.error(f"Error updating user memory: {e}", exc_info=True)

    def _store_message_in_history(self, message: discord.Message):
        """Store message in recent history (memory only)"""
        try:
            channel_id = message.channel.id
            
            # Initialize deque for this channel if not exists
            if channel_id not in self.recent_messages:
                self.recent_messages[channel_id] = deque(maxlen=50)
            
            # Store message data
            message_data = {
                'content': message.content,
                'author_id': message.author.id,
                'author_name': message.author.display_name,
                'timestamp': message.created_at.isoformat(),
                'message_id': message.id,
                'is_bot': message.author.bot,
                'channel_name': getattr(message.channel, 'name', 'DM') if message.guild else 'DM',
                'guild_name': message.guild.name if message.guild else None
            }
            
            self.recent_messages[channel_id].append(message_data)
            
        except Exception as e:
            logger.error(f"Error storing message in history: {e}", exc_info=True)

    def get_recent_messages(self, channel_id: int, limit: int = None) -> list:
        """Get recent messages for a channel (memory only)"""
        if channel_id not in self.recent_messages:
            return []
        
        messages = list(self.recent_messages[channel_id])
        if limit:
            return messages[-limit:]
        return messages

    def _should_process_message(self, message: discord.Message) -> bool:
        """Check if message should be processed for memory"""
        # Skip bots
        if message.author.bot:
            return False
            
        # Skip ignored channels
        if message.guild and message.channel.id in self.ignored_channels:
            return False
                        
        # Skip commands
        content = message.content.strip()
        if content.startswith(('!', '/', '$', '?', '.', '-', '+', '=', '*', '&', '%', '#')):
            return False
            
        return True

    def _start_auto_save(self):
        """Start the auto-save task"""
        try:
            # Check if there's a running event loop
            asyncio.get_running_loop()
            if self.auto_save_task is None or self.auto_save_task.done():
                self.auto_save_task = asyncio.create_task(self._auto_save_loop())
        except RuntimeError:
            # No event loop running (e.g., during testing)
            self.auto_save_task = None

    async def _auto_save_loop(self):
        """Auto-save memories every 3 minutes if modified"""
        while True:
            try:
                await asyncio.sleep(180)  # Wait 3 minutes
                
                if self.memory_modified and self.memory_repo:
                    logger.debug("Auto-saving modified memories...")
                    
                    # Run file operations in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    
                    # Save general insights
                    await loop.run_in_executor(None, self._save_general_insights)
                    
                    # Save all modified user memories
                    saved_count = 0
                    for user_id in self.user_memories:
                        await loop.run_in_executor(None, self._save_user_memory, user_id)
                        saved_count += 1
                    
                    self.memory_modified = False
                    logger.info(f"🕒 Auto-saved {saved_count} user memories (3min interval)")
                    
            except Exception as e:
                logger.error(f"Error in auto-save loop: {e}", exc_info=True)

    async def _start_processor(self):
        """Start the message processor task"""
        if self.processor_task is None or self.processor_task.done():
            self.processor_task = asyncio.create_task(self._message_processor())

    async def _message_processor(self):
        """Process queued messages"""
        while True:
            try:
                message = await self.processing_queue.get()
                logger.debug(f"🔄 Processing queued message from {message.author.display_name}")
                
                await self._process_message_for_memory(message)
                self.processing_queue.task_done()
                
                # Small delay to avoid overwhelming the LLM
                await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"Error in message processor: {e}", exc_info=True)

    async def _backfill_message_history(self):
        """Backfill message history from Discord API on startup"""
        if self.history_backfilled:
            return
            
        try:
            logger.info("🔄 Starting message history backfill...")
            channels_processed = 0
            total_messages_loaded = 0
            
            # Get all text channels the bot can see
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    try:
                        # Check if bot can read message history in this channel
                        if not channel.permissions_for(guild.me).read_message_history:
                            continue
                            
                        # Fetch recent messages (limit 50 to match our deque size)
                        messages = []
                        async for message in channel.history(limit=50, oldest_first=False):
                            messages.append(message)
                        
                        # Store messages in reverse order (oldest first in deque)
                        messages.reverse()
                        
                        for message in messages:
                            self._store_message_in_history(message)
                            total_messages_loaded += 1
                            
                        if messages:
                            channels_processed += 1
                            logger.debug(f"📝 Loaded {len(messages)} messages from #{channel.name} in {guild.name}")
                            
                    except Exception as e:
                        logger.warning(f"Error loading history from #{channel.name} in {guild.name}: {e}")
                        continue
            
            # Also load DM history if possible
            try:
                if hasattr(self.bot, 'private_channels'):
                    for dm_channel in self.bot.private_channels:
                        if dm_channel.type == discord.ChannelType.private:
                            try:
                                messages = []
                                async for message in dm_channel.history(limit=50, oldest_first=False):
                                    messages.append(message)
                                
                                messages.reverse()
                                for message in messages:
                                    self._store_message_in_history(message)
                                    total_messages_loaded += 1
                                    
                                if messages:
                                    channels_processed += 1
                                    logger.debug(f"📝 Loaded {len(messages)} messages from DM with {message.author.display_name}")
                                    
                            except Exception as e:
                                logger.warning(f"Error loading DM history: {e}")
                                continue
            except Exception as e:
                logger.warning(f"Error accessing private channels: {e}")
            
            self.history_backfilled = True
            logger.info(f"✅ Message history backfill complete: {total_messages_loaded} messages from {channels_processed} channels")
            
        except Exception as e:
            logger.error(f"Error during message history backfill: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready - backfill message history"""
        try:
            # Start backfill in background to avoid blocking bot startup
            asyncio.create_task(self._backfill_message_history())
        except Exception as e:
            logger.error(f"Error starting message history backfill: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen to messages for memory processing and history storage"""
        try:
            # Store ALL messages in history (including bot messages, commands, etc.)
            self._store_message_in_history(message)
            
            # Only process non-bot, non-command messages for memory extraction
            should_process = self._should_process_message(message)
            logger.debug(f"📝 Message from {message.author.display_name}: should_process={should_process}, content='{message.content[:30]}...'")
            
            if not should_process:
                return
                
            # Add to processing queue for LLM analysis
            logger.debug(f"➕ Adding message to queue from {message.author.display_name}")
            await self.processing_queue.put(message)
            
            # Start processor if needed
            await self._start_processor()
            
        except Exception as e:
            logger.error(f"Error in message listener: {e}", exc_info=True)

    @commands.command(name='ai_toggle', help='Toggle AI memory processing in this channel')
    @is_admin_or_owner()
    async def toggle_ai(self, ctx):
        """Toggle AI memory processing in the current channel"""
        if not ctx.guild:
            await ctx.send("❌ This command only works in server channels.")
            return
            
        channel_id = ctx.channel.id
        
        if channel_id in self.ignored_channels:
            self.ignored_channels.remove(channel_id)
            await ctx.send("🧠 AI memory processing enabled in this channel!")
        else:
            self.ignored_channels.add(channel_id)
            await ctx.send("🚫 AI memory processing disabled in this channel!")

    @commands.command(name='ai_stats', help='Show AI memory stats')
    async def ai_stats(self, ctx):
        """Show AI memory statistics"""
        embed = discord.Embed(title="🧠 Memory System Stats", color=0x9932cc)
        
        embed.add_field(name="Current Model", value=f"`{self.ollama.get_current_model()}`", inline=False)
        
        user_count = len(self.user_memories)
        embed.add_field(name="Users Remembered", value=str(user_count), inline=True)
        
        if self.general_insights.get('conversation_patterns'):
            total_convos = self.general_insights['conversation_patterns'].get('total_conversations', 0)
            embed.add_field(name="Interactions Tracked", value=str(total_convos), inline=True)
        
        embed.add_field(name="Ignored Channels", value=len(self.ignored_channels), inline=True)
        embed.add_field(name="Queue Size", value=self.processing_queue.qsize(), inline=True)
        embed.add_field(name="Processor Status", value="Running" if self.processor_task and not self.processor_task.done() else "Stopped", inline=True)
        
        # Message history stats
        channels_with_history = len(self.recent_messages)
        total_stored_messages = sum(len(msgs) for msgs in self.recent_messages.values())
        embed.add_field(name="Channels with History", value=str(channels_with_history), inline=True)
        embed.add_field(name="Total Messages Stored", value=str(total_stored_messages), inline=True)
        embed.add_field(name="Auto-Save Status", value="Running" if self.auto_save_task and not self.auto_save_task.done() else "Stopped", inline=True)
        embed.add_field(name="History Backfilled", value="✅ Yes" if self.history_backfilled else "❌ No", inline=True)
        embed.add_field(name="Bot Mentions Detected", value=str(self.bot_mentions_detected), inline=True)
        embed.add_field(name="Responses Sent", value=str(self.responses_sent), inline=True)
        
        embed.set_footer(text="🧠 Memory system + 📝 Message history (50 per channel)")
        await ctx.send(embed=embed)

    @commands.command(name='ai_user', help='View AI memory for a user')
    async def user_memory_command(self, ctx, user: discord.User = None):
        """View AI memory for a specific user"""
        if not user:
            await ctx.send("❌ Please provide a user: `!ai_user @username`")
            return
        
        user_id = user.id
        if user_id not in self.user_memories:
            await ctx.send(f"❌ No memories found for {user.display_name}.")
            return
            
        memory = self.user_memories[user_id]
        embed = discord.Embed(title=f"🧠 Memory for {memory['user_name']}", color=0x9932cc)
        
        embed.add_field(name="Interactions", value=str(memory['interaction_count']), inline=True)
        embed.add_field(name="First Seen", value=memory['first_seen'][:10], inline=True)
        embed.add_field(name="Last Interaction", value=memory['last_interaction'][:10], inline=True)
        
        if memory['topics_discussed']:
            topics_text = ", ".join(memory['topics_discussed'][-10:])
            embed.add_field(name="Recent Topics", value=topics_text[:1000], inline=False)
        
        if memory.get('personality_notes'):
            insights_text = "\n".join([f"• {insight}" for insight in memory['personality_notes'][-5:]])
            embed.add_field(name="Personality Insights", value=insights_text[:1000], inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name='ai_forget_me', help='Clear your own AI memory')
    async def forget_me_command(self, ctx):
        """Allow users to clear their own AI memory"""
        user_id = ctx.author.id
        
        if user_id not in self.user_memories:
            await ctx.send("❌ I don't have any memories of you yet!")
            return
        
        interaction_count = self.user_memories[user_id]['interaction_count']
        del self.user_memories[user_id]
        
        await ctx.send(f"✅ Cleared your memory! ({interaction_count} interactions removed)")
        logger.info(f"User {ctx.author.display_name} cleared their own memory")

    @commands.command(name='ai_backfill', help='Manually backfill message history')
    @is_admin_or_owner()
    async def backfill_command(self, ctx):
        """Manually trigger message history backfill"""
        if self.history_backfilled:
            # Reset flag to allow re-backfill
            self.history_backfilled = False
            
        await ctx.send("🔄 Starting message history backfill...")
        
        # Run backfill
        await self._backfill_message_history()
        
        # Send updated stats
        channels_with_history = len(self.recent_messages)
        total_stored_messages = sum(len(msgs) for msgs in self.recent_messages.values())
        
        await ctx.send(f"✅ Backfill complete! Now storing messages from {channels_with_history} channels ({total_stored_messages} total messages)")

    @commands.command(name='ai_debug', help='Toggle debug logging for conversation AI')
    @is_admin_or_owner()
    async def debug_command(self, ctx, level: str = "INFO"):
        """Toggle debug logging level"""
        import logging
        
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }
        
        if level.upper() not in level_map:
            await ctx.send("❌ Invalid level. Use: DEBUG, INFO, WARNING, ERROR")
            return
            
        # Set logger level
        conversation_logger = logging.getLogger('discord.conversation_ai')
        conversation_logger.setLevel(level_map[level.upper()])
        
        await ctx.send(f"🔧 Set conversation AI logging to {level.upper()}")
        logger.info(f"Logging level changed to {level.upper()} by {ctx.author.display_name}") 