import asyncio
import logging
import httpx
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger('discord.ollama')

class OllamaClient:
    """
    Client for interacting with Open WebUI API (OpenAI-compatible)
    
    Requires an API key from Open WebUI (Settings > Account > API Key)
    """
    def __init__(self, base_url: str, api_key: str, default_model: str = "gpt-4.1-mini"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.default_model = default_model
        self.current_model = default_model
        self.available_models = []
        self.last_health_check = None
        self.is_healthy = False
        
        logger.info(f"Initialized OllamaClient with base_url: {self.base_url}, default_model: {self.default_model}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def health_check(self) -> bool:
        """Check if Open WebUI service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/models",
                    headers=self._get_headers()
                )
                self.is_healthy = response.status_code == 200
                self.last_health_check = datetime.now()
                
                if self.is_healthy:
                    logger.debug("Open WebUI health check passed")
                else:
                    logger.warning(f"Open WebUI health check failed: {response.status_code}")
                    
                return self.is_healthy
                
        except Exception as e:
            self.is_healthy = False
            self.last_health_check = datetime.now()
            logger.error(f"Open WebUI health check failed: {e}")
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from Open WebUI"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/models",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                
                result = response.json()
                # Open WebUI returns models in 'data' field, similar to OpenAI format
                self.available_models = result.get("data", [])
                logger.info(f"Found {len(self.available_models)} available models")
                return self.available_models
                
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []

    async def test_model(self, model_name: str) -> bool:
        """Test if a specific model is available and working"""
        try:
            test_payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": "test"}]
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat/completions",
                    headers=self._get_headers(),
                    json=test_payload
                )
                response.raise_for_status()
                
                logger.debug(f"Model {model_name} test successful")
                return True
                
        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 404:
                logger.warning(f"Model {model_name} not found")
            else:
                logger.error(f"Error testing model {model_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error testing model {model_name}: {e}")
            return False

    def set_model(self, model_name: str) -> bool:
        """Set the current model"""
        try:
            old_model = self.current_model
            self.current_model = model_name
            logger.info(f"Changed model from {old_model} to {model_name}")
            return True
        except Exception as e:
            logger.error(f"Error setting model to {model_name}: {e}")
            return False

    def get_current_model(self) -> str:
        """Get the currently selected model"""
        return self.current_model

    async def chat_completion(self, 
                            messages: List[Dict[str, str]], 
                            model: Optional[str] = None,
                            stream: bool = False,
                            format: Optional[str] = None,
                            options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """OpenAI-compatible chat completion method for Open WebUI"""
        try:
            model_to_use = model or self.current_model
            
            payload = {
                "model": model_to_use,
                "messages": messages
            }
            
            # Add stream parameter if requested
            if stream:
                payload["stream"] = stream
                
            # Add additional options if provided
            if options:
                payload.update(options)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                if stream:
                    return await self._handle_streaming_response(client, payload)
                else:
                    response = await client.post(
                        f"{self.base_url}/api/chat/completions",
                        headers=self._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()
                    return response.json()
                    
        except Exception as e:
            logger.error(f"Error in chat completion with model {model_to_use}: {e}")
            return None

    async def _handle_streaming_response(self, client: httpx.AsyncClient, payload: Dict[str, Any]) -> Optional[str]:
        """Handle streaming responses from Open WebUI"""
        try:
            generated_text = ""
            
            async with client.stream(
                "POST", 
                f"{self.base_url}/api/chat/completions",
                headers=self._get_headers(),
                json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        # Handle Server-Sent Events format
                        if line.startswith("data: "):
                            line = line[6:]  # Remove "data: " prefix
                        
                        if line == "[DONE]":
                            break
                            
                        try:
                            data = json.loads(line)
                            # OpenAI format: choices[0].delta.content
                            if "choices" in data and len(data["choices"]) > 0:
                                choice = data["choices"][0]
                                if "delta" in choice and "content" in choice["delta"]:
                                    generated_text += choice["delta"]["content"]
                                elif "message" in choice and "content" in choice["message"]:
                                    generated_text += choice["message"]["content"]
                        except json.JSONDecodeError:
                            continue
            
            return generated_text.strip() if generated_text else None
            
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            return None

    async def generate_with_metadata(self, 
                                   messages: List[Dict[str, str]], 
                                   model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Generate response with structured metadata (for conversation AI)"""
        try:
            result = await self.chat_completion(
                messages=messages,
                model=model,
                stream=False
            )
            
            # Open WebUI returns OpenAI-compatible format
            if result and "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                    
                    # Try to parse as JSON if it looks like structured data
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        # Return a fallback structure
                        return {
                            "should_respond": True,
                            "response": content,
                            "metadata": {}
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating response with metadata: {e}")
            return None

    async def simple_chat(self, 
                         prompt: str, 
                         model: Optional[str] = None,
                         system_prompt: Optional[str] = None) -> Optional[str]:
        """Simple chat method for basic interactions"""
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
                
            messages.append({"role": "user", "content": prompt})
            
            result = await self.chat_completion(messages=messages, model=model, stream=False)
            
            # Parse OpenAI-compatible response format
            if result and "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"].strip()
                
            return None
            
        except Exception as e:
            logger.error(f"Error in simple chat: {e}")
            return None

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "is_healthy": self.is_healthy,
            "last_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "base_url": self.base_url,
            "current_model": self.current_model,
            "available_models_count": len(self.available_models)
        } 