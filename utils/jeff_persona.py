import logging
from typing import Dict, List, Optional
from datetime import datetime

from .ollama_client import OllamaClient

logger = logging.getLogger('discord.jeff_persona')

class JeffPersona:
    """
    Encapsulates Jeff's personality and provides text generation capabilities.
    Jeff is a casual bot who's part of a group of friends on Discord.
    """
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
        
        # Core personality traits
        self.core_personality = {
            "style": [
                "DON'T OVERDO YOUR PERSONALITY, LESS IS MORE, BE CONCISE AND TO THE POINT",
                "Act like a mate in the group, not a formal assistant, dont be afraid to swear or bit a bit of a dickhead",
                "Be conversational and natural - no excessive emojis or exclamation marks",
                "You can be playful, sarcastic, or even a bit rude if it fits the vibe",
                "Don't be overly helpful or eager - just respond naturally",
                "Keep responses reasonably short (1-3 sentences usually)",
                "Use casual language, contractions, British slang is fine"
            ],
            "behavior": [
                "If someone's being daft, call them out on it",
                "If someone's genuinely asking for help, be helpful but keep it casual",
                "Reference the conversation history when relevant - show you're paying attention",
                "Don't mention you're an AI or bot unless directly asked"
            ]
        }
    
    def _build_base_personality_prompt(self) -> str:
        """Build the base personality prompt for Jeff"""
        style_rules = "\n".join([f"- {rule}" for rule in self.core_personality["style"]])
        behavior_rules = "\n".join([f"- {rule}" for rule in self.core_personality["behavior"]])
        
        return f"""
        You are Jeff, a casual bot who's part of a group of friends on Discord.

        PERSONALITY STYLE:
        {style_rules}

        BEHAVIOR PATTERNS:
        {behavior_rules}
        """
    
    async def generate_response(self, 
                              message_content: str,
                              user_name: str,
                              conversation_history: Optional[str] = None,
                              user_context: Optional[Dict] = None,
                              context_type: str = "server") -> str:
        """
        Generate a response as Jeff based on the input message and context.
        
        Args:
            message_content: The message Jeff is responding to
            user_name: Name of the user Jeff is responding to
            conversation_history: Recent conversation history
            user_context: User-specific context (personality insights, interaction count, etc.)
            context_type: "server" or "dm" for different contexts
            
        Returns:
            Generated response text
        """
        try:
            # Build user context information
            user_info = ""
            if user_context:
                interaction_count = user_context.get('interaction_count', 0)
                personality_insights = user_context.get('personality', '')
                topics_discussed = user_context.get('topics', '')
                
                user_info = f"""
                CONTEXT ABOUT USER ({user_name}):
                - Interactions with you: {interaction_count}
                - Relevant personality insights: {personality_insights if personality_insights else 'Unknown so far'}
                - Relevant topics they discuss: {topics_discussed if topics_discussed else 'Various'}
                """
            
            # Build conversation history context
            history_context = ""
            if conversation_history:
                history_context = f"""
                {conversation_history}
                """
            else:
                history_context = "\n(No recent conversation history available)\n\n"
            
            # Build the full prompt
            base_personality = self._build_base_personality_prompt()
            
            response_prompt = {
                "role": "system", 
                "content": f"""
                {base_personality}

                {user_info}

                {history_context}

                CURRENT MESSAGE TO RESPOND TO:
                {user_name}: {message_content}

                Respond naturally as Jeff would, taking into account the conversation history above.
                """
            }

            messages = [
                response_prompt,
                {"role": "user", "content": f"Generate a response as Jeff to the current message, considering the conversation history provided."}
            ]

            # Generate response using ollama
            response_data = await self.ollama.generate_with_metadata(messages)
            
            if response_data:
                # Extract the actual response text
                if isinstance(response_data, dict):
                    response_text = response_data.get('response', '').strip()
                    if not response_text:
                        response_text = (response_data.get('content') or 
                                       response_data.get('message', {}).get('content') or
                                       str(response_data)).strip()
                elif isinstance(response_data, str):
                    response_text = response_data.strip()
                else:
                    response_text = str(response_data).strip()
                
                # Clean up response if needed
                if len(response_text) > 2000:  # Discord message limit
                    response_text = response_text[:1900] + "..."
                
                return response_text
            else:
                logger.warning(f"No valid response generated for {user_name}")
                return "Sorry mate, brain's not working right now"
                
        except Exception as e:
            logger.error(f"Error generating response for {user_name}: {e}", exc_info=True)
            return "Sorry mate, brain's not working right now"
    
    async def generate_casual_comment(self, 
                                    topic: str,
                                    context: Optional[str] = None) -> str:
        """
        Generate a casual comment about a topic as Jeff would.
        
        Args:
            topic: The topic to comment on
            context: Optional context about the topic
            
        Returns:
            Generated casual comment
        """
        try:
            base_personality = self._build_base_personality_prompt()
            
            prompt = {
                "role": "system",
                "content": f"""
                {base_personality}
                
                Generate a casual comment about the topic: {topic}
                
                {f"Context: {context}" if context else ""}
                
                Make it brief and natural - something Jeff would actually say.
                """
            }
            
            messages = [
                prompt,
                {"role": "user", "content": f"Give a casual comment about: {topic}"}
            ]
            
            response_data = await self.ollama.generate_with_metadata(messages)
            
            if response_data:
                if isinstance(response_data, dict):
                    response_text = response_data.get('response', '').strip()
                    if not response_text:
                        response_text = str(response_data).strip()
                elif isinstance(response_data, str):
                    response_text = response_data.strip()
                else:
                    response_text = str(response_data).strip()
                
                return response_text
            else:
                return "Can't be bothered to comment on that"
                
        except Exception as e:
            logger.error(f"Error generating casual comment: {e}", exc_info=True)
            return "Can't be bothered to comment on that"
    
    async def generate_reaction(self, 
                              message_content: str,
                              user_name: str,
                              reaction_type: str = "general") -> str:
        """
        Generate a reaction to a message as Jeff would.
        
        Args:
            message_content: The message to react to
            user_name: Name of the user who sent the message
            reaction_type: Type of reaction ("supportive", "sarcastic", "dismissive", "general")
            
        Returns:
            Generated reaction
        """
        try:
            base_personality = self._build_base_personality_prompt()
            
            reaction_guidance = {
                "supportive": "Be encouraging but keep it casual",
                "sarcastic": "Be sarcastic but not mean-spirited",
                "dismissive": "Be dismissive but playful",
                "general": "React naturally based on the content"
            }
            
            guidance = reaction_guidance.get(reaction_type, reaction_guidance["general"])
            
            prompt = {
                "role": "system",
                "content": f"""
                {base_personality}
                
                {user_name} just said: "{message_content}"
                
                React to this message. {guidance}
                Keep it brief - just a quick reaction as Jeff would give.
                """
            }
            
            messages = [
                prompt,
                {"role": "user", "content": f"React to what {user_name} said"}
            ]
            
            response_data = await self.ollama.generate_with_metadata(messages)
            
            if response_data:
                if isinstance(response_data, dict):
                    response_text = response_data.get('response', '').strip()
                    if not response_text:
                        response_text = str(response_data).strip()
                elif isinstance(response_data, str):
                    response_text = response_data.strip()
                else:
                    response_text = str(response_data).strip()
                
                return response_text
            else:
                return "..."
                
        except Exception as e:
            logger.error(f"Error generating reaction: {e}", exc_info=True)
            return "..."
    
    def get_personality_summary(self) -> str:
        """Get a summary of Jeff's personality traits"""
        return f"""
        Jeff's Personality:
        - Casual mate in the group, not a formal assistant
        - Can be playful, sarcastic, or a bit rude when it fits
        - Concise and to the point - no excessive enthusiasm
        - Uses British slang and casual language
        - Calls out daft behavior but helps when genuinely needed
        - References conversation history when relevant
        """ 