import openai
from typing import Dict, Any, List
from . import AIProvider

class OpenAIProvider(AIProvider):
    def __init__(self, config: Dict[str, Any]):
        openai.api_key = config["api_key"]
        self.model = config["model"]
        self.max_tokens = config["max_tokens"]
        self.temperature = config["temperature"]
        
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """使用 OpenAI API 进行对话"""
        response = await openai.ChatCompletion.acreate(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        return response.choices[0].message.content 