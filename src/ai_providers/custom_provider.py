import aiohttp
import json
from typing import Dict, Any, List, Optional
from loguru import logger
from . import AIProvider
import time

class CustomAIProvider(AIProvider):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key", "")
        self.ai_endpoint = config.get("ai_endpoint", "")  # Customizable AI endpoint
        self.max_tokens = config.get("max_tokens", 2000)
        self.temperature = config.get("temperature", 0.7)
        
        # Model configuration
        self.primary_model = config.get("model", "default-model")
        self.fallback_models = config.get("fallback_models", [])
        
        # Rate limiting and cooldown tracking
        self.model_cooldowns = {}
        self.current_model = self.primary_model
        self.rate_limits = {}

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Implement AIProvider interface for chat"""
        system_prompt = ""
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                chat_messages.append(msg)
        
        return await self.generate(system_prompt, chat_messages, 0)

    def _select_available_model(self) -> str:
        """Select available model considering cooldowns"""
        now = time.time()
        
        # Clean expired cooldowns
        expired_models = [m for m, t in self.model_cooldowns.items() if now > t]
        for model in expired_models:
            del self.model_cooldowns[model]
            logger.info(f"Model {model} cooldown expired")
        
        # Try primary model first
        if self.primary_model not in self.model_cooldowns:
            return self.primary_model
            
        # Try fallback models
        for model in self.fallback_models:
            if model not in self.model_cooldowns:
                logger.warning(f"Primary model unavailable, using fallback: {model}")
                return model
                
        # If all models are cooling, use the one with shortest cooldown
        if self.model_cooldowns:
            soonest = min(self.model_cooldowns.items(), key=lambda x: x[1])
            logger.warning(f"All models cooling, using {soonest[0]} with shortest cooldown")
            return soonest[0]
            
        return self.primary_model

    def _set_model_cooldown(self, model: str, seconds: int = 60) -> None:
        """Set model cooldown"""
        self.model_cooldowns[model] = time.time() + seconds
        logger.warning(f"Model {model} cooling for {seconds} seconds")

    async def generate(self, system_prompt: str, messages: List[Dict[str, str]], recursion_depth: int = 0) -> str:
        """Generate response from custom AI endpoint"""
        if recursion_depth > 5:
            logger.error("Max recursion depth reached")
            return "AI service unavailable, please try again later"
            
        model = self._select_available_model()
        logger.info(f"Using model: {model}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Format messages
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        payload = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"Sending request to {self.ai_endpoint}")
                start_time = time.time()
                
                async with session.post(self.ai_endpoint, headers=headers, json=payload) as response:
                    elapsed_time = time.time() - start_time
                    logger.debug(f"Response time: {elapsed_time:.2f}s, status: {response.status}")
                    
                    if response.status == 429:  # Rate limited
                        self._set_model_cooldown(model, 300)
                        return await self.generate(system_prompt, messages, recursion_depth + 1)
                        
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API error: {response.status} - {error_text}")
                        return "AI service error, please try again later"
                    
                    try:
                        result = await response.json()
                        if "choices" in result and result["choices"]:
                            return result["choices"][0]["message"]["content"]
                        else:
                            logger.error(f"Unexpected response format: {result}")
                            return "AI returned unexpected response"
                    except json.JSONDecodeError:
                        logger.error("Failed to parse API response")
                        return "AI service returned invalid data"
        except Exception as e:
            logger.error(f"API request failed: {e}")
            self._set_model_cooldown(model, 60)
            return "Failed to connect to AI service"
